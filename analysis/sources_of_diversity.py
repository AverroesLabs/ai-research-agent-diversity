"""Where the spread among agents comes from (Figure 7).

For the 120 agents choosing alone (searching: frontier_max; without search: frontier_no_search), takes each part of an
agent and gives the effective number of projects among pairs of agents that share it and among pairs that differ in
it. Each part is compared where nothing larger differs: lab over all pairs (agents from different labs always run
different models), model within a lab, instructions and harness within a model. Also identical agents (same model,
instructions and harness) and all pairs. Our brief (F) and its short form (V00) count as one set of instructions.

Intervals are 95%, from resampling agents (2,000 draws); "agents" is the number of agents in a row's pairs.
Run: python analysis/sources_of_diversity.py
"""
from itertools import combinations
from pathlib import Path

import numpy as np

import effnum as EN

DATA = Path(__file__).resolve().parents[1] / "data"
ROWS = [("identical agents", None, None), ("same lab", None, ("lab", True)), ("different labs", None, ("lab", False)),
        ("same model, within a lab", "lab", ("model", True)), ("different models, within a lab", "lab", ("model", False)),
        ("same instructions, within a model", "model", ("instructions", True)),
        ("different instructions, within a model", "model", ("instructions", False)),
        ("same harness, within a model", "model", ("harness", True)),
        ("different harnesses, within a model", "model", ("harness", False)), ("all pairs", None, None)]


def instructions_of(a):
    p = a["launch_prompt"]
    return "F" if p == "F" or p.startswith("V00") else p


def analyse(name, seed):
    agents = sorted(EN.load_jsonl(DATA / f"agents_{name}.jsonl"), key=lambda a: a["agent_id"])
    ids = [a["agent_id"] for a in agents]
    D = EN.duplicate_matrix(ids, [(r["a"], r["b"]) for r in EN.load_jsonl(DATA / f"pairs_{name}.jsonl")
                                  if r["duplicate"] and r["rule"] == "every_pair"])
    n = len(agents)
    part = {"lab": lambda a: a["model"].split("/")[0], "model": lambda a: a["model"],
            "instructions": instructions_of, "harness": lambda a: a["harness"]}
    same = {k: np.zeros((n, n), bool) for k in part}
    for i, j in combinations(range(n), 2):
        for k, f in part.items():
            same[k][i, j] = same[k][j, i] = f(agents[i]) == f(agents[j])
    M = {}
    for label, ctx, cmp in ROWS:
        if label == "identical agents":
            M[label] = same["model"] & same["instructions"] & same["harness"]
        elif label == "all pairs":
            M[label] = np.ones((n, n), bool)
        else:
            base = same[ctx] if ctx else np.ones((n, n), bool)
            k, s = cmp
            M[label] = base & (same[k] if s else ~same[k])

    def stats(s):
        Ds = D[np.ix_(s, s)]
        ok = s[:, None] != s[None, :]   # drop an agent paired with its own copy
        return {c: (Ds[ok & m[np.ix_(s, s)]].sum() / 2, (ok & m[np.ix_(s, s)]).sum() / 2) for c, m in M.items()}

    point = stats(np.arange(n))
    rng = np.random.default_rng(seed)
    boots = [stats(rng.integers(0, n, n)) for _ in range(EN.DRAWS)]
    print(f"\n{name}: {n} agents")
    for c, (dup, pairs) in point.items():
        vals = np.sort([b[c][1] / b[c][0] if b[c][0] else np.inf for b in boots])
        lo, hi = vals[int(0.025 * len(vals))], vals[int(np.ceil(0.975 * len(vals))) - 1]   # an upper end can be infinite
        E = pairs / dup if dup else np.inf
        k = int((M[c] & ~np.eye(n, dtype=bool)).any(axis=1).sum())
        print(f"  {c:40s} {int(dup):4d} duplicates in {int(pairs):5d} pairs, {k:3d} agents   E = {E:7.1f} ({lo:.0f} to {hi:.0f})")


if __name__ == "__main__":
    analyse("frontier_max", 20261119)
    analyse("frontier_no_search", 20261119)
