"""Our literature search tool (search + read), as a spec and a small reference implementation
(EXPERIMENTS.md, "Search tool").

Agents searched a frozen copy of the AI-safety literature (99,464 papers, forum posts, research blog posts and
overview pages, snapshot of 8 November 2026) through two tools:

    search(query)      -> JSON list of up to 10 {"id", "title", "source", "date", "snippet"}
    read(id, page=1)   -> "Title: ...\\nSource: ... | Date: ... | URL: ...\\n[Text: ...\\n]Page p of n[ (read page=p+1 for
                          more)]\\n\\n" + 8,000 characters of the document

The corpus is not ours to release, so this file rebuilds the tool around a corpus you assemble (corpus_from_ids.py
lists the documents our agents opened). Ranking, exactly as configured in our runs:

 1. BM25 (k1 1.2, b 0.75) over title x2 + indexed abstract + tags + first 10 authors + arXiv ids / DOIs, with our
    tokenizer (lowercase alphanumerics, stopwords, a light plural stemmer; arXiv ids and DOIs kept whole). A document
    whose abstract is under 300 characters (web pages) is indexed on its abstract plus the first 1,000 characters
    of its text. Optional dense retrieval (BAAI/bge-small-en-v1.5, query prefix "Represent this sentence for
    searching relevant passages: ") over the "core" layer only.
 2. Reciprocal rank fusion of the top 100 of each list, k = 60, equal weights; a document without a vector uses its
    BM25 rank in place of the missing dense rank; relevance = RRF / its maximum, in [0, 1].
 3. Forum posts' relevance x 0.65. score = relevance + 0.25 x pop + tau x Gumbel noise. pop in [0, 1] is a
    popularity percentile (papers: mid-rank percentile of citations within field and year, falling back to year,
    then to all papers, for groups under 30; posts: karma within forum, EA Forum or LessWrong/Alignment Forum, and
    year; missing values and other kinds: the kind's median). data/corpus_docs.jsonl gives `pop` for every document
    (null where it was missing); corpus_from_ids.py carries it into the corpus and build() fills the medians. Noise: tau 0.02 ("moderate", the frontier setup and step one's Sr cells), 0 or 0.0945 in
    other step-one cells; the Gumbel draw is a hash of (agent seed, normalised query, how many times this agent ran
    that query before, document index), so repeating a query gives a fresh draw, reproducible from the seed.
 4. Sort by score, ties by document id. Documents whose arXiv id or DOI the query names go first.
 5. Walk the ranking and keep at most 3 overview pages per site and at most one copy of a work (same normalised
    title from another site), until 10 results.

The tool's error results are {"error": "..."} in our minimal loop and "Error: ..." with isError over MCP.

    python3 search_tool.py build corpus.jsonl index_dir [--dense]
    python3 search_tool.py search index_dir "chain of thought monitoring" [--seed 2026111600 --tau 0.02]
"""
import argparse
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter

import numpy as np

K1, B, TITLE_REPEAT, RRF_K, DEPTH = 1.2, 0.75, 2, 60, 100
CONFIG = {"k": 10, "snippet_chars": 200, "page_chars": 8000, "w_pop": 0.25, "post_weight": 0.65, "site_cap": 3,
          "site_cap_kinds": ["overview"], "dup_cap": 1, "tau": 0.0, "rank_seed": None, "noise_scope": "call"}
PAGE_TEXT = {"min_chars": 300, "pad_chars": 1000}
DENSE_MODEL, DENSE_PREFIX = "BAAI/bge-small-en-v1.5", "Represent this sentence for searching relevant passages: "
SCHEMAS = [
    {"name": "search",
     "description": "Search for research papers, posts and articles. Returns up to 10 results, each with id, title, "
                    "source, date and a short snippet. Use read to open a result.",
     "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "The search query."}},
                    "required": ["query"], "additionalProperties": False}},
    {"name": "read",
     "description": "Read a document by its id from search results. Returns its text one page at a time; request "
                    "later pages with page.",
     "parameters": {"type": "object", "properties": {
         "id": {"type": "string", "description": "Document id from a search result."},
         "page": {"type": "integer", "description": "Page number, starting at 1.", "default": 1, "minimum": 1}},
         "required": ["id"], "additionalProperties": False}},
]

