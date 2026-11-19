"""Where the frontier field's spread comes from (appendix Figure A4).

Splits every pair of the frontier setup's 120 agents choosing alone (searching: frontier_max; without search:
frontier_no_search) by what its two agents share, and gives the effective number of projects among the pairs of each
class: models from different labs, the same lab but different models, the same model with different launch prompts,
and the same model and launch prompt. Our brief (F) and its short form (V00) count as one launch prompt.

Also, among pairs of agents of one model, the number of duplicates in pairs that share a harness (or a launch prompt),
divided by the number expected from that model's duplicate share.

Intervals are 95%, from resampling agents (2,000 draws). Run: python analysis/sources_of_diversity.py
"""
from itertools import combinations
from pathlib import Path

import numpy as np

import effnum as EN

DATA = Path(__file__).resolve().parents[1] / "data"
LAB = {"anthropic": "Anthropic", "openai": "OpenAI"}
CLASSES = ["different labs", "same lab, other model", "same model, other prompt", "same model and prompt"]


def prompt_of(a):
    p = a["launch_prompt"]
    return "F" if p == "F" or p.startswith("V00") else p


def analyse(name, seed):
    agents = sorted(EN.load_jsonl(DATA / f"agents_{name}.jsonl"), key=lambda a: a["agent_id"])
    ids = [a["agent_id"] for a in agents]
    D = EN.duplicate_matrix(ids, [(r["a"], r["b"]) for r in EN.load_jsonl(DATA / f"pairs_{name}.jsonl")
                                  if r["duplicate"] and r["rule"] == "every_pair"])
    n = len(agents)
    C = np.full((n, n), -1)
    H = np.zeros((n, n), bool)
    P = np.zeros((n, n), bool)
    for i, j in combinations(range(n), 2):
        a, b = agents[i], agents[j]
        la, lb = a["model"].split("/")[0], b["model"].split("/")[0]
        k = 0 if la != lb else 1 if a["model"] != b["model"] else 3 if prompt_of(a) == prompt_of(b) else 2
        C[i, j] = C[j, i] = k
        H[i, j] = H[j, i] = a["harness"] == b["harness"]
        P[i, j] = P[j, i] = prompt_of(a) == prompt_of(b)

    def stats(s):
        Ds, Cs = D[np.ix_(s, s)], C[np.ix_(s, s)]
        ok = s[:, None] != s[None, :]   # drop an agent paired with its own copy
        out = {c: (Ds[ok & (Cs == k)].sum() / 2, (ok & (Cs == k)).sum() / 2) for k, c in enumerate(CLASSES)}
        out["all pairs"] = (Ds[ok].sum() / 2, ok.sum() / 2)
        same = ok & (Cs >= 2)
        share = Ds[same].sum() / same.sum()
        for f, F in (("harness", H), ("launch prompt", P)):
            m = same & F[np.ix_(s, s)]
            out[f"same model, same {f}: observed / expected"] = (Ds[m].sum() / 2, share * m.sum() / 2)
        return out

    point = stats(np.arange(n))
    rng = np.random.default_rng(seed)
    boots = [stats(rng.integers(0, n, n)) for _ in range(EN.DRAWS)]
    print(f"\n{name}: {n} agents")
    for key, (dup, pairs) in point.items():
        if "observed" in key:
            vals = [b[key][0] / b[key][1] for b in boots if b[key][1] > 0]
            lo, hi = np.percentile(vals, [2.5, 97.5])
            print(f"  {key:50s} {int(dup)} / {pairs:.1f} = {dup / pairs:.2f} ({lo:.2f} to {hi:.2f})")
        else:
            vals = np.sort([b[key][1] / b[key][0] if b[key][0] else np.inf for b in boots])
            lo, hi = vals[int(0.025 * len(vals))], vals[int(np.ceil(0.975 * len(vals))) - 1]   # an upper end can be infinite
            E = pairs / dup if dup else np.inf
            print(f"  {key:50s} {int(dup):4d} duplicates in {int(pairs):5d} pairs   E = {E:7.1f} ({lo:.0f} to {hi:.0f})")


if __name__ == "__main__":
    analyse("frontier_max", 20261119)
    analyse("frontier_no_search", 20261119)
