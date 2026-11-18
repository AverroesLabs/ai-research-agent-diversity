"""Run one population of agents under one condition in our minimal loop, and write their picks in the release's
agents_*.jsonl format (EXPERIMENTS.md; worked example in README.md).

    OPENAI_BASE_URL=https://openrouter.ai/api/v1 OPENAI_API_KEY=... python3 run_population.py \\
        --condition registry_projects --model z-ai/glm-5.3-flash \\
        --provider '{"order": ["Z.AI"], "allow_fallbacks": false, "require_parameters": true}' \\
        --n 20 --population-seed 25261112 --out runs/glm_registry.jsonl

Conditions: max, novelty, registry_projects, registry_agenda_counts, registry_placebo, tree, tree_take_best.
--setup simple (default): our brief from memory, plus the condition's text and tool, as in the simple setup.
--setup frontier: launch prompt --launch (default F) with search; needs --index (search_tool.py build).
Agents run one at a time; agent k gets seed population_seed + k and, in registry conditions, sees agents 0..k-1.
Rows are appended to --out, so several populations (use --population) can share one file.
"""
import argparse
import json
from pathlib import Path

import labeller
import minimal_loop
import prompts
import random_choice
import registry
import search_tool

CONDITIONS = ("max", "novelty", "registry_projects", "registry_agenda_counts", "registry_placebo", "tree",
              "tree_take_best")


def agent_messages(condition, setup, launch_id="F"):
    tools_on = setup == "frontier"
    system, user = prompts.launch(launch_id, tools=tools_on)
    if condition == "novelty":
        user = prompts.add_novelty_sentence(user, setup)
    elif condition.startswith("registry_"):
        user = prompts.add_registry_sentence(user, setup)
    elif condition in ("tree", "tree_take_best"):
        user = prompts.add_tree_protocol(user, take_best=condition == "tree_take_best", setup=setup)
    return system, user


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--condition", choices=CONDITIONS, required=True)
    ap.add_argument("--setup", choices=["simple", "frontier"], default="simple")
    ap.add_argument("--launch", default="F")
    ap.add_argument("--model", required=True)
    ap.add_argument("--provider", type=json.loads, help="OpenRouter provider routing, JSON")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--population", type=int, default=0)
    ap.add_argument("--population-seed", type=int, default=0)
    ap.add_argument("--index", help="search index directory (frontier setup)")
    ap.add_argument("--tau", type=float, default=0.02, help="search noise (frontier setup used 0.02)")
    ap.add_argument("--context-tokens", type=int, help="the model's context window, for compaction")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.setup == "frontier" and not a.index:
        ap.error("--setup frontier needs --index")
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pop = registry.Population(out.with_suffix(".registry.json"), a.population_seed)
    system, user = agent_messages(a.condition, a.setup, a.launch)
    extra = {"provider": a.provider} if a.provider else {}
    with open(out, "a") as f:
        for k in range(a.n):
            seed = a.population_seed + k
            tools, must = {}, None
            if a.setup == "frontier":
                st = search_tool.SearchTool(a.index, tau=a.tau, rank_seed=seed)   # own instance per agent
                tools.update(search=st, read=st)
            if a.condition.startswith("registry_"):
                tools["read_registry"] = registry.RegistryTool(a.condition[len("registry_"):], pop, k)
                must = "read_registry"
            if a.condition == "tree":
                tools["random_choice"] = random_choice.RandomChoice()
                must = "random_choice"
            rec = minimal_loop.run_session(a.model, system, user, tools=tools, seed=seed, must_call=must,
                                           context_tokens=a.context_tokens, **extra)
            p = rec["parsed"] or {}
            if a.condition.startswith("registry_") and a.condition != "registry_placebo":
                label = labeller.live_label(p) if a.condition == "registry_agenda_counts" else None
                pop.register(k, f"pop{a.population:02d}_a{k:02d}", p, label=label, status=rec["status"],
                             rule="frontier" if a.setup == "frontier" else "simple")
            row = {"agent_id": f"{a.condition}_pop{a.population:02d}_a{k:02d}", "experiment": out.stem,
                   "condition": a.condition, "population": a.population, "position": k, "model": a.model,
                   "harness": "minimal_loop", "launch_prompt": a.launch, "status": rec["status"],
                   "usable": rec["status"] == "ok" and not minimal_loop.is_template_echo(p) and bool(p.get("direction") and p.get("project")),
                   "direction": p.get("direction"), "project": p.get("project"), "question": p.get("question"),
                   "first_experiment": p.get("first_experiment"), "why": p.get("why_this"),
                   "n_tool_calls": len(rec["tool_events"]), "followups": len(rec["followups"])}
            if a.condition == "tree":
                row["draws"] = tools["random_choice"].log
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            print(k, rec["status"], (p.get("project") or "")[:80])


if __name__ == "__main__":
    main()
