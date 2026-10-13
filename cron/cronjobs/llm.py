"""LLM adapter: generate JSON content via headless opencode.

Replaces Hermes' ``hermes_tools.model_tools``. The project ships a tool-less
opencode agent (``content-gen``) so the model only returns text.
"""

from __future__ import annotations

import json
import subprocess
import time


def extract_json(text: str) -> str:
    """Return the JSON object contained in ``text``.

    Tolerates ```json fences and surrounding prose. Raises ``ValueError`` when
    no valid JSON object is present.
    """
    s = text.strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        s = "\n".join(lines).strip()

    try:
        json.loads(s)
        return s
    except json.JSONDecodeError:
        pass

    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end > start:
        candidate = s[start:end + 1]
        json.loads(candidate)  # validate; raises JSONDecodeError if bad
        return candidate

    raise ValueError("no JSON object found in model output")


def parse_opencode_events(stdout: str) -> str:
    """Concatenate assistant ``text`` parts from opencode's --format json stream."""
    parts: list[str] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "text":
            continue
        part = event.get("part") or {}
        if part.get("type") == "text" and isinstance(part.get("text"), str):
            parts.append(part["text"])
    return "".join(parts)


def build_argv(
    prompt: str,
    *,
    project_dir: str,
    agent: str = "content-gen",
    model: str | None = None,
) -> list[str]:
    argv = [
        "opencode", "run",
        "--dir", str(project_dir),
        "--agent", agent,
        "--format", "json",
    ]
    if model:
        argv += ["--model", model]
    argv.append(prompt)
    return argv


def _default_runner(argv: list[str], timeout: int, cwd: str) -> str:
    proc = subprocess.run(
        argv, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(
            f"opencode failed rc={proc.returncode}: {detail[-800:]}")
    return proc.stdout


def _run_with_retries(
    argv: list[str], timeout: int, cwd: str, retries: int, runner,
) -> str:
    last: Exception | None = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            return runner(argv, timeout, cwd)
        except Exception as exc:  # noqa: BLE001 - transient provider errors
            last = exc
            if attempt < retries:
                time.sleep(min(30, 5 * attempt))
    raise RuntimeError(f"opencode failed after {retries} attempt(s): {last}")


def generate(
    system_prompt: str,
    user_prompt: str,
    *,
    project_dir: str,
    runner=None,
    timeout: int = 900,
    agent: str = "content-gen",
    model: str | None = None,
    retries: int = 3,
) -> str:
    """Ask opencode for the weekly content and return the JSON string.

    ``retries`` guards against transient provider throttling (the zen free tier
    intermittently answers 403 FreeTierError).
    """
    run = runner or _default_runner
    prompt = system_prompt.rstrip() + "\n\n" + user_prompt.strip()
    argv = build_argv(prompt, project_dir=project_dir, agent=agent, model=model)
    stdout = _run_with_retries(
        argv, timeout, str(project_dir), retries, run)
    return extract_json(parse_opencode_events(stdout))
