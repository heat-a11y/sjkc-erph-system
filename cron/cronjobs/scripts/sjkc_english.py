#!/usr/bin/env python3
"""
SJKC Pin Min — KSSR English Weekly Content Generator
======================================================
Generates three types of content for Year 1-6 every week:

  python3 sjkc_english_cron.py --task homework → Fri  (one PDF per year)
  python3 sjkc_english_cron.py --task story    → Sat  (one TTS video + 3 polls
                                                        per year)
  python3 sjkc_english_cron.py --task quiz     → Sun  (one reading text + 3
                                                        polls per year)

Word lists are organised by 6-week rotating themes to keep prompts lean.
Education content is generated via the headless opencode adapter
(``cronjobs.llm``). Homework PDFs use reportlab; bedtime stories are built into
a narrated photo slideshow — Wikimedia Commons photos per scene (attributed),
edge-tts narration with burned-in word-timed subtitles, muxed by ffmpeg; quiz
and story questions are delivered as native Telegram quiz polls. Everything for
a year is sent to that year's Telegram forum topic (TG_TOPIC_Y1..Y6).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                 Table, TableStyle, HRFlowable, KeepTogether)

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
OUTPUT_DIR  = PROJECT_ROOT / "output" / "sjkc_english"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SCHOOL_LOGO = Path.home() / "Downloads" / "exam2026" / \
              "Lencana__sekolah_HD_SJKC_PIN_MIN_BIDOR_STESEN-removebg-preview (NOBG).png"

# ── Week themes ────────────────────────────────────────────────────────────────
# 6-week cycle. Each week pulls a tight word set per year from the DSKP lists.
# Total embedded vocab across all 6 years × 6 weeks ≈ 270 words ≈ 350 tokens.
# Full word lists (6000+ tokens) are NEVER sent to the model.

THEMES = [
    # Week 1
    {
        "name": "Fun at the Beach / Pet Show",
        "words": {
            1: ["beach", "ball", "bat", "duck", "cat", "dog", "fish", "frog", "swim", "run",
                "play", "jump", "sun", "sand", "bucket", "spade", "wave", "shell", "red", "blue",
                "yellow", "green", "big", "small", "happy", "hot"],
            2: ["head", "eyes", "nose", "mouth", "arms", "legs", "hands", "feet", "hat", "shirt",
                "shoes", "shorts", "coat", "jacket", "sun", "rain", "wind", "tree", "flower",
                "beach", "sea", "sky", "ball", "doll", "bike", "kite", "clean", "wash", "dirty",
                "new", "old", "funny", "scared"],
            3: ["school", "hospital", "library", "park", "beach", "zoo", "supermarket", "cafe",
                "teacher", "doctor", "nurse", "driver", "chef", "farmer", "bus", "train", "boat",
                "car", "bicycle", "breakfast", "lunch", "dinner", "rice", "bread", "fruit",
                "vegetable", "water", "milk", "buy", "sell", "help", "work", "visit"],
            4: ["computer", "laptop", "phone", "camera", "television", "internet", "email",
                "message", "screen", "keyboard", "plant", "seed", "water", "soil", "air",
                "recycle", "bin", "plastic", "paper", "glass", "rubbish", "energy", "nature",
                "save", "protect", "search", "click", "type", "send", "modern", "digital",
                "useful", "dangerous", "safe", "quickly", "slowly", "always", "never"],
            5: ["passport", "ticket", "luggage", "hotel", "map", "souvenir", "journey", "destination",
                "adventure", "tourist", "suitcase", "flight", "camp", "exercise", "medicine",
                "fever", "cough", "flu", "healthy", "unhealthy", "diet", "headache", "stomach ache",
                "explore", "discover", "plan", "decide", "imagine", "invent", "design", "compare",
                "crowded", "deserted", "ancient", "modern", "fantastic", "terrible", "exhausting",
                "relaxing", "popular", "expensive", "extremely", "quite", "slightly"],
            6: ["environment", "conservation", "endangered", "species", "charity", "volunteer",
                "community", "responsibility", "project", "goal", "pollution", "climate", "sea",
                "beach", "tree", "flower", "forest", "nature", "plant", "water", "air", "recycle",
                "bin", "plastic", "paper", "glass", "energy", "save", "protect", "reduce", "reuse",
                "achieve", "accomplish", "contribute", "participate", "support", "organize",
                "manage", "evaluate", "analyze", "investigate", "design", "produce",
                "successful", "responsible", "independent", "confident", "creative", "reliable",
                "global"],
        },
    },
    # Week 2
    {
        "name": "My Body & My Clothes",
        "words": {
            1: ["head", "hair", "face", "eyes", "ears", "nose", "mouth", "arms", "legs", "hands",
                "feet", "shirt", "T-shirt", "trousers", "shorts", "skirt", "shoes", "socks",
                "jacket", "coat", "hat", "red", "blue", "yellow", "green", "pink", "purple",
                "black", "white", "brown", "orange", "big", "small", "long", "short"],
            2: ["head", "hair", "face", "eyes", "ears", "nose", "mouth", "teeth", "arms", "legs",
                "hands", "feet", "fingers", "toes", "hat", "shirt", "T-shirt", "trousers", "shorts",
                "skirt", "shoes", "socks", "jacket", "coat", "scarf", "boots", "sweater", "clean",
                "dirty", "new", "old", "loud", "quiet", "fast", "slow", "hungry", "thirsty",
                "tired", "scared", "angry", "funny"],
            3: ["head", "face", "eyes", "nose", "mouth", "ears", "hair", "hands", "feet", "house",
                "room", "bedroom", "kitchen", "bathroom", "living room", "bed", "table", "chair",
                "door", "window", "wall", "floor", "garden", "shirt", "T-shirt", "trousers",
                "shorts", "skirt", "shoes", "socks", "jacket", "coat", "clean", "wash", "cook",
                "help", "open", "close", "draw", "paint", "catch", "throw", "long", "short",
                "clean", "dirty", "new", "old", "loud", "quiet"],
            4: ["head", "face", "eyes", "nose", "mouth", "hair", "arms", "legs", "hands", "feet",
                "hat", "shirt", "coat", "jacket", "shoes", "socks", "sweater", "glass", "paper",
                "plastic", "rubbish", "recycle", "bin", "clean", "wash", "dirty", "new", "old",
                "modern", "traditional", "digital", "useful", "dangerous", "safe", "carefully",
                "quickly", "slowly", "loudly", "quietly", "usually", "sometimes", "always", "never"],
            5: ["head", "face", "eyes", "nose", "mouth", "teeth", "hair", "arms", "legs", "hands",
                "feet", "hat", "shirt", "coat", "jacket", "shoes", "socks", "exercise", "medicine",
                "fever", "cough", "flu", "healthy", "unhealthy", "diet", "stomach ache", "headache",
                "plaster", "doctor", "hospital", "dentist", "explore", "discover", "plan", "decide",
                "imagine", "healthy", "crowded", "deserted", "ancient", "modern", "fantastic",
                "terrible", "exhausting", "relaxing", "extremely", "quite"],
            6: ["head", "face", "eyes", "nose", "mouth", "hair", "arms", "legs", "hands", "feet",
                "hat", "shirt", "coat", "jacket", "shoes", "socks", "glasses", "achieve", "accomplish",
                "contribute", "participate", "support", "manage", "evaluate", "analyze", "investigate",
                "design", "career", "profession", "qualification", "interview", "resume", "success",
                "achievement", "skill", "experience", "employer", "employee", "responsible",
                "independent", "confident", "creative", "reliable", "however", "furthermore",
                "nevertheless", "consequently", "meanwhile", "similarly"],
        },
    },
    # Week 3
    {
        "name": "My House & My Family",
        "words": {
            1: ["house", "home", "room", "bed", "table", "chair", "door", "window", "wall", "floor",
                "garden", "mother", "father", "brother", "sister", "baby", "grandmother", "grandfather",
                "friend", "boy", "girl", "family", "big", "small", "tall", "short", "happy", "sad",
                "hot", "cold", "good", "nice", "beautiful", "old", "young"],
            2: ["house", "home", "room", "bedroom", "kitchen", "bathroom", "living room", "bed", "table",
                "chair", "door", "window", "wall", "floor", "garden", "mother", "father", "brother",
                "sister", "grandmother", "grandfather", "family", "friend", "baby", "boy", "girl",
                "clean", "wash", "cook", "help", "open", "close", "draw", "paint", "big", "small",
                "long", "short", "clean", "dirty", "new", "old", "loud", "quiet", "happy", "sad",
                "tired", "hungry", "thirsty", "scared", "funny"],
            3: ["house", "home", "room", "bedroom", "kitchen", "bathroom", "living room", "garden",
                "door", "window", "wall", "floor", "table", "chair", "bed", "mother", "father",
                "brother", "sister", "grandmother", "grandfather", "family", "friend", "baby",
                "boy", "girl", "teacher", "doctor", "nurse", "clean", "wash", "cook", "help",
                "open", "close", "draw", "paint", "busy", "tired", "bored", "exciting", "interesting",
                "delicious", "morning", "afternoon", "evening", "night", "early", "late", "today",
                "tomorrow", "yesterday"],
            4: ["house", "home", "room", "bedroom", "kitchen", "bathroom", "living room", "door",
                "window", "wall", "floor", "garden", "plant", "seed", "water", "soil", "air",
                "pollution", "recycle", "bin", "plastic", "paper", "glass", "rubbish", "energy",
                "nature", "forest", "save", "protect", "clean", "wash", "cook", "help", "decorate",
                "prepare", "design", "modern", "traditional", "digital", "useful", "dangerous",
                "safe", "carefully", "quickly", "slowly", "usually", "sometimes", "always", "never"],
            5: ["house", "home", "room", "bedroom", "kitchen", "bathroom", "living room", "door",
                "window", "wall", "floor", "garden", "hotel", "map", "journey", "destination",
                "adventure", "tourist", "suitcase", "flight", "camp", "exercise", "medicine",
                "fever", "cough", "flu", "healthy", "unhealthy", "diet", "stomach ache", "headache",
                "plan", "decide", "imagine", "invent", "design", "explore", "discover", "compare",
                "suggest", "recommend", "survive", "achieve", "protect", "crowded", "deserted",
                "ancient", "modern", "fantastic", "terrible", "exhausting", "relaxing", "extremely",
                "quite", "slightly", "popular", "expensive"],
            6: ["house", "home", "room", "community", "responsibility", "project", "goal", "pollution",
                "climate", "environment", "conservation", "endangered", "species", "charity",
                "volunteer", "plant", "tree", "flower", "forest", "nature", "water", "air",
                "recycle", "bin", "plastic", "paper", "glass", "energy", "save", "protect",
                "reduce", "reuse", "achieve", "accomplish", "contribute", "participate", "support",
                "organize", "manage", "evaluate", "analyze", "investigate", "design", "produce",
                "successful", "responsible", "independent", "confident", "creative", "reliable",
                "global", "however", "furthermore", "nevertheless", "consequently", "meanwhile",
                "similarly", "efficient"],
        },
    },
    # Week 4
    {
        "name": "Food, Festivals & Hobbies",
        "words": {
            1: ["apple", "banana", "burger", "cake", "cheese", "chicken", "chocolate", "fish", "milk",
                "water", "juice", "pizza", "sausage", "sandwich", "cake", "eat", "drink", "cook",
                "happy", "sad", "good", "bad", "nice", "beautiful", "red", "blue", "yellow", "green",
                "pink", "orange", "one", "two", "three", "four", "five"],
            2: ["apple", "banana", "burger", "cake", "cheese", "chocolate", "fish", "milk", "water",
                "juice", "pizza", "sausage", "sandwich", "ball", "doll", "car", "train", "bike", "kite",
                "board game", "computer", "piano", "guitar", "camera", "skateboard", "computer game",
                "cook", "clean", "wash", "help", "open", "close", "draw", "paint", "fly", "catch",
                "throw", "ride", "skate", "skip", "climb", "eat", "drink", "happy", "sad", "good",
                "bad", "nice", "funny", "tired", "hungry", "thirsty", "scared", "angry"],
            3: ["breakfast", "lunch", "dinner", "rice", "noodles", "bread", "egg", "meat", "soup",
                "vegetable", "fruit", "water", "milk", "tea", "coffee", "fish", "chips", "cake",
                "apple", "banana", "burger", "cheese", "chocolate", "juice", "cook", "help", "buy",
                "sell", "work", "study", "visit", "travel", "catch", "miss", "wake up", "brush teeth",
                "get dressed", "wash", "tidy", "busy", "tired", "bored", "exciting", "interesting",
                "delicious", "heavy", "light", "yesterday", "today", "tomorrow", "morning", "afternoon",
                "evening", "night", "early", "late"],
            4: ["Hari Raya", "Chinese New Year", "Deepavali", "Christmas", "Gawai", "Kaamatan",
                "ang pow", "lemang", "mooncake", "gift", "card", "parade", "costume", "fireworks",
                "apple", "banana", "burger", "cake", "cheese", "chocolate", "fish", "milk", "water",
                "juice", "pizza", "sandwich", "recycle", "save", "protect", "celebrate", "invite",
                "decorate", "prepare", "design", "invent", "discover", "reduce", "reuse", "modern",
                "traditional", "digital", "useful", "dangerous", "safe", "carefully", "quickly",
                "slowly", "loudly", "quietly", "usually", "sometimes", "always", "never"],
            5: ["breakfast", "lunch", "dinner", "rice", "noodles", "bread", "egg", "meat", "soup",
                "vegetable", "fruit", "water", "milk", "tea", "coffee", "fish", "chips", "cake",
                "apple", "banana", "burger", "cheese", "chocolate", "Hari Raya", "Christmas", "gift",
                "card", "parade", "costume", "fireworks", "exercise", "medicine", "fever", "cough",
                "flu", "healthy", "unhealthy", "diet", "stomach ache", "headache", "plaster",
                "explore", "discover", "plan", "decide", "imagine", "invent", "design", "compare",
                "suggest", "recommend", "crowded", "deserted", "ancient", "modern", "fantastic",
                "terrible", "exhausting", "relaxing", "extremely", "quite", "slightly", "popular",
                "expensive", "dangerous"],
            6: ["breakfast", "lunch", "dinner", "rice", "noodles", "bread", "egg", "meat", "soup",
                "vegetable", "fruit", "water", "milk", "fish", "cake", "apple", "banana", "burger",
                "cheese", "chocolate", "environment", "conservation", "endangered", "species", "charity",
                "volunteer", "community", "responsibility", "project", "goal", "pollution", "climate",
                "celebrate", "invite", "decorate", "prepare", "design", "invent", "discover",
                "achieve", "accomplish", "contribute", "participate", "support", "organize", "manage",
                "evaluate", "analyze", "investigate", "design", "produce", "successful", "responsible",
                "independent", "confident", "creative", "reliable", "global", "however", "furthermore",
                "nevertheless", "consequently", "meanwhile", "similarly", "efficient"],
        },
    },
    # Week 5
    {
        "name": "Travel & Health",
        "words": {
            1: ["bus", "train", "car", "boat", "plane", "bicycle", "taxi", "bike", "go", "stop",
                "move", "fast", "slow", "red", "blue", "green", "yellow", "big", "small", "tall",
                "happy", "sad", "hot", "cold", "good", "bad", "one", "two", "three", "four", "five",
                "six", "seven", "eight", "nine", "ten"],
            2: ["bus", "train", "car", "boat", "plane", "bicycle", "taxi", "bike", "go", "stop", "move",
                "visit", "travel", "catch", "miss", "ride", "walk", "fly", "throw", "clean", "wash",
                "cook", "help", "open", "close", "draw", "paint", "fast", "slow", "loud", "quiet",
                "happy", "sad", "good", "bad", "nice", "funny", "tired", "hungry", "thirsty", "scared",
                "angry", "red", "blue", "yellow", "green", "black", "white", "brown"],
            3: ["bus", "train", "car", "boat", "plane", "bicycle", "motorcycle", "helicopter", "lorry",
                "taxi", "underground", "ship", "go", "stop", "visit", "travel", "catch", "miss",
                "ride", "walk", "fly", "move", "fast", "slow", "busy", "tired", "bored", "exciting",
                "interesting", "delicious", "heavy", "light", "yesterday", "today", "tomorrow",
                "morning", "afternoon", "evening", "night", "early", "late"],
            4: ["computer", "laptop", "phone", "camera", "television", "internet", "email", "message",
                "website", "screen", "keyboard", "mouse", "search", "click", "type", "send", "go",
                "stop", "move", "fast", "slow", "recycle", "save", "protect", "celebrate", "invite",
                "decorate", "prepare", "design", "invent", "discover", "reduce", "reuse", "modern",
                "traditional", "digital", "useful", "dangerous", "safe", "carefully", "quickly",
                "slowly", "loudly", "quietly", "usually", "sometimes", "always", "never"],
            5: ["passport", "ticket", "luggage", "hotel", "map", "souvenir", "journey", "destination",
                "adventure", "tourist", "suitcase", "flight", "camp", "exercise", "medicine", "symptom",
                "fever", "cough", "flu", "dentist", "hospital", "healthy", "unhealthy", "diet",
                "stomach ache", "headache", "plaster", "go", "stop", "visit", "travel", "catch", "miss",
                "ride", "walk", "fly", "explore", "discover", "plan", "decide", "imagine", "invent",
                "design", "compare", "suggest", "recommend", "survive", "achieve", "protect",
                "crowded", "deserted", "ancient", "modern", "fantastic", "terrible", "exhausting",
                "relaxing", "extremely", "quite", "slightly", "popular", "expensive", "dangerous"],
            6: ["passport", "ticket", "luggage", "hotel", "map", "souvenir", "journey", "destination",
                "adventure", "tourist", "suitcase", "flight", "camp", "environment", "conservation",
                "endangered", "species", "charity", "volunteer", "community", "responsibility", "project",
                "goal", "pollution", "climate", "go", "stop", "visit", "travel", "catch", "miss",
                "achieve", "accomplish", "contribute", "participate", "support", "organize", "manage",
                "evaluate", "analyze", "investigate", "design", "produce", "successful", "responsible",
                "independent", "confident", "creative", "reliable", "global", "however", "furthermore",
                "nevertheless", "consequently", "meanwhile", "similarly", "efficient"],
        },
    },
    # Week 6
    {
        "name": "World of Knowledge: Science & Nature",
        "words": {
            1: ["sun", "moon", "star", "sky", "cloud", "rain", "wind", "tree", "flower", "grass",
                "leaf", "seed", "bird", "cat", "dog", "fish", "frog", "horse", "duck", "mouse",
                "spider", "snake", "lizard", "run", "jump", "swim", "walk", "fly", "climb", "big",
                "small", "tall", "short", "hot", "cold", "red", "blue", "yellow", "green"],
            2: ["sun", "rain", "wind", "tree", "flower", "grass", "park", "sea", "beach", "snow", "sky",
                "weather", "cat", "dog", "bird", "fish", "duck", "mouse", "spider", "frog", "horse",
                "fly", "catch", "throw", "climb", "skate", "skip", "clean", "wash", "cook", "help",
                "open", "close", "draw", "paint", "big", "small", "long", "short", "clean", "dirty",
                "new", "old", "loud", "quiet", "happy", "sad", "hot", "cold", "good", "bad", "nice",
                "funny", "tired", "hungry", "scared", "angry"],
            3: ["sun", "moon", "star", "sky", "cloud", "rain", "wind", "tree", "flower", "grass", "park",
                "sea", "beach", "school", "hospital", "library", "zoo", "supermarket", "cafe", "cinema",
                "swimming pool", "plant", "seed", "water", "soil", "air", "buy", "sell", "help", "work",
                "study", "visit", "travel", "catch", "miss", "wake up", "brush teeth", "get dressed",
                "wash", "tidy", "cook", "skate", "busy", "tired", "bored", "exciting", "interesting",
                "delicious", "heavy", "light", "morning", "afternoon", "evening", "night", "early",
                "late"],
            4: ["sun", "moon", "star", "sky", "cloud", "rain", "wind", "tree", "flower", "grass", "plant",
                "seed", "soil", "water", "air", "pollution", "recycle", "bin", "plastic", "paper",
                "glass", "rubbish", "energy", "nature", "forest", "save", "protect", "search", "click",
                "type", "send", "recycle", "reduce", "reuse", "celebrate", "invite", "decorate",
                "prepare", "design", "invent", "discover", "modern", "traditional", "digital", "useful",
                "dangerous", "safe", "carefully", "quickly", "slowly", "loudly", "quietly", "usually",
                "sometimes", "always", "never"],
            5: ["planet", "star", "moon", "sun", "rocket", "astronaut", "galaxy", "space", "telescope",
                "universe", "alien", "satellite", "tree", "flower", "grass", "plant", "seed", "soil",
                "water", "air", "pollution", "recycle", "bin", "plastic", "paper", "glass", "rubbish",
                "energy", "nature", "forest", "exercise", "medicine", "fever", "cough", "flu", "dentist",
                "hospital", "healthy", "unhealthy", "diet", "stomach ache", "headache", "plaster",
                "explore", "discover", "plan", "decide", "imagine", "invent", "design", "compare",
                "suggest", "recommend", "survive", "achieve", "protect", "crowded", "deserted", "ancient",
                "modern", "fantastic", "terrible", "exhausting", "relaxing", "extremely", "quite",
                "slightly", "popular", "expensive", "dangerous"],
            6: ["environment", "conservation", "endangered", "species", "charity", "volunteer", "community",
                "responsibility", "project", "goal", "pollution", "climate", "sun", "moon", "star", "sky",
                "tree", "flower", "grass", "plant", "seed", "water", "air", "recycle", "bin", "plastic",
                "paper", "glass", "rubbish", "energy", "nature", "forest", "achieve", "accomplish",
                "contribute", "participate", "support", "organize", "manage", "evaluate", "analyze",
                "investigate", "design", "produce", "invention", "discovery", "experiment", "laboratory",
                "technology", "innovation", "automatic", "digital", "machine", "screen", "system",
                "network", "successful", "responsible", "independent", "confident", "creative", "reliable",
                "global", "however", "furthermore", "nevertheless", "consequently", "meanwhile",
                "similarly", "efficient"],
        },
    },
]

YEAR_NAMES = {1:"Year 1", 2:"Year 2", 3:"Year 3", 4:"Year 4", 5:"Year 5", 6:"Year 6"}

# Prompt-size constants (keep LLM prompts lean)
FIVE_OR_SIX   = "6"        # "Generate 6 sections..."
SIX_SHORT_STORIES = "6"    # "Write 6 bedtime stories..."
EXAMPLE_WORDS = "8 to 12"  # "include 8 to 12 of the week's target words"

# ── LLM helpers ────────────────────────────────────────────────────────────────
def call_llm(system_prompt: str, user_prompt: str) -> str:
    """Generate JSON content via the project's headless opencode adapter.

    Replaces the old Hermes ``hermes_tools.model_tools`` call.
    """
    from cronjobs import llm
    return llm.generate(system_prompt, user_prompt, project_dir=str(PROJECT_ROOT))


# ── Telegram helpers ────────────────────────────────────────────────────────────
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT_ID   = os.environ.get("TG_CHAT_ID", "")
TG_THREAD_ID = os.environ.get("TG_THREAD_ID", "")

# Quiz polls are non-anonymous by default so the teacher can see who answered;
# set TG_POLL_ANONYMOUS=1 to make pupil answers anonymous.
TG_POLL_ANONYMOUS = os.environ.get("TG_POLL_ANONYMOUS", "").strip().lower() in {
    "1", "true", "yes", "on"}

# Per-class Telegram topic routing. Each year posts to its own thread so a Year 3
# parent never sees a Year 5 worksheet. A missing year topic is treated as
# unconfigured — NOT as "post to the group main chat" — so class content can
# never spill into the group's main conversation.
#   TG_TOPIC_Y1=2 TG_TOPIC_Y2=3 ... TG_TOPIC_Y6=7
TG_TOPIC_BY_YEAR = {
    y: os.environ.get(f"TG_TOPIC_Y{y}", "").strip() for y in range(1, 7)
}


def _topic_for_year(year: int) -> str:
    """Topic id for a specific year. Empty = not configured for that class."""
    return TG_TOPIC_BY_YEAR.get(year, "")


def telegram_send_text(text: str) -> dict:
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print(f"[TG] not configured — would send:\n{text[:500]}")
        return {}
    from cronjobs import telegram
    return telegram.send_text(
        TG_BOT_TOKEN, TG_CHAT_ID, TG_THREAD_ID or None, text)

def telegram_send_document(file_path: Path, caption: str = "",
                           topic_id: str = "") -> dict:
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print(f"[TG] not configured — would send document: {file_path.name}")
        return {}
    from cronjobs import telegram
    thread = (topic_id or TG_THREAD_ID or "").strip() or None
    return telegram.send_document(
        TG_BOT_TOKEN, TG_CHAT_ID, thread, file_path, caption)


def telegram_send_video(file_path: Path, caption: str = "",
                        topic_id: str = "") -> dict:
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print(f"[TG] not configured — would send video: {file_path.name}")
        return {}
    from cronjobs import telegram
    thread = (topic_id or TG_THREAD_ID or "").strip() or None
    return telegram.send_video(
        TG_BOT_TOKEN, TG_CHAT_ID, thread, file_path, caption)


def telegram_send_text_to(text: str, topic_id: str = "") -> dict:
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print(f"[TG] not configured — would send text:\n{text[:300]}")
        return {}
    from cronjobs import telegram
    thread = (topic_id or TG_THREAD_ID or "").strip() or None
    return telegram.send_text(TG_BOT_TOKEN, TG_CHAT_ID, thread, text)


def telegram_send_poll(question: str, options: list[str], correct_index: int,
                       topic_id: str = "") -> dict:
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print(f"[TG] not configured — would send poll: {question!r} "
              f"options={options} correct={correct_index}")
        return {}
    from cronjobs import telegram
    thread = (topic_id or TG_THREAD_ID or "").strip() or None
    return telegram.send_poll(
        TG_BOT_TOKEN, TG_CHAT_ID, thread, question, options, correct_index,
        anonymous=TG_POLL_ANONYMOUS)


# ── Narration + slideshow video (bedtime stories) ──────────────────────────────
DEFAULT_TTS_VOICE = "en-GB-SoniaNeural"
DEFAULT_TTS_RATE = "-10%"
TITLE_CARD_FONT = "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"
VIDEO_SIZE = (1280, 720)

# Wikimedia Commons: freely-licensed photos, no API key required.
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
COMMONS_UA = ("SJKC-PinMin-Cron/1.0 (educational children's stories; "
              "contact: sjkc-pin-min)")

# PIL needs plain RGB tuples; the reportlab YEAR_COLORS are for PDFs.
YEAR_COLORS_RGB = {
    1: (79, 195, 247),
    2: (129, 199, 132),
    3: (255, 183, 77),
    4: (229, 115, 115),
    5: (186, 104, 200),
    6: (77, 208, 225),
}


def _http_get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": COMMONS_UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read()


def _tts_reconnect(attempt: int) -> None:
    """Between TTS attempts, move to a VPN exit the endpoint will accept.

    The free edge-tts endpoint answers 403 from some exits, so a failed attempt
    is often fixed by re-running the VPN preflight.
    """
    print(f"[sjkc_english] TTS attempt {attempt} failed — re-running VPN preflight")
    try:
        from cronjobs import network
        network.ensure_vpn()
    except Exception as exc:  # noqa: BLE001 - best effort, never fatal
        print(f"[sjkc_english] VPN reconnect failed: {type(exc).__name__}: {exc}")
    time.sleep(2)


def synthesize_speech(text: str, out_path: Path, *,
                      voice: str = DEFAULT_TTS_VOICE,
                      rate: str = DEFAULT_TTS_RATE,
                      retries: int = 4,
                      on_retry=_tts_reconnect) -> list[dict]:
    """Narrate ``text`` to an MP3 and return its word timings.

    Timings are ``{"text", "start", "end"}`` in seconds relative to this clip.
    Retries across VPN exits because the free endpoint 403s from some of them.
    """
    import asyncio

    import edge_tts

    last_exc: Exception | None = None
    for attempt in range(1, max(1, retries) + 1):
        async def _go():
            comm = edge_tts.Communicate(text, voice, rate=rate,
                                        boundary="WordBoundary")
            buf = bytearray()
            words: list[dict] = []
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    buf += chunk["data"]
                elif chunk["type"] == "WordBoundary":
                    start = chunk["offset"] / 1e7
                    words.append({"text": chunk["text"], "start": start,
                                  "end": start + chunk["duration"] / 1e7})
            return bytes(buf), words

        try:
            data, words = asyncio.run(_go())
            if not data:
                raise RuntimeError("edge-tts returned no audio")
            Path(out_path).write_bytes(data)
            return words
        except Exception as exc:  # noqa: BLE001 - retry across VPN exits
            last_exc = exc
            print(f"[sjkc_english] TTS error (attempt {attempt}/{retries}): "
                  f"{type(exc).__name__}: {exc}")
            if attempt < retries and on_retry is not None:
                on_retry(attempt)
    raise RuntimeError(f"TTS failed after {retries} attempts: {last_exc}")


def _audio_duration(path: Path, *, ffprobe: str = "ffprobe") -> float:
    """Duration of a media file in seconds (0.0 when unavailable)."""
    try:
        proc = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, timeout=30)
        return float((proc.stdout or "").strip() or 0.0)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


def _close_cue(cues: list[dict], line: list[dict], start: float) -> None:
    if not line:
        return
    text = " ".join(str(w.get("text", "")).strip() for w in line).strip()
    if not text:
        return
    begin = float(line[0].get("start", 0.0)) + start
    end = float(line[-1].get("end", line[-1].get("start", 0.0))) + start
    cues.append({"start": max(0.0, begin), "end": end, "text": text})


def _words_to_cues(words: list[dict], start: float, *, max_chars: int = 42,
                   hold: float = 0.4) -> list[dict]:
    """Group word timings into short, non-overlapping caption cues.

    Cues are offset by ``start`` seconds; the final cue is held slightly longer
    so it does not blink away the instant the last word is spoken.
    """
    cues: list[dict] = []
    line: list[dict] = []
    length = 0
    for word in words:
        token = str(word.get("text", "")).strip()
        if not token:
            continue
        extra = len(token) + (1 if line else 0)
        if line and length + extra > max_chars:
            _close_cue(cues, line, start)
            line, length, extra = [], 0, len(token)
        line.append(word)
        length += extra
    _close_cue(cues, line, start)
    if cues:
        cues[-1]["end"] += hold
    for current, nxt in zip(cues, cues[1:]):
        if current["end"] > nxt["start"]:
            current["end"] = nxt["start"]
    return cues


def _srt_timestamp(seconds: float) -> str:
    ms = max(0, int(round(seconds * 1000)))
    hours, ms = divmod(ms, 3_600_000)
    minutes, ms = divmod(ms, 60_000)
    secs, ms = divmod(ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def build_srt(cues: list[dict]) -> str:
    blocks = []
    for i, cue in enumerate(cues, 1):
        blocks.append(f"{i}\n{_srt_timestamp(cue['start'])} --> "
                      f"{_srt_timestamp(cue['end'])}\n{cue['text']}\n")
    return "\n".join(blocks)


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _clean_html(value) -> str:
    text = _TAG_RE.sub("", str(value if value is not None else ""))
    for old, new in (("&amp;", "&"), ("&quot;", '"'), ("&#39;", "'"),
                     ("&lt;", "<"), ("&gt;", ">"), ("&nbsp;", " ")):
        text = text.replace(old, new)
    return _WS_RE.sub(" ", text).strip()


def _pick_commons_image(data: dict) -> dict | None:
    """Choose the first usable Commons search hit (raster image with a URL)."""
    pages = (data.get("query") or {}).get("pages") or {}
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        url = info.get("thumburl") or info.get("url")
        mime = str(info.get("mime") or "")
        if not url or not mime.startswith("image/") or mime == "image/svg+xml":
            continue
        meta = info.get("extmetadata") or {}
        return {
            "url": url,
            "title": _clean_html(page.get("title")),
            "artist": _clean_html((meta.get("Artist") or {}).get("value")),
            "license": _clean_html((meta.get("LicenseShortName") or {}).get("value")),
        }
    return None


def _cover_crop(img, size: tuple[int, int]):
    """Scale-and-centre-crop a PIL image to exactly ``size``."""
    from PIL import Image

    target_w, target_h = size
    width, height = img.size
    if width <= 0 or height <= 0:
        raise ValueError("empty image")
    scale = max(target_w / width, target_h / height)
    new_w = max(target_w, int(width * scale + 0.5))
    new_h = max(target_h, int(height * scale + 0.5))
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def _draw_attribution(img, credit: str):
    from PIL import ImageDraw, ImageFont

    if not credit:
        return img
    draw = ImageDraw.Draw(img, "RGBA")
    try:
        font = ImageFont.truetype(TITLE_CARD_FONT, 20)
    except Exception:  # noqa: BLE001
        font = ImageFont.load_default()
    width, height = img.size
    label = credit if len(credit) <= 110 else credit[:107] + "…"
    text_w = draw.textlength(label, font=font)
    bar_h = 34
    draw.rectangle([0, height - bar_h, width, height], fill=(0, 0, 0, 140))
    draw.text((max(10, width - text_w - 12), height - bar_h + 7), label,
              font=font, fill=(255, 255, 255))
    return img


def fetch_commons_image(keywords, out_path: Path, *,
                        get=_http_get, size: tuple[int, int] = VIDEO_SIZE,
                        timeout: int = 20) -> dict | None:
    """Download + crop + attribute a Commons photo for a scene.

    Returns ``{"url", "title", "artist", "license"}`` on success, else ``None``.
    Never raises for network faults (the caller falls back to a local card).
    """
    import io

    from PIL import Image

    query = " ".join(str(k) for k in (keywords or []) if str(k).strip())
    if not query:
        return None
    params = urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": query, "gsrnamespace": "6", "gsrlimit": "6",
        "prop": "imageinfo", "iiprop": "url|mime|extmetadata",
        "iiurlwidth": str(size[0]),
    })
    try:
        payload = json.loads(get(f"{COMMONS_API}?{params}", timeout))
        pick = _pick_commons_image(payload)
        if not pick:
            return None
        raw = get(pick["url"], timeout)
        img = _cover_crop(Image.open(io.BytesIO(raw)).convert("RGB"), size)
        credit = " · ".join(x for x in [pick.get("artist"),
                                        pick.get("license")] if x)
        credit = f"Photo: {credit} / Wikimedia Commons" if credit else \
                 "Photo: Wikimedia Commons"
        _draw_attribution(img, credit).save(out_path, "PNG")
        return pick
    except Exception as exc:  # noqa: BLE001 - fall back to a local card
        print(f"[sjkc_english] image fetch failed for {query!r}: "
              f"{type(exc).__name__}: {exc}")
        return None


def make_fallback_card(text: str, out_path: Path, *,
                       size: tuple[int, int] = VIDEO_SIZE,
                       year: int | None = None) -> Path:
    """Draw a simple year-coloured scene when no Commons photo is available."""
    from PIL import Image, ImageDraw, ImageFont

    base = YEAR_COLORS_RGB.get(year, (21, 101, 192))
    img = Image.new("RGB", size, base)
    draw = ImageDraw.Draw(img)
    width, height = size
    draw.rectangle([0, int(height * 0.62), width, height],
                   fill=tuple(min(255, c + 24) for c in base))
    draw.ellipse([width - 260, 60, width - 100, 220], fill=(255, 236, 179))
    try:
        font = ImageFont.truetype(TITLE_CARD_FONT, 34)
    except Exception:  # noqa: BLE001
        font = ImageFont.load_default()
    label = (text or "").strip()[:70]
    if label:
        text_w = draw.textlength(label, font=font)
        draw.text((max(30, (width - text_w) / 2), int(height * 0.45)), label,
                  font=font, fill=(255, 255, 255))
    img.save(out_path)
    return Path(out_path)


def normalize_scenes(raw, story: str = "") -> list[dict]:
    """Validate the LLM's scenes (or fall back to a single whole-story scene)."""
    scenes: list[dict] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or item.get("story") or "").strip()
            if not text:
                continue
            keywords = [str(k).strip() for k in (item.get("keywords") or [])
                        if str(k).strip()]
            scenes.append({"text": text, "keywords": keywords[:4]})
    if not scenes and str(story or "").strip():
        scenes = [{"text": str(story).strip(), "keywords": []}]
    if not scenes:
        raise ValueError("story has no usable scenes")
    return scenes


