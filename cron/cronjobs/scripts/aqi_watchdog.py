#!/usr/bin/env python3
"""SJKC Pin Min — AQI Basketball Cancellor
Checks Ipoh + Tanjung Malim US AQI via Open-Meteo (free, no token).
If either exceeds 100 → sends bilingual cancellation message to basketball
topic in SJKC Pin Min group. Runs daily at 06:00 via cron."""

from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import date, datetime
from pathlib import Path

# ── Load .env if TELEGRAM_BOT_TOKEN not in environment ────────────────────────
if not os.environ.get("TELEGRAM_BOT_TOKEN"):
    env_path = Path.home() / ".hermes" / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    os.environ["TELEGRAM_BOT_TOKEN"] = line.split("=", 1)[1].strip()
                    break

# ── Config ─────────────────────────────────────────────────────────────────────
IPOH_LAT, IPOH_LON = 4.59, 101.10
TM_LAT,  TM_LON  = 3.68,  101.52
AQI_THRESHOLD = 100  # Malaysian API / US EPA: >100 = Unhealthy

TG_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_BASKETBALL_CHAT = os.environ.get("TG_CHAT_ID", "")
TG_BASKETBALL_TOPIC = os.environ.get("TG_THREAD_ID", "")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "output" / "aqi_watchdog"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ── API ────────────────────────────────────────────────────────────────────────

def fetch_us_aqi(lat: float, lon: float) -> dict | None:
    """Return current US AQI + PM data for a lat/lon from Open-Meteo."""
    url = (
        "https://air-quality-api.open-meteo.com/v1/air-quality"
        f"?latitude={lat}&longitude={lon}"
        "&current=us_aqi,pm2_5,pm10"
        "&timezone=Asia/Kuala_Lumpur"
    )
    try:
        with urllib.request.urlopen(url, timeout=12) as resp:
            data = json.loads(resp.read())
        cur = data.get("current", {})
        return {
            "us_aqi": int(cur.get("us_aqi", 0) or 0),
            "pm2_5": float(cur.get("pm2_5", 0) or 0),
            "pm10": float(cur.get("pm10", 0) or 0),
            "time": cur.get("time", ""),
        }
    except Exception as exc:
        print(f"[AQI] fetch error for ({lat},{lon}): {exc}", file=sys.stderr)
        return None


def today_is_weekday() -> bool:
    """Return True if today is Mon-Fri (Malaysia timezone)."""
    import datetime as dt
    tz = dt.timezone(dt.timedelta(hours=8))
    now = dt.datetime.now(tz)
    return now.weekday() < 5  # Mon=0 .. Fri=4


def aqi_label_us(aqi: int) -> str:
    """Descriptive label for US AQI / Malaysian API scale."""
    if aqi <= 50:
        return "Baik (Good)"
    elif aqi <= 100:
        return "Sederhana (Moderate)"
    elif aqi <= 200:
        return "Tidak Sihat (Unhealthy)"
    elif aqi <= 300:
        return "Sangat Tidak Sihat (Very Unhealthy)"
    return "Berbahaya (Hazardous)"


def aqi_label_zh(aqi: int) -> str:
    """中文空气质量标签."""
    if aqi <= 50:
        return "优 (Good)"
    elif aqi <= 100:
        return "良 (Moderate)"
    elif aqi <= 200:
        return "不健康 (Unhealthy)"
    elif aqi <= 300:
        return "非常不健康 (Very Unhealthy)"
    return "危险 (Hazardous)"


# ── Telegram ───────────────────────────────────────────────────────────────────

def send_telegram(text: str) -> bool:
    """Post message to the configured target (owner DM by default)."""
    if not TG_BOT_TOKEN:
        print(f"[AQI] NOT SENT — no TELEGRAM_BOT_TOKEN:\n{text[:300]}")
        return False

    if not TG_BASKETBALL_CHAT:
        print("[AQI] NOT SENT — no TG_CHAT_ID", file=sys.stderr)
        return False

    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from cronjobs import telegram
    try:
        result = telegram.send_text(
            TG_BOT_TOKEN, TG_BASKETBALL_CHAT, TG_BASKETBALL_TOPIC or None,
            text, parse_mode="Markdown")
    except Exception as exc:
        print(f"[AQI] Telegram send failed: {exc}", file=sys.stderr)
        return False

    if result.get("ok"):
        print("[AQI] Telegram message sent OK")
        return True
    print(f"[AQI] Telegram error: {result.get('description', result)}")
    return False


