"""Offline check of this folder's plumbing with a fake model: no network, no key, $0.

    python3 selftest.py

Runs a registry population, a tree-protocol agent, the judge, the MCP server handshake and a tiny search index,
drives run_frontier.py through four frontier conditions in the loop and through a scripted harness that talks to the
MCP servers, and checks the slot draw against the released data. It tests the code paths, not any result.
"""
import io
import json
import tempfile
from pathlib import Path

import subprocess
import sys

import judge
import llm
import prompts
import mcp_server
import random_choice
import registry
import run_frontier
import run_population
import search_tool
import slots

_n = [0]


def fake_chat(model, messages, tools=None, tool_choice=None, **params):
    """A scripted model: calls each offered tool once, then answers with the five lines."""
    names = [t["function"]["name"] for t in tools or []]
    called = {c["function"]["name"] for m in messages if m["role"] == "assistant" for c in m.get("tool_calls") or []}
    if "<project_A>" in (messages[-1].get("content") or ""):
        return {"message": {"content": '{"label": "same_project", "reason": "x"}'}, "usage": {}}
    if (messages[-1].get("content") or "").startswith("Classify each AI safety research pick"):
        return {"message": {"content": '[{"primary": "cot_monitoring", "secondary": null}]'}, "usage": {}}
    for name in names:
        if name not in called:
            args = {"options": ["A", "B"], "weights": [0.5, 0.5]} if name == "random_choice" else \
                {"query": "chain of thought"} if name == "search" else {}
            _n[0] += 1
            return {"message": {"content": "", "tool_calls": [{"id": f"c{_n[0]}", "type": "function", "function": {
                "name": name, "arguments": json.dumps(args)}}]}, "usage": {}}
    _n[0] += 1
    return {"message": {"content": f"DIRECTION: d{_n[0]}\nPROJECT: Project {_n[0] % 3}\nQUESTION: q?\n"
                                   "FIRST EXPERIMENT: e\nWHY THIS: w"}, "usage": {}}


def main():
    llm.chat = fake_chat
    tmp = Path(tempfile.mkdtemp())
    run_population.main(["--condition", "registry_projects", "--model", "fake", "--n", "4", "--population-seed", "7",
                         "--out", str(tmp / "reg.jsonl")])
    rows = [json.loads(l) for l in open(tmp / "reg.jsonl")]
    assert len(rows) == 4 and all(r["status"] == "ok" for r in rows), rows
    shown = registry.render("projects", registry.Population(tmp / "reg.registry.json", 7).visible(3), 3, 7)
    assert shown.startswith("Shared registry of active work (3 earlier agents):") and shown.endswith("End of registry.\n")
    run_population.main(["--condition", "tree", "--model", "fake", "--n", "1", "--out", str(tmp / "tree.jsonl")])
    assert json.loads(open(tmp / "tree.jsonl").readline())["draws"][0]["choice"] in ("A", "B")
    judge.main([str(tmp / "reg.jsonl"), "--out", str(tmp / "twins.jsonl"), "--threads", "2"])
    assert sum(1 for _ in open(tmp / "twins.jsonl")) == 6                   # the fake judge calls every pair the same
    assert judge.mask_draw_sentences("The tool returned B. Do probes transfer? Draws on prior work.") == \
        "Do probes transfer? Draws on prior work."
    out = io.StringIO()
    mcp_server.serve("random_choice", random_choice.RandomChoice(), io.StringIO(
        '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18"}}\n'
        '{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n'
        '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"random_choice","arguments":'
        '{"options":["x","y"],"weights":[1,0]}}}\n'), out)
    resp = [json.loads(l) for l in out.getvalue().splitlines()]
    assert json.loads(resp[2]["result"]["content"][0]["text"])["choice"] == "x"
    corpus = tmp / "corpus.jsonl"
    corpus.write_text("\n".join(json.dumps(d) for d in [
        {"id": "arxiv:2610.29734", "kind": "paper", "title": "Monitorability Is Trainable: Post-Training for "
         "Chain-of-Thought Monitorability", "date": "2026-10-20", "abstract": "Chain of thought monitoring " * 20},
        {"id": "lw:abc", "kind": "post", "title": "Sabotage in automated research", "date": "2026-07-01",
         "abstract": "Agents may sabotage research.", "text": "long text " * 3000}]) + "\n")
    search_tool.build(corpus, tmp / "index")
    st = search_tool.SearchTool(tmp / "index", tau=0.02, rank_seed=1)
    assert st.search("chain of thought monitoring")[0]["id"] == "arxiv:2610.29734"
    assert "Page 1 of 4 (read page=2 for more)" in st.read("lw:abc")
    run_population.main(["--condition", "max", "--setup", "frontier", "--index", str(tmp / "index"), "--model", "fake",
                         "--n", "1", "--out", str(tmp / "max.jsonl")])
    frontier(tmp)
    slots.check()
    print("selftest passed")


