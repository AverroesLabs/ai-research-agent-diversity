"""Rebuild a search corpus from the document ids and links we release (EXPERIMENTS.md, "Search tool").

We cannot release the texts of the 99,464 documents our agents searched. We release the list of all of them
(data/corpus_docs.jsonl: id, url, kind, year, layer, the title for papers and posts, and the popularity
percentile `pop` the ranking used) and the documents each
searching agent opened (the `opened` lists of data/reading_frontier_*.jsonl). This script turns them into a corpus
JSONL that search_tool.py can index:

    python3 corpus_from_ids.py --out corpus_stub.jsonl                 # all 99,464 ids, urls, kinds, titles; no text
    python3 corpus_from_ids.py --out corpus.jsonl --fetch-arxiv       # adds arXiv titles and abstracts (network)
    python3 corpus_from_ids.py --out opened.jsonl --opened-only       # only the documents released agents opened
    python3 search_tool.py build corpus.jsonl index/

Id forms: arxiv:<id> -> https://arxiv.org/abs/<id>; doi:<doi> -> https://doi.org/<doi>; lw:<postId> ->
https://www.lesswrong.com/posts/<postId>; web:..., conf:..., tracker:... and the rest keep the url given in
corpus_docs.jsonl. Blog and overview pages have no title in the release; the stub uses the id until you fetch the
page. Fetching arXiv abstracts for the about 50,000 arXiv papers takes about an hour at arXiv's requested pace.
Fetching full text and other sites' pages is up to you. Our corpus attached full text to most core arXiv papers and
served abstracts elsewhere, so a corpus of abstracts or titles ranks differently from ours; treat it as a close
starting point, not a replica.
"""
import argparse
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def url_of(doc_id):
    kind, _, rest = doc_id.partition(":")
    return {"arxiv": f"https://arxiv.org/abs/{rest}", "doi": f"https://doi.org/{rest}",
            "lw": f"https://www.lesswrong.com/posts/{rest}"}.get(kind)


def released_docs(opened_only=False):
    """{doc_id: record} from data/corpus_docs.jsonl and the opened lists of data/reading_*.jsonl."""
    docs = {}
    cd = DATA / "corpus_docs.jsonl"
    if cd.exists() and not opened_only:
        for l in open(cd):
            if l.strip():
                d = json.loads(l)
                docs[d["doc_id"]] = d
    opened = set()
    for f in sorted(DATA.glob("reading_*.jsonl")):
        for l in open(f):
            for o in json.loads(l).get("opened") or []:
                docs.setdefault(o["doc_id"], {**o})
                opened.add(o["doc_id"])
    if opened_only:
        full = {}
        if cd.exists():
            for l in open(cd):
                d = json.loads(l)
                if d["doc_id"] in opened:
                    full[d["doc_id"]] = d
        docs = {k: full.get(k, v) for k, v in docs.items()}
    return docs


def fetch_arxiv(ids, batch=50):
    """{arxiv id: (title, abstract, published date)} from the arXiv export API (needs network)."""
    out, ns = {}, {"a": "http://www.w3.org/2005/Atom"}
    for s in range(0, len(ids), batch):
        q = ",".join(ids[s:s + batch])
        with urllib.request.urlopen(f"http://export.arxiv.org/api/query?id_list={q}&max_results={batch}") as r:
            root = ET.fromstring(r.read())
        for e in root.findall("a:entry", ns):
            aid = re.sub(r"v\d+$", "", e.find("a:id", ns).text.rsplit("/abs/", 1)[-1])
            out[aid] = (" ".join(e.find("a:title", ns).text.split()), " ".join(e.find("a:summary", ns).text.split()),
                        e.find("a:published", ns).text[:10])
        time.sleep(3)                                             # arXiv asks for a pause between calls
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fetch-arxiv", action="store_true")
    ap.add_argument("--opened-only", action="store_true", help="only the documents released agents opened")
    a = ap.parse_args()
    docs = released_docs(a.opened_only)
    meta = fetch_arxiv([k[6:] for k in docs if k.startswith("arxiv:")]) if a.fetch_arxiv else {}
    with open(a.out, "w") as f:
        for k, d in sorted(docs.items()):
            title, abstract, date = meta.get(k[6:], (d.get("title"), None, None)) if k.startswith("arxiv:") \
                else (d.get("title"), None, None)
            f.write(json.dumps({"id": k, "kind": d.get("kind") or "paper", "title": title or k,
                                "date": date or f"{d.get('year') or 2026}-01-01", "url": d.get("url") or url_of(k),
                                "abstract": abstract, "text": None, "layer": d.get("layer") or "core",
                                "pop": d.get("pop")}, ensure_ascii=False) + "\n")
    print(f"{len(docs)} documents -> {a.out}")


if __name__ == "__main__":
    main()