def _write_concat_file(entries: list[tuple[Path, float | None]],
                       path: Path) -> Path:
    timed = any(duration is not None for _, duration in entries)
    lines: list[str] = []
    for file_path, duration in entries:
        lines.append(f"file '{Path(file_path).as_posix()}'")
        if duration is not None:
            lines.append(f"duration {max(0.04, float(duration)):.3f}")
    if timed and entries:
        lines.append(f"file '{Path(entries[-1][0]).as_posix()}'")
    path.write_text("\n".join(lines) + "\n")
    return path


def build_story_video_command(images_txt: Path, audio_txt: Path, srt: Path,
                              out_path: Path, *, fps: int = 25,
                              ffmpeg: str = "ffmpeg") -> list[str]:
    style = ("FontName=DejaVu Sans,FontSize=22,PrimaryColour=&H00FFFFFF,"
             "OutlineColour=&HA0000000,Outline=2,Shadow=0,MarginV=36")
    vf = f"subtitles='{Path(srt).as_posix()}':force_style='{style}'"
    return [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(images_txt),
        "-f", "concat", "-safe", "0", "-i", str(audio_txt),
        "-vf", vf,
        "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
        "-r", str(fps), "-c:a", "aac", "-b:a", "96k",
        "-shortest", "-movflags", "+faststart",
        str(out_path),
    ]