STOP = frozenset("""a about above after again against all am an and any are as at be because been before being below
between both but by can could did do does doing down during each few for from further had has have having he her here hers
him his how i if in into is it its itself just me more most my no nor not of off on once only or other our ours out over own
same she should so some such than that the their theirs them then there these they this those through to too under until up
very was we were what when where which while who whom why will with would you your yours via using use et al""".split())
ID_RE = re.compile(r'(?<![\w.])(?:arxiv:\s*)?(\d{4}\.\d{4,5})(?:v\d+)?(?![\w.]*\d)'
                   r'|(?<![\w/])([a-z][a-z\-]+(?:\.[a-z]{2})?/\d{7})(?:v\d+)?(?!\d)'
                   r'|(?<![\w.])(10\.\d{4,9}/[^\s"<>]+[^\s"<>.,;:)\]])', re.I)


class ToolError(Exception):
    pass


# ---------------------------------------------------------------- text
def _stem(w):
    if len(w) <= 3: return w
    if w.endswith("ies") and len(w) > 4: return w[:-3] + "y"
    if w.endswith("sses"): return w[:-2]
    if w.endswith("s") and not w.endswith(("ss", "us", "is")): return w[:-1]
    return w


def tokenize(text):
    text = (text or "").lower()
    ids = [next(g for g in m.groups() if g) for m in ID_RE.finditer(text)]
    text = ID_RE.sub(" ", text)
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", text) if w not in STOP and len(w) <= 40] + \
           [i for i in ids if len(i) <= 80]


def known_ids(doc):
    """'arxiv:<id>' and 'doi:<doi>' keys of a document (for known-item lookup)."""
    out, did = set(), doc.get("id") or ""
    if did.startswith("arxiv:"): out.add("arxiv:" + re.sub(r"v\d+$", "", did[6:].lower()))
    if did.startswith("doi:"): out.add("doi:" + did[4:].lower())
    for scheme in ("arxiv", "doi"):
        v = (doc.get("ids") or {}).get(scheme)
        for x in (v if isinstance(v, list) else [v] if v else []):
            x = str(x).strip().lower()
            out.add(f"{scheme}:" + (re.sub(r"v\d+$", "", x) if scheme == "arxiv" else x))
    return sorted(out)


def query_ids(text):
    out = []
    for m in ID_RE.finditer(text or ""):
        a, old, doi = m.groups()
        if doi:
            d = doi.lower()
            k = "arxiv:" + d[len("10.48550/arxiv."):] if d.startswith("10.48550/arxiv.") else "doi:" + d
        else:
            k = "arxiv:" + (a or old).lower()
        if k not in out: out.append(k)
    return out


def abstract(doc):
    return doc.get("abstract") or " ".join((doc.get("text") or "")[:1500].split())


def index_abstract(doc):
    a = abstract(doc)
    if len(a.strip()) < PAGE_TEXT["min_chars"]:
        t = " ".join((doc.get("text") or "").split())
        if len(t) > len(a.strip()): a = (a.strip() + " " + t[:PAGE_TEXT["pad_chars"]]).strip()
    return a


def bm25_text(doc):
    return " ".join([doc.get("title") or ""] * TITLE_REPEAT + [index_abstract(doc), " ".join(doc.get("tags") or []),
                     " ".join(str(a) for a in (doc.get("authors") or [])[:10])] +
                    [k.split(":", 1)[1] for k in known_ids(doc)])


