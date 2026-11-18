"""Our minimal agent loop, cleaned (EXPERIMENTS.md, "Harnesses").

The loop sends the system and user messages of a launch prompt, declares only the condition's tools (none when
answering from memory), runs every tool call the model makes, and stops at the first reply without a tool call.
It has no prompt text of its own beyond two follow-ups and the compaction texts in prompts.py:

- if the condition has a tool the agent must use (registry, random_choice) and the agent ended without calling
  it, one follow-up asks it to (registry: its sentence plus the answer-line reminder; random_choice: one sentence);
- then, if the final message lacks any of the five answer lines, one answer-line follow-up.

Settings as ours: max_tokens 32,000, provider-default temperature, the agent seed sent as `seed` (most providers
ignore it), caps of 400 turns, 400 tool calls (after which tools are refused with tool_choice "none") and $2 per
session, and compaction when a call's prompt + completion tokens (+ new tool output / 4) pass 0.8 of the context
window: older turns are summarised by the same model and the most recent ~30% of the conversation (by characters)
is kept. The assistant message is sent back with its tool calls and any reasoning fields the endpoint returned.

    from minimal_loop import run_session
    rec = run_session("z-ai/glm-5.3-flash", system, user, tools={"read_registry": reg_tool}, seed=25261112,
                      provider={"order": ["Z.AI"], "allow_fallbacks": False, "require_parameters": True})
    rec["parsed"]  -> {"direction": ..., "project": ..., "question": ..., "first_experiment": ..., "why_this": ...}

`tools` maps a tool name to an object with .schemas (list of {name, description, parameters}) and .call(...):
registry.RegistryTool and random_choice.RandomChoice take the raw arguments; search_tool.SearchTool takes
(name, args). Our GPT runs used OpenAI's Responses API (reasoning effort low, store false, encrypted reasoning
passed back); this chat-completions loop is the version we ran for every OpenRouter model.
"""
import json
import re

import llm
import prompts
import random_choice

LABELS = [("direction", r"direction"), ("project", r"project(?:\s+title)?"), ("question", r"(?:research\s+)?question"),
          ("first_experiment", r"first\s+experiment"), ("why_this", r"why\s+this")]
_LINE = re.compile(r"^\s*(?:[-*+>]\s*)?(?:#+\s*)?(?:\*\*|__|\*)?\s*(" + "|".join(p for _, p in LABELS) +
                   r")\s*(?:\*\*|__|\*)?\s*:\s*(?:\*\*|__|\*)?\s*(.*)$", re.I)


def parse_final(text):
    """Lenient parse of the five answer lines: markdown decoration allowed, a value runs on over following lines until
    the next label, the last occurrence of a label wins. status ok (all five), partial or failed."""
    t = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    occ, cur = {}, None
    for ln in t.splitlines():
        m = _LINE.match(ln)
        if m:
            cur = next(k for k, p in LABELS if re.fullmatch(p, m.group(1).strip(), re.I))
            occ.setdefault(cur, []).append([m.group(2)])
        elif cur is not None:
            occ[cur][-1].append(ln)
    res = {k: re.sub(r"\s+", " ", " ".join(v[-1])).strip(" *_") for k, v in occ.items()}
    res = {k: v for k, v in res.items() if v}
    res["missing"] = [k for k, _ in LABELS if k not in res]
    res["status"] = ("ok" if not res["missing"] else
                     "partial" if "direction" in res and ("project" in res or "question" in res) else "failed")
    return res


def is_template_echo(parsed):
    """Excluded picks that copy the answer template instead of answering."""
    p = parsed or {}
    return (p.get("direction") or "").strip() == "one sentence" or \
        (p.get("question") or "").strip().lower().startswith("as stated")


def _call_tool(tool, name, raw):
    if hasattr(tool, "search"):                                    # search_tool.SearchTool: (name, parsed args)
        try:
            args = json.loads(raw) if isinstance(raw, str) and raw.strip() else (raw or {})
        except ValueError:
            return json.dumps({"error": "arguments must be a JSON object"})
        return tool.call(name, args)
    return tool.call(raw)