def mcp_call(command, name, args):
    """Start one MCP server from its command line, call one tool, return the text (what a harness would do)."""
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": name, "arguments": args}}]
    out = subprocess.run(command, input="".join(json.dumps(m) + "\n" for m in msgs), capture_output=True, text=True,
                         check=True).stdout
    return json.loads(out.splitlines()[-1])["result"]["content"][0]["text"]


def fake_harness_runner(calls):
    """A scripted harness for run_frontier --runner: turn 1 searches and ends without the tool or the answer lines;
    turn 2 (the uncalled-tool follow-up) draws twice and still gives no answer lines; turn 3 answers."""
    def runner(model, harness, system, prompt, servers, resume):
        calls.append({"prompt": prompt, "servers": servers, "resume": resume})
        cmd = {s["name"]: s["command"] for s in servers}
        n = len(calls)
        if n == 1:
            assert resume is None
            mcp_call(cmd["survey"], "search", {"query": "chain of thought"})
            return {"final_text": "Thinking.", "session": "s1"}
        if n == 2:
            for _ in range(2):
                mcp_call(cmd["random_choice"], "random_choice", {"options": ["A", "B"], "weights": [0.5, 0.5]})
            return {"final_text": "Drawn.", "session": "s1"}
        return {"final_text": "DIRECTION: d\nPROJECT: P\nQUESTION: q?\nFIRST EXPERIMENT: e\nWHY THIS: w", "session": "s1"}
    return runner


