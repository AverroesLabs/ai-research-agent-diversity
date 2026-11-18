"""Effective number of projects from a list of agents and their duplicate pairs.

The effective number of projects is 1 / p, where p is the share of pairs of agents that a judge marks as duplicate
work. It is the inverse Simpson index (Hill number of order 2) estimated from pairs of distinct agents, so a group of
agents spread evenly over k projects scores k.

The 95% interval comes from an agent bootstrap, the same procedure the post used:

* each draw resamples the agents with replacement (within each population when pairs are counted only within
  populations), giving every agent a weight w_i equal to the number of times it was drawn;
* p* = sum_{i != j} w_i w_j D_ij / sum_{i != j} w_i w_j, where D_ij is 1 for a duplicate pair, so a pair counts with
  weight w_i w_j and the pairs of an agent with its own copies are dropped;
* a draw with no duplicate pair is floored at half a pair (the numerator, which counts every pair twice, is set to 1);
* the interval is the 2.5th and 97.5th percentiles of 1 / p* over the draws (order statistics, so the ends are
  actual draws).

Only numpy is needed.
"""
import json
from pathlib import Path

import numpy as np

DRAWS = 2000


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def duplicate_matrix(agent_ids, pairs):
    """Symmetric 0/1 matrix over agent_ids (in that order) from an iterable of (a, b) duplicate pairs."""
    index = {a: i for i, a in enumerate(agent_ids)}
    D = np.zeros((len(agent_ids), len(agent_ids)))
    for a, b in pairs:
        if a in index and b in index and a != b:
            D[index[a], index[b]] = D[index[b], index[a]] = 1.0
    return D


def groups_of(labels):
    """Lists of agent positions that share a label (in order of first appearance); None labels form one group."""
    out = {}
    for i, g in enumerate(labels):
        out.setdefault(g, []).append(i)
    return list(out.values())


