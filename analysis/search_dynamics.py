"""How search shaped the frontier agents' choices (appendix, "How search shaped the choices").

Reads the released session transcripts and the corpus list, and prints:

1. what searching agents first searched for, in the no-tool run and in the three registries of 100 agents: the share
   of first queries about monitoring or control, the share asking for 2026 work, and how many words two agents' first
   queries share on average;
2. for the documents the most no-tool agents opened: how many agents saw each in their results, how many opened it,
   how many of the queries that returned it were distinct, and how many words those queries share;
3. the share of the corpus's core documents, by year, whose titles are about monitoring or control;
4. how many Claude Opus agents saw the "Generalization Hacking" paper in their results, in each registry of 100.

Word overlap is the Jaccard index of two queries' word sets, without a short list of words every query uses ("AI",
"safety", "2026", "research", articles and prepositions). Topic matching uses the fixed patterns below. Decided after
the results were known; descriptive only.

Run: python analysis/search_dynamics.py   (needs Python 3.14's compression.zstd, or the zstandard package)
"""
import collections
import io
import itertools
import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOPIC = re.compile(r"monitor|\bcontrol\b|untrusted|sabotage|collu", re.I)
STOP = {"ai", "safety", "2026", "2025", "research", "the", "of", "and", "in", "for", "a", "an", "to", "on", "with",
        "model", "models", "language", "llm", "llms", "agent", "agents"}
GH = "arxiv:2606.12016"   # Generalization Hacking


def open_zst(path):
    try:
        from compression import zstd
        return zstd.open(path, "rt")
    except ImportError:
        import zstandard
        return io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(open(path, "rb")))


def sessions(name):
    """Per agent: model, population, its search queries in order, the documents each query returned, and the
    documents it opened in order. Tool names differ by harness (search, survey.search, survey_search,
    mcp__survey__search); built-in harness tools are ignored."""
    out = {}
    for line in open_zst(ROOT / "transcripts" / f"transcripts_{name}.jsonl.zst"):
        r = json.loads(line)
        calls, qs, opened, returned = {}, [], [], []
        for m in r["messages"]:
            for c in m.get("tool_calls") or []:
                calls[c["id"]] = c
            if m.get("role") != "tool":
                continue
            nm = m.get("name") or ""
            res = m.get("tool_result") if isinstance(m.get("tool_result"), dict) else {}
            ids = [d["doc_id"] for d in res.get("docs", [])]
            if nm.endswith("search") and "mcp_resource" not in nm:
                q = calls.get(m["tool_call_id"], {}).get("arguments", {}).get("query", "")
                qs.append(q)
                returned.append(ids)
            elif ids and (nm in ("survey.read", "survey_read", "mcp__survey__read")
                          or (nm == "read" and r["harness"] == "minimal_loop")):
                opened.append(ids[0])
        out[r["agent_id"]] = {"model": r["model"], "population": r.get("population"), "qs": qs,
                              "returned": returned, "opened": opened}
    return out


def words(q):
    return set(re.findall(r"[a-z0-9]+", q.lower())) - STOP


def overlap(qs, rng, k=5000):
    pairs = list(itertools.combinations(qs, 2))
    pairs = rng.sample(pairs, min(k, len(pairs)))
    return sum(len(words(a) & words(b)) / max(1, len(words(a) | words(b))) for a, b in pairs) / len(pairs)


def first_queries(name, rng):
    S = sessions(name)
    fq = [a["qs"][0] for a in S.values() if a["qs"]]
    print(f"  {name:42s} agents {len(S):3d}   first query about monitoring or control "
          f"{sum(bool(TOPIC.search(q)) for q in fq):3d} ({sum(bool(TOPIC.search(q)) for q in fq) / len(fq):.0%})"
          f"   asks for 2026 {sum('2026' in q for q in fq) / len(fq):.0%}   word overlap {overlap(fq, rng):.3f}")
    return S


def main():
    rng = random.Random(20261120)
    print("1. First search queries")
    N = first_queries("frontier_max", rng)
    for arm in ("registry_100_placebo", "registry_100_agenda_counts", "registry_100_projects"):
        first_queries(f"frontier_{arm}", rng)
    allq = [q for a in N.values() for q in a["qs"]]
    print(f"  no-tool run: {len(allq)} queries, {len(set(q.lower().strip() for q in allq))} distinct; word overlap of "
          f"two random queries {overlap(rng.sample(allq, 400), rng):.3f}")

    print("\n2. The documents the most no-tool agents opened")
    titles = {d["doc_id"]: d["title"] for d in map(json.loads, open(ROOT / "data/corpus_docs.jsonl"))}
    opened = collections.Counter(d for a in N.values() for d in set(a["opened"]))
    for doc, n_open in opened.most_common(5):
        saw = [a for a in N.values() if any(doc in ids for ids in a["returned"])]
        qs = [q for a in saw for q, ids in zip(a["qs"], a["returned"]) if doc in ids]
        firsts = [next(q for q, ids in zip(a["qs"], a["returned"]) if doc in ids) for a in saw]
        print(f"  {titles.get(doc, doc)[:60]:60s} in results for {len(saw):3d}, opened by {n_open:3d}; "
              f"{len(qs)} queries returned it, {len(set(q.lower().strip() for q in qs))} distinct; "
              f"word overlap {overlap(firsts, rng):.3f}")

    print("\n3. Core corpus documents whose titles are about monitoring or control, by year")
    core = [d for d in map(json.loads, open(ROOT / "data/corpus_docs.jsonl")) if d.get("layer") == "core"]
    for label, ys in (("2022 and earlier", range(0, 2023)), ("2023", [2023]), ("2024", [2024]), ("2025", [2025]),
                      ("2026", [2026])):
        ds = [d for d in core if (d.get("year") or 0) in ys]
        k = sum(bool(TOPIC.search(d.get("title") or "")) for d in ds)
        print(f"  {label:18s} {k:5d} of {len(ds):6d} ({k / max(1, len(ds)):.0%})")

    print("\n4. Claude Opus agents who saw 'Generalization Hacking' in their results, registries of 100")
    for arm in ("registry_100_placebo", "registry_100_agenda_counts", "registry_100_projects"):
        S = sessions(f"frontier_{arm}")
        opus = [a for a in S.values() if "opus" in a["model"]]
        saw = sum(any(GH in ids for ids in a["returned"]) for a in opus)
        print(f"  {arm:30s} {saw:3d} of {len(opus)}")


if __name__ == "__main__":
    main()
