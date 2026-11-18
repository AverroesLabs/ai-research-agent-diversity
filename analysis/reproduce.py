"""Recompute every effective number in data/experiments.json from the released files and print reported vs recomputed.

    python3 analysis/reproduce.py            # all experiments
    python3 analysis/reproduce.py frontier   # experiments whose name contains "frontier"

For each measure, the agents are read from its agents file and filtered by the measure's condition, model,
populations and batch (and, where only_analysed is true, to agents with analysed = true). The duplicate pairs are the
rows of its duplicates file with that judging rule (in a pairs_* file, those with duplicate = true). Pairs are counted
among all the agents, or only within each population when the measure's scope is within_population.

Intervals. agent_bootstrap is effnum.summarise with the measure's seed; stratified_agent_bootstrap is
effnum.stratified_bootstrap (the simple-setup grids), with each agent's population as its stratum. Where the reported
interval came from another method (a jackknife, a t interval over populations, an unrecorded seed), the script prints
its own agent bootstrap beside it, which is not expected to match; where a cell also reported an agent bootstrap with
its seed (reported_bootstrap_ci95), that one is recomputed and compared. A ratio of two arms on the same slots that
carries a "check" (the tree against the placebo registry) is recomputed with effnum.joint_ratio. People's numbers are
recomputed from data/people/.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import effnum as EN  # noqa: E402

DATA = EN.data_dir()


def fmt(x, digits=1):
    if x is None:
        return "open"
    return f"{x:,.{digits}f}" if x < 1000 else f"{x:,.0f}"


def fmt_ci(ci):
    if not ci:
        return "-"
    return f"[{fmt(ci[0])}, {fmt(ci[1])}]"


def close(a, b, rel=0.005):
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= rel * max(abs(a), abs(b))


def ci_close(a, b):
    return bool(a) and bool(b) and close(a[0], b[0]) and close(a[1], b[1])


_cache = {}


def rows_of(name):
    if name not in _cache:
        _cache[name] = EN.load_jsonl(DATA / name)
    return _cache[name]


def load_agents(m):
    rows = rows_of(m["agents"])
    c = m.get("condition")
    if c:
        rows = [r for r in rows if r["condition"] in (c if isinstance(c, list) else [c])]
    if m.get("model"):
        rows = [r for r in rows if r["model"] == m["model"]]
    if m.get("populations") is not None:
        rows = [r for r in rows if r["population"] in m["populations"]]
    if m.get("batch"):
        rows = [r for r in rows if r.get("batch") == m["batch"]]
    if m.get("only_analysed"):
        rows = [r for r in rows if r.get("analysed")]
    order = m.get("agent_order")
    if order == "run_order":
        rows = sorted(rows, key=lambda r: r["run_order"])
    elif order == "stratum then id":
        rows = sorted(rows, key=lambda r: (r["population"], r["agent_id"].rsplit("/", 1)[-1]))
    return rows


def load_duplicates(m):
    rows = rows_of(m["duplicates"])
    if m["duplicates"].startswith("pairs_"):
        # a duplicate verdict the published screened analysis did not count (a pair below the screen that the judge
        # read later for another analysis) is not a duplicate under the screened rule
        return [(r["a"], r["b"]) for r in rows if r["duplicate"] and r["rule"] == m["duplicate_rule"]
                and r.get("counted_in_published_analysis") is not False]
    return [(r["a"], r["b"]) for r in rows if r["rule"] == m["duplicate_rule"]]


def recompute(m):
    agents = load_agents(m)
    ids = [a["agent_id"] for a in agents]
    within = m["scope"] == "within_population"
    groups = EN.groups_of([a["population"] for a in agents]) if within else None
    seed = m["bootstrap_seed"] if m.get("bootstrap_seed") is not None else 0
    dups = load_duplicates(m)
    out = EN.summarise(ids, dups, groups, seed)
    D = EN.duplicate_matrix(ids, dups)
    pops = [a["population"] for a in agents]
    valid = np.array([[(not within) or pops[i] == pops[j] for j in range(len(ids))] for i in range(len(ids))], float)
    if m["ci_method"] == "stratified_agent_bootstrap":
        out["ci95"] = EN.stratified_bootstrap(D, valid, [f"r{p}" for p in pops], seed)
    if m.get("reported_bootstrap_ci95") is not None:
        out["bootstrap_ci95_as_reported"] = EN.stratified_bootstrap(D, valid, [0] * len(ids), m["reported_bootstrap_seed"])
    return out


def main(filt=""):
    meta = json.load(open(DATA / "experiments.json"))
    print(f"{'experiment / measure':<84} {'n':>5} {'dups':>5}  {'reported':<24} {'recomputed':<24} match")
    n_ok = n_all = 0
    misses = []
    for name, e in meta["experiments"].items():
        if filt not in name:
            continue
        if not e.get("measures"):
            print(f"{name:<84} (no effective number reported)")
            continue
        for m in e["measures"]:
            r = recompute(m)
            rep = m["reported"]
            point_ok = close(rep["effective_number"], r["effective_number"]) and (
                rep.get("n_duplicates") in (None, r["n_duplicates"])) and (rep.get("n_agents") in (None, r["n_agents"]))
            boot = m["ci_method"] in ("agent_bootstrap", "stratified_agent_bootstrap") or m["ci_method"].startswith("agent_bootstrap")
            ci = rep["ci95"]
            ci_ok = (not boot) or (ci and close(ci[0], r["ci95"][0]) and close(ci[1], r["ci95"][1]))
            extra = ""
            if m.get("reported_bootstrap_ci95") is not None:
                bo = ci_close(m["reported_bootstrap_ci95"], r["bootstrap_ci95_as_reported"])
                ci_ok = ci_ok and bo
                extra = f"  bootstrap {fmt_ci(m['reported_bootstrap_ci95'])} vs {fmt_ci(r['bootstrap_ci95_as_reported'])}"
            ok = point_ok and ci_ok
            n_all += 1
            n_ok += ok
            label = f"{name}: {m['name']}"[:84]
            rs = f"{fmt(rep['effective_number'])} {fmt_ci(ci)}"
            cs = f"{fmt(r['effective_number'])} {fmt_ci(r['ci95'])}"
            flag = ("yes" if (boot or extra) else "yes (point; interval method differs)") if ok else "NO"
            if not ok:
                misses.append(label)
            print(f"{label:<84} {r['n_agents']:>5} {r['n_duplicates']:>5}  {rs:<24} {cs:<24} {flag}{extra}")
            if not ok and m.get("note"):
                print(f"{'':<8}note: {m['note']}")
    for name, e in meta["experiments"].items():                 # ratios of two arms on the same slots
        if filt not in name:
            continue
        for rname, rr in (e.get("reported_ratios") or {}).items():
            if rr.get("method") != "joint agent bootstrap over matched slots" or not rr.get("check"):
                continue
            c = rr["check"]
            arms = []
            for exp in (c["numerator"], c["denominator"]):
                ag = EN.load_jsonl(DATA / f"agents_{exp}.jsonl")
                slot = {a["agent_id"]: (a["population"], a["position"]) for a in ag if a.get("analysed", True)}
                dup = [(slot[p["a"]], slot[p["b"]]) for p in EN.load_jsonl(DATA / f"pairs_{exp}.jsonl")
                       if p["rule"] == c["rule"] and p["duplicate"] and p["a"] in slot and p["b"] in slot]
                arms.append((ag, slot, dup))
            both = set(arms[0][1].values()) & set(arms[1][1].values())
            keys = [arms[0][1][a["agent_id"]] for a in sorted(arms[0][0], key=lambda a: a[c["key_order"]])
                    if arms[0][1].get(a["agent_id"]) in both]
            got = EN.joint_ratio(keys, arms[0][2], arms[1][2], seed=c["bootstrap_seed"], draws=c["bootstrap_draws"])
            ok = close(rr["ratio"], got["ratio"]) and ci_close(rr["ci95"], got["ci95"])
            n_all += 1
            n_ok += ok
            if not ok:
                misses.append(f"{name}: {rname}")
            label = f"{name}: ratio {rname}"[:84]
            print(f"{label:<84} {len(keys):>5} {sum(got['n_duplicates']):>5}  "
                  f"{fmt(rr['ratio']) + ' ' + fmt_ci(rr['ci95']):<24} {fmt(got['ratio']) + ' ' + fmt_ci(got['ci95']):<24} "
                  f"{'yes' if ok else 'NO'}")
    if not filt or "people" in filt:
        for key, p in meta["people"].items():
            def group_shares(k):
                groups = [g["item_ids"] for g in EN.load_jsonl(DATA / "people" / f"groups_{k}.jsonl")]
                counts = [0] * len(groups)
                pf = DATA / "people" / f"pairs_{k}.jsonl"
                if pf.exists():
                    for r in EN.load_jsonl(pf):
                        if r["duplicate"]:
                            for gi in r["groups"]:
                                counts[gi] += 1
                else:
                    for d in EN.load_jsonl(DATA / "people" / f"duplicates_{k}.jsonl"):
                        counts[d["group"]] += 1
                return [c / (len(g) * (len(g) - 1) / 2) for c, g in zip(counts, groups)], sum(counts)

            if p.get("members"):     # pooled sources, each weighted equally
                per = [group_shares(k) for k in p["members"]]
                shares = [s for ss, _ in per for s in ss]
                pooled = float(np.mean([np.mean(ss) for ss, _ in per]))
                n_d = sum(n for _, n in per)
            else:
                shares, n_d = group_shares(key)
                pooled = float(np.mean(shares))
            lo, hi = np.percentile(shares, [2.5, 97.5])
            inv = lambda x: float(1 / x) if x > 0 else None
            rep = p["reported"]
            got = (inv(pooled), [inv(hi), inv(lo)])
            ok = close(rep["effective_number"], got[0]) and ci_close(rep["range95"], got[1]) if got[1][1] is not None \
                else close(rep["effective_number"], got[0])
            n_all += 1
            n_ok += ok
            if not ok:
                misses.append("people: " + key)
            print(f"{'people: ' + p['label']:<84.84} {len(shares) * 40:>5} {n_d:>5}  "
                  f"{fmt(rep['effective_number']) + ' ' + fmt_ci(rep['range95']):<24} {fmt(got[0]) + ' ' + fmt_ci(got[1]):<24} "
                  f"{'yes' if ok else 'NO'}")
    print(f"\n{n_ok} of {n_all} measures match (point estimate, agent and duplicate counts, and, for agent-bootstrap "
          f"intervals, both ends within 0.5%).")
    if misses:
        print("Not matching:\n  " + "\n  ".join(misses))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
