"""Generate systemd *user* service + timer units from the job registry."""

from __future__ import annotations

from .model import Job


def unit_names(job: Job) -> tuple[str, str]:
    base = f"sjkc-cron-{job.key}"
    return f"{base}.service", f"{base}.timer"


def service_unit(
    job: Job, *, project_dir: str, python_exe: str, path_env: str
) -> str:
    return f"""\
[Unit]
Description=SJKC cron job: {job.name}
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory={project_dir}
Environment=PATH={path_env}
ExecStart={python_exe} {project_dir}/main.py --run {job.key}
# LLM jobs need minutes, far beyond the 90s oneshot default.
TimeoutStartSec=1800
Nice=10
"""


def timer_unit(job: Job) -> str:
    service, _ = unit_names(job)
    return f"""\
[Unit]
Description=Timer for SJKC cron job: {job.name}

[Timer]
OnCalendar={job.on_calendar}
Persistent=true
AccuracySec=1min
Unit={service}

[Install]
WantedBy=timers.target
"""