def _default_ffmpeg_runner(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed rc={proc.returncode}: "
            f"{(proc.stderr or proc.stdout or '').strip()[-500:]}")


def build_story_video(scenes, title: str, year: int, week: int, theme: str,
                      out_path: Path, *, tts=synthesize_speech,
                      fetch_image=fetch_commons_image,
                      make_card=make_fallback_card,
                      run=_default_ffmpeg_runner, ffmpeg: str = "ffmpeg",
                      hold: float = 0.4) -> Path:
    """Build a narrated photo-slideshow MP4 with burned-in subtitles.

    Each scene gets its own TTS clip (for exact slide/subtitle alignment) and a
    Commons photo (or a local fallback card); ffmpeg concatenates images and
    narration and burns the generated ``.srt`` in.
    """
    out_path = Path(out_path)
    work = out_path.parent / f".{out_path.stem}"
    work.mkdir(parents=True, exist_ok=True)
    scenes = normalize_scenes(scenes)

    image_entries: list[tuple[Path, float]] = []
    audio_entries: list[tuple[Path, None]] = []
    cues: list[dict] = []
    credits: list[str] = []
    clock = 0.0

    for i, scene in enumerate(scenes, 1):
        audio_path = work / f"scene{i}.mp3"
        words = tts(scene["text"], audio_path) or []
        seg = (float(words[-1].get("end", 0.0)) + hold) if words else \
              _audio_duration(audio_path)
        seg = max(0.5, seg)
        cues.extend(_words_to_cues(words, clock, hold=hold))
        clock += seg

        img_path = work / f"scene{i}.png"
        got = fetch_image(scene.get("keywords") or [], img_path)
        if not got:
            make_card(scene["text"], img_path, year=year)
        else:
            credit = " · ".join(x for x in [got.get("artist"),
                                            got.get("license")] if x)
            credits.append(f"{got.get('title', '')} ({credit})")
        image_entries.append((img_path, seg))
        audio_entries.append((audio_path, None))

    images_txt = _write_concat_file(image_entries, work / "images.txt")
    audio_txt = _write_concat_file(audio_entries, work / "audio.txt")
    srt_path = work / "captions.srt"
    srt_path.write_text(build_srt(cues))
    if credits:
        print("[sjkc_english] image credits: " + "; ".join(credits[:8]))
    run(build_story_video_command(images_txt, audio_txt, srt_path, out_path,
                                  ffmpeg=ffmpeg))
    return out_path