def counts(D, groups=None):
    """(number of pairs, number of duplicate pairs), counting pairs only within groups if groups is given."""
    groups = groups or [list(range(len(D)))]
    n_pairs = sum(len(g) * (len(g) - 1) // 2 for g in groups)
    n_dup = sum(int(np.triu(D[np.ix_(g, g)], 1).sum()) for g in groups)
    return n_pairs, n_dup


def effective_number(n_pairs, n_dup):
    """1 / share of duplicate pairs; None (unbounded) when there is no duplicate pair."""
    return n_pairs / n_dup if n_dup else None


def bootstrap(D, groups=None, seed=0, draws=DRAWS):
    """Draws of p* (agent bootstrap, within groups) and the share of draws floored at half a pair."""
    groups = groups or [list(range(len(D)))]
    rng = np.random.default_rng(seed)
    mats = []
    for g in groups:
        sub = np.asarray(D[np.ix_(g, g)], float)
        mats.append((sub, (~np.eye(len(g), dtype=bool)).astype(float)))
    ps, floored = [], 0
    for _ in range(draws):
        num = den = 0.0
        for sub, off in mats:
            n = len(sub)
            w = np.bincount(rng.integers(0, n, n), minlength=n).astype(float)
            num += w @ sub @ w
            den += w @ off @ w
        if num == 0:
            floored += 1
            num = 1.0
        ps.append(num / den)
    return np.array(ps), floored / draws


def interval(ps):
    """95% interval of 1 / p from draws of p, as order statistics."""
    lo = np.quantile(ps, 0.975, method="higher")
    hi = np.quantile(ps, 0.025, method="lower")
    return [float(1 / lo), float(1 / hi)]


def summarise(agent_ids, pairs, groups=None, seed=0, draws=DRAWS):
    """Effective number, its 95% interval and the counts behind them."""
    D = duplicate_matrix(agent_ids, pairs)
    n_pairs, n_dup = counts(D, groups)
    ps, floored = bootstrap(D, groups, seed, draws)
    return {"n_agents": len(agent_ids), "n_pairs": n_pairs, "n_duplicates": n_dup,
            "effective_number": effective_number(n_pairs, n_dup), "ci95": interval(ps),
            "share_draws_floored": floored}



def joint_ratio(keys, pairs_a, pairs_b, groups=None, seed=0, draws=DRAWS):
    """Ratio of effective numbers E_a / E_b for two arms run on the same slots, with a joint slot bootstrap: each draw
    resamples the slots (within groups, if given) once and applies the same weights to both arms; each arm's
    no-duplicate draw is floored at half a pair. keys: the slots usable in both arms, in a fixed order (our tree
    against placebo test used the tree arm's run order); pairs_a, pairs_b: duplicate pairs of each arm as pairs of
    keys. The interval is the 2.5th and 97.5th percentiles of the ratio as order statistics."""
    Da, Db = duplicate_matrix(keys, pairs_a), duplicate_matrix(keys, pairs_b)
    groups = groups or [list(range(len(keys)))]
    _, na = counts(Da, groups)
    _, nb = counts(Db, groups)
    rng = np.random.default_rng(seed)
    subs = [(np.asarray(Da[np.ix_(g, g)]), np.asarray(Db[np.ix_(g, g)])) for g in groups]
    r = []
    for _ in range(draws):
        xa = xb = 0.0
        for sa, sb in subs:
            n = len(sa)
            w = np.bincount(rng.integers(0, n, n), minlength=n).astype(float)
            xa += w @ sa @ w
            xb += w @ sb @ w
        r.append((xb or 1.0) / (xa or 1.0))                    # the shared denominators cancel
    r = np.array(r)
    return {"ratio": nb / na if na else None, "n_duplicates": [na, nb],
            "ci95": [float(np.quantile(r, 0.025, method="lower")), float(np.quantile(r, 0.975, method="higher"))]}

def stratified_bootstrap(D, valid, strata, seed=0, draws=DRAWS):
    """The interval used for the simple setup's grids (Figures A11 and A13). Agents are resampled with replacement
    within each stratum (their group of 20, or one stratum for a single group), strata taken in sorted order of their
    names; a pair counts with weight w_i w_j if it is valid (valid[i, j] is 1: both agents shared the setting, and for
    assigned lists read the same list); p* = sum w_i w_j D_ij / sum w_i w_j valid_ij. The interval is the 2.5th and
    97.5th percentiles of p* (numpy's default linear interpolation), inverted; no flooring, so a lower end of p* at
    zero leaves the upper end open (None)."""
    rng = np.random.default_rng(seed)
    idx = {}
    for i, s in enumerate(strata):
        idx.setdefault(s, []).append(i)
    groups = [np.array(v) for _, v in sorted(idx.items())]
    T = np.asarray(D, float) * np.asarray(valid, float)
    V = np.asarray(valid, float).copy()
    np.fill_diagonal(V, 0.0)
    ps = []
    for _ in range(draws):
        w = np.zeros(len(strata))
        for g in groups:
            w[g] = np.bincount(rng.integers(0, len(g), len(g)), minlength=len(g))
        ps.append((w @ T @ w) / (w @ V @ w))
    lo, hi = (float(x) for x in np.quantile(np.array(ps), [0.025, 0.975]))
    return [1 / hi if hi > 0 else None, 1 / lo if lo > 0 else None]


def people_summary(groups_of_items, duplicate_pairs):
    """People's number: 1 / pooled duplicate share over random groups of equal size, and the middle 95% of the groups'
    own values (numpy percentile, linear interpolation, on the share scale)."""
    shares = []
    for items in groups_of_items:
        s = set(items)
        n = len(items)
        k = sum(1 for a, b in duplicate_pairs if a in s and b in s)
        shares.append(k / (n * (n - 1) / 2))
    pooled = float(np.mean(shares))
    lo, hi = np.percentile(shares, [2.5, 97.5])
    inv = lambda x: float(1 / x) if x > 0 else None
    return {"pooled_share": pooled, "effective_number": inv(pooled), "range95": [inv(hi), inv(lo)]}


def data_dir():
    return Path(__file__).resolve().parent.parent / "data"
