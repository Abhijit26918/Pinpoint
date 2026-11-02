"""PinPoint web demo. Local only (127.0.0.1), standard library only, reuses the real pinpoint package.

    .venv\\Scripts\\python demo\\web\\server.py          # then open http://127.0.0.1:8765

Everything on the page that says LIVE is executed when you click: the code of each arm is checked against the
installed `halyard` with pinpoint's own probe, and run against the task's visible and hidden tests in a subprocess.
The only recorded thing is the model's text: the answers come from the stored gpt-4.1-mini runs
(data/cache/psdk_answers_tasks_heldout_gpt-4.1-mini.json), so the demo never needs a network or an API key.
"""
import difflib
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SDK = ROOT / "experiments" / "private_sdk"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(SDK))
from pinpoint.check import check_source, format_issue  # noqa: E402
from pinpoint.repair import code_of, render_findings  # noqa: E402
from tasks_heldout import PRE, T  # noqa: E402

ANSWERS = json.loads((ROOT / "data/cache/psdk_answers_tasks_heldout_gpt-4.1-mini.json").read_text(encoding="utf8"))
STORED = json.loads((ROOT / "data/cache/psdk_results_tasks_heldout_gpt-4.1-mini.json").read_text(encoding="utf8"))
GC = json.loads((ROOT / "demo/gc_cases.json").read_text(encoding="utf8"))
ARMS = {"none": "P1 no help", "selfdebug": "P3 self-debug", "docs": "P2 written docs", "pinpoint": "P4 PinPoint (on P1)"}
FEATURED = [1, 13, 15, 18, 12]  # baselines fail, PinPoint passes; chosen from the stored results, not by running new ones
POOL = ThreadPoolExecutor(max_workers=6)


def run_code(code: str, timeout: int = 30) -> dict:
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, "-c", code], cwd=SDK, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return dict(ok=False, msg="TimeoutError: did not finish in 30 s", ms=int((time.time() - t0) * 1000))
    msg = (p.stderr.strip().splitlines() or [p.stdout.strip()])[-1] if p.returncode else "passed"
    return dict(ok=p.returncode == 0, msg=msg, ms=int((time.time() - t0) * 1000))


def issue_json(x) -> dict:
    return dict(line=x.line, kind=x.kind, path=x.path, text=format_issue(x), detail=x.detail,
                suggestions=x.suggestions, signature=x.signature)


def run_arm(task_id: int, arm: str) -> dict:
    """LIVE: pinpoint check + visible test + hidden test on one stored answer."""
    t = T[task_id]
    code = code_of(ANSWERS[ARMS[arm]][str(task_id)]).strip("\n")
    t0 = time.time()
    issues, _ = check_source(code, extra_paths=[SDK])
    check_ms = int((time.time() - t0) * 1000)
    vis = run_code(PRE + code + "\n" + t["visible"])
    hid = run_code(PRE + code + "\n" + t["hidden"])
    stored = STORED[ARMS[arm]][str(task_id)]
    return dict(arm=arm, code=code, findings=[issue_json(x) for x in sorted(issues, key=lambda x: x.line)],
                evidence=render_findings(sorted(issues, key=lambda x: x.line)), check_ms=check_ms, visible=vis, hidden=hid,
                matches_stored=[vis["ok"], hid["ok"]] == stored)


def api_tasks() -> list:
    out = []
    for t in T:
        out.append(dict(id=t["id"], stem=t["stem"], desc=t["desc"], starter=t["starter"], featured=t["id"] in FEATURED,
                        stored={a: STORED[n][str(t["id"])][1] for a, n in ARMS.items()}))
    return out


def api_diff(task_id: int) -> str:
    a = code_of(ANSWERS[ARMS["none"]][str(task_id)]).strip("\n").splitlines()
    b = code_of(ANSWERS[ARMS["pinpoint"]][str(task_id)]).strip("\n").splitlines()
    return "\n".join(l for l in difflib.unified_diff(a, b, "before", "after", lineterm="", n=2) if not l.startswith(("---", "+++")))


def api_scoreboard() -> dict:
    """LIVE: run every task x arm. Returns hidden-test pass counts out of 24."""
    jobs = [(t["id"], a) for t in T for a in ARMS]
    res = list(POOL.map(lambda j: (j, run_arm(*j)), jobs))
    counts = {a: 0 for a in ARMS}
    mismatch = 0
    per_task = {}
    for (tid, a), r in res:
        counts[a] += r["hidden"]["ok"]
        mismatch += not r["matches_stored"]
        per_task.setdefault(tid, {})[a] = r["hidden"]["ok"]
    return dict(counts=counts, total=len(T), mismatch=mismatch, per_task=per_task)


def api_gc() -> list:
    return [{k: c[k] for k in ("id", "library", "version", "python", "problem", "before", "after", "findings", "kinds",
                               "hidden_before", "hidden_after")} for c in GC]


def api_machine() -> dict:
    """LIVE: check the 'assistant' code in demo/drift_example.py against the packages installed on THIS machine."""
    code = (HERE.parent / "drift_example.py").read_text(encoding="utf8")
    t0 = time.time()
    issues, roots = check_source(code)
    vers = {}
    for r in ("packaging", "pytest"):
        try:
            vers[r] = __import__(r).__version__
        except Exception as e:  # noqa: BLE001
            vers[r] = f"not installed ({type(e).__name__})"
    return dict(code=code, findings=[issue_json(x) for x in sorted(issues, key=lambda x: x.line)], versions=vers,
                ms=int((time.time() - t0) * 1000))


class H(BaseHTTPRequestHandler):
    def _send(self, body, ctype="application/json", code=200):
        data = body if isinstance(body, bytes) else (json.dumps(body) if ctype == "application/json" else body).encode("utf8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        p = self.path.split("?")[0]
        try:
            if p in ("/", "/index.html"):
                return self._send((HERE / "index.html").read_text(encoding="utf8"), "text/html")
            if p == "/api/tasks":
                return self._send(api_tasks())
            if p == "/api/scoreboard":
                return self._send(api_scoreboard())
            if p == "/api/gc":
                return self._send(api_gc())
            if p == "/api/machine":
                return self._send(api_machine())
            if p.startswith("/api/run/"):
                _, _, _, tid, arm = p.split("/")
                return self._send(run_arm(int(tid), arm))
            if p.startswith("/api/diff/"):
                return self._send(api_diff(int(p.rsplit("/", 1)[1])))
            self._send({"error": "not found"}, code=404)
        except Exception as e:  # noqa: BLE001
            self._send({"error": f"{type(e).__name__}: {e}"}, code=500)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"PinPoint demo on http://127.0.0.1:{port}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