# ── Telegram quiz-poll normalization ───────────────────────────────────────────
_OPTION_LABEL_RE = re.compile(r"^\s*[A-Ja-j][\.\)\:\-]\s+")


def _strip_option_label(option) -> str:
    return _OPTION_LABEL_RE.sub("", str(option)).strip()


def _answer_index(answer, num_options: int) -> int | None:
    """Map an answer letter (A/B/C) or 0-based index to an option index."""
    if isinstance(answer, bool) or answer is None:
        return None
    if isinstance(answer, int):
        return answer if 0 <= answer < num_options else None
    text = str(answer).strip()
    if not text:
        return None
    letter = text[0].upper()
    if letter in "ABCDEFGHIJ" and (len(text) == 1 or not text[1].isalnum()
                                   or text[1] in ".)](: -"):
        idx = ord(letter) - ord("A")
        return idx if idx < num_options else None
    if text.isdigit():
        value = int(text)
        return (value - 1) if 1 <= value <= num_options else None
    return None


def normalize_questions(raw, *, count: int = 3) -> list[dict]:
    """Validate/normalize LLM questions into Telegram quiz-poll dicts.

    Returns a list of ``{"q", "options", "correct"}`` with option labels
    stripped and text truncated to Telegram's limits. Raises ``ValueError``
    unless exactly ``count`` usable questions are produced.
    """
    if not isinstance(raw, list):
        raise ValueError("questions must be a list")
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        question = str(item.get("q") or item.get("question") or "").strip()
        options = [_strip_option_label(o) for o in (item.get("options") or [])]
        options = [o for o in options if o][:10]
        correct = _answer_index(item.get("answer"), len(options))
        if not question or len(options) < 2 or correct is None:
            continue
        out.append({"q": question[:300],
                    "options": [o[:100] for o in options],
                    "correct": correct})
    if len(out) != count:
        raise ValueError(
            f"expected {count} usable questions, got {len(out)}")
    return out


