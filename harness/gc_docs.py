"""Docs corpus for the A2 (docs-RAG) arm: fetch the per-problem `docs` URLs, chunk, embed, retrieve.

stdlib only. Pages are cached under data/cache/docs/, embeddings in the generations SQLite file.
Dead links fall back to the Wayback Machine snapshot listed in data/cache/dead_docs.json; problems
whose pages cannot be recovered get no documentation (reported separately, never patched by hand).

ASSUMPTIONS (the paper gives only: text-embedding-3-large, top-k in {1, 3}): chunk = 1500 chars with
200 overlap, query = the problem statement, retrieval restricted to that problem's own doc pages.
"""
import hashlib
import json
import math
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gc_runner as g  # noqa: E402

DOCS = g.ROOT / "data/cache/docs"
DEAD = g.ROOT / "data/cache/dead_docs.json"
EMB_MODEL = "text-embedding-3-large"
CHUNK, OVERLAP = 1500, 200
SKIP = {"script", "style", "nav", "header", "footer", "aside", "noscript", "svg"}
BLOCK = {"p", "div", "br", "li", "tr", "pre", "dt", "dd", "h1", "h2", "h3", "h4", "h5", "h6", "table", "section"}


_WAYBACK = threading.Lock()


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.depth = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self.depth += 1
        elif tag in BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in SKIP and self.depth:
            self.depth -= 1
        elif tag in BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.depth:
            self.out.append(data)


def html_to_text(html: str) -> str:
    p = _Text()
    p.feed(html)
    text = re.sub(r"[ \t\r\f\v]+", " ", "".join(p.out))
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def _fetch(url: str, tries: int = 6) -> str:
    """GET with backoff (Wayback rate-limits hard); follows meta-refresh stubs such as moved sympy/matplotlib pages."""
    for hops in range(3):
        for attempt in range(tries):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                html = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", errors="replace")
                break
            except urllib.error.HTTPError as e:
                if e.code not in (429, 500, 502, 503, 504) or attempt == tries - 1:
                    raise
                time.sleep(5 * 2 ** attempt)
            except (urllib.error.URLError, ConnectionError, TimeoutError):
                if attempt == tries - 1:
                    raise
                time.sleep(5 * 2 ** attempt)
        m = re.search(r'http-equiv="refresh"[^>]*url=([^"\s]+)', html, re.I) if len(html) < 2000 else None
        if not m:
            return html
        url = urllib.parse.urljoin(url, m.group(1))
    return html


def page_path(url: str) -> Path:
    return DOCS / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".json")


def fetch_page(url: str, wayback: dict) -> dict:
    path = page_path(url)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    rec = {"url": url, "source": None, "text": ""}
    for source, target in (("live", url), ("wayback", wayback.get(url))):
        if not target:
            continue
        if source == "wayback":  # id_ = the original page without Wayback's rewriting/toolbar
            target = re.sub(r"/web/(\d+)/", r"/web/\1id_/", target)
        try:
            if source == "wayback":
                with _WAYBACK:  # one request at a time, spaced out
                    time.sleep(2)
                    html = _fetch(target)
            else:
                html = _fetch(target)
            rec.update(source=source, text=html_to_text(html))
            if rec["text"]:
                break
        except Exception as e:  # noqa: BLE001 - dead links are expected
            rec["error"] = repr(e)[:80]
    DOCS.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec), encoding="utf-8")
    return rec


def chunks(text: str) -> list[str]:
    step = CHUNK - OVERLAP
    return [text[i:i + CHUNK] for i in range(0, max(len(text), 1), step) if text[i:i + CHUNK].strip()]


def build_corpus(workers: int = 8) -> dict[str, dict]:
    wayback = json.loads(DEAD.read_text())["wayback"] if DEAD.exists() else {}
    urls = sorted({u for r in g.load_dataset() for u in r["docs"]})
    with ThreadPoolExecutor(workers) as ex:
        return {rec["url"]: rec for rec in ex.map(lambda u: fetch_page(u, wayback), urls)}


def _emb_db():
    db = g.open_cache()
    db.execute("CREATE TABLE IF NOT EXISTS emb (key TEXT PRIMARY KEY, vec TEXT)")
    return db


def _ekey(text: str) -> str:
    return hashlib.sha256((EMB_MODEL + text).encode()).hexdigest()


def embed(texts: list[str], key: str, base: str, batch: int = 64, workers: int = 4) -> dict[str, list[float]]:
    """Embed texts (cached by content). Returns {ekey: vector}."""
    db = _emb_db()
    need = {}
    for t in texts:
        k = _ekey(t)
        if db.execute("SELECT 1 FROM emb WHERE key=?", (k,)).fetchone() is None:
            need[k] = t
    items = list(need.items())

    def work(part):
        body = {"model": EMB_MODEL, "input": [t for _, t in part]}
        out = g.call_api(base, key, body, path="/embeddings")
        return [(k, json.dumps(d["embedding"])) for (k, _), d in zip(part, out["data"])]

    parts = [items[i:i + batch] for i in range(0, len(items), batch)]
    with ThreadPoolExecutor(workers) as ex:
        for done, rows in enumerate(ex.map(work, parts), 1):
            db.executemany("INSERT OR REPLACE INTO emb VALUES (?,?)", rows)
            db.commit()
            print(f"  embedded batch {done}/{len(parts)}", flush=True)
    return {_ekey(t): json.loads(db.execute("SELECT vec FROM emb WHERE key=?", (_ekey(t),)).fetchone()[0])
            for t in texts}


def _cos(a, b):
    return sum(x * y for x, y in zip(a, b)) / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def retrieve(row: dict, corpus: dict, vecs: dict, qvec: list[float], k: int) -> list[str]:
    cand = [(c, vecs[_ekey(c)]) for u in row["docs"] for c in chunks(corpus[u]["text"])]
    cand.sort(key=lambda cv: -_cos(qvec, cv[1]))
    return [c for c, _ in cand[:k]]


if __name__ == "__main__":
    corpus = build_corpus()
    ok = sum(1 for r in corpus.values() if r["text"])
    src = {s: sum(1 for r in corpus.values() if r["source"] == s) for s in ("live", "wayback")}
    n_chars = sum(len(c) for r in corpus.values() for c in chunks(r["text"]))
    print(f"pages {len(corpus)}: with text {ok}, {src}; chunk chars {n_chars:,} (~{n_chars // 4:,} tokens)")
    print("empty:", [u for u, r in corpus.items() if not r["text"]])
