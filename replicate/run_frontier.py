"""Run one condition of the frontier setup over its slots, and write agents and judged pairs in the release's format
(EXPERIMENTS.md, "The frontier setup"; replicate/README.md, "Running a frontier condition").

    OPENAI_BASE_URL=https://openrouter.ai/api/v1 OPENAI_API_KEY=... python3 run_frontier.py \\
        --condition tree --index INDEX_DIR --out-dir runs/ [--judge]

What it does, as our runner did:
- Slots: slots.slots_120() (six populations of 20) or, with --size 100, slots.slots_300(). Each slot fixes the
  model, the harness and the launch prompt. Agent (p, i) gets seed base + 1000 p + i and its population's registry
  seed is base + 1000 p, with base 2026111600 (Max, no search, novelty, tree, tree taking the best), 2026111300
  (registries in populations of 20) or 2026111700 (populations of 100), unless --seed-base says otherwise.
- Launch text: prompts.launch(slot's launch prompt) in its tools form (memory form for no_search), plus the
  condition's text: the registry sentence, the novelty sentence, or the tree protocol (with draws, or taking the
  best), placed as EXPERIMENTS.md, "What text is added where", says.
- Tools: search and read (the agent's seed as the noise seed, --tau, default 0.02) unless no_search; read_registry
  for registry conditions; random_choice for the tree.
- Order: registry agents of a population run strictly in position order, and an agent's pick joins the registry
  (labelled first, for agenda counts) only if its session finished with all five answer lines. Other 120-slot arms
  (placebo included) run in slots.run_order(); populations of 100 without a registry run by position, then
  population.
- Follow-ups, in the same session, each at most once: the uncalled-tool follow-up (registry or random_choice), then
  the answer-line follow-up (with the no-tools paragraph when the agent has no tools). A failed session (an error or
  an empty answer) is run again once from the start.
- Output: OUT_DIR/agents_<experiment>.jsonl, one row per agent in the schema of data/agents_frontier_*.jsonl
  (plus seed, status, followups, slot_harness and, for the tree, the draws), and with --judge
  OUT_DIR/pairs_<experiment>.jsonl in the schema of data/pairs_*.jsonl, every pair of analysed agents (within
  populations for registry conditions) judged in both orders with the judge pinned to DeepInfra, followed by the
  effective number and its interval.

Harnesses. By default every slot runs in our minimal loop, whatever harness the slot names (rows keep it as
slot_harness; harness is "minimal_loop"). To run slots in Claude Code, Codex CLI or opencode, pass --runner
MODULE:FUNCTION, a function you write that runs one harness turn (see run_external below for its contract and
claude_code_runner for an example). The tools then run as MCP servers (mcp_server.py), started by the harness from
the commands this script gives it, with a log file per agent from which the script reads whether the agent used its
tool and how many draws it made (so a resumed tree session gets --prior-draws).

Launch prompts adapted from other people's prompts (V03, V04, V08, V10, V11, V12) are not in this repository. Slots
that use them are skipped and listed, unless you supply their text with --custom-launch FILE (a JSON object
{"<id>": [system text or null, first part of the user message]}, assembled from prompts/README.md section 7).
"""
import argparse
import importlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import judge
import labeller
import minimal_loop
import prompts
import random_choice
import registry
import search_tool
import slots

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

# condition -> (agent id prefix, condition name in the data, experiment name; {n} is the population size)
CONDITIONS = {
    "max": ("N", "max", "frontier_max"),
    "no_search": ("N0", "no_search", "frontier_no_search"),
    "novelty": ("NV", "novelty_sentence", "frontier_novelty"),
    "tree": ("TT", "tree_random_draw", "frontier_tree"),
    "tree_take_best": ("TW", "tree_take_best", "frontier_tree_take_best"),
    "registry_projects": ("D", "registry_of_earlier_projects", "frontier_registry_{n}_projects"),
    "registry_agenda_counts": ("C", "agenda_counts", "frontier_registry_{n}_agenda_counts"),
    "registry_placebo": ("P", "placebo_list", "frontier_registry_{n}_placebo"),
}
REGISTRY_MODE = {"registry_projects": "projects", "registry_agenda_counts": "agenda_counts",
                 "registry_placebo": "placebo"}