# ── PDF helpers (reportlab) ────────────────────────────────────────────────────
# Palette — colour per year for easy visual separation inside a combined PDF.
YEAR_COLORS = {
    1: colors.HexColor("#4FC3F7"),  # light blue
    2: colors.HexColor("#81C784"),  # green
    3: colors.HexColor("#FFB74D"),  # orange
    4: colors.HexColor("#E57373"),  # red
    5: colors.HexColor("#BA68C8"),  # purple
    6: colors.HexColor("#4DD0E1"),  # cyan
}
HEADER_BG   = colors.HexColor("#1565C0")   # dark blue header bar
ANSWER_BG   = colors.HexColor("#F5F5F5")   # light grey answer section
DARK_TEXT   = colors.HexColor("#1A1A1A")
MEDIUM_TEXT = colors.HexColor("#455A64")
SECTION_RULE = colors.HexColor("#CFD8DC")

PAGE_W, PAGE_H = A4
LM = RM = 20*mm
TM = 25*mm
BM = 18*mm
CONTENT_W = PAGE_W - LM - RM

def _logo_image():
    if SCHOOL_LOGO.exists():
        from reportlab.platypus import Image as RLImage
        try:
            return RLImage(str(SCHOOL_LOGO), width=30*mm, height=10*mm)
        except Exception:
            pass
    return None

def _styles():
    s = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=s["Title"], fontSize=15,
                                textColor=HEADER_BG, spaceAfter=2*mm,
                                alignment=1, fontName="Helvetica-Bold"),
        "subtitle": ParagraphStyle("subtitle", parent=s["Normal"], fontSize=9,
                                   textColor=MEDIUM_TEXT, spaceAfter=3*mm,
                                   alignment=1, fontName="Helvetica"),
        "year_label": ParagraphStyle("year_label", fontSize=11,
                                      textColor=colors.white, fontName="Helvetica-Bold",
                                      spaceAfter=0, spaceBefore=0),
        "section_title": ParagraphStyle("section_title", fontSize=10,
                                         textColor=colors.white, fontName="Helvetica-Bold",
                                         spaceAfter=0, spaceBefore=0),
        "body": ParagraphStyle("body", parent=s["Normal"], fontSize=9.5,
                                textColor=DARK_TEXT, fontName="Helvetica",
                                leading=13, spaceAfter=2*mm),
        "instruction": ParagraphStyle("instruction", parent=s["Normal"], fontSize=8.5,
                                       textColor=MEDIUM_TEXT, fontName="Helvetica-Oblique",
                                       spaceAfter=2*mm),
        "answer": ParagraphStyle("answer", parent=s["Normal"], fontSize=9,
                                  textColor=DARK_TEXT, fontName="Helvetica",
                                  leading=13, leftIndent=8),
    }

def _header_block(story, doc, styles, title, subtitle, level_labels=None):
    """Top matter: logo + title + subtitle. Returns y-space used."""
    if _logo_image():
        story.append(_logo_image())
        story.append(Spacer(1, 4*mm))
    story.append(Paragraph(title, styles["title"]))
    story.append(Paragraph(subtitle, styles["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=HEADER_BG,
                             spaceAfter=4*mm))
    if level_labels:
        lbl_data = [[Paragraph(lbl, styles["year_label"]) for lbl in level_labels]]
        tbl = Table(lbl_data, colWidths=[CONTENT_W/len(level_labels)]*len(level_labels))
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), HEADER_BG),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING",   (0,0), (-1,-1), 4),
            ("RIGHTPADDING",  (0,0), (-1,-1), 4),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 3*mm))

