# eRPH-PM System
Automated RPH planner for **SJKC Pin Min, Bidor** — Chrome extension for auto-filling MOE IDMe, AI RPH content generator, and face-based attendance, all in one monorepo.

## What Is This?

A system adapted from [ez-rph](https://ez-rph.gataltech.com/) for SJKC Pin Min:

| Component | Purpose |
|---|---|
| Chrome Extension | Auto-fills the MOE IDMe portal (`idme.moe.gov.my`) with teacher identity and RPH data |
| AI Content Generator | Generates RPH activities, learning objectives, reflections, and remedial notes via LLM |
| Face Attendance | Face recognition attendance system (replaces the removed `face_attendance/face_engine.js`) |

**Color theme:** `#C4956A` (SJKC school uniform color)

## Project Structure

```
Work/
  shared/           # TypeScript interfaces (IdentityProfile, FieldMapping, etc.)
  extension/        # Chrome Extension (MV3)
    manifest.json
    src/            # core.ts, background.ts, content.ts, default-mappings.ts
    popup/          # Popup UI (popup.html + popup.js)
    options/        # Profile management and field mapping editor
    test/           # 19 unit tests
    icons/          # SVG + PNG icons (16/32/48/128px)
  ai-content/       # AI RPH content generator
    src/index.ts     # Prompt builder, OpenRouter client, credit tracker
    api/             # Serverless endpoint (deploy to Vercel)
    test/            # 31 unit tests
  face-attendance/  # Face recognition attendance
    src/face-attendance.ts
    test/            # 18 unit tests
  cron/             # Cron jobs (AQI watchdog, English homework, etc.)
  SPEC.md           # Full specification
```

## Installation

### Prerequisites
- Node.js 20+
- npm
- Git

### Clone and Install

```bash
git clone https://github.com/heat-a11y/sjkc-erph-system.git
cd sjkc-erph-system
npm install
```

## Usage

### 1. Chrome Extension — Auto-Fill MOE IDMe Forms

**What it does:** Detects when you're on the MOE IDMe portal (`idme.moe.gov.my`), then auto-fills form fields with your saved teacher profile data (name, IC, email, school, state, district, etc.) and RPH data.

**Setup:**

1. **Build the extension:**
```bash
cd extension
node build.js
```

2. **Load in Chrome:**
   - Go to `chrome://extensions/`
   - Toggle **Developer mode** (top-right corner)
   - Click **Load unpacked**
   - Select the `extension/` folder
   - The extension icon (🇲🇾) appears in your toolbar

3. **Save your teacher profile:**
   - Click the extension icon → **Options**
   - Enter your name, IC number, email, phone, school, state, district
   - Click **Save Profile**
   - Set it as the active profile

4. **Auto-fill on IDMe:**
   - Open [idme.moe.gov.my](https://idme.moe.gov.my) and log in
   - Navigate to the form you need to fill
   - Click the extension icon → **Fill Form**
   - The extension auto-fills all matching fields
   - A 🇲🇾 badge appears at bottom-right on MOE sites when the extension is active

**Default field mappings:** The extension includes pre-configured CSS selectors for common IDMe fields (name, IC/noKP, email, phone, school, state, district). If a field doesn't auto-fill, edit the selectors in **Options → Field Mappings**.

### 2. AI Content Generator — Auto-Generate RPH Content

**What it does:** Generates complete RPH (Ringkasan Perkongsian Hasil Belajar) content — activities, learning objectives (PBD), reflections, and remedial suggestions — following KSSR DSKP standards. Content is generated in Bahasa Malaysia by default.

**Deploy to Vercel (recommended):**

```bash
cd ai-content
npm install
vercel --y           # auto-deploys to Vercel
```

**Or run locally:**

```bash
cd ai-content
npm install
# Set your OpenRouter API key:
export OPENROUTER_API_KEY="sk-xxxxxxxx"
# Then deploy locally or integrate into your web app
```

**API usage:**

```bash
curl -X POST https://your-vercel-url/api/generate-content \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "BM",
    "year": 3,
    "theme": "Sayangi Keluarga",
    "unit": "Saya Sayang",
    "topic": "PKJR",
    "sk": ["1.1"],
    "sp": ["1.1.1"],
    "studentCount": 25
  }'
```

**API request fields:**
| Field | Type | Required | Example |
|---|---|---|---|
| `subject` | string | Yes | `"BM"` (BM, BI, BC, Math, Science, etc.) |
| `year` | number | Yes | `3` (1–6) |
| `theme` | string | Yes | `"Sayangi Keluarga"` |
| `unit` | string | Yes | `"Saya Sayang"` |
| `topic` | string | No | `"PKJR"` (PKJR, PKn, etc.) |
| `sk` | string[] | Yes | `["1.1"]` (Standard Kurikulum) |
| `sp` | string[] | Yes | `["1.1.1"]` (Standard Progres) |
| `studentCount` | number | Yes | `25` |
| `language` | string | No | `"bm"` (default: `"bm"`) |

**Response:** Returns JSON with `activities`, `objectives`, `reflection`, `remedial` sections — ready to paste into IDMe.

**AI model:** `inclusionai/ling-3.0-flash-sante:free` (via OpenRouter)

**Credit system:** 20 AI credits per day (resets at midnight Malaysia time). When exhausted, the API returns `429 AI_RATE_LIMIT`.

### 3. Face Attendance — Face Recognition Attendance

**What it does:** Uses your laptop/webcam to detect students' faces, match against registered templates, and log attendance. Replaces the removed `face_attendance/face_engine.js`.

**Integration (in your web app):**

```ts
import { FaceAttendance } from "../../face-attendance/src/face-attendance";

const fa = new FaceAttendance();
await fa.init();  // requests camera access

// Register a new student (one-time per student)
const descriptor = await fa.enroll(
  "student-001",   // student ID
  "Ahmad",         // student name
  "3 Blue",        // class
  videoElement     // HTMLVideoElement from camera
);
// Template automatically saved to localStorage

// Take attendance for the class
const results = await fa.recognize(videoElement, {
  threshold: 0.6,      // minimum confidence (0.0–1.0)
  timeoutMs: 10000,    // timeout after 10 seconds
});
// results: [{ studentId, studentName, confidence, recognized }]
```

### Combined Workflow

1. **Generate RPH content** using the AI content generator → get activities, objectives, reflections
2. **Go to IDMe portal** → fill the RPH form → extension auto-fills your teacher profile + RPH data
3. **Take attendance** using face recognition → export attendance list

## Testing

```bash
# Run all tests
cd extension && npx vitest run        # 19 tests
cd ../ai-content && npx vitest run    # 31 tests
cd ../face-attendance && npx vitest run  # 18 tests
```

**Total: 68 tests, all passing.**

## Cron Jobs (Automated Tasks)

This system includes cron jobs for SJKC Pin Min:

1. **AQI Watchdog** — Daily at 06:00. Checks air quality at Ipoh (4.59,101.10) and Tanjung Malim (3.68,101.52). Cancels basketball if AQI > 100 (US EPA standard). Sends 3-language alert.
2. **English Homework** — Fridays at 18:00
3. **Bedtime Stories** — Saturdays at 20:00
4. **Mini-Quiz** — Sundays at 10:00

```bash
cd cron
python3 main.py           # run all cron jobs
python3 tests/run_tests.py  # test cron infrastructure
```

Scripts live in `cron/cronjobs/scripts/`.

## Deployment

| Component | Where | How |
|---|---|---|
| AI Content API | Vercel | `cd ai-content && vercel --prod` |
| Chrome Extension | Chrome | Build with `node build.js`, then load unpacked |
| Face Attendance | erph-pm web app | Import the module and integrate |
| Cron Jobs | Local server | `cd cron && python3 main.py` |

**GitHub repo:** [heat-a11y/sjkc-erph-system](https://github.com/heat-a11y/sjkc-erph-system)

## Configuration

### Environment Variables (AI Content API)
```
OPENROUTER_API_KEY=sk-xxxxxxxx
```

### Chrome Extension Permissions
- `storage` — save profiles and mappings
- `activeTab` — access current tab
- `scripting` — inject content script
- `host_permissions` — access to `*.moe.gov.my` and `*.kpm.gov.my` domains

## Contact

- **GitHub:** [heat-a11y/sjkc-erph-system](https://github.com/heat-a11y/sjkc-erph-system)
- Open a GitHub issue for bugs or feature requests.