# OpenRouter routes of our runs (EXPERIMENTS.md, "Agents"). The GPT models went to OpenAI's API directly, through
# the Responses API in our loop; to run them through this chat-completions loop, map them with --model-map.
PROVIDERS = {"anthropic/": {"order": ["Anthropic"], "allow_fallbacks": False, "require_parameters": True}}
JUDGE_PIN = "DeepInfra"
BOOTSTRAP_SEED = 20261116


def seed_base(condition, size):
    if size == 100:
        return 2026111700
    return 2026111300 if condition.startswith("registry_") else 2026111600


def launch_text(condition, launch_id):
    """(system, user) of a slot under a condition, or raise KeyError for an adapted prompt not supplied."""
    system, user = prompts.launch(launch_id, tools=condition != "no_search")
    if condition == "novelty":
        user = prompts.add_novelty_sentence(user, "frontier")
    elif condition.startswith("registry_"):
        user = prompts.add_registry_sentence(user, "frontier")
    elif condition in ("tree", "tree_take_best"):
        user = prompts.add_tree_protocol(user, take_best=condition == "tree_take_best", setup="frontier")
    return system, user


def must_call(condition):
    return "read_registry" if condition.startswith("registry_") else "random_choice" if condition == "tree" else None


def agent_plan(condition, size, base=None, populations=None):
    """Every agent of the arm, in the order they run: dicts with agent_id, population, position, model, harness,
    launch_prompt, seed, registry_seed, run_order."""
    table = slots.slots_300() if size == 100 else slots.slots_120()
    base = seed_base(condition, size) if base is None else base
    prefix = CONDITIONS[condition][0]
    order = slots.run_order() if size == 20 else None
    rows = []
    for (p, i), (model, harness, launch) in table.items():
        if populations is not None and p not in populations:
            continue
        rows.append({"agent_id": f"{prefix}_pop{p:02d}_a{i:02d}", "population": p, "position": i, "model": model,
                     "harness": harness, "launch_prompt": launch, "seed": base + 1000 * p + i,
                     "registry_seed": base + 1000 * p, "run_order": order[(p, i)] if order else None})
    if condition in ("registry_projects", "registry_agenda_counts"):
        rows.sort(key=lambda r: (r["population"], r["position"]))      # each population in position order
    elif order is not None:
        rows.sort(key=lambda r: r["run_order"])                         # the shared run order of the 120 slots
    else:
        rows.sort(key=lambda r: (r["position"], r["population"]))      # populations of 100 without a registry
    return rows


# ---------------------------------------------------------------- one agent in our minimal loop
def run_loop(agent, condition, system, user, a, pop, model, provider):
    tools = {}
    if condition != "no_search":
        st = search_tool.SearchTool(a.index, tau=a.tau, rank_seed=agent["seed"])
        tools.update(search=st, read=st)
    if condition.startswith("registry_"):
        tools["read_registry"] = registry.RegistryTool(REGISTRY_MODE[condition], pop, agent["position"])
    if condition == "tree":
        tools["random_choice"] = random_choice.RandomChoice()
    rec = minimal_loop.run_session(model, system, user, tools=tools, seed=agent["seed"], must_call=must_call(condition),
                                   context_tokens=a.context_tokens, **({"provider": provider} if provider else {}))
    rec["draws"] = tools["random_choice"].log if condition == "tree" else None
    rec["harness"] = "minimal_loop"
    return rec