def _year_separator(story, styles, year_label):
    data = [[Paragraph(year_label, styles["year_label"])]]
    tbl = Table(data, colWidths=[CONTENT_W])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), YEAR_COLORS[int(year_label.split()[-1])]),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 2*mm))

def _answer_section(story, styles, items):
    """Grey boxed answer key at the end of a year section."""
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("ANSWER KEY", styles["section_title"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=SECTION_RULE,
                             spaceAfter=2*mm))
    for i, ans in enumerate(items, 1):
        story.append(Paragraph(f"<b>{i}.</b> {ans}", styles["answer"]))


# ══════════════════════════════════════════════════════════════════════════════
#  CONTENT GENERATION PROMPTS
# ══════════════════════════════════════════════════════════════════════════════

def _homework_system_fmt(themes: list[dict]) -> str:
    return f"""\
You are an expert primary English teacher for Malaysian SJK(C) schools.
Curriculum: KSSR Semakan 2017 English (013), CEFR-aligned, DSKP-compliant.

TASK: Generate {FIVE_OR_SIX} sections of English homework exercises —
one section per year level (Year 1 to Year 6) — for this week's topic.

Each year section must use the week's target vocabulary (listed below per year)
and follow the KSSR year-level CEFR requirements.

WEEK TOPIC: {THEMES[0]["name"]}

OUTPUT FORMAT (return ONLY valid JSON, no other text):
{{
  "year1": {{
    "vocab_match": [{{"word": "...", "match": "..."}}, ...],
    "fill_blank": [{{"sentence": "The ___ is red.", "answer": "apple"}}, ...],
    "write_sentence": [{{"prompt": "Use 'run' in a sentence about the beach.",
                            "answer": "I can run on the beach."}}, ...],
    "reading_passage": "...",
    "comprehension_qa": [{{"question": "...", "answer": "..."}}, ...]
  }},
  "year2": {{ ... same structure ... }},
  "year3": {{ ... same structure ... }},
  "year4": {{ ... same structure ... }},
  "year5": {{ ... same structure ... }},
  "year6": {{ ... same structure ... }}
}}

YEAR-LEVEL REQUIREMENTS:
- Year 1 (pre-A1): Very short, picture-supported items. 20-30 words per text.
  Use simple words from the Year 1 word list. 2 vocab matches, 2 fill-in-blanks,
  2 write-sentences, 1 short reading passage (20-30 words), 2 comprehension Qs.
- Year 2 (A1 low): Short simple sentences, familiar topics, visual clues. 30-40 words.
  3 vocab matches, 2 fill-in-blanks, 2 write-sentences, 1 short reading (30-40 words),
  2 comprehension Qs.
- Year 3 (A1 mid): Short simple texts, 40-60 words. 3 vocab matches, 3 fill-in-blanks,
  2 write-sentences, 1 reading passage (40-60 words), 3 comprehension Qs.
- Year 4 (A1+): 1 short text 50-80 words. 3 vocab matches, 3 fill-in-blanks,
  3 write-sentences, 1 reading (50-80 words), 3 comprehension Qs.
- Year 5 (A2 low): 2 paragraphs, 60-100 words total. 4 vocab matches, 3 fill-in-blanks,
  3 write-sentences, 1 reading (60-100 words), 4 comprehension Qs.
- Year 6 (A2 mid): 2 paragraphs, 80-120 words total. 4 vocab matches, 3 fill-in-blanks,
  3 write-sentences, 1 reading (80-120 words), 4 comprehension Qs.

=== WEEK TARGET VOCABULARY (use these words; add others from the same theme ONLY if needed) ===
""" + "\n".join(
    f"Year {y}: {', '.join(WORDS)}" for y, WORDS in enumerate(themes[0]["words"].values(), 1)
)


def _homework_user_fmt(themes: list[dict], week_num: int) -> str:
    return f"""\
Generate this week's homework (Week {week_num}).

WEEK TOPIC: {themes[0]['name']}

IMPORTANT RULES:
1. Use ONLY the week's target vocabulary listed in the system prompt.
2. Exercises must be age-appropriate: short sentences for Year 1-2, longer for Year 5-6.
3. Reading passages must be original (not copied from any textbook).
4. All comprehension answers must be directly stated in the passage.
5. For fill-in-the-blank: leave the blank represented by "___" in the sentence.
6. Output must be valid JSON. No markdown formatting around the JSON.
7. NO extra fields beyond the structure shown in the system prompt.
8. Each year section must have ALL 5 sub-sections (vocab_match, fill_blank,
   write_sentence, reading_passage, comprehension_qa).
"""


def _story_system_fmt(themes: list[dict]) -> str:
    return f"""\
You are a children's story writer specialising in gentle bedtime stories
for Malaysian SJK(C) primary school pupils (Year 1 to Year 6).

TASK: Write {SIX_SHORT_STORIES} bedtime stories — one for each year level
(Year 1 to Year 6) — using this week's target vocabulary.

WEEK TOPIC: {THEMES[0]["name"]}

OUTPUT FORMAT (return ONLY valid JSON, no other text):
{{
  "year1": {{
    "title": "A short, friendly title",
    "story": "The full story text — 80 to 120 words, simple sentences.",
    "scenes": [
      {{"text": "First 1-2 sentences of the story.",
        "keywords": ["beach", "children", "sandcastle"]}},
      {{"text": "Next 1-2 sentences of the story.",
        "keywords": ["dog", "ball"]}},
      {{"text": "Final 1-2 sentences of the story.",
        "keywords": ["sunset", "sea"]}}
    ],
    "questions": [
      {{"q": "Comprehension question about the story?",
        "options": ["option one", "option two", "option three"],
        "answer": "A"}},
      {{"q": "...", "options": ["...", "...", "..."], "answer": "B"}},
      {{"q": "...", "options": ["...", "...", "..."], "answer": "C"}}
    ]
  }},
  "year2": {{ "title": "...", "story": "...", "scenes": [ ... ], "questions": [ ...3... ] }},
  "year3": {{ "title": "...", "story": "...", "scenes": [ ... ], "questions": [ ...3... ] }},
  "year4": {{ "title": "...", "story": "...", "scenes": [ ... ], "questions": [ ...3... ] }},
  "year5": {{ "title": "...", "story": "...", "scenes": [ ... ], "questions": [ ...3... ] }},
  "year6": {{ "title": "...", "story": "...", "scenes": [ ... ], "questions": [ ...3... ] }}
}}

SCENE RULES (each scene becomes one picture + one subtitle block):
- Give 3 to 5 scenes per story (younger years: fewer, ~3).
- The scene "text" values, joined in order, MUST equal the "story" text.
- Each scene "text" is 1-2 complete sentences.
- "keywords" = 2-4 simple, common English nouns describing what a PHOTO of
  that scene would show (e.g. "beach", "duck", "bicycle", "cake", "sunset").
  Use concrete, easily-photographed things. NO character names, NO brand
  names, NO abstract or scary words.

WORD COUNT TARGETS (include {EXAMPLE_WORDS} of the week's target words naturally):
- Year 1: 80-120 words. Simple sentences (5-8 words each). Past simple or present simple.
- Year 2: 100-150 words. Short paragraphs. Use adjectives (big, small, happy, sad, etc.).
- Year 3: 120-180 words. Use connectives (and, then, but, so). Simple past tense.
- Year 4: 150-200 words. 2-3 short paragraphs. Use adjectives and time words (first, then, after).
- Year 5: 180-250 words. 3 paragraphs. Use connecting words (however, because, so, although).
- Year 6: 200-280 words. 3 paragraphs. Use linking words (however, furthermore, consequently).

STYLE RULES:
- Gentle, warm tone. No scary content.
- Each story should reference the week's topic naturally.
- End each story with a calm, positive sentence suitable for bedtime.
- Do NOT include the answer key or any educator notes in the story text.

QUESTION RULES (these become Telegram quiz polls, one per question):
- Exactly 3 questions per year. Each question has exactly 3 options.
- Questions test simple comprehension of that year's story.
- Exactly ONE option is correct; "answer" is the letter of the correct option
  ("A", "B" or "C") matching the option's position (A = first option).
- Options must be short (<= 80 characters), distinct, and clearly different.
- Do NOT prefix options with letters ("A.") — the position implies the letter.

=== WEEK TARGET VOCABULARY ===
""" + "\n".join(
    f"Year {y}: {', '.join(WORDS)}" for y, WORDS in enumerate(themes[0]["words"].values(), 1)
)


def _story_user_fmt(themes: list[dict], week_num: int) -> str:
    return f"""\
Write this week's bedtime stories (Week {week_num}).

WEEK TOPIC: {themes[0]['name']}

Write {SIX_SHORT_STORIES} stories — one per year (Year 1 to Year 6).
Follow the word counts and style rules in the system prompt.
Split each story into 3-5 scenes whose texts join back into the story, and give
each scene 2-4 simple photo keywords (see the scene rules).
Also give EXACTLY 3 comprehension questions per story (see the question rules).
OUTPUT: A single JSON object (as shown in the system prompt). No other text.
"""


