"""Execute one job: build argv + delivery env, then run the script."""

from __future__ import annotations

import json
import os
import subprocess

from . import network
from .model import Job


def build_command(job: Job, *, project_dir: str, python_exe: str) -> list[str]:
    script = os.path.join(project_dir, job.script)
    return [python_exe, script, *job.args]


def build_env(job: Job, base_env: dict[str, str], secret: str) -> dict[str, str]:
    env = dict(base_env)
    env["TELEGRAM_BOT_TOKEN"] = secret
    env["TG_BOT_TOKEN"] = secret
    env["TG_CHAT_ID"] = job.target.chat_id
    env["TG_THREAD_ID"] = job.target.thread_id or ""
    for year, topic in job.year_topics:
        env[f"TG_TOPIC_Y{year}"] = topic
    return env


def describe(
    job: Job, *, project_dir: str, python_exe: str, secret: str
) -> dict:
    """Dry-run description. Never includes the secret value."""
    return {
        "job": job.key,
        "name": job.name,
        "command": build_command(job, project_dir=project_dir, python_exe=python_exe),
        "workdir": project_dir,
        "target": job.target.display(),
        "needs_llm": job.needs_llm,
        "token_set": bool(secret),
    }


def _default_exec(cmd: list[str], env: dict[str, str], cwd: str) -> int:
    return subprocess.call(cmd, env=env, cwd=cwd)


def run_job(
    job: Job,
    *,
    project_dir: str,
    python_exe: str,
    secret: str,
    base_env: dict[str, str] | None = None,
    exec_fn=None,
    dry_run: bool = False,
    preflight=None,
) -> int:
    if dry_run:
        print(json.dumps(
            describe(job, project_dir=project_dir, python_exe=python_exe,
                     secret=secret),
            indent=2))
        return 0

    check = preflight if preflight is not None else network.ensure_vpn_best_effort
    check()

    env = build_env(job, base_env if base_env is not None else dict(os.environ),
                    secret)
    run = exec_fn or _default_exec
    return run(build_command(job, project_dir=project_dir, python_exe=python_exe),
               env, str(project_dir))