# ---------------------------------------------------------------- one agent in a real harness, tools over MCP
def mcp_servers(agent, condition, a, pop_state, logs, prior_draws=0):
    """The MCP servers of one agent session: [{"name", "command": [argv]}], each logging its calls."""
    py, srv = sys.executable, str(HERE / "mcp_server.py")
    out = []
    if condition != "no_search":
        out.append({"name": "survey", "command": [py, srv, "survey", "--index", str(a.index), "--seed",
                                                  str(agent["seed"]), "--tau", str(a.tau), "--log", str(logs["survey"])]})
    if condition.startswith("registry_"):
        out.append({"name": "registry", "command": [
            py, srv, "registry", "--mode", REGISTRY_MODE[condition], "--state", str(pop_state), "--position",
            str(agent["position"]), "--population-seed", str(agent["registry_seed"]), "--log", str(logs["registry"])]})
    if condition == "tree":
        out.append({"name": "random_choice", "command": [py, srv, "random_choice", "--prior-draws", str(prior_draws),
                                                         "--log", str(logs["random_choice"])]})
    return out


def read_log(path):
    return [json.loads(l) for l in open(path)] if Path(path).exists() else []


def run_external(runner, agent, condition, system, user, a, pop_state, model, workdir):
    """Drive a harness through `runner`. Contract: runner(model=, harness=, system=, prompt=, servers=, resume=)
    runs one turn and returns {"final_text": str, "session": anything needed to resume}; resume is None for the
    first turn and the previous turn's "session" for a follow-up. The runner must start the given MCP servers
    (and no built-in tools), append `system` to the harness's system prompt, and raise or return an empty
    final_text on failure."""
    logs = {k: workdir / f"{agent['agent_id']}.{k}.jsonl" for k in ("survey", "registry", "random_choice")}
    for f in logs.values():
        f.unlink(missing_ok=True)
    turn = lambda prompt, resume, prior=0: runner(model=model, harness=agent["harness"], system=system, prompt=prompt,
                                                  servers=mcp_servers(agent, condition, a, pop_state, logs, prior),
                                                  resume=resume)
    r = turn(user, None)
    final, session, followups = r.get("final_text") or "", r.get("session"), []
    tool = must_call(condition)
    if tool:
        used = read_log(logs["registry" if tool == "read_registry" else "random_choice"])
        if not used:
            text = prompts.registry_nudge() if tool == "read_registry" else random_choice.UNCALLED_NUDGE
            r = turn(text, session)
            final, session = r.get("final_text") or final, r.get("session", session)
            followups.append(text)
    if minimal_loop.parse_final(final)["status"] != "ok":
        n_draws = sum(1 for e in read_log(logs["random_choice"]) if not e["is_error"])
        text = prompts.answer_nudge(tools=condition != "no_search")
        r = turn(text, session, n_draws)
        final = r.get("final_text") or final
        followups.append(text)
    parsed = minimal_loop.parse_final(final) if final.strip() else None
    status = "empty_final" if not final.strip() else ("ok" if parsed["status"] == "ok" else "no_answer_lines")
    draws = None
    if condition == "tree":
        draws = [{"args": e["args"], "result": e["result"], "error": e["is_error"]}
                 for e in read_log(logs["random_choice"])]
    return {"status": status, "final_text": final, "parsed": parsed, "followups": followups, "draws": draws,
            "tool_events": [e for k in logs for e in read_log(logs[k])], "harness": agent["harness"]}


def claude_code_runner(model, harness, system, prompt, servers, resume):
    """Example runner for Claude Code slots (print mode, built-in tools off, only our MCP tools allowed). Point it at
    your endpoint with Claude Code's own environment variables. Not exercised by selftest.py: check the flags
    against your Claude Code version. Slots of other harnesses need their own runner (README.md)."""
    if harness != "claude_code":
        raise NotImplementedError(f"this example runs Claude Code only, not {harness}")
    cfg = {"mcpServers": {s["name"]: {"command": s["command"][0], "args": s["command"][1:]} for s in servers}}
    allowed = ",".join({"survey": "mcp__survey__search,mcp__survey__read", "registry": "mcp__registry__read_registry",
                        "random_choice": "mcp__random_choice__random_choice"}[s["name"]] for s in servers)
    cmd = ["claude", "-p", prompt, "--model", model.split("/", 1)[-1], "--output-format", "json",
           "--mcp-config", json.dumps(cfg), "--strict-mcp-config", "--disable-slash-commands", "--tools", ""]
    cmd += ["--allowedTools", allowed] if allowed else []
    cmd += ["--resume", resume] if resume else ["--append-system-prompt", system or ""]
    with tempfile.TemporaryDirectory() as home:                      # a fresh home: no user settings or memory
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=home, env={**os.environ, "HOME": home},
                           timeout=3600)
    if p.returncode != 0:
        raise RuntimeError(f"claude exited {p.returncode}: {p.stderr[-500:]}")
    out = json.loads(p.stdout)
    return {"final_text": out.get("result") or "", "session": out.get("session_id")}


