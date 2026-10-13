# SPEC — Hermes-free SJKC Cron Runner

## Purpose

Run the four existing SJKC Pin Min scheduled jobs on this machine **without the
Hermes gateway**, and deliver their output to Telegram through an existing bot.
Hermes' free model tier is being abandoned; everything else about the jobs
(scripts, schedules, targets) is preserved.

## Contract

### Jobs (unchanged schedules)

| key        | run at (local, Asia/Kuala_Lumpur) | action                                              | Telegram target                          |
|------------|------------------------------------|-----------------------------------------------------|------------------------------------------|
| `aqi`      | daily 06:00                        | `aqi_watchdog.py` (no LLM)                          | group `-1002575685985` topic `16`        |
| `homework` | Fri 18:00                          | `sjkc_english.py --task homework` (PDF)             | group, one PDF per year -> topic Y1..Y6  |
| `story`    | Sat 18:00                          | `sjkc_english.py --task story` (slideshow video + 3 polls)| group, one video + 3 polls per year -> Y1..Y6 |
| `quiz`     | Sun 18:00                          | `sjkc_english.py --task quiz` (reading text + 3 polls)| group, one text + 3 polls per year -> Y1..Y6 |

- **The bot is in the SJKC Pin Min supergroup `-1002575685985` (forum).** Delivery
  targets the group's per-year topics, **never** the group's main chat.
- **Year -> topic map (confirmed by owner):** Year 1 -> `2`, Year 2 -> `3`,
  Year 3 -> `4`, Year 4 -> `5`, Year 5 -> `6`, Year 6 -> `7`. Topic `1` is the
  group's General topic and `16` is the basketball topic (used by `aqi`).
- **Class-scoped content must never leak.** Each year's worksheet is a separate
  PDF sent to that year's topic. If a year has **no** topic configured the send
  must be **skipped** (loudly) — never fall back to the group main chat.
- **The group receives ONLY deliveries.** The bot must never reply to, or
  otherwise react to, any message in the group; all interaction is via the
  cronjobs' own output (documents, videos, texts, polls). Pupil answers are
  collected by Telegram's native quiz polls, which need no bot message reading.
- Targets live in the domain registry (`cronjobs/model.py`), not in scripts: the
  runner exports `TG_CHAT_ID`, `TG_THREAD_ID` and `TG_TOPIC_Y1..Y6`; the scripts
  only read them.
- Bot: existing `@clawdy9876bot` (token in `.env`, never committed).

### Scheduling

- One systemd **user** timer per job (`sjkc-cron-<key>.timer`), each paired with
  a concrete `sjkc-cron-<key>.service`.
- `Persistent=true` so a missed run (machine off/asleep) fires when it returns.
- Units are generated from the domain registry by `main.py --install-timers`;
  nothing about schedules is hard-coded in the shell.

### Generation (LLM)

- Content jobs need an LLM. We no longer call Hermes' `hermes_tools.model_tools`.
- `cronjobs/llm.py` shells out to **headless opencode**:
  `opencode run --agent content-gen --format json "<system+user prompt>"`.
- The project defines a generation agent (`.opencode/agent/content-gen.md`).
  It is instruction-only — **do not add `permission:` to that file**: denying
  tools in agent frontmatter makes the opencode zen provider reject every
  request with `403 FreeTierError: free tier can only be used from within
  OpenCode`. Tool-free behaviour is enforced by the prompt plus strict JSON
  validation in `cronjobs/llm.py` instead.