# ── Messages ───────────────────────────────────────────────────────────────────

def build_cancellation_msg(ipoh: dict, tm: dict) -> str:
    now = datetime.now().strftime("%H:%M")
    today = date.today().strftime("%d %B %Y")

    triggered: list[tuple] = []
    if ipoh["us_aqi"] > AQI_THRESHOLD:
        triggered.append(("Ipoh", ipoh["us_aqi"], ipoh["pm2_5"], ipoh["pm10"]))
    if tm["us_aqi"] > AQI_THRESHOLD:
        triggered.append(("Tanjung Malim", tm["us_aqi"], tm["pm2_5"], tm["pm10"]))

    lines = [
        "🇲🇾 *SJKC PIN MIN — LATIHAN BOLA BULU DIBATALKAN* 🇲🇾",
        "",
        "*📢 AQI TIDAK SIHAT — API > 100*",
        "",
        f"*📅 {today} {now}*",
        "",
        "*📍 AQI Hari Ini:*",
    ]
    for name, aqi, pm25, pm10 in triggered:
        lines.append(
            f"  • *{name}:* API *{aqi}* ({aqi_label_us(aqi)}) | "
            f"PM2.5: {pm25} | PM10: {pm10}"
        )
    lines += [
        "",
        "*🚫 Latihan bola bulu Hari Ini: DIBATALKAN.*",
        "*📌 Sebab:* API melebihi 100 — tidak sihat untuk aktiviti luar.",
        "*💡 Panduan:* Elak aktiviti luar, tingkap ditutup, pakai mask jika perlu.",
        "*✅ Latihan akan dibaiki sebaik API turun di bawah 100.*",
        "",
        "━━━━━━━━━━━━━━━━━━━",
        "",
        "🏀 *SJKC PIN MIN — BASKETBALL TRAINING CANCELLED* 🏀",
        "",
        f"*📅 {today} {now}*",
        "",
        "*📍 AQI Today:*",
    ]
    for name, aqi, pm25, pm10 in triggered:
        lines.append(
            f"  • *{name}:* API *{aqi}* ({aqi_label_us(aqi)}) | "
            f"PM2.5: {pm25} | PM10: {pm10}"
        )
    lines += [
        "",
        "*🚫 Basketball Training Today: CANCELLED.*",
        "*📌 Reason:* API exceeds 100 — unhealthy for outdoor activities.",
        "*💡 Advice:* Avoid outdoor activities, keep windows closed, wear mask if needed.",
        "*✅ Training resumes once API drops below 100.*",
        "",
        "━━━━━━━━━━━━━━━━━━━",
        "",
        "🏀 *SJKC  Pin Min — 篮球训练取消* 🏀",
        "",
        f"*📅 {today} {now}*",
        "",
        "*📍 空气质量今日:*",
    ]
    for name, aqi, pm25, pm10 in triggered:
        lines.append(
            f"  • *{name}:* 空气指数 *{aqi}* ({aqi_label_zh(aqi)}) | "
            f"PM2.5: {pm25} | PM10: {pm10}"
        )
    lines += [
        "",
        "*🚫 今日篮球训练：已取消。*",
        "*📌 原因:* 空气指数超过 100 — 不适合户外活动。",
        "*💡 建议:* 避免户外活动，关窗，必要时戴口罩。",
        "*✅ 空气指数降至 100 以下后，训练将恢复。*",
        "",
        "📊 Sumber: Open-Meteo Air Quality API (percuma)",
    ]
    return "\n".join(lines)