def _compact(model, msgs, seed, schemas, params):
    n_head = next(i for i, m in enumerate(msgs) if m["role"] == "user") + 1
    head, body = msgs[:n_head], msgs[n_head:]
    size = lambda ms: sum(len(json.dumps(m, ensure_ascii=False)) for m in ms)
    total, keep_at = size(body), len(body)
    for i, m in enumerate(body):
        if i > 0 and m["role"] == "assistant" and size(body[i:]) <= 0.3 * total:
            keep_at = i
            break
    r = llm.chat(model, head + body[:keep_at] + [{"role": "user", "content": prompts.COMPACT_PROMPT}],
                 tools=schemas or None, tool_choice="none" if schemas else None, seed=seed,
                 **{**params, "max_tokens": 8000})
    summary = re.sub(r"<think>.*?</think>", "", r["message"].get("content") or "", flags=re.S).strip()
    return head + [{"role": "user", "content": prompts.COMPACT_PREFIX + summary}] + body[keep_at:]


def run_session(model, system, user, tools=None, seed=None, must_call=None, context_tokens=None,
                max_turns=400, max_tool_calls=400, max_usd=2.0, max_tokens=32000, **params):
    """One agent session. must_call: name of a tool whose non-use triggers its follow-up ("read_registry" or
    "random_choice"). context_tokens: the endpoint's context window (compaction off if None).
    Returns {"status", "final_text", "parsed", "messages", "tool_events", "usage", "followups"}."""
    tools = tools or {}
    schemas = [{"type": "function", "function": s} for t in dict.fromkeys(tools.values()) for s in t.schemas]
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
    params = {"max_tokens": max_tokens, **params}
    if seed is not None:
        params["seed"] = seed
    events, followups, cost, final, status = [], [], 0.0, None, None
    tool_nudge_sent = answer_nudge_sent = False
    for turn in range(max_turns):
        if cost > max_usd:
            status = "cap_session_usd"
            break
        choice = "none" if schemas and len(events) >= max_tool_calls else None
        r = llm.chat(model, msgs, tools=schemas or None, tool_choice=choice, **params)
        u = r["usage"]
        cost += float(u.get("cost") or 0)
        m = r["message"]
        calls = m.get("tool_calls") or []
        back = {k: v for k, v in m.items() if k in ("role", "content", "tool_calls", "reasoning_details") and v}
        back.update(role="assistant", content=m.get("content") or "")
        msgs.append(back)
        if not schemas or not calls or choice == "none":
            final = m.get("content") or ""
            if must_call and not tool_nudge_sent and not any(e["tool"] == must_call for e in events):
                text = (prompts.registry_nudge() if must_call == "read_registry"
                        else random_choice.UNCALLED_NUDGE)
                msgs.append({"role": "user", "content": text}); followups.append(text); tool_nudge_sent = True
                continue
            if not answer_nudge_sent and parse_final(final)["status"] != "ok":
                text = prompts.answer_nudge(tools=bool(schemas))
                msgs.append({"role": "user", "content": text}); followups.append(text); answer_nudge_sent = True
                continue
            break
        for tc in calls:
            fn = tc.get("function") or {}
            tool = tools.get(fn.get("name"))
            content = (_call_tool(tool, fn.get("name"), fn.get("arguments")) if tool is not None
                       else json.dumps({"error": f"unknown tool: {fn.get('name')}"}))
            events.append({"turn": turn, "tool": fn.get("name"), "args": fn.get("arguments"), "n_chars": len(content)})
            msgs.append({"role": "tool", "tool_call_id": tc.get("id"), "content": content})
        if context_tokens and (u.get("prompt_tokens", 0) + u.get("completion_tokens", 0)
                               + sum(len(x["content"]) for x in msgs[-len(calls):]) / 4) > 0.8 * context_tokens:
            msgs = _compact(model, msgs, seed, schemas, params)
    else:
        status = "cap_turns"
    parsed = parse_final(final) if final else None
    if status is None:
        status = "empty_final" if not (final or "").strip() else ("ok" if parsed["status"] == "ok" else "no_answer_lines")
    return {"status": status, "final_text": final, "parsed": parsed, "messages": msgs, "tool_events": events,
            "usd": cost, "followups": followups}