- The adapter parses opencode's JSON event stream, concatenates `text` parts,
  and robustly extracts the JSON object (tolerates ```json fences / prose).
- The zen free tier intermittently answers 403/throttling, so `generate()`
  retries up to 3 attempts with backoff before failing.
- AQI job has `needs_llm=False` and never invokes opencode.

### Narration & video (story job)

The story video is a **photo slideshow with narration and burned-in subtitles**:

- The LLM returns, per year, a `scenes` list: each scene has `text` (a 1–2
  sentence chunk of the story) and `keywords` (2–4 simple common nouns suitable
  for a photo search). The concatenation of the scene texts is the story.
- **edge-tts** (project `.venv`) narrates each scene separately to MP3 (voice
  `en-GB-SoniaNeural`, rate `-10%`, `boundary="WordBoundary"`) and reports
  **word-level timings**. The script groups consecutive words into short caption
  cues and writes a `.srt`. Because each scene is synthesized on its own, slide
  changes and subtitle cues stay exactly aligned.
- **Wikimedia Commons** (public API, no key) supplies one freely-licensed photo
  per scene via keyword search, cover-cropped to 1280×720 with an **on-screen
  attribution** strip (author + licence). If a search/download fails the scene
  falls back to a locally drawn Pillow illustration card, so a year is never
  lost to a missing image.
- **ffmpeg** (system binary) concatenates the scene images (each held for its
  scene's narration duration), concatenates the narration MP3s, and burns the
  `.srt` in with the `subtitles` filter to produce H.264/AAC `.mp4`
  (`-shortest`, `+faststart`). edge-tts, the image fetch and ffmpeg are all
  invoked through injectable seams so tests stay hermetic.
- **Network gotcha:** the free edge-tts endpoint answers `403` from some VPN
  exits but works from others. `synthesize_speech` therefore retries and re-runs
  the VPN preflight between attempts. If TTS still fails the year **degrades
  gracefully** to a text story + polls instead of being dropped.

### Delivery

- Scripts send via the Telegram Bot API themselves (as before), through the
  shared resilient client `cronjobs/telegram.py`.
- The runner exports `TELEGRAM_BOT_TOKEN`, `TG_BOT_TOKEN`, `TG_CHAT_ID`,
  `TG_THREAD_ID` and `TG_TOPIC_Y1..Y6` from the registry + `.env`.
- Document sends MUST include `message_thread_id` when a thread is configured.
  For per-year jobs the single `TG_THREAD_ID` is empty and the script picks
  `TG_TOPIC_Y<year>` per PDF; a missing year topic means "skip that year".
- All sends retry with backoff (5 attempts); the VPN route resets connections
  mid-transfer often enough that a single attempt is not trustworthy.

### Per-task delivery shapes

- **`homework`** — one printable PDF per year (unchanged).
- **`story`** — a **bedtime-story video (photo slideshow + narration + burned-in
  subtitles)** plus **three Telegram quiz polls** per year:
  - The LLM returns, per year, `title`, `story`, `scenes` and `questions`
    (exactly 3).
  - Each scene is narrated with **edge-tts** (`en-GB-SoniaNeural`, slight slow
    rate) and illustrated with a **Wikimedia Commons** photo (attributed
    on-screen; local fallback card on failure); ffmpeg muxes the slideshow +
    narration + burned-in `.srt` into an H.264/AAC `.mp4`, sent with `sendVideo`
    (per-year topic).
  - If TTS/ffmpeg fails for a year the job must **degrade gracefully**: send the
    story as text, then still post the 3 polls, and record the year as degraded.
- **`quiz`** — a **reading text message** plus **three Telegram quiz polls** per
  year (no PDF): the LLM returns, per year, `reading` and `questions` (exactly 3).
- **Questions are delivered as native Telegram quiz polls** (`type=quiz`,
  `correct_option_id`): Telegram auto-grades them, so the bot **never reads or
  replies to group messages**. This is what preserves the no-reply rule in
  "The group receives ONLY deliveries" above.
  - 3 options per question, one correct; answer supplied as the option letter
    (`"A"`/`"B"`/`"C"`) and normalized to a 0-based index.
  - Option labels the model may emit (`"A. cat"`) are stripped — Telegram shows
    polls without automatic letters.
  - Question text is capped at 300 chars, options at 100 chars (API limits).
  - Polls are **non-anonymous by default** so the teacher can see who answered;
    set `TG_POLL_ANONYMOUS=1` to make pupil answers anonymous.

### Network precondition (VPN)

Telegram **file uploads are reset** on this machine's direct ISP path, while text
messages survive. Verified: `sendDocument`/`sendPhoto` reset from 1 KB to 267 KB
over HTTP/1.1 and HTTP/2, IPv4 and IPv6, while an identical multipart POST to
`httpbin.org` succeeds. Through **ProtonVPN** the 267 KB upload returns HTTP 200
in ~3 s.

Therefore every job runs a network preflight (`cronjobs/network.py`):
`protonvpn status` → if not `Status: Connected`, `protonvpn connect` and wait.
The preflight is **best-effort**: if the VPN cannot be brought up (the free tier
intermittently refuses the WireGuard handshake) it is logged as a warning and the
job proceeds over the direct path — a direct 264 KB `sendDocument` was verified
working — rather than generating a PDF nobody receives. The resilient Telegram
client still retries every send. ProtonVPN kill-switch is `standard`, so a
dropped tunnel already blocks the internet.

### Secrets

- `.env` (mode 0600, git-ignored) holds `TELEGRAM_BOT_TOKEN`.
- Token is read at runtime; never logged, never written into systemd units.

## Runner CLI

```
python3 main.py --list
python3 main.py --run <key> [--dry-run]
python3 main.py --install-timers [--enable]
python3 main.py --uninstall-timers
```

- `--dry-run` prints the resolved argv + env keys (no secret values) and exits 0
  without running the job or contacting Telegram.

## Non-goals

- No changes to the homework PDF layout or the weekly prompts' vocabulary.
- No Hermes gateway dependency at runtime.
- No web service; systemd timers are the scheduler.
- Story/quiz no longer produce PDFs on the scheduled path; the story/quiz
  builders are replaced by the video/poll and text/poll pipelines above.

## Verification

1. `python3 tests/run_tests.py` — all green, hermetic (no network, no LLM, no
   ffmpeg: TTS/ffmpeg are injected fakes).
2. `python3 main.py --list` prints the 4 jobs.
3. `python3 main.py --run aqi --dry-run` resolves correct argv/env.
4. Install timers; `systemctl --user list-timers` shows the 4 OnCalendar entries.
5. End-to-end, one real generation each + Telegram send into the matching group
   topics:
   - homework: one PDF per year;
   - story: one narrated slideshow `.mp4` (attributed photos + burned-in
     subtitles) + 3 quiz polls per year;
   - quiz: one reading text + 3 quiz polls per year.