def build_normal_msg(ipoh: dict, tm: dict) -> str:
    today = date.today().strftime("%d %B %Y")
    lines = [
        "🏀 *SJKC PIN MIN — AQI Harian* 🏀",
        "",
        f"*📅 {today}*",
        "",
        "*📍 AQI Hari Ini:*",
        f"  • *Ipoh:* API *{ipoh['us_aqi']}* ({aqi_label_us(ipoh['us_aqi'])}) | PM2.5: {ipoh['pm2_5']} | PM10: {ipoh['pm10']}",
        f"  • *Tanjung Malim:* API *{tm['us_aqi']}* ({aqi_label_us(tm['us_aqi'])}) | PM2.5: {tm['pm2_5']} | PM10: {tm['pm10']}",
        "",
        "*✅ Latihan Bola Bulu: BOLEH BERLANGSUNG.* 💪🏀",
        "",
        "━━━━━━━━━━━━━━━━━━━",
        "",
        "🏀 *SJKC PIN MIN — Daily AQI* 🏀",
        "",
        f"*📅 {today}*",
        "",
        "*📍 AQI Today:*",
        f"  • *Ipoh:* API *{ipoh['us_aqi']}* ({aqi_label_us(ipoh['us_aqi'])}) | PM2.5: {ipoh['pm2_5']} | PM10: {ipoh['pm10']}",
        f"  • *Tanjung Malim:* API *{tm['us_aqi']}* ({aqi_label_us(tm['us_aqi'])}) | PM2.5: {tm['pm2_5']} | PM10: {tm['pm10']}",
        "",
        "*✅ Basketball Training: ON as scheduled.* 💪🏀",
        "",
        "━━━━━━━━━━━━━━━━━━━",
        "",
        "🏀 *SJKC Pin Min — 每日空气质量* 🏀",
        "",
        f"*📅 {today}*",
        "",
        "*📍 空气质量今日:*",
        f"  • *Ipoh:* 空气指数 *{ipoh['us_aqi']}* ({aqi_label_zh(ipoh['us_aqi'])}) | PM2.5: {ipoh['pm2_5']} | PM10: {ipoh['pm10']}",
        f"  • *Tanjung Malim:* 空气指数 *{tm['us_aqi']}* ({aqi_label_zh(tm['us_aqi'])}) | PM2.5: {tm['pm2_5']} | PM10: {tm['pm10']}",
        "",
        "*✅ 篮球训练：如计划进行。* 💪🏀",
        "",
        "📊 Sumber: Open-Meteo (percuma)",
    ]
    return "\n".join(lines)


# ── Main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"[AQI Watchdog] Running — {date.today()}")

    ipoh = fetch_us_aqi(IPOH_LAT, IPOH_LON)
    tm   = fetch_us_aqi(TM_LAT,  TM_LON)

    if not ipoh:
        print("[AQI] Ipoh fetch FAILED")
    else:
        print(f"[AQI] Ipoh:      US AQI={ipoh['us_aqi']} | PM2.5={ipoh['pm2_5']} | PM10={ipoh['pm10']}")

    if not tm:
        print("[AQI] Tanjung Malim fetch FAILED")
    else:
        print(f"[AQI] Tanjung Malim: US AQI={tm['us_aqi']} | PM2.5={tm['pm2_5']} | PM10={tm['pm10']}")

    if not ipoh or not tm:
        fail_msg = (
            "⚠️ *SJKC PIN MIN — AQI DATA TIDAK Boleh Diambil* ⚠️\n\n"
            "Sistem AQI tidak dapat mengambil data hari ini. Sila rujuk sumber lain "
            "(APDA/DOE) sebelum membuat keputusan.\n\n"
            "_Dihantar oleh bot AQI Watchdog._"
        )
        send_telegram(fail_msg)
        sys.exit(1)

    cancelled = ipoh["us_aqi"] > AQI_THRESHOLD or tm["us_aqi"] > AQI_THRESHOLD

    if cancelled:
        print(f"[AQI] ⚠️  CANCELLATION — API > 100")
        msg = build_cancellation_msg(ipoh, tm)
        send_telegram(msg)
    elif today_is_weekday():
        print(f"[AQI] ✅ Normal — AQI ≤ 100 (weekday)")
        msg = build_normal_msg(ipoh, tm)
        send_telegram(msg)
    else:
        print(f"[AQI] ✅ Normal — AQI ≤ 100 (weekend, no post)")


if __name__ == "__main__":
    main()