# ---------------------------------------------------------------- the arm
def usable(rec):
    p = rec.get("parsed") or {}
    if rec["status"] != "ok":
        return False, "session failed"
    if minimal_loop.is_template_echo(p):
        return False, "answer copies the format template"
    if not (p.get("direction") and p.get("project")):
        return False, "session failed"
    return True, None


def run_arm(a, runner=None):
    prefix, cond_name, exp = CONDITIONS[a.condition]
    exp = exp.format(n=a.size)
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    agents_path = out_dir / f"agents_{exp}.jsonl"
    custom = json.loads(Path(a.custom_launch).read_text()) if a.custom_launch else {}
    prompts.CUSTOM_LAUNCH.update({k: tuple(v) for k, v in custom.items()})
    model_map = a.model_map or {}
    provider_map = {**PROVIDERS, **(a.provider_map or {})}
    plan = agent_plan(a.condition, a.size, a.seed_base, a.populations)
    if a.limit:
        plan = plan[:a.limit]
    done = {json.loads(l)["agent_id"] for l in open(agents_path)} if agents_path.exists() else set()
    skipped = []
    with open(agents_path, "a") as f:
        for agent in plan:
            if agent["agent_id"] in done:
                continue
            try:
                system, user = launch_text(a.condition, agent["launch_prompt"])
            except KeyError:
                skipped.append(agent["agent_id"])
                continue
            model = model_map.get(agent["model"], agent["model"])
            provider = next((v for k, v in provider_map.items() if model.startswith(k)), None)
            pop_state = out_dir / f"{exp}.pop{agent['population']:02d}.registry.json"
            pop = registry.Population(pop_state, agent["registry_seed"])
            for attempt in range(2):                                  # a failed session is retried once
                try:
                    rec = (run_external(runner, agent, a.condition, system, user, a, pop_state, model, out_dir)
                           if runner else run_loop(agent, a.condition, system, user, a, pop, model, provider))
                except Exception as e:                                # noqa: BLE001 (any failure counts)
                    rec = {"status": f"error: {type(e).__name__}: {e}"[:300], "parsed": None, "followups": [],
                           "draws": None, "tool_events": [], "harness": "minimal_loop" if not runner else agent["harness"]}
                if rec["status"] not in ("empty_final",) and not rec["status"].startswith("error"):
                    break
            p = rec.get("parsed") or {}
            ok, why = usable(rec)
            if a.condition in ("registry_projects", "registry_agenda_counts"):
                label = labeller.live_label(p) if a.condition == "registry_agenda_counts" and rec["status"] == "ok" else None
                pop.register(agent["position"], agent["agent_id"], p, label=label, status=rec["status"], rule="frontier")
            row = {"agent_id": agent["agent_id"], "experiment": exp, "condition": cond_name,
                   "population": agent["population"], "position": agent["position"], "model": model,
                   "harness": rec["harness"], "slot_harness": agent["harness"], "launch_prompt": agent["launch_prompt"],
                   "brief": "ai_safety, memory only (no tools)" if a.condition == "no_search"
                   else "ai_safety, tools-on (search)", "run_date": time.strftime("%Y-%m-%d", time.gmtime()),
                   "analysed": ok, "excluded_because": why, "direction": p.get("direction"),
                   "project": p.get("project"), "question": p.get("question"),
                   "first_experiment": p.get("first_experiment"), "why": p.get("why_this"),
                   "run_order": agent["run_order"], "seed": agent["seed"], "status": rec["status"],
                   "followups": len(rec.get("followups") or []), "n_tool_calls": len(rec.get("tool_events") or [])}
            if a.condition == "tree":
                row["draws"] = rec.get("draws")
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            print(agent["agent_id"], rec["status"], (p.get("project") or "")[:70], file=sys.stderr)
    if skipped:
        print(f"skipped {len(skipped)} slots whose launch prompt is not in this repository (--custom-launch): "
              + ", ".join(skipped), file=sys.stderr)
    return exp, agents_path