def _quiz_system_fmt(themes: list[dict]) -> str:
    return f"""\
You are an expert primary English reading-assessment writer for Malaysian SJK(C)
schools. Curriculum: KSSR Semakan 2017 English (013), CEFR-aligned.

TASK: For each year level (Year 1 to Year 6), write ONE short original reading
text and THREE comprehension questions about it. The text is sent to the pupils
on Telegram, then the three questions are posted as Telegram quiz polls.

OUTPUT FORMAT (return ONLY valid JSON, no other text):
{{
  "year1": {{
    "reading": "Original reading text (20-30 words)...",
    "questions": [
      {{"q": "Comprehension question?",
        "options": ["option one", "option two", "option three"],
        "answer": "A"}},
      {{"q": "...", "options": ["...", "...", "..."], "answer": "B"}},
      {{"q": "...", "options": ["...", "...", "..."], "answer": "C"}}
    ]
  }},
  "year2": {{ "reading": "...", "questions": [ ...3... ] }},
  "year3": {{ "reading": "...", "questions": [ ...3... ] }},
  "year4": {{ "reading": "...", "questions": [ ...3... ] }},
  "year5": {{ "reading": "...", "questions": [ ...3... ] }},
  "year6": {{ "reading": "...", "questions": [ ...3... ] }}
}}

READING LENGTH BY YEAR (use the week's target vocabulary naturally):
- Year 1 (pre-A1): 20-30 words, very simple sentences.
- Year 2 (A1 low): 30-40 words.
- Year 3 (A1 mid): 40-60 words.
- Year 4 (A1+): 50-80 words.
- Year 5 (A2 low): 60-100 words.
- Year 6 (A2 mid): 80-120 words.

QUESTION RULES (these become Telegram quiz polls, one per question):
- Exactly 3 questions per year. Each question has exactly 3 options.
- Every answer must be directly stated or clearly inferable from the reading.
- Exactly ONE option is correct; "answer" is the letter of the correct option
  ("A", "B" or "C") matching the option's position (A = first option).
- Options must be short (<= 80 characters), distinct, and clearly different.
- Do NOT prefix options with letters ("A.") — the position implies the letter.
- Reading texts must be ORIGINAL (not copied from any textbook).

=== WEEK TARGET VOCABULARY (use these words where possible) ===
""" + "\n".join(
    f"Year {y}: {', '.join(WORDS)}" for y, WORDS in enumerate(themes[0]["words"].values(), 1)
)


def _quiz_user_fmt(themes: list[dict], week_num: int) -> str:
    return f"""\
Write this week's reading-and-questions quiz (Week {week_num}).

WEEK TOPIC: {themes[0]['name']}

For each year (Year 1 to Year 6): one original reading text and EXACTLY 3
comprehension questions (see the rules in the system prompt).
Use the week's target vocabulary where possible.

OUTPUT: A single JSON object (as shown in the system prompt). No other text.
No markdown formatting around the JSON.
"""


# ══════════════════════════════════════════════════════════════════════════════
#  PDF BUILDERS
# ══════════════════════════════════════════════════════════════════════════════

def build_homework_pdf(data: dict, week_num: int, output_path: Path, years=None):
    """Build a homework PDF. years=[1..6] (default) builds one combined sheet;
    years=[3] builds a Year 3-only sheet."""
    years = list(years) if years else list(range(1, 7))
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4, leftMargin=LM, rightMargin=RM,
        topMargin=TM, bottomMargin=BM,
        title=f"KSJ(C) Pin Min — English Homework Week {week_num}",
        author="KSJ(C) Pin Min English Dept",
    )
    styles = _styles()
    story = []
    level_labels = [YEAR_NAMES[y] for y in years]
    _header_block(story, doc, styles,
                  "KSSR English — Weekly Homework",
                  f"KSJ(C) Pin Min Bidor  |  Week {week_num}  |  Theme: {THEMES[week_num - 1]['name']}",
                  level_labels)

    for year in years:
        yd = data[f"year{year}"]
        _year_separator(story, styles, YEAR_NAMES[year])

        # ── Part A: Vocabulary Matching ──────────────────────────────────────
        vm = yd.get("vocab_match", [])
        if vm:
            story.append(Paragraph("A. Vocabulary Matching", styles["section_title"]))
            story.append(HRFlowable(width="100%", thickness=0.5, color=SECTION_RULE,
                                     spaceAfter=2*mm))
            story.append(Paragraph(
                "Match the word on the left with the correct meaning on the right.",
                styles["instruction"]))
            for item in vm[:5]:
                story.append(Paragraph(
                    f"<b>{item['word']}</b> &nbsp;&nbsp;───────&nbsp;&nbsp; {item['match']}",
                    styles["body"]))
            _answer_section(story, styles,
                            [f"{item['word']} — {item['match']}" for item in vm[:5]])

        # ── Part B: Fill in the Blanks ────────────────────────────────────────
        fb = yd.get("fill_blank", [])
        if fb:
            story.append(Spacer(1, 3*mm))
            story.append(Paragraph("B. Fill in the Blanks", styles["section_title"]))
            story.append(HRFlowable(width="100%", thickness=0.5, color=SECTION_RULE,
                                     spaceAfter=2*mm))
            story.append(Paragraph(
                "Fill in each blank with the correct word from the box.",
                styles["instruction"]))
            word_box = sorted(set(item["answer"] for item in fb[:4]))
            story.append(Paragraph(f"<b>Word Box:</b> {', '.join(word_box)}",
                                   styles["body"]))
            story.append(Spacer(1, 1*mm))
            for item in fb[:4]:
                story.append(Paragraph(f"<br/>{item['sentence']}", styles["body"]))
            _answer_section(story, styles,
                            [item["sentence"].replace("___", item["answer"])
                             for item in fb[:4]])

        # ── Part C: Write Sentences ───────────────────────────────────────────
        ws = yd.get("write_sentence", [])
        if ws:
            story.append(Spacer(1, 3*mm))
            story.append(Paragraph("C. Write Sentences", styles["section_title"]))
            story.append(HRFlowable(width="100%", thickness=0.5, color=SECTION_RULE,
                                     spaceAfter=2*mm))
            story.append(Paragraph(
                "Write a complete sentence using each word below.",
                styles["instruction"]))
            for item in ws[:3]:
                story.append(Paragraph(f"<b>{item['prompt']}</b>", styles["body"]))
                story.append(Paragraph(
                    "_________________________________________________________________________",
                    styles["body"]))
                story.append(Spacer(1, 1.5*mm))
            _answer_section(story, styles,
                            [item["answer"] for item in ws[:3]])

        # ── Part D: Reading Comprehension ─────────────────────────────────────
        rc = yd.get("reading_passage", "")
        cq = yd.get("comprehension_qa", [])
        if rc:
            story.append(Spacer(1, 3*mm))
            story.append(Paragraph("D. Reading Comprehension", styles["section_title"]))
            story.append(HRFlowable(width="100%", thickness=0.5, color=SECTION_RULE,
                                     spaceAfter=2*mm))
            story.append(Paragraph("<b>Read the passage below:</b>",
                                   styles["instruction"]))
            story.append(Paragraph(rc, styles["body"]))
            story.append(Spacer(1, 1*mm))
            for q in cq[:3]:
                story.append(Paragraph(f"<b>Q:</b> {q['question']}",
                                       styles["body"]))
                story.append(Paragraph("□ A. _______   □ B. _______   □ C. _______",
                                       styles["body"]))
            _answer_section(story, styles,
                            [f"Q: {q['question']}  →  Answer: {q['answer']}"
                             for q in cq[:3]])

        story.append(Spacer(1, 5*mm))
        story.append(HRFlowable(width="100%", thickness=0.3, color=colors.grey,
                                 spaceAfter=3*mm))

    doc.build(story)
    return output_path


def _is_direct_chat() -> bool:
    return not TG_CHAT_ID.startswith("-")


def _topic_or_skip(year: int, task: str) -> str | None:
    """Topic for a year, or None when the year must be skipped.

    A missing year topic in a group means "skip" — never the group main chat.
    In a direct chat (dev/testing) an empty topic is allowed.
    """
    topic = _topic_for_year(year)
    if not topic and not _is_direct_chat():
        print(f"[sjkc_english] Year {year} SKIPPED — no TG_TOPIC_Y{year} set, "
              f"refusing to post {task} to the group main chat.")
        return None
    return topic


def _deliver_polls(questions: list[dict], topic: str) -> int:
    """Post quiz polls for a year. Returns how many were accepted."""
    ok = 0
    for i, q in enumerate(questions, 1):
        try:
            result = telegram_send_poll(q["q"], q["options"], q["correct"], topic)
        except Exception as exc:  # noqa: BLE001 - one poll must not stop the rest
            print(f"[sjkc_english]   poll {i} error: {type(exc).__name__}: {exc}")
            continue
        if result.get("ok") or not TG_CHAT_ID:
            ok += 1
        else:
            print(f"[sjkc_english]   poll {i} NOT sent")
    return ok


def _homework_caption(year: int, week: int, theme: str) -> str:
    return (f"📚 SJKC Pin Min English Homework — {YEAR_NAMES[year]} — Week {week}\n"
            f"Theme: {theme}\n(KSSR DSKP aligned)")


def _story_caption(year: int, week: int, theme: str) -> str:
    return (f"📖 SJKC Pin Min Bedtime Story — {YEAR_NAMES[year]} — Week {week}\n"
            f"Theme: {theme}\n(Listen, then answer the 3 questions below 👇)")