def snippet(text, n):
    s = " ".join((text or "").split())
    if len(s) <= n: return s
    cut = s[:n - 3]
    if " " in cut[n // 2:]: cut = cut[:cut.rfind(" ")]
    return cut.rstrip(" ,;:") + "..."


def dup_key(title):
    """Near-duplicate key: lowercase alphanumerics, without a leading '[arXiv id]' or a trailing ' | Site' of <= 3 words."""
    s = re.sub(r"^\s*\[(?:arxiv:)?\d{4}\.\d{4,5}(?:v\d+)?\]\s*", "", " ".join((title or "").split()), flags=re.I)
    parts = re.split(r"\s+[|\-–—]\s+", s)
    if len(parts) > 1 and len(re.findall(r"\w+", parts[-1])) <= 3 and len(re.findall(r"\w+", " ".join(parts[:-1]))) >= 4:
        s = " ".join(parts[:-1])
    toks = re.findall(r"[a-z0-9]+", s.lower())
    return " ".join(toks) if len(toks) >= 4 else None


def source_label(d):
    from urllib.parse import urlparse
    if d.get("site"): return d["site"]
    host = urlparse(d.get("url") or "").netloc.lower()
    return (host[4:] if host.startswith("www.") else host) or d.get("source") or d["kind"]


# ---------------------------------------------------------------- noise
_M64 = np.uint64(0xFFFFFFFFFFFFFFFF)


def _splitmix(x):
    with np.errstate(over="ignore"):
        x = (x + np.uint64(0x9E3779B97F4A7C15)) & _M64
        x = ((x ^ (x >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)) & _M64
        x = ((x ^ (x >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)) & _M64
        return x ^ (x >> np.uint64(31))


def gumbel(seed, key, idx):
    """Standard Gumbel draws for document indices idx, a pure function of (seed, key, idx). Same as ours, so with the
    same corpus sorted by id the noise matches ours draw for draw."""
    h = int.from_bytes(hashlib.sha256(f"{seed}|{key}".encode()).digest()[:8], "little")
    with np.errstate(over="ignore"):
        x = _splitmix(np.asarray(idx, np.uint64) * np.uint64(0xD1B54A32D192ED03) ^ np.uint64(h))
    u = ((x >> np.uint64(11)).astype(np.float64) + 0.5) / float(1 << 53)
    return -np.log(-np.log(u))


# ---------------------------------------------------------------- index
def build(corpus_path, out_dir, dense=False):
    """Index a corpus JSONL. Each line: id, kind (paper|post|blog|overview), title, date (YYYY-MM-DD), and optionally
    abstract, text, url, site, source, authors, tags, ids, layer (core|neighbour|broad), pop (0-1)."""
    docs = {}
    for line in open(corpus_path):
        if line.strip():
            d = json.loads(line)
            docs[d["id"]] = d
    docs = [docs[k] for k in sorted(docs)]                      # sorted by id: the order the noise hash uses
    toks = [Counter(tokenize(bm25_text(d))) for d in docs]
    dl = np.array([sum(t.values()) for t in toks], float)
    avgdl = float(dl.mean()) if len(dl) else 1.0
    df = Counter(w for t in toks for w in t)
    N, post = len(docs), {}
    for i, t in enumerate(toks):
        for w, tf in t.items():
            idf = math.log(1 + (N - df[w] + 0.5) / (df[w] + 0.5))
            post.setdefault(w, []).append((i, idf * tf * (K1 + 1) / (tf + K1 * (1 - B + B * dl[i] / avgdl))))
    kinds = np.array([d["kind"] for d in docs])
    pop = np.array([np.nan if d.get("pop") is None else float(d["pop"]) for d in docs])
    glob = float(np.nanmedian(pop)) if np.isfinite(pop).any() else 0.0
    for k in set(kinds):                                         # missing popularity: the kind's median
        m = kinds == k
        fill = float(np.nanmedian(pop[m])) if np.isfinite(pop[m]).any() else glob
        pop[m & np.isnan(pop)] = fill
    os.makedirs(out_dir, exist_ok=True)
    terms = sorted(post)
    np.savez(os.path.join(out_dir, "index.npz"), pop=np.clip(pop, 0, 1),
             ptr=np.cumsum([0] + [len(post[w]) for w in terms]),
             doc=np.array([i for w in terms for i, _ in post[w]], np.int32),
             w=np.array([x for w in terms for _, x in post[w]], np.float32))
    with open(os.path.join(out_dir, "terms.json"), "w") as f: json.dump(terms, f)
    with open(os.path.join(out_dir, "docs.jsonl"), "w") as f:
        for d in docs:
            f.write(json.dumps({"id": d["id"], "kind": d["kind"], "title": d["title"], "date": d["date"],
                                "source": source_label(d), "url": d.get("url") or "", "abstract": abstract(d),
                                "text": d.get("text") or abstract(d), "text_source": d.get("text_source"),
                                "keys": known_ids(d), "layer": d.get("layer", "core")}, ensure_ascii=False) + "\n")
    if dense:                                                     # needs sentence-transformers
        from sentence_transformers import SentenceTransformer
        rows = [i for i, d in enumerate(docs) if d.get("layer", "core") == "core"]
        X = SentenceTransformer(DENSE_MODEL).encode([f"{docs[i]['title'].strip()}. {index_abstract(docs[i]).strip()}"
                                                     for i in rows], normalize_embeddings=True)
        np.savez(os.path.join(out_dir, "dense.npz"), rows=np.array(rows, np.int64), X=X.astype(np.float32))
    return len(docs)


class SearchTool:
    """search and read over a built index, for one agent session (the noise call counter is per instance)."""
    schemas = SCHEMAS

    def __init__(self, index_dir, **config):
        self.cfg = {**CONFIG, **config}
        z = np.load(os.path.join(index_dir, "index.npz"))
        self.pop, self.ptr, self.pdoc, self.pw = z["pop"], z["ptr"], z["doc"], z["w"]
        self.terms = {w: j for j, w in enumerate(json.load(open(os.path.join(index_dir, "terms.json"))))}
        self.docs = [json.loads(l) for l in open(os.path.join(index_dir, "docs.jsonl"))]
        self.by_id = {d["id"]: i for i, d in enumerate(self.docs)}
        self.by_key = {}
        for i, d in enumerate(self.docs):
            for k in d["keys"]: self.by_key.setdefault(k, i)
        self.by_url = {}
        for i, d in enumerate(self.docs):
            if d["url"]: self.by_url.setdefault(d["url"], i)
        dp = os.path.join(index_dir, "dense.npz")
        self.dense = np.load(dp) if os.path.exists(dp) else None
        self._enc, self._calls = None, Counter()

    def _encode(self, q):
        if self._enc is None:
            from sentence_transformers import SentenceTransformer
            self._enc = SentenceTransformer(DENSE_MODEL)
        return self._enc.encode([DENSE_PREFIX + q], normalize_embeddings=True)[0]

    @staticmethod
    def _top(idx, scores, depth=DEPTH):
        o = np.lexsort((idx, -scores))[:depth]                    # score descending, ties by document index
        return idx[o]

    def rank(self, query):
        n, c = len(self.docs), self.cfg
        s = np.zeros(n, np.float32)
        for w in set(tokenize(query)):
            j = self.terms.get(w)
            if j is not None:
                s[self.pdoc[self.ptr[j]:self.ptr[j + 1]]] += self.pw[self.ptr[j]:self.ptr[j + 1]]
        ib = np.flatnonzero(s > 0)
        rb = {int(i): r for r, i in enumerate(self._top(ib, s[ib]), 1)}
        rd, wd, has_vec = {}, 0.0, set()
        if self.dense is not None:
            wd, rows = 1.0, self.dense["rows"]
            has_vec = set(rows.tolist())
            ds = np.round((self.dense["X"] @ self._encode(query)).astype(np.float64), 6)
            rd = {int(i): r for r, i in enumerate(self._top(rows, ds), 1)}
        cand = np.array(sorted(set(rb) | set(rd)), np.int64)
        if not len(cand): return []
        rel = np.zeros(len(cand))
        for j, i in enumerate(cand.tolist()):
            if i in rb: rel[j] += 1.0 / (RRF_K + rb[i])
            if i in rd: rel[j] += wd / (RRF_K + rd[i])
            elif wd and i not in has_vec and i in rb: rel[j] += wd / (RRF_K + rb[i])
        rel /= (1.0 + wd) / (RRF_K + 1)
        rel = np.where([self.docs[i]["kind"] == "post" for i in cand], rel * c["post_weight"], rel)
        score = rel + c["w_pop"] * self.pop[cand]
        if c["tau"] > 0:
            key = " ".join(query.lower().split())
            n_before = self._calls[key]; self._calls[key] += 1
            score = score + c["tau"] * gumbel(c["rank_seed"], f"{key}|call{n_before}", cand)
        score = np.round(score, 12)
        ranked = cand[np.lexsort((cand, -score))].tolist()
        pin = [self.by_key[k] for k in query_ids(query) if k in self.by_key]
        return list(dict.fromkeys(pin)) + [i for i in ranked if i not in pin]

    def search(self, query):
        if not isinstance(query, str) or not query.strip(): raise ToolError("query must be a non-empty string")
        c, out, per_site, shown = self.cfg, [], Counter(), {}
        for i in self.rank(query):
            d = self.docs[i]
            capped = d["kind"] in c["site_cap_kinds"]
            if capped and per_site[d["source"]] >= c["site_cap"]: continue
            k = dup_key(d["title"])
            if k is not None:
                srcs = shown.setdefault(k, [])
                if sum(s != d["source"] for s in srcs) >= c["dup_cap"]: continue
                srcs.append(d["source"])
            if capped: per_site[d["source"]] += 1
            out.append({"id": d["id"], "title": d["title"], "source": d["source"], "date": d["date"],
                        "snippet": snippet(d["abstract"], c["snippet_chars"])})
            if len(out) == c["k"]: break
        return out

    def read(self, id, page=1):
        i = self.by_id.get(id, self.by_url.get(id, -1)) if isinstance(id, str) else -1
        if i < 0 and isinstance(id, str):
            ks = query_ids(id)
            if len(ks) == 1: i = self.by_key.get(ks[0], -1)
        if i < 0: raise ToolError("not found")
        try: page = int(page if page is not None else 1)
        except (TypeError, ValueError): raise ToolError("page must be an integer")
        d, P = self.docs[i], self.cfg["page_chars"]
        n_pages = max(1, -(-len(d["text"]) // P))
        if not 1 <= page <= n_pages: raise ToolError(f"page out of range (document has {n_pages} pages)")
        line = ""
        if d["kind"] == "paper":
            line = ("Text: full text (" + {"arxiv_html": "arXiv HTML", "arxiv_pdf": "arXiv PDF"}.get(d["text_source"],
                    d["text_source"] or "") + ")\n") if d["text_source"] else "Text: abstract only (full text not in this corpus)\n"
        more = f" (read page={page + 1} for more)" if page < n_pages else ""
        return (f"Title: {d['title']}\nSource: {d['source']} | Date: {d['date']} | URL: {d['url']}\n" + line
                + f"Page {page} of {n_pages}{more}\n\n" + d["text"][(page - 1) * P: page * P])

    def call(self, name, args):
        """Tool result string, as our minimal loop sent it ({"error": ...} on a bad call)."""
        try:
            if name == "search": return json.dumps(self.search((args or {}).get("query")), ensure_ascii=False)
            if name == "read": return self.read((args or {}).get("id"), (args or {}).get("page", 1))
            raise ToolError(f"unknown tool: {name}")
        except ToolError as e:
            return json.dumps({"error": str(e)})


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("corpus"); b.add_argument("index"); b.add_argument("--dense", action="store_true")
    s = sub.add_parser("search"); s.add_argument("index"); s.add_argument("query")
    s.add_argument("--seed", type=int); s.add_argument("--tau", type=float, default=0.0)
    a = ap.parse_args()
    if a.cmd == "build":
        print(build(a.corpus, a.index, a.dense), "documents indexed", file=sys.stderr)
    else:
        print(json.dumps(SearchTool(a.index, tau=a.tau, rank_seed=a.seed).search(a.query), indent=1, ensure_ascii=False))
