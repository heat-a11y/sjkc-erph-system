"""Domain model: the scheduled jobs and their delivery targets.

This is the single source of truth. Timers, the CLI and the runner are all
derived from ``JOBS`` — never duplicate a schedule or chat id elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Target:
    """A Telegram delivery target: a chat, optionally a forum topic/thread."""

    chat_id: str
    thread_id: str | None = None

    @classmethod
    def parse(cls, text: str) -> "Target":
        chat, _, thread = text.partition(":")
        chat = chat.strip()
        thread = thread.strip() or None
        if not chat:
            raise ValueError(f"invalid target: {text!r}")
        return cls(chat_id=chat, thread_id=thread)

    def display(self) -> str:
        return f"{self.chat_id}:{self.thread_id}" if self.thread_id else self.chat_id


@dataclass(frozen=True)
class Job:
    """One scheduled job.

    ``script`` is relative to the project root. ``args`` are extra argv passed
    to the script. ``needs_llm`` gates whether the opencode adapter is used.

    ``year_topics`` maps a school year (1-6) to a Telegram forum topic/thread
    for class-scoped content. When set, the job targets a group chat and the
    runner exports ``TG_TOPIC_Y<year>`` for each pair; the script must send one
    item per year and skip a year whose topic is missing.

    ``delivery`` names the per-year output shape (see ``DELIVERY_*``) so the
    contract is visible in the registry rather than only in the script.
    """

    key: str
    name: str
    script: str
    on_calendar: str
    target: Target
    args: tuple[str, ...] = ()
    needs_llm: bool = False
    year_topics: tuple[tuple[int, str], ...] = ()
    delivery: str = "pdf"

    def topic_for_year(self, year: int) -> str | None:
        return dict(self.year_topics).get(year)


# The bot is a member of the SJKC Pin Min supergroup (forum). Content is
# class-scoped, so it is delivered to per-year topics — never the main chat.
PIN_MIN_GROUP = "-1002575685985"
BASKETBALL_TOPIC = "16"
YEAR_TOPICS: tuple[tuple[int, str], ...] = (
    (1, "2"),
    (2, "3"),
    (3, "4"),
    (4, "5"),
    (5, "6"),
    (6, "7"),
)

# How a per-year content job delivers to its group topic.
DELIVERY_PDF = "pdf"                     # one printable PDF per year
DELIVERY_STORY_VIDEO = "story_video"     # narrated TTS video + 3 quiz polls
DELIVERY_QUIZ_TEXT = "quiz_text"         # reading text + 3 quiz polls

JOBS: tuple[Job, ...] = (
    Job(
        key="aqi",
        name="AQI Basketball Watchdog (daily 06:00)",
        script="cronjobs/scripts/aqi_watchdog.py",
        on_calendar="*-*-* 06:00:00",
        target=Target(chat_id=PIN_MIN_GROUP, thread_id=BASKETBALL_TOPIC),
        needs_llm=False,
    ),
    Job(
        key="homework",
        name="English Homework (Friday PDF, Y1-6)",
        script="cronjobs/scripts/sjkc_english.py",
        on_calendar="Fri *-*-* 18:00:00",
        target=Target(chat_id=PIN_MIN_GROUP),
        args=("--task", "homework"),
        needs_llm=True,
        year_topics=YEAR_TOPICS,
    ),
    Job(
        key="story",
        name="Bedtime Stories (Saturday video + quiz polls, Y1-6)",
        script="cronjobs/scripts/sjkc_english.py",
        on_calendar="Sat *-*-* 18:00:00",
        target=Target(chat_id=PIN_MIN_GROUP),
        args=("--task", "story"),
        needs_llm=True,
        year_topics=YEAR_TOPICS,
        delivery=DELIVERY_STORY_VIDEO,
    ),
    Job(
        key="quiz",
        name="English Mini-Quiz (Sunday reading text + quiz polls, Y1-6)",
        script="cronjobs/scripts/sjkc_english.py",
        on_calendar="Sun *-*-* 18:00:00",
        target=Target(chat_id=PIN_MIN_GROUP),
        args=("--task", "quiz"),
        needs_llm=True,
        year_topics=YEAR_TOPICS,
        delivery=DELIVERY_QUIZ_TEXT,
    ),
)

JOBS_BY_KEY: dict[str, Job] = {job.key: job for job in JOBS}


def get_job(key: str) -> Job:
    try:
        return JOBS_BY_KEY[key]
    except KeyError:
        known = ", ".join(sorted(JOBS_BY_KEY))
        raise KeyError(f"unknown job {key!r}; known jobs: {known}") from None
