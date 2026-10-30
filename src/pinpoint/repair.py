"""repair: ask a model to fix the verified findings, re-check, repeat (<= `turns`).

The model sees facts from the installed package (what exists, what a call accepts, what the parent really
exposes), never documentation. The system prompt and the findings text are the ones used in the experiments
(harness/gc_pinpoint.py); tests/test_cli.py asserts they stay identical.
"""
import json
import os
import re
import urllib.error
import urllib.request

from .diff import Issue

FENCE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.S)

SYSTEM_PROMPT = """You are an expert programming assistant. Your task is to fix version-compatibility errors in a generated Python solution. You are provided with:
- A problem statement and starter code
- The exact Python and library versions that will run the code
- A previously generated solution
- Findings obtained by inspecting the INSTALLED library (not documentation): these are facts about what exists in that exact version

Fix every finding with the smallest change that keeps the solution's behaviour. Follow these rules:
1. Use only names, modules and arguments that the findings show exist in the installed version.
2. Correctly incorporate the starter code - do not remove or alter its structure.
3. Wrap your entire solution within a single Markdown code block.
4. Do not include any text outside the code block.
5. The code must run in a non-interactive environment.

Example output format:

```python
# [Your corrected code here]
```"""

USER_TEMPLATE = """<Problem>
{problem}
</Problem>

<Python Version>
{python_version}
</Python Version>

<Library>
{library}
</Library>

<Generated Solution>
{solution}
</Generated Solution>

<Findings from the installed library>
{findings}
</Findings from the installed library>"""

DEFAULT_TASK = "Fix the code so it runs on the installed library versions without changing what it does."


def code_of(answer: str) -> str:
    m = FENCE.search(answer)
    return m.group(1) if m else answer


def _members(x: Issue) -> str:
    if not x.siblings:
        return ""
    parent = x.path.rsplit(".", 1)[0]
    items = ", ".join(f"{m['name']}{m['signature'] or ''}" if m["kind"] in ("function", "class") else m["name"]
                      for m in x.siblings)
    return f" The installed `{parent}` provides: {items}."


def render_findings(issues: list[Issue]) -> str:
    lines = []
    for n, x in enumerate(issues, 1):
        if x.kind == "SIGNATURE":
            lines.append(f"{n}. line {x.line}: call to `{x.path}`: {x.detail}. The installed signature is `{x.path.rsplit('.', 1)[-1]}{x.signature}`.")
        elif x.kind in ("RENAMED", "MOVED"):
            where = "Names that do exist nearby" if x.kind == "RENAMED" else "It is defined in"
            lines.append(f"{n}. line {x.line}: `{x.path}` does not exist in the installed version ({x.detail}). {where}: " + ", ".join(f"`{s}`" for s in x.suggestions) + "." + _members(x))
        else:
            lines.append(f"{n}. line {x.line}: `{x.path}` does not exist in the installed version ({x.detail}); no similarly named symbol was found, so use a different approach." + _members(x))
    return "\n".join(lines)


def openai_complete(model: str, base_url: str | None = None, api_key: str | None = None):
    """Return complete(system, user) -> text for any OpenAI-compatible chat endpoint (stdlib only)."""
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("pinpoint repair needs an API key: set OPENAI_API_KEY (or pass --base-url for a compatible server).")
    base = (base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")

    def complete(system: str, user: str) -> str:
        body = json.dumps({"model": model, "temperature": 0, "messages": [
            {"role": "system", "content": system}, {"role": "user", "content": user}]}).encode()
        req = urllib.request.Request(base + "/chat/completions", data=body, headers={
            "Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": "pinpoint/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.load(r)["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            raise SystemExit(f"model API error {e.code}: {e.read().decode()[:300]}")
    return complete


def repair_code(code: str, find, complete, python_version: str, libraries: str, task: str = DEFAULT_TASK,
                turns: int = 3, log=lambda s: None) -> tuple[str, list[Issue]]:
    """find(code) -> issues; complete(system, user) -> text. Returns (final code, findings left)."""
    for turn in range(1, turns + 1):
        issues = find(code)
        log(f"turn {turn}: {len(issues)} verified finding(s)")
        if not issues:
            return code, []
        user = USER_TEMPLATE.format(problem=task, python_version=python_version, library=libraries,
                                    solution=code, findings=render_findings(issues))
        new = code_of(complete(SYSTEM_PROMPT, user)).strip("\n") + "\n"
        if new == code:
            return code, issues
        code = new
    return code, find(code)
