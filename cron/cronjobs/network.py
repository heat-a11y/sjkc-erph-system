"""Network preflight.

Telegram *file uploads* are reset by the local ISP path, so every job needs the
VPN up before it can deliver a PDF. Text messages happen to survive without it,
but we do not depend on that.
"""

from __future__ import annotations

import subprocess
import time

PROTONVPN = "protonvpn"


def _run(argv: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return 127, ""
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def vpn_status(run=None) -> bool:
    """True when ProtonVPN reports a connected session."""
    call = run or _run
    rc, out = call([PROTONVPN, "status"], 30)
    if rc != 0:
        return False
    return "Status: Connected" in out


def ensure_vpn(run=None, wait_seconds: int = 30) -> bool:
    """Make sure the VPN is up, connecting it if needed.

    Returns True when connected. Raises ``RuntimeError`` when the CLI is
    missing or the connection cannot be established, so the job fails loudly
    instead of silently skipping delivery.
    """
    call = run or _run
    if vpn_status(call):
        return True

    rc, out = call([PROTONVPN, "connect"], 180)
    if rc != 0:
        raise RuntimeError(f"protonvpn connect failed rc={rc}: {out.strip()[-300:]}")

    deadline = time.monotonic() + max(0, wait_seconds)
    while True:
        if vpn_status(call):
            return True
        if time.monotonic() >= deadline:
            raise RuntimeError(
                "VPN did not come up within "
                f"{wait_seconds}s — Telegram uploads would be blocked")
        time.sleep(2)


def ensure_vpn_best_effort(run=None, wait_seconds: int = 30) -> bool:
    """Try to bring the VPN up but never fail the job.

    A healthy direct path plus the resilient Telegram client can still deliver
    when the free VPN tier is unavailable, so a VPN failure is logged and
    treated as non-fatal rather than aborting the run.
    """
    try:
        return ensure_vpn(run=run, wait_seconds=wait_seconds)
    except RuntimeError as exc:
        print(f"[network] VPN unavailable ({exc}); continuing without it")
        return False