def judge_arm(exp, agents_path, condition, threads=16, seed=BOOTSTRAP_SEED):
    """Judge every pair of analysed agents (within populations for registry arms) and write pairs_<exp>.jsonl; return
    the effective number and its interval."""
    from analysis import effnum
    agents = [r for r in map(json.loads, open(agents_path)) if r["analysed"]]
    scope = "population" if condition.startswith("registry_") else "all"
    texts = [judge.pick_text(r["project"], r["question"]) for r in agents]
    todo = judge.pairs_to_judge(agents, scope)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(threads) as ex:
        res = list(ex.map(lambda ij: judge.judge_pair(texts[ij[0]], texts[ij[1]], JUDGE_PIN), todo))
    rule = "every_pair" + ("_within_population" if scope == "population" else "")
    with open(agents_path.parent / f"pairs_{exp}.jsonl", "w") as f:
        for (i, j), (mean, sab, sba, dup) in zip(todo, res):
            f.write(json.dumps({"experiment": exp, "a": agents[i]["agent_id"], "b": agents[j]["agent_id"],
                                "score_ab": sab, "score_ba": sba, "score": mean, "duplicate": dup, "rule": rule,
                                "both_orders_cached": sab is not None and sba is not None}) + "\n")
    ids = [r["agent_id"] for r in agents]
    dups = [(agents[i]["agent_id"], agents[j]["agent_id"]) for (i, j), r in zip(todo, res) if r[3]]
    groups = effnum.groups_of([r["population"] for r in agents]) if scope == "population" else None
    return effnum.summarise(ids, dups, groups=groups, seed=seed)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--condition", choices=list(CONDITIONS), required=True)
    ap.add_argument("--size", type=int, choices=[20, 100], default=20, help="population size: 6 x 20 or 3 x 100")
    ap.add_argument("--populations", type=lambda s: [int(x) for x in s.split(",")], help="e.g. 0,1 (default all)")
    ap.add_argument("--limit", type=int, help="run only the first N agents of the plan (a smoke test)")
    ap.add_argument("--seed-base", type=int, help="override the seed base (agent seed = base + 1000 p + i)")
    ap.add_argument("--index", help="search index directory (search_tool.py build); not needed for no_search")
    ap.add_argument("--tau", type=float, default=0.02, help="search noise (0.02 in the frontier setup)")
    ap.add_argument("--model-map", type=json.loads, help='JSON {"slot model": "model to call"}')
    ap.add_argument("--provider-map", type=json.loads, help='JSON {"model prefix": OpenRouter provider routing}')
    ap.add_argument("--custom-launch", help="JSON file with the adapted launch prompts' text")
    ap.add_argument("--context-tokens", type=int, help="context window for the loop's compaction")
    ap.add_argument("--runner", help="MODULE:FUNCTION that runs one harness turn (default: our minimal loop)")
    ap.add_argument("--judge", action="store_true", help="judge every pair afterwards (paid) and print the number")
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args(argv)
    if a.condition != "no_search" and not a.index:
        ap.error("--index is needed for every condition with search")
    runner = None
    if a.runner:
        mod, _, fn = a.runner.partition(":")
        runner = getattr(importlib.import_module(mod), fn)
    exp, path = run_arm(a, runner)
    print(f"agents -> {path}", file=sys.stderr)
    if a.judge:
        print(exp, judge_arm(exp, path, a.condition))


if __name__ == "__main__":
    main()