def frontier(tmp):
    """run_frontier.py offline: launch texts, seeds, tools, registry order, follow-ups, output schema, judging."""
    idx, out = str(tmp / "index"), tmp / "frontier"
    data = Path(__file__).resolve().parent.parent / "data"
    for cond, exp, size in (("tree", "frontier_tree", 20), ("registry_placebo", "frontier_registry_20_placebo", 20),
                            ("registry_projects", "frontier_registry_100_projects", 100)):
        p = {r["agent_id"]: r for r in run_frontier.agent_plan(cond, size)}   # ids, slots and run order as released
        for d in map(json.loads, open(data / f"agents_{exp}.jsonl")):
            r = p[d["agent_id"]]
            assert (r["model"], r["harness"], r["launch_prompt"]) == (d["model"], d["harness"], d["launch_prompt"])
            assert size == 100 or r["run_order"] == d["run_order"]
            assert run_frontier.CONDITIONS[cond][1] == d["condition"]
    plan = run_frontier.agent_plan("tree", 20)
    assert len(plan) == 120 and [r["run_order"] for r in plan] == list(range(120))
    first = plan[0]
    assert first["seed"] == 2026111600 + 1000 * first["population"] + first["position"]
    assert run_frontier.agent_plan("registry_projects", 100)[0]["seed"] == 2026111700
    reg = run_frontier.agent_plan("registry_projects", 20)
    assert [(r["population"], r["position"]) for r in reg[:3]] == [(0, 0), (0, 1), (0, 2)]
    assert reg[0]["seed"] == 2026111300 and reg[0]["registry_seed"] == 2026111300
    s, u = run_frontier.launch_text("novelty", "F")
    assert prompts.TOOLS_SENTENCE + " " + prompts.NOVELTY in u
    s, u = run_frontier.launch_text("no_search", "F")
    assert prompts.TOOLS_SENTENCE not in u and s == prompts.F_SYSTEM_MEMORY.format(date=prompts.DATE)
    try:
        run_frontier.launch_text("max", "V08_ai_scientist_v1")
        raise AssertionError("adapted prompt should be unavailable")
    except KeyError:
        pass
    # four conditions in the minimal loop, a few agents each; population 1 starts with two adapted prompts,
    # supplied here as stand-in text through --custom-launch
    custom = tmp / "custom_launch.json"
    custom.write_text(json.dumps({"V04_task_md_sprint": [None, "Stand-in text."], "V08_ai_scientist_v1": ["S", "T."]}))
    for cond, extra in (("tree", ["--limit", "3"]), ("registry_projects", ["--populations", "0", "--limit", "3"]),
                        ("registry_agenda_counts", ["--populations", "1", "--limit", "2", "--custom-launch", str(custom)]),
                        ("no_search", ["--limit", "2"])):
        run_frontier.main(["--condition", cond, "--index", idx, "--out-dir", str(out), "--model-map",
                           json.dumps({m: "fake" for m in slots.MODELS})] + extra)
    exp_rows = lambda e: [json.loads(l) for l in open(out / f"agents_{e}.jsonl")]
    tree = exp_rows("frontier_tree")
    assert all(r["condition"] == "tree_random_draw" and r["agent_id"].startswith("TT_pop") for r in tree)
    assert all(r["draws"] for r in tree if r["status"] == "ok")
    proj = exp_rows("frontier_registry_20_projects")
    assert [r["position"] for r in proj][:2] == [0, 1] and all("analysed" in r and "excluded_because" in r for r in proj)
    state = json.loads((out / "frontier_registry_20_projects.pop00.registry.json").read_text())
    assert [e["agent_id"] for e in state] == [r["agent_id"] for r in proj if r["status"] == "ok"]
    counts = json.loads((out / "frontier_registry_20_agenda_counts.pop01.registry.json").read_text())
    assert all(e["label"] == "cot_monitoring" for e in counts)
    assert all(r["brief"].endswith("(no tools)") for r in exp_rows("frontier_no_search"))
    print(run_frontier.judge_arm("frontier_registry_20_projects", out / "agents_frontier_registry_20_projects.jsonl",
                                 "registry_projects", threads=2))
    pairs = [json.loads(l) for l in open(out / "pairs_frontier_registry_20_projects.jsonl")]
    assert pairs and all(p["rule"] == "every_pair_within_population" and p["duplicate"] for p in pairs)
    # a harness slot: tools over MCP, both follow-ups, the draw count carried into the resumed session
    calls = []
    args = argparse_ns(index=idx, out_dir=str(tmp / "harness"))
    run_frontier.run_arm(args, fake_harness_runner(calls))
    row = json.loads(open(tmp / "harness" / "agents_frontier_tree.jsonl").readline())
    assert row["status"] == "ok" and row["followups"] == 2 and row["harness"] == row["slot_harness"]
    assert calls[1]["prompt"] == run_frontier.random_choice.UNCALLED_NUDGE and calls[1]["resume"] == "s1"
    assert calls[2]["prompt"] == prompts.answer_nudge(tools=True)
    rc = next(s["command"] for s in calls[2]["servers"] if s["name"] == "random_choice")
    assert rc[rc.index("--prior-draws") + 1] == "2"
    sv = next(s["command"] for s in calls[0]["servers"] if s["name"] == "survey")
    assert sv[sv.index("--seed") + 1] == str(plan[0]["seed"]) and sv[sv.index("--tau") + 1] == "0.02"
    assert len(row["draws"]) == 2


def argparse_ns(**kw):
    import argparse
    base = dict(condition="tree", size=20, populations=None, limit=1, seed_base=None, index=None, tau=0.02,
                model_map=None, provider_map=None, custom_launch=None, context_tokens=None, out_dir=None)
    return argparse.Namespace(**{**base, **kw})


if __name__ == "__main__":
    main()