def run_homework(content: dict, week: int, theme: str,
                 years_to_send: list[int], *, combined: bool = False):
    """One printable PDF per year (or one combined PDF for manual use)."""
    sent, failed = [], []
    if combined:
        path = OUTPUT_DIR / f"homework_week{week}.pdf"
        build_homework_pdf(content, week, path)
        print(f"[sjkc_english] combined PDF: {path} ({path.stat().st_size} bytes)")
        result = telegram_send_document(
            path, f"📚 SJKC Pin Min English Homework — Years 1-6 — Week {week}\n"
                  f"Theme: {theme}")
        return (["all"] if result.get("ok") else [], [] if result.get("ok") else ["all"])

    for year in years_to_send:
        if year not in range(1, 7):
            print(f"[sjkc_english] invalid year {year}, skipping")
            continue
        ypath = OUTPUT_DIR / f"homework_y{year}_week{week}.pdf"
        build_homework_pdf(content, week, ypath, years=[year])
        print(f"[sjkc_english] Year {year} PDF: {ypath} "
              f"({ypath.stat().st_size} bytes)")
        topic = _topic_or_skip(year, "worksheet")
        if topic is None:
            failed.append(year)
            continue
        try:
            result = telegram_send_document(ypath, _homework_caption(year, week, theme), topic)
        except Exception as exc:  # noqa: BLE001 - one year must not stop the rest
            result = {}
            print(f"[sjkc_english] Year {year} send error: "
                  f"{type(exc).__name__}: {exc}")
        if result.get("ok") or not TG_CHAT_ID:
            sent.append(year)
            print(f"[sjkc_english] Year {year} -> Telegram topic {topic}")
        else:
            failed.append(year)
            print(f"[sjkc_english] Year {year} Telegram: NOT sent "
                  f"(saved locally: {ypath})")
    return sent, failed


def run_story(content: dict, week: int, theme: str, years_to_send: list[int]):
    """Narrated photo-slideshow video + 3 comprehension polls per year."""
    sent, failed = [], []
    for year in years_to_send:
        if year not in range(1, 7):
            print(f"[sjkc_english] invalid year {year}, skipping")
            continue
        sd = content[f"year{year}"]
        topic = _topic_or_skip(year, "story")
        if topic is None:
            failed.append(year)
            continue
        try:
            questions = normalize_questions(sd.get("questions"))
        except ValueError as exc:
            print(f"[sjkc_english] Year {year} question problem: {exc}")
            questions = []

        story_text = str(sd.get("story") or "").strip()
        try:
            scenes = normalize_scenes(sd.get("scenes"), story_text)
        except ValueError as exc:
            print(f"[sjkc_english] Year {year} story problem: {exc}")
            scenes = []
        if not story_text:
            story_text = "\n\n".join(s["text"] for s in scenes)

        video_ok = False
        vpath = OUTPUT_DIR / f"story_y{year}_week{week}.mp4"
        try:
            if not scenes:
                raise ValueError("no usable scenes")
            print(f"[sjkc_english] Year {year} narrating + building video …")
            build_story_video(scenes, sd.get("title", ""), year, week, theme,
                              vpath)
            print(f"[sjkc_english] Year {year} video: {vpath.name} "
                  f"({vpath.stat().st_size} bytes)")
            result = telegram_send_video(
                vpath, _story_caption(year, week, theme), topic)
            video_ok = bool(result.get("ok")) or not TG_CHAT_ID
        except Exception as exc:  # noqa: BLE001 - degrade to a text story
            print(f"[sjkc_english] Year {year} video error: "
                  f"{type(exc).__name__}: {exc} — falling back to text story")
        if not video_ok:
            telegram_send_text_to(
                f"📖 {sd.get('title', '')}\n\n{story_text}", topic)

        polls_ok = _deliver_polls(questions, topic)
        if questions and polls_ok == len(questions):
            sent.append(year)
        else:
            failed.append(year)
    return sent, failed


def run_quiz(content: dict, week: int, theme: str, years_to_send: list[int]):
    """Reading text + 3 comprehension polls per year."""
    sent, failed = [], []
    for year in years_to_send:
        if year not in range(1, 7):
            print(f"[sjkc_english] invalid year {year}, skipping")
            continue
        qd = content[f"year{year}"]
        reading = str(qd.get("reading") or "").strip()
        if not reading:
            print(f"[sjkc_english] Year {year} has no reading text, skipping")
            failed.append(year)
            continue
        try:
            questions = normalize_questions(qd.get("questions"))
        except ValueError as exc:
            print(f"[sjkc_english] Year {year} question problem: {exc}")
            failed.append(year)
            continue
        topic = _topic_or_skip(year, "quiz")
        if topic is None:
            failed.append(year)
            continue

        heading = (f"📝 English Mini-Quiz — {YEAR_NAMES[year]} — Week {week}\n"
                   f"Theme: {theme}\n\nRead this:\n{reading}\n\n"
                   f"Now answer the 3 questions below 👇")
        try:
            telegram_send_text_to(heading, topic)
        except Exception as exc:  # noqa: BLE001
            print(f"[sjkc_english] Year {year} reading send error: "
                  f"{type(exc).__name__}: {exc}")

        polls_ok = _deliver_polls(questions, topic)
        if polls_ok == len(questions):
            sent.append(year)
            print(f"[sjkc_english] Year {year} -> reading + {polls_ok} polls "
                  f"in topic {topic}")
        else:
            failed.append(year)
    return sent, failed


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def _week_num() -> int:
    today = date.today()
    # Week 1 starts 2026-01-05 (first Monday of January 2026)
    start = date(2026, 1, 5)
    return ((today - start).days // 7) % 6 + 1


def _parse_content(llm_output: str) -> dict:
    """Parse the model's JSON (tolerating fences / a stray trailing ])."""
    cleaned = llm_output.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```", maxsplit=2)
        cleaned = parts[1] if len(parts) > 1 else cleaned
        if cleaned.lstrip().lower().startswith("json"):
            cleaned = cleaned.lstrip()[4:]
        cleaned = cleaned.strip()
    content = None
    try:
        content = json.loads(cleaned)
    except json.JSONDecodeError:
        stripped = cleaned.rstrip()
        # Free models occasionally emit one stray ']' before the closing '}'.
        for marker in ('"}]]', '}}}]'):
            if stripped.endswith(marker):
                try:
                    content = json.loads(stripped[:-2] + stripped[-1:])
                    break
                except json.JSONDecodeError:
                    pass
    if content is None:
        print(f"[sjkc_english] LLM returned non-JSON. First 500 chars:\n"
              f"{llm_output[:500]}")
        sys.exit(1)
    missing = [f"year{y}" for y in range(1, 7) if f"year{y}" not in content]
    if missing:
        print(f"[sjkc_english] LLM output missing year sections: {missing}. "
              f"Keys present: {sorted(content.keys())}")
        sys.exit(1)
    return content


def main():
    parser = argparse.ArgumentParser(
        description="SJKC Pin Min KSSR English weekly content generator")
    parser.add_argument("--task", required=True,
                        choices=["homework", "story", "quiz"],
                        help="Task to run: homework (Fri), story (Sat), quiz (Sun)")
    parser.add_argument("--week", type=int, default=None,
                        help="Override week number (1-6)")
    parser.add_argument("--year", type=int, default=None,
                        help="Send only this year level (1-6). Default: all years.")
    parser.add_argument("--combined", action="store_true",
                        help="Homework only: one combined PDF for all years.")
    args = parser.parse_args()

    week = args.week or _week_num()
    themes_this_week = [THEMES[week - 1]]  # single-element list for prompt fns
    theme = themes_this_week[0]["name"]

    print(f"[sjkc_english] task={args.task}  week={week}  theme={theme}")

    # ── Build system + user prompts ──────────────────────────────────────────
    if args.task == "homework":
        sys_prompt = _homework_system_fmt(themes_this_week)
        user_prompt = _homework_user_fmt(themes_this_week, week)
    elif args.task == "story":
        sys_prompt = _story_system_fmt(themes_this_week)
        user_prompt = _story_user_fmt(themes_this_week, week)
    else:
        sys_prompt = _quiz_system_fmt(themes_this_week)
        user_prompt = _quiz_user_fmt(themes_this_week, week)

    # ── Call LLM ─────────────────────────────────────────────────────────────
    print("[sjkc_english] Calling LLM …")
    try:
        llm_output = call_llm(sys_prompt, user_prompt)
    except Exception as e:
        print(f"[sjkc_english] LLM error: {e}")
        sys.exit(1)
    print(f"[sjkc_english] LLM output length: {len(llm_output)} chars")

    content = _parse_content(llm_output)

    # ── Deliver per year, class-scoped to each year's topic ──────────────────
    years_to_send = [args.year] if args.year else list(range(1, 7))
    if args.task == "homework":
        sent, failed = run_homework(content, week, theme, years_to_send,
                                    combined=args.combined)
    elif args.task == "story":
        sent, failed = run_story(content, week, theme, years_to_send)
    else:
        sent, failed = run_quiz(content, week, theme, years_to_send)

    print(f"[sjkc_english] summary: sent={sent} failed={failed}")
    print("[sjkc_english] Done.")


if __name__ == "__main__":
    main()
