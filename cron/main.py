#!/usr/bin/env python3
"""Hermes-free SJKC cron runner — CLI entry point.

    python3 main.py --list
    python3 main.py --run <key> [--dry-run]
    python3 main.py --install-timers [--enable]
    python3 main.py --uninstall-timers
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cronjobs import env as env_mod
from cronjobs import model as model_mod
from cronjobs import runner as runner_mod
from cronjobs import systemd as systemd_mod

PROJECT_DIR = str(ROOT)
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
ENV_FILE = ROOT / ".env"
UNIT_DIR = Path.home() / ".config" / "systemd" / "user"


def _python_exe() -> str:
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    return sys.executable


def _secret() -> str:
    return (
        os.environ.get("TELEGRAM_BOT_TOKEN")
        or env_mod.load_env(ENV_FILE).get("TELEGRAM_BOT_TOKEN", "")
    )


def _path_env() -> str:
    candidates = [
        str(Path.home() / ".local/share/mise/shims"),
        str(Path.home() / ".local/share/mise/installs/opencode/latest"),
        str(Path.home() / ".local/bin"),
    ]
    opencode = shutil.which("opencode")
    if opencode:
        candidates.append(str(Path(opencode).parent))
    candidates += ["/usr/local/bin", "/usr/bin", "/bin"]
    seen: set[str] = set()
    out: list[str] = []
    for p in candidates:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return ":".join(out)


def cmd_list() -> int:
    for job in model_mod.JOBS:
        llm = "LLM" if job.needs_llm else "script"
        print(f"  {job.key:<9} {job.on_calendar:<20} [{llm}]  {job.name}")
    return 0


def cmd_run(key: str, dry_run: bool) -> int:
    try:
        job = model_mod.get_job(key)
    except KeyError as exc:
        print(f"main: {exc}", file=sys.stderr)
        return 2
    return runner_mod.run_job(
        job,
        project_dir=PROJECT_DIR,
        python_exe=_python_exe(),
        secret=_secret(),
        dry_run=dry_run,
    )


def _write_units() -> list[Path]:
    UNIT_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for job in model_mod.JOBS:
        service, timer = systemd_mod.unit_names(job)
        svc_path = UNIT_DIR / service
        tmr_path = UNIT_DIR / timer
        svc_path.write_text(
            systemd_mod.service_unit(
                job, project_dir=PROJECT_DIR, python_exe=_python_exe(),
                path_env=_path_env()),
            encoding="utf-8")
        tmr_path.write_text(
            systemd_mod.timer_unit(job), encoding="utf-8")
        written += [svc_path, tmr_path]
    return written


def cmd_install(enable: bool) -> int:
    for path in _write_units():
        print(f"wrote {path}")
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    if enable:
        for job in model_mod.JOBS:
            _, timer = systemd_mod.unit_names(job)
            subprocess.run(
                ["systemctl", "--user", "enable", "--now", timer], check=False)
            print(f"enabled {timer}")
    return 0


def cmd_uninstall() -> int:
    for job in model_mod.JOBS:
        service, timer = systemd_mod.unit_names(job)
        subprocess.run(
            ["systemctl", "--user", "disable", "--now", timer], check=False)
        for name in (service, timer):
            path = UNIT_DIR / name
            if path.exists():
                path.unlink()
                print(f"removed {path}")
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hermes-free SJKC cron runner")
    parser.add_argument("--list", action="store_true", help="list jobs")
    parser.add_argument("--run", metavar="KEY", help="run one job now")
    parser.add_argument("--dry-run", action="store_true",
                        help="with --run: show argv/env, do nothing")
    parser.add_argument("--install-timers", action="store_true",
                        help="write systemd user units")
    parser.add_argument("--enable", action="store_true",
                        help="with --install-timers: enable + start them")
    parser.add_argument("--uninstall-timers", action="store_true",
                        help="disable and remove systemd user units")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list:
        return cmd_list()
    if args.run:
        return cmd_run(args.run, args.dry_run)
    if args.install_timers:
        return cmd_install(args.enable)
    if args.uninstall_timers:
        return cmd_uninstall()
    build_parser().print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
