"""How each frontier agent got its model, harness and launch prompt, and its seeds (EXPERIMENTS.md, "Populations and
slots"). Running this file checks the draw against the released agent files.

Every frontier agent is a slot: (population p, position i) -> (model, harness, launch prompt). A slot is drawn per
factor with one Python random.Random(<string seed>): model uniform over the four, then harness uniform over the
harnesses that model runs in (Claude Code only for the Claude models), then launch prompt uniform over the twelve
texts (F and V00 are counted as one prompt in the post). The 120-agent slots (6 populations of 20) are the first 80
rows of the draw seeded "20261111:p13:field" (populations 0-3, drawn for an earlier field of 80 agents) followed by
one draw of 20 per population seeded "20261112:act2s2:<p>" (populations 4-5). The populations of 100 use
"20261117:p100:<p>". These strings are literal seeds and must be used as written.

    python3 slots.py            # prints the slots and checks them against ../data/agents_frontier_*.jsonl
"""
import json
import random
from pathlib import Path

MODELS = ["anthropic/claude-opus-5.5", "anthropic/claude-sonnet-5.5", "openai/gpt-6.1-sol", "openai/gpt-6-astra"]
HARNESSES = ["claude_code", "codex_cli", "opencode", "minimal_loop"]
LAUNCH = ["F", "V00_step0_canonical", "V01_terse_run_research", "V02_terse_lw_ideas", "V03_autoresearch_program",
          "V04_task_md_sprint", "V05_terse_generate_ideas", "V08_ai_scientist_v1", "V09_agent_laboratory",
          "V10_anthropic_aar_undirected", "V11_claudini_skill", "V12_claude_lab_orchestrator"]

# Agent and population seeds. Agent (p, i) gets base + 1000 p + i; its population's registry seed is base + 1000 p.
# The agent seed is the search tool's noise seed and the `seed` request parameter; random draws are not seeded.
SEED_BASE = {
    "frontier_registry_20_*": 2026111300,         # placebo, projects (14 Nov) and agenda counts (16 Nov)
    "frontier_tree, frontier_max, frontier_no_search, frontier_novelty, frontier_tree_take_best": 2026111600,
    "frontier_registry_100_*": 2026111700,
}
RUN_ORDER_SEED = "20261116:w118:tree-order"   # literal seed string, used as written


def harness_ok(model, harness):
    return harness != "claude_code" or model.startswith("anthropic/")


def draw(seed, n):
    """n slots (model, harness, launch prompt) from one generator, factor by factor."""
    rng, out = random.Random(seed), []
    for _ in range(n):
        m = rng.choice(MODELS)
        h = rng.choice([h for h in HARNESSES if harness_ok(m, h)])
        out.append((m, h, rng.choice(LAUNCH)))
    return out


def slots_120():
    """{(population, position): (model, harness, launch prompt)} for the six populations of 20."""
    first80 = draw("20261111:p13:field", 80)
    out = {}
    for p in range(6):
        rows = first80[20 * p:20 * (p + 1)] if p < 4 else draw(f"20261112:act2s2:{p}", 20)
        out.update({(p, i): r for i, r in enumerate(rows)})
    return out


def slots_300():
    """{(population, position): slot} for the three populations of 100."""
    return {(p, i): r for p in range(3) for i, r in enumerate(draw(f"20261117:p100:{p}", 100))}


def run_order():
    """The order in which the 120-slot arms without a registry ran their slots (data field run_order)."""
    s = [(p, i) for p in range(6) for i in range(20)]
    random.Random(RUN_ORDER_SEED).shuffle(s)
    return {slot: k for k, slot in enumerate(s)}


def check(data=Path(__file__).resolve().parent.parent / "data"):
    s120, s300, order = slots_120(), slots_300(), run_order()
    for f in sorted(data.glob("agents_frontier_*.jsonl")):
        if "assigned_reading" in f.name or "earlier_groups" in f.name:   # other slot rules, see EXPERIMENTS.md
            continue
        ref = s300 if "_100_" in f.name else s120
        rows = [json.loads(l) for l in open(f)]
        bad = sum((r["model"], r["harness"], r["launch_prompt"]) != ref[(r["population"], r["position"])] for r in rows)
        bad_order = sum(r.get("run_order") is not None and order[(r["population"], r["position"])] != r["run_order"]
                        for r in rows if "_100_" not in f.name)
        print(f"{f.name}: {len(rows)} agents, {bad} slot mismatches, {bad_order} run-order mismatches")


if __name__ == "__main__":
    for (p, i), (m, h, l) in sorted(slots_120().items())[:5]:
        print(p, i, m, h, l)
    check()
