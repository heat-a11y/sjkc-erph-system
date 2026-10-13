#!/usr/bin/env python3
"""Hermetic test suite for the Hermes-free SJKC cron runner.

No network, no LLM, no Telegram. Run with:  python3 tests/run_tests.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cronjobs import env as env_mod
from cronjobs import llm as llm_mod
from cronjobs import model as model_mod
from cronjobs import network as network_mod
from cronjobs import runner as runner_mod
from cronjobs import systemd as systemd_mod
from cronjobs import telegram as telegram_mod

_SCRIPT = ROOT / "cronjobs" / "scripts" / "sjkc_english.py"
_spec = importlib.util.spec_from_file_location("sjkc_english", _SCRIPT)
sjkc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sjkc)

FAILURES: list[str] = []


def check(name, fn):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - test harness
        FAILURES.append(f"{name}: {type(exc).__name__}: {exc}")
        print(f"  FAIL  {name}\n        {type(exc).__name__}: {exc}")
        if os.environ.get("TEST_TRACE"):
            import traceback
            traceback.print_exc()
    else:
        print(f"  ok    {name}")


def eq(actual, expected, msg=""):
    assert actual == expected, f"{msg} expected {expected!r} got {actual!r}"


# ── domain model ─────────────────────────────────────────────────────────────
def test_jobs():
    eq(len(model_mod.JOBS), 4)
    eq({j.key for j in model_mod.JOBS}, {"aqi", "homework", "story", "quiz"})
    eq(model_mod.get_job("homework").needs_llm, True)
    eq(model_mod.get_job("aqi").needs_llm, False)


def test_schedules():
    eq(model_mod.get_job("aqi").on_calendar, "*-*-* 06:00:00")
    eq(model_mod.get_job("homework").on_calendar, "Fri *-*-* 18:00:00")
    eq(model_mod.get_job("story").on_calendar, "Sat *-*-* 18:00:00")
    eq(model_mod.get_job("quiz").on_calendar, "Sun *-*-* 18:00:00")


def test_content_jobs_all_at_6pm():
    for key, day in (("homework", "Fri"), ("story", "Sat"), ("quiz", "Sun")):
        eq(model_mod.get_job(key).on_calendar, f"{day} *-*-* 18:00:00", key)


def test_targets():
    group = model_mod.PIN_MIN_GROUP
    aqi = model_mod.get_job("aqi")
    eq(aqi.target.chat_id, group, "aqi")
    eq(aqi.target.thread_id, "16", "aqi")
    for key in ("homework", "story", "quiz"):
        job = model_mod.get_job(key)
        eq(job.target.chat_id, group, key)
        eq(job.target.thread_id, None, f"{key} must pick a topic per year")


def test_year_topics():
    job = model_mod.get_job("homework")
    eq(job.topic_for_year(1), "2")
    eq(job.topic_for_year(2), "3")
    eq(job.topic_for_year(6), "7")
    eq(job.topic_for_year(7), None, "unknown year has no topic")
    eq(model_mod.get_job("aqi").year_topics, ())
    for key in ("homework", "story", "quiz"):
        eq(dict(model_mod.get_job(key).year_topics),
           {1: "2", 2: "3", 3: "4", 4: "5", 5: "6", 6: "7"}, key)


def test_no_group_target_without_topic():
    """Regression: class-scoped content must never hit the group main chat."""
    group = model_mod.PIN_MIN_GROUP
    for job in model_mod.JOBS:
        if job.target.chat_id != group:
            continue
        if job.year_topics:
            assert job.target.thread_id is None, (
                f"{job.key} uses per-year topics; no single thread allowed")
        else:
            assert job.target.thread_id, (
                f"{job.key} would post to the group main chat")


def test_delivery_kinds():
    eq(model_mod.get_job("homework").delivery, model_mod.DELIVERY_PDF)
    eq(model_mod.get_job("story").delivery, model_mod.DELIVERY_STORY_VIDEO)
    eq(model_mod.get_job("quiz").delivery, model_mod.DELIVERY_QUIZ_TEXT)


def test_target_parse():
    t = model_mod.Target.parse("-100123:99")
    eq((t.chat_id, t.thread_id), ("-100123", "99"))
    t2 = model_mod.Target.parse("109937961")
    eq((t2.chat_id, t2.thread_id), ("109937961", None))
    try:
        model_mod.Target.parse("")
    except ValueError:
        pass
    else:
        raise AssertionError("empty target should raise")


def test_unknown_job():
    try:
        model_mod.get_job("nope")
    except KeyError:
        pass
    else:
        raise AssertionError("unknown job should raise KeyError")


# ── env parsing ──────────────────────────────────────────────────────────────
def test_parse_env_text():
    text = (
        "# comment\n"
        "TELEGRAM_BOT_TOKEN=abc:123\n"
        "export TG_CHAT_ID='-100'\n"
        'QUOTED="hello world"\n'
        "EMPTY=\n"
        "not a pair\n"
    )
    d = env_mod.parse_env_text(text)
    eq(d["TELEGRAM_BOT_TOKEN"], "abc:123")
    eq(d["TG_CHAT_ID"], "-100")
    eq(d["QUOTED"], "hello world")
    eq(d["EMPTY"], "")
    assert "not a pair" not in d


def test_load_env_missing(tmp: Path):
    eq(env_mod.load_env(tmp / "nope.env"), {})


def test_load_env_roundtrip(tmp: Path):
    p = tmp / ".env"
    p.write_text("FOO=bar\n# c\n")
    eq(env_mod.load_env(p), {"FOO": "bar"})


# ── llm adapter ──────────────────────────────────────────────────────────────
def test_extract_json_plain():
    eq(llm_mod.extract_json('{"a": 1}'), '{"a": 1}')


def test_extract_json_fenced():
    eq(llm_mod.extract_json('```json\n{"a": 1}\n```'), '{"a": 1}')


def test_extract_json_prose():
    text = 'Sure! Here it is:\n{"a": {"b": 2}}\nHope that helps.'
    eq(llm_mod.extract_json(text), '{"a": {"b": 2}}')


def test_extract_json_rejects_garbage():
    try:
        llm_mod.extract_json("no json here")
    except ValueError:
        pass
    else:
        raise AssertionError("garbage should raise ValueError")


def test_parse_opencode_events():
    events = "\n".join([
        json.dumps({"type": "step_start"}),
        json.dumps({"type": "text", "part": {"type": "text", "text": "Hel"}}),
        json.dumps({"type": "text", "part": {"type": "text", "text": "lo"}}),
        json.dumps({"type": "step_finish"}),
        "not json at all",
    ])
    eq(llm_mod.parse_opencode_events(events), "Hello")


def test_build_argv():
    argv = llm_mod.build_argv("PROMPT", project_dir="/proj", agent="content-gen")
    eq(argv[0], "opencode")
    assert "run" in argv
    assert "--dir" in argv and "/proj" in argv
    assert "--agent" in argv and "content-gen" in argv
    assert "--format" in argv and "json" in argv
    eq(argv[-1], "PROMPT")


def test_generate_with_fake_runner():
    captured = {}

    def fake_runner(argv, timeout, cwd):
        captured["argv"] = argv
        captured["timeout"] = timeout
        captured["cwd"] = cwd
        return "\n".join([
            json.dumps({"type": "text", "part": {"type": "text",
                                                 "text": '```json\n{"ok": true}\n```'}}),
        ])

    out = llm_mod.generate(
        "SYS", "USER", project_dir="/proj", runner=fake_runner, timeout=42)
    eq(out, '{"ok": true}')
    assert captured["argv"][-1].startswith("SYS")
    assert "USER" in captured["argv"][-1]
    eq(captured["timeout"], 42)


def test_default_runner_includes_stdout_on_failure():
    calls = {"n": 0}

    class Proc:
        returncode = 1
        stdout = '{"type":"error","error":{"data":{"message":"FreeTierError"}}}'
        stderr = ""

    def fake_run(argv, capture_output, text, timeout, cwd):
        calls["n"] += 1
        return Proc()

    original = llm_mod.subprocess.run
    llm_mod.subprocess.run = fake_run
    try:
        llm_mod._default_runner(["opencode"], 5, ".")
    except RuntimeError as exc:
        msg = str(exc)
        assert "rc=1" in msg, msg
        assert "FreeTierError" in msg, f"stdout must be in the error: {msg}"
    else:
        raise AssertionError("rc!=0 should raise RuntimeError")
    finally:
        llm_mod.subprocess.run = original
    assert calls["n"] == 1, "retry=0 expected a single attempt"


def test_generate_retries_on_transient_error():
    attempts = {"n": 0}
    original = llm_mod.subprocess.run

    class Proc:
        stdout = ""
        stderr = ""

        def __init__(self, rc):
            self.returncode = rc

    ok_stdout = json.dumps({"type": "text", "part": {"type": "text",
                                                    "text": '{"a": 1}'}})

    class OkProc(Proc):
        stdout = ok_stdout

    def flaky_run(argv, capture_output, text, timeout, cwd):
        attempts["n"] += 1
        if attempts["n"] < 3:
            return Proc(1)
        return OkProc(0)

    llm_mod.subprocess.run = flaky_run
    original_sleep = llm_mod.time.sleep
    llm_mod.time.sleep = lambda *_: None
    try:
        out = llm_mod.generate("SYS", "USER", project_dir="/proj", retries=3)
    finally:
        llm_mod.subprocess.run = original
        llm_mod.time.sleep = original_sleep
    eq(attempts["n"], 3)
    eq(out, '{"a": 1}')


def test_generate_gives_up_after_retries():
    attempts = {"n": 0}
    original = llm_mod.subprocess.run

    class Proc:
        returncode = 1
        stdout = '{"type":"error"}'
        stderr = "nope"

    def always_fail(argv, capture_output, text, timeout, cwd):
        attempts["n"] += 1
        return Proc()

    llm_mod.subprocess.run = always_fail
    original_sleep = llm_mod.time.sleep
    llm_mod.time.sleep = lambda *_: None
    try:
        llm_mod.generate("SYS", "USER", project_dir="/proj", retries=2)
    except RuntimeError as exc:
        assert "after 2 attempt" in str(exc), str(exc)
    else:
        raise AssertionError("should raise after exhausting retries")
    finally:
        llm_mod.subprocess.run = original
        llm_mod.time.sleep = original_sleep
    eq(attempts["n"], 2)


# ── network / vpn preflight ───────────────────────────────────────────────────
def test_vpn_status_connected():
    out = "Status: Connected\nServer: RO-FREE#17 in Bucharest, Romania\n"
    eq(network_mod.vpn_status(lambda argv, timeout: (0, out)), True)


def test_vpn_status_disconnected():
    eq(network_mod.vpn_status(lambda argv, timeout: (0, "Status: Disconnected\n")), False)


def test_vpn_status_cli_missing():
    eq(network_mod.vpn_status(lambda argv, timeout: (127, "")), False)


def test_ensure_vpn_noop_when_connected():
    calls = []

    def fake(argv, timeout):
        calls.append(argv)
        return 0, "Status: Connected\n"

    eq(network_mod.ensure_vpn(run=fake), True)
    eq([c[0] for c in calls], ["protonvpn"])


def test_ensure_vpn_connects_when_down():
    calls = []
    state = {"connected": False}

    def fake(argv, timeout):
        calls.append(argv[:2])
        if argv[1] == "status":
            return 0, ("Status: Connected\n" if state["connected"]
                       else "Status: Disconnected\n")
        state["connected"] = True
        return 0, "Connected to RO-FREE#17"

    eq(network_mod.ensure_vpn(run=fake, wait_seconds=0), True)
    eq(calls[1], ["protonvpn", "connect"])


def test_ensure_vpn_raises_when_connect_fails():
    def fake(argv, timeout):
        return 0, "Status: Disconnected\n"

    try:
        network_mod.ensure_vpn(run=fake, wait_seconds=0)
    except RuntimeError as exc:
        assert "VPN" in str(exc), str(exc)
    else:
        raise AssertionError("should raise when VPN cannot connect")


def test_ensure_vpn_best_effort_never_raises():
    def fake(argv, timeout):
        return 0, "Status: Disconnected\n"

    eq(network_mod.ensure_vpn_best_effort(run=fake, wait_seconds=0), False)


def test_ensure_vpn_best_effort_true_when_connected():
    def fake(argv, timeout):
        return 0, "Status: Connected\n"

    eq(network_mod.ensure_vpn_best_effort(run=fake), True)


def test_run_job_calls_preflight():
    order = []

    def preflight():
        order.append("preflight")

    def fake_exec(cmd, env, cwd):
        order.append("exec")
        return 0

    runner_mod.run_job(
        model_mod.get_job("homework"), project_dir="/proj", python_exe="py",
        secret="tok", exec_fn=fake_exec, dry_run=False, preflight=preflight)
    eq(order, ["preflight", "exec"])


def test_run_job_dry_run_skips_preflight():
    order = []

    def preflight():
        order.append("preflight")

    runner_mod.run_job(
        model_mod.get_job("homework"), project_dir="/proj", python_exe="py",
        secret="tok", exec_fn=lambda *a: 0, dry_run=True, preflight=preflight)
    eq(order, [])


def test_run_job_continues_when_preflight_returns_false():
    order = []

    def preflight():
        order.append("preflight")
        return False

    def fake_exec(cmd, env, cwd):
        order.append("exec")
        return 0

    rc = runner_mod.run_job(
        model_mod.get_job("quiz"), project_dir="/proj", python_exe="py",
        secret="tok", exec_fn=fake_exec, dry_run=False, preflight=preflight)
    eq(rc, 0)
    eq(order, ["preflight", "exec"])


# ── telegram delivery ─────────────────────────────────────────────────────────
class FakeOpener:
    def __init__(self, failures=0, payload=None):
        self.failures = failures
        self.calls = []
        self.bodies = []
        self.payload = payload or {"ok": True, "result": {"message_id": 7}}

    def __call__(self, req, timeout=None):
        self.calls.append(timeout)
        self.bodies.append(req.data)
        if len(self.calls) <= self.failures:
            raise OSError("Connection reset by peer")
        return _FakeResponse(self.payload)


class _FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _pdf(tmp: Path) -> Path:
    p = tmp / "doc.pdf"
    p.write_bytes(b"%PDF-1.4 fake")
    return p


def test_send_document_includes_thread(tmp: Path):
    op = FakeOpener()
    out = telegram_mod.send_document(
        "tok", "-100", "16", _pdf(tmp), "caption here",
        opener=op, sleep=lambda *_: None)
    eq(out["ok"], True)
    body = op.bodies[0]
    assert b'name="message_thread_id"' in body, body[:400]
    assert b"16" in body
    assert b'name="document"; filename="doc.pdf"' in body
    assert b"caption here" in body


def test_send_document_omits_thread_when_absent(tmp: Path):
    op = FakeOpener()
    telegram_mod.send_document("tok", "-100", None, _pdf(tmp), "c",
                               opener=op, sleep=lambda *_: None)
    assert b"message_thread_id" not in op.bodies[0]


def test_send_document_retries_then_succeeds(tmp: Path):
    op = FakeOpener(failures=2)
    out = telegram_mod.send_document("tok", "-100", None, _pdf(tmp), "c",
                                     opener=op, attempts=4,
                                     sleep=lambda *_: None)
    eq(out["ok"], True)
    eq(len(op.calls), 3)


def test_send_document_gives_up(tmp: Path):
    op = FakeOpener(failures=99)
    try:
        telegram_mod.send_document("tok", "-100", None, _pdf(tmp), "c",
                                   opener=op, attempts=2,
                                   sleep=lambda *_: None)
    except RuntimeError as exc:
        assert "after 2 attempt" in str(exc), str(exc)
    else:
        raise AssertionError("should raise after exhausting attempts")
    eq(len(op.calls), 2)


def test_send_text_includes_thread():
    op = FakeOpener()
    out = telegram_mod.send_text("tok", "-100", "16", "hello",
                                 opener=op, sleep=lambda *_: None)
    eq(out["ok"], True)
    payload = json.loads(op.bodies[0].decode())
    eq(payload["chat_id"], "-100")
    eq(payload["message_thread_id"], 16)
    eq(payload["text"], "hello")


def test_send_text_no_thread():
    op = FakeOpener()
    telegram_mod.send_text("tok", "-100", None, "hi", opener=op,
                           sleep=lambda *_: None)
    eq(json.loads(op.bodies[0].decode()).get("message_thread_id"), None)


def test_send_poll_payload():
    op = FakeOpener()
    out = telegram_mod.send_poll(
        "tok", "-100", "16", "What is it?", ["cat", "dog", "bird"], 1,
        opener=op, sleep=lambda *_: None)
    eq(out["ok"], True)
    payload = json.loads(op.bodies[0].decode())
    eq(payload["chat_id"], "-100")
    eq(payload["message_thread_id"], 16)
    eq(payload["type"], "quiz")
    eq(payload["correct_option_id"], 1)
    eq(payload["allows_multiple_answers"], False)
    eq(payload["is_anonymous"], True)
    eq(json.loads(payload["options"]), ["cat", "dog", "bird"])


def test_send_poll_truncates_to_api_limits():
    op = FakeOpener()
    telegram_mod.send_poll(
        "tok", "-100", None, "Q" * 400, ["o" * 150, "b"], 0,
        opener=op, sleep=lambda *_: None)
    payload = json.loads(op.bodies[0].decode())
    eq(len(payload["question"]), 300)
    eq(len(json.loads(payload["options"])[0]), 100)
    eq("message_thread_id" in payload, False)


def test_send_video_multipart(tmp: Path):
    op = FakeOpener()
    vid = tmp / "story.mp4"
    vid.write_bytes(b"\x00\x00\x00\x18ftypmp42 fake video")
    out = telegram_mod.send_video("tok", "-100", "16", vid, "caption here",
                                  opener=op, sleep=lambda *_: None)
    eq(out["ok"], True)
    body = op.bodies[0]
    assert b'name="video"; filename="story.mp4"' in body, body[:400]
    assert b"video/mp4" in body
    assert b'name="message_thread_id"' in body
    assert b"caption here" in body


# ── content script (sjkc_english) ────────────────────────────────────────────
def test_normalize_questions_letter_answers():
    raw = [
        {"q": "Q1", "options": ["A. cat", "B. dog", "C. bird"], "answer": "B"},
        {"q": "Q2", "options": ["x", "y", "z"], "answer": "C"},
        {"q": "Q3", "options": ["p", "q", "r"], "answer": "A"},
    ]
    out = sjkc.normalize_questions(raw)
    eq(len(out), 3)
    eq(out[0]["options"], ["cat", "dog", "bird"], "labels stripped")
    eq(out[0]["correct"], 1)
    eq(out[1]["correct"], 2)
    eq(out[2]["correct"], 0)


def test_normalize_questions_wrong_count_raises():
    try:
        sjkc.normalize_questions([{"q": "x", "options": ["a", "b"], "answer": "A"}])
    except ValueError:
        pass
    else:
        raise AssertionError("fewer than 3 usable questions must raise")


def test_normalize_questions_truncates():
    raw = [{"q": "Q" * 400, "options": ["a" * 200, "b", "c"], "answer": "A"}] * 3
    out = sjkc.normalize_questions(raw)
    eq(len(out[0]["q"]), 300)
    eq(len(out[0]["options"][0]), 100)


def test_answer_index_variants():
    eq(sjkc._answer_index("A", 3), 0)
    eq(sjkc._answer_index("c", 3), 2)
    eq(sjkc._answer_index("B.", 3), 1)
    eq(sjkc._answer_index(2, 3), 2)
    eq(sjkc._answer_index("3", 3), 2)
    eq(sjkc._answer_index("D", 3), None)
    eq(sjkc._answer_index("", 3), None)
    eq(sjkc._answer_index(True, 3), None)


def test_strip_option_label():
    eq(sjkc._strip_option_label("A. cat"), "cat")
    eq(sjkc._strip_option_label("b) dog"), "dog")
    eq(sjkc._strip_option_label("cat"), "cat")


def test_build_story_video_command():
    cmd = sjkc.build_story_video_command(Path("/w/i.txt"), Path("/w/a.txt"),
                                         Path("/w/c.srt"), Path("/o.mp4"))
    eq(cmd[0], "ffmpeg")
    assert "libx264" in cmd and "aac" in cmd, cmd
    assert "concat" in cmd and "subtitles=" in " ".join(cmd), cmd
    eq(cmd[-1], "/o.mp4")


def test_clean_html():
    eq(sjkc._clean_html('<a href="x">Jane &amp; Bob</a>'), "Jane & Bob")
    eq(sjkc._clean_html(None), "")
    eq(sjkc._clean_html("  many   spaces  "), "many spaces")


def test_words_to_cues():
    words = [{"text": w, "start": i * 0.5, "end": i * 0.5 + 0.4}
             for i, w in enumerate("one two three four five".split())]
    cues = sjkc._words_to_cues(words, 10.0, max_chars=12, hold=0.3)
    assert len(cues) >= 2, cues
    eq(cues[0]["start"], 10.0)
    assert all(c["end"] > c["start"] for c in cues), cues
    assert all(a["end"] <= b["start"] for a, b in zip(cues, cues[1:])), cues
    eq(" ".join(c["text"] for c in cues), "one two three four five")


def test_build_srt():
    srt = sjkc.build_srt([{"start": 1.5, "end": 3.0, "text": "Hello there"},
                          {"start": 3661.25, "end": 3662.0, "text": "Bye"}])
    assert "00:00:01,500 --> 00:00:03,000" in srt, srt
    assert "01:01:01,250 --> 01:01:02,000" in srt, srt
    assert "Hello there" in srt and "Bye" in srt


def test_pick_commons_image():
    data = {"query": {"pages": {
        "1": {"title": "File:Doc.pdf",
              "imageinfo": [{"mime": "application/pdf", "url": "u"}]},
        "2": {"title": "File:A Duck.jpg",
              "imageinfo": [{"mime": "image/jpeg", "thumburl": "https://t/x.jpg",
                             "extmetadata": {
                                 "Artist": {"value": "<a>Jane</a>"},
                                 "LicenseShortName": {"value": "CC BY-SA 4.0"}}}]},
    }}}
    pick = sjkc._pick_commons_image(data)
    eq(pick["url"], "https://t/x.jpg")
    eq(pick["artist"], "Jane")
    eq(pick["license"], "CC BY-SA 4.0")
    eq(sjkc._pick_commons_image({"query": {"pages": {}}}), None)


def test_normalize_scenes():
    scenes = sjkc.normalize_scenes(
        [{"text": "A.", "keywords": ["x", "y", "z", "w", "v"]},
         {"story": "B."}, "junk"], "")
    eq([s["text"] for s in scenes], ["A.", "B."])
    eq(scenes[0]["keywords"], ["x", "y", "z", "w"])
    eq(sjkc.normalize_scenes(None, "Whole story."),
       [{"text": "Whole story.", "keywords": []}])
    try:
        sjkc.normalize_scenes([], "")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for empty scenes")


def test_make_fallback_card(tmp: Path):
    from PIL import Image
    out = tmp / "card.png"
    sjkc.make_fallback_card("A scene here", out, year=4)
    assert out.stat().st_size > 0
    eq(Image.open(out).size, (1280, 720))


def test_cover_crop():
    from PIL import Image
    out = sjkc._cover_crop(Image.new("RGB", (400, 200), (10, 20, 30)),
                           (1280, 720))
    eq(out.size, (1280, 720))


def test_fetch_commons_image_with_fake_get(tmp: Path):
    import io
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (1600, 900), (200, 100, 50)).save(buf, "JPEG")
    jpeg = buf.getvalue()
    payload = {"query": {"pages": {"1": {
        "title": "File:Duck.jpg",
        "imageinfo": [{"mime": "image/jpeg", "thumburl": "https://t/d.jpg",
                       "extmetadata": {"Artist": {"value": "Jane"},
                                       "LicenseShortName": {"value": "CC0"}}}]}}}}

    def fake_get(url, timeout=20):
        return json.dumps(payload).encode() if "api.php" in url else jpeg

    out = tmp / "scene.png"
    got = sjkc.fetch_commons_image(["duck"], out, get=fake_get)
    eq(got["license"], "CC0")
    eq(Image.open(out).size, (1280, 720))
    eq(sjkc.fetch_commons_image([], tmp / "x.png", get=fake_get), None)


def test_story_prompt_has_scenes():
    sysp = sjkc._story_system_fmt([sjkc.THEMES[0]])
    assert '"scenes"' in sysp and "SCENE RULES" in sysp


def test_build_story_video_with_fakes(tmp: Path):
    calls = {}

    def tts(text, out):
        Path(out).write_bytes(b"AUDIO")
        calls.setdefault("tts", []).append(text)
        return [{"text": "Once", "start": 0.0, "end": 0.4},
                {"text": "upon", "start": 0.4, "end": 0.8}]

    def fetch(keywords, out, **k):
        Path(out).write_bytes(b"PNG")
        calls.setdefault("imgs", []).append(tuple(keywords))
        return {"title": "File:X.jpg", "artist": "A", "license": "CC0"}

    def run(cmd):
        calls["cmd"] = cmd
        Path(cmd[-1]).write_bytes(b"MP4")

    scenes = [{"text": "Once upon a time.", "keywords": ["beach", "sun"]},
              {"text": "It was a good day.", "keywords": []}]
    out = sjkc.build_story_video(scenes, "Title", 3, 4, "Food", tmp / "s.mp4",
                                 tts=tts, fetch_image=fetch, run=run)
    eq(Path(out).read_bytes(), b"MP4")
    eq(calls["tts"], ["Once upon a time.", "It was a good day."])
    eq(calls["imgs"], [("beach", "sun"), ()])
    cmd = calls["cmd"]
    assert "libx264" in cmd and "aac" in cmd, cmd
    assert any("subtitles=" in part for part in cmd), cmd
    work = (tmp / "s.mp4").parent / ".s"
    srt = (work / "captions.srt").read_text()
    assert "-->" in srt and "Once upon" in srt, srt
    images_txt = (work / "images.txt").read_text()
    assert "duration" in images_txt and "scene1.png" in images_txt, images_txt
    assert (work / "audio.txt").read_text().count("file '") == 2


def test_build_story_video_falls_back_to_card(tmp: Path):
    def tts(text, out):
        Path(out).write_bytes(b"AUDIO")
        return [{"text": "Hi", "start": 0.0, "end": 0.3}]

    def run(cmd):
        Path(cmd[-1]).write_bytes(b"MP4")

    cards = []

    def card(text, out, *, year=None):
        cards.append((text, year))
        Path(out).write_bytes(b"PNG")

    scenes = [{"text": "A lonely scene.", "keywords": ["zzz"]}]
    sjkc.build_story_video(scenes, "T", 2, 1, "Theme", tmp / "f.mp4",
                           tts=tts, fetch_image=lambda k, o, **kw: None,
                           make_card=card, run=run)
    eq(cards, [("A lonely scene.", 2)])


def _valid_questions():
    return [
        {"q": "Q1", "options": ["a", "b", "c"], "answer": "A"},
        {"q": "Q2", "options": ["a", "b", "c"], "answer": "B"},
        {"q": "Q3", "options": ["a", "b", "c"], "answer": "C"},
    ]


def test_run_story_degrades_to_text_when_video_fails():
    names = ("build_story_video", "telegram_send_video", "telegram_send_text_to",
             "telegram_send_poll", "TG_CHAT_ID")
    orig = {n: getattr(sjkc, n) for n in names}
    texts, polls = [], []

    def boom(*a, **k):
        raise RuntimeError("no tts")

    try:
        sjkc.TG_CHAT_ID = "109937961"          # direct chat: topics optional
        sjkc.build_story_video = boom
        sjkc.telegram_send_video = lambda *a, **k: {"ok": True}
        sjkc.telegram_send_text_to = (
            lambda text, topic="": (texts.append(text), {"ok": True})[1])
        sjkc.telegram_send_poll = (
            lambda q, o, c, topic="": (polls.append((q, o, c)), {"ok": True})[1])
        content = {"year3": {"title": "T", "story": "Once",
                             "questions": _valid_questions()}}
        sent, failed = sjkc.run_story(content, 4, "Theme", [3])
        eq(sent, [3])
        eq(len(texts), 1, "story text fallback sent")
        eq(len(polls), 3, "3 polls still delivered")
    finally:
        for n, v in orig.items():
            setattr(sjkc, n, v)


def test_run_quiz_sends_reading_text_then_polls():
    names = ("telegram_send_text_to", "telegram_send_poll", "TG_CHAT_ID")
    orig = {n: getattr(sjkc, n) for n in names}
    texts, polls = [], []
    try:
        sjkc.TG_CHAT_ID = "109937961"
        sjkc.telegram_send_text_to = (
            lambda text, topic="": (texts.append(text), {"ok": True})[1])
        sjkc.telegram_send_poll = (
            lambda q, o, c, topic="": (polls.append((q, o, c)), {"ok": True})[1])
        content = {"year2": {"reading": "A cat sat on a mat.",
                             "questions": _valid_questions()}}
        sent, failed = sjkc.run_quiz(content, 4, "Theme", [2])
        eq(sent, [2])
        eq(len(texts), 1)
        assert "A cat sat on a mat." in texts[0]
        eq(len(polls), 3)
    finally:
        for n, v in orig.items():
            setattr(sjkc, n, v)


def test_run_quiz_skips_year_without_reading():
    names = ("telegram_send_text_to", "telegram_send_poll", "TG_CHAT_ID")
    orig = {n: getattr(sjkc, n) for n in names}
    try:
        sjkc.TG_CHAT_ID = "109937961"
        sjkc.telegram_send_text_to = lambda *a, **k: {"ok": True}
        sjkc.telegram_send_poll = lambda *a, **k: {"ok": True}
        content = {"year2": {"questions": _valid_questions()}}
        sent, failed = sjkc.run_quiz(content, 4, "Theme", [2])
        eq(sent, [])
        eq(failed, [2])
    finally:
        for n, v in orig.items():
            setattr(sjkc, n, v)


def test_script_poll_defaults_non_anonymous():
    names = ("TG_BOT_TOKEN", "TG_CHAT_ID", "TG_POLL_ANONYMOUS")
    orig = {n: getattr(sjkc, n) for n in names}
    captured = {}
    orig_send = telegram_mod.send_poll

    def fake(token, chat, thread, q, opts, correct, *, anonymous=True, **k):
        captured["anonymous"] = anonymous
        captured["correct"] = correct
        captured["thread"] = thread
        return {"ok": True}

    try:
        sjkc.TG_BOT_TOKEN = "tok"
        sjkc.TG_CHAT_ID = "-100"
        sjkc.TG_POLL_ANONYMOUS = False
        telegram_mod.send_poll = fake
        sjkc.telegram_send_poll("Q", ["a", "b", "c"], 1, "16")
        eq(captured["anonymous"], False)
        eq(captured["correct"], 1)
        eq(captured["thread"], "16")
    finally:
        telegram_mod.send_poll = orig_send
        for n, v in orig.items():
            setattr(sjkc, n, v)


def test_run_homework_skips_year_without_topic():
    """Regression: no topic in a group => skip, never the group main chat."""
    names = ("TG_CHAT_ID", "TG_TOPIC_BY_YEAR", "build_homework_pdf",
             "telegram_send_document", "OUTPUT_DIR")
    orig = {n: getattr(sjkc, n) for n in names}
    sends = []
    try:
        sjkc.TG_CHAT_ID = "-1002575685985"        # a group
        sjkc.TG_TOPIC_BY_YEAR = {y: "" for y in range(1, 7)}
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            sjkc.OUTPUT_DIR = Path(td)
            sjkc.build_homework_pdf = (
                lambda data, week, path, years=None: Path(path).write_bytes(b"%PDF"))
            sjkc.telegram_send_document = (
                lambda path, caption="", topic="": sends.append(topic) or {"ok": True})
            content = {"year3": {"vocab_match": []}}
            sent, failed = sjkc.run_homework(content, 4, "Theme", [3])
        eq(sent, [])
        eq(failed, [3])
        eq(sends, [], "must NOT send class content to the group main chat")
    finally:
        for n, v in orig.items():
            setattr(sjkc, n, v)


# ── runner ───────────────────────────────────────────────────────────────────
def test_build_command():
    job = model_mod.get_job("homework")
    cmd = runner_mod.build_command(job, project_dir="/proj", python_exe="/venv/bin/python")
    eq(cmd[0], "/venv/bin/python")
    eq(cmd[1], "/proj/cronjobs/scripts/sjkc_english.py")
    eq(cmd[2:], ["--task", "homework"])


def test_build_env():
    job = model_mod.get_job("homework")
    base = {"PATH": "/bin", "HOME": "/home/x"}
    out = runner_mod.build_env(job, base, secret="tok:123")
    eq(out["TELEGRAM_BOT_TOKEN"], "tok:123")
    eq(out["TG_BOT_TOKEN"], "tok:123")
    eq(out["TG_CHAT_ID"], model_mod.PIN_MIN_GROUP)
    eq(out["TG_THREAD_ID"], "")
    eq(out["TG_TOPIC_Y1"], "2")
    eq(out["TG_TOPIC_Y6"], "7")
    eq(out["PATH"], "/bin")
    assert "TELEGRAM_BOT_TOKEN" not in base, "must not mutate base env"


def test_build_env_aqi_has_thread_no_year_topics():
    job = model_mod.get_job("aqi")
    out = runner_mod.build_env(job, {}, secret="tok")
    eq(out["TG_CHAT_ID"], model_mod.PIN_MIN_GROUP)
    eq(out["TG_THREAD_ID"], "16")
    assert "TG_TOPIC_Y1" not in out, "aqi is not per-year"


def test_build_env_no_thread():
    job = model_mod.Job(
        key="dm", name="dm", script="s.py", on_calendar="*-*-* 00:00:00",
        target=model_mod.Target.parse("109937961"))
    out = runner_mod.build_env(job, {}, secret="tok")
    eq(out["TG_CHAT_ID"], "109937961")
    assert out["TG_THREAD_ID"] == "", "unthreaded target must clear TG_THREAD_ID"
    assert "TG_TOPIC_Y1" not in out


def test_describe_masks_secret():
    job = model_mod.get_job("quiz")
    d = runner_mod.describe(job, project_dir="/proj", python_exe="py", secret="supersecret")
    blob = json.dumps(d)
    assert "supersecret" not in blob, "dry-run must not leak the token"
    eq(d["job"], "quiz")
    eq(d["target"], model_mod.PIN_MIN_GROUP)
    eq(d["token_set"], True)


def test_run_job_dry_run_does_not_execute():
    called = {"n": 0}

    def fake_exec(cmd, env, cwd):
        called["n"] += 1
        return 0

    rc = runner_mod.run_job(
        model_mod.get_job("aqi"), project_dir="/proj", python_exe="py",
        secret="tok", exec_fn=fake_exec, dry_run=True)
    eq(rc, 0)
    eq(called["n"], 0)


def test_run_job_passes_command():
    seen = {}

    def fake_exec(cmd, env, cwd):
        seen["cmd"] = cmd
        seen["env"] = env
        return 7

    rc = runner_mod.run_job(
        model_mod.get_job("story"), project_dir="/proj", python_exe="py",
        secret="tok", exec_fn=fake_exec, dry_run=False,
        preflight=lambda: None)
    eq(rc, 7)
    eq(seen["cmd"][2:], ["--task", "story"])
    eq(seen["env"]["TG_CHAT_ID"], model_mod.PIN_MIN_GROUP)
    eq(seen["env"]["TG_THREAD_ID"], "")
    eq(seen["env"]["TG_TOPIC_Y3"], "4")


# ── systemd units ────────────────────────────────────────────────────────────
def test_unit_names():
    svc, tmr = systemd_mod.unit_names(model_mod.get_job("homework"))
    eq(svc, "sjkc-cron-homework.service")
    eq(tmr, "sjkc-cron-homework.timer")


def test_service_unit():
    text = systemd_mod.service_unit(
        model_mod.get_job("homework"), project_dir="/proj",
        python_exe="/venv/bin/python", path_env="/mise/shims:/usr/bin")
    assert "ExecStart=/venv/bin/python /proj/main.py --run homework" in text, text
    assert "WorkingDirectory=/proj" in text
    assert "Environment=PATH=/mise/shims:/usr/bin" in text
    assert "Type=oneshot" in text
    assert "TimeoutStartSec=1800" in text
    assert "tok" not in text.lower().replace("token", "")  # no secrets


def test_timer_unit():
    text = systemd_mod.timer_unit(model_mod.get_job("story"))
    assert "OnCalendar=Sat *-*-* 18:00:00" in text
    assert "Persistent=true" in text
    assert "Unit=sjkc-cron-story.service" in text
    assert "WantedBy=timers.target" in text


# ── harness ──────────────────────────────────────────────────────────────────
def main() -> int:
    import tempfile

    print("model")
    check("jobs registry", test_jobs)
    check("schedules", test_schedules)
    check("content jobs at 6pm", test_content_jobs_all_at_6pm)
    check("targets", test_targets)
    check("year topics", test_year_topics)
    check("no group main-chat target", test_no_group_target_without_topic)
    check("delivery kinds", test_delivery_kinds)
    check("target parse", test_target_parse)
    check("unknown job", test_unknown_job)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        print("env")
        check("parse_env_text", test_parse_env_text)
        check("load_env missing", lambda: test_load_env_missing(tmp))
        check("load_env roundtrip", lambda: test_load_env_roundtrip(tmp))
        print("telegram")
        check("document thread", lambda: test_send_document_includes_thread(tmp))
        check("document no thread", lambda: test_send_document_omits_thread_when_absent(tmp))
        check("document retries", lambda: test_send_document_retries_then_succeeds(tmp))
        check("document gives up", lambda: test_send_document_gives_up(tmp))
        check("text thread", test_send_text_includes_thread)
        check("text no thread", test_send_text_no_thread)
        check("poll payload", test_send_poll_payload)
        check("poll truncates", test_send_poll_truncates_to_api_limits)
        check("video multipart", lambda: test_send_video_multipart(tmp))

        print("content script")
        check("normalize questions", test_normalize_questions_letter_answers)
        check("normalize wrong count", test_normalize_questions_wrong_count_raises)
        check("normalize truncates", test_normalize_questions_truncates)
        check("answer index", test_answer_index_variants)
        check("strip option label", test_strip_option_label)
        check("story video command", test_build_story_video_command)
        check("clean html", test_clean_html)
        check("words to cues", test_words_to_cues)
        check("build srt", test_build_srt)
        check("pick commons image", test_pick_commons_image)
        check("normalize scenes", test_normalize_scenes)
        check("fallback card", lambda: test_make_fallback_card(tmp))
        check("cover crop", test_cover_crop)
        check("fetch commons image (fake)",
              lambda: test_fetch_commons_image_with_fake_get(tmp))
        check("story prompt has scenes", test_story_prompt_has_scenes)
        check("build story video (fakes)",
              lambda: test_build_story_video_with_fakes(tmp))
        check("story video card fallback",
              lambda: test_build_story_video_falls_back_to_card(tmp))
        check("story degrades to text", test_run_story_degrades_to_text_when_video_fails)
        check("quiz text + polls", test_run_quiz_sends_reading_text_then_polls)
        check("quiz skips no-reading", test_run_quiz_skips_year_without_reading)
        check("homework skips no-topic", test_run_homework_skips_year_without_topic)
        check("poll non-anonymous default", test_script_poll_defaults_non_anonymous)

    print("llm")
    check("extract_json plain", test_extract_json_plain)
    check("extract_json fenced", test_extract_json_fenced)
    check("extract_json prose", test_extract_json_prose)
    check("extract_json garbage", test_extract_json_rejects_garbage)
    check("parse_opencode_events", test_parse_opencode_events)
    check("build_argv", test_build_argv)
    check("generate fake runner", test_generate_with_fake_runner)
    check("default_runner stdout in error", test_default_runner_includes_stdout_on_failure)
    check("generate retries", test_generate_retries_on_transient_error)
    check("generate gives up", test_generate_gives_up_after_retries)

    print("network")
    check("vpn connected", test_vpn_status_connected)
    check("vpn disconnected", test_vpn_status_disconnected)
    check("vpn cli missing", test_vpn_status_cli_missing)
    check("ensure_vpn noop", test_ensure_vpn_noop_when_connected)
    check("ensure_vpn connects", test_ensure_vpn_connects_when_down)
    check("ensure_vpn raises", test_ensure_vpn_raises_when_connect_fails)
    check("ensure_vpn best-effort false", test_ensure_vpn_best_effort_never_raises)
    check("ensure_vpn best-effort true", test_ensure_vpn_best_effort_true_when_connected)

    print("runner")
    check("build_command", test_build_command)
    check("build_env", test_build_env)
    check("build_env aqi thread", test_build_env_aqi_has_thread_no_year_topics)
    check("build_env no thread", test_build_env_no_thread)
    check("describe masks secret", test_describe_masks_secret)
    check("run_job dry-run", test_run_job_dry_run_does_not_execute)
    check("run_job passes command", test_run_job_passes_command)
    check("run_job preflight order", test_run_job_calls_preflight)
    check("run_job dry skips preflight", test_run_job_dry_run_skips_preflight)
    check("run_job tolerates VPN down", test_run_job_continues_when_preflight_returns_false)

    print("systemd")
    check("unit names", test_unit_names)
    check("service unit", test_service_unit)
    check("timer unit", test_timer_unit)

    print()
    total = 74
    if FAILURES:
        print(f"FAILED: {len(FAILURES)}/{total}")
        for f in FAILURES:
            print("  -", f)
        return 1
    print(f"ALL GREEN: {total}/{total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
