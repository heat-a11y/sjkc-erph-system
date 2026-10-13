"""Resilient Telegram Bot API delivery.

The VPN route to Telegram intermittently resets connections mid-transfer, so
every request is retried with backoff. Both the AQI text message and the weekly
PDFs go through here.
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

BOUNDARY = "----SjkcCronBoundary"


def _post_with_retries(
    request,
    *,
    timeout: int,
    attempts: int,
    backoff: int,
    sleep,
    opener,
) -> dict:
    last: Exception | None = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            with opener(request, timeout=timeout) as resp:
                return json.loads(resp.read())
        except Exception as exc:  # noqa: BLE001 - network flakiness
            last = exc
            if attempt < attempts:
                sleep(backoff * attempt)
    raise RuntimeError(f"telegram send failed after {attempts} attempt(s): {last}")


def send_text(
    token: str,
    chat_id: str,
    thread_id: str | None,
    text: str,
    *,
    parse_mode: str | None = None,
    timeout: int = 30,
    attempts: int = 5,
    backoff: int = 3,
    sleep=time.sleep,
    opener=urllib.request.urlopen,
) -> dict:
    payload: dict = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if thread_id:
        payload["message_thread_id"] = int(thread_id)
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST")
    return _post_with_retries(
        req, timeout=timeout, attempts=attempts, backoff=backoff,
        sleep=sleep, opener=opener)


def _send_file(
    token: str,
    method: str,
    field: str,
    content_type: str,
    chat_id: str,
    thread_id: str | None,
    file_path: str | Path,
    caption: str,
    *,
    timeout: int,
    attempts: int,
    backoff: int,
    sleep,
    opener,
) -> dict:
    path = Path(file_path)
    file_bytes = path.read_bytes()
    thread_field = ""
    if thread_id:
        thread_field = (
            f"--{BOUNDARY}\r\n"
            f'Content-Disposition: form-data; name="message_thread_id"\r\n\r\n'
            f"{thread_id}\r\n"
        )
    body = (
        f"--{BOUNDARY}\r\n"
        f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'
        + thread_field +
        f"--{BOUNDARY}\r\n"
        f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'
        f"--{BOUNDARY}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{path.name}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode() + file_bytes + f"\r\n--{BOUNDARY}--".encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={BOUNDARY}"},
        method="POST")
    return _post_with_retries(
        req, timeout=timeout, attempts=attempts, backoff=backoff,
        sleep=sleep, opener=opener)


def send_document(
    token: str,
    chat_id: str,
    thread_id: str | None,
    file_path: str | Path,
    caption: str = "",
    *,
    timeout: int = 120,
    attempts: int = 5,
    backoff: int = 5,
    sleep=time.sleep,
    opener=urllib.request.urlopen,
) -> dict:
    return _send_file(
        token, "sendDocument", "document", "application/pdf",
        chat_id, thread_id, file_path, caption,
        timeout=timeout, attempts=attempts, backoff=backoff,
        sleep=sleep, opener=opener)


def send_video(
    token: str,
    chat_id: str,
    thread_id: str | None,
    file_path: str | Path,
    caption: str = "",
    *,
    timeout: int = 300,
    attempts: int = 5,
    backoff: int = 5,
    sleep=time.sleep,
    opener=urllib.request.urlopen,
) -> dict:
    return _send_file(
        token, "sendVideo", "video", "video/mp4",
        chat_id, thread_id, file_path, caption,
        timeout=timeout, attempts=attempts, backoff=backoff,
        sleep=sleep, opener=opener)


def send_poll(
    token: str,
    chat_id: str,
    thread_id: str | None,
    question: str,
    options: list[str],
    correct_option_id: int,
    *,
    anonymous: bool = True,
    timeout: int = 30,
    attempts: int = 5,
    backoff: int = 3,
    sleep=time.sleep,
    opener=urllib.request.urlopen,
) -> dict:
    payload: dict = {
        "chat_id": chat_id,
        "question": question[:300],
        "options": json.dumps([o[:100] for o in options]),
        "type": "quiz",
        "correct_option_id": int(correct_option_id),
        "is_anonymous": bool(anonymous),
        "allows_multiple_answers": False,
    }
    if thread_id:
        payload["message_thread_id"] = int(thread_id)
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendPoll",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST")
    return _post_with_retries(
        req, timeout=timeout, attempts=attempts, backoff=backoff,
        sleep=sleep, opener=opener)