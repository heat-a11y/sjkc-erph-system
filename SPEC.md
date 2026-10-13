# SJKC-PinMin RPH System — Specification

Companion system to `erph-pm` (the offline-first RPH generator PWA for
SJKC Pin Min, Bidor). This package adds three capabilities that the
ez-rph reference site demonstrated:

1. **Chrome Extension** — Auto-fill teacher identity and RPH-derived
   data into the Malaysian Ministry of Education **IDMe** portal
   (`idme.moe.gov.my`) and related MOE web applications (SGMy, MySST,
   e-Profile, SPLKPM modules).
2. **AI Content Generator** — Serverless function that calls an LLM
   (OpenRouter: `inclusionai/ling-3.0-flash-sante:free`) to generate
   SK-aligned learning objectives, activities (5-phase), success
   criteria, reflections, and remedial banks in the correct language
   (BM / EN / ZH) per KSSR DSKP.
3. **Face Attendance Module** — In-browser JavaScript face-recognition
   engine (FaceAPI.js + MediaPipe BlazeFace) for classroom attendance
   capture, with templates exported/imported as JSON (replaces the
   removed `face_attendance/face_engine.js` from the ez-rph build).

## Existing Web App Context (erph-pm)

| Concern | Value |
|---|---|
| Repo | `heat-a11y/erph-pm` (Vercel, static PWA) |
| Stack | HTML + Alpine.js + Tailwind CSS (compiled) + Service Worker |
| Backend | Vercel Edge Middleware (HMAC session cookie auth) |
| Storage | localStorage (`eprh`, `eptg`, `epprog`, `erteac`, `etakwim`, …) |
| Subjects | BM, BC, BI, MT, SN, SJ, RBT, PJ, PK, PSV, MZ, PM, PI, MA |
| Languages | BM / EN / ZH (auto per subject, toggle for UI) |
| Deployment | `https://erph-pm.vercel.app` (password-gated) |

## 1. Chrome Extension

### 1.1 Overview
A Manifest V3 extension that injects identity data and structured RPH
content into MOE portal forms. No user data is sent to any server other
than the MOE portal itself.

### 1.2 Identity Profile (Domain Model)
```ts
interface IdentityProfile {
  id: string;          // UUID
  name: string;        // Full name as on MyKad
  ic: string;          // 12-digit Malaysian IC number
  schoolCode: string;  // e.g. "0001" (SJKC Pin Min, Bidor)
  schoolName: string;  // "SJKC PIN MIN, BIDOR"
  teacherId: string;   // e.g. "G123456" (MOE guru ID)
  email: string;       // e.g. teacher@sjkc-pinmin.edu.my
  phone: string;       // e.g. "012-XXX-XXXX"
  department: string;  // e.g. "Bahasa Melayu"
  position: string;    // e.g. "Guru"
}
```

### 1.3 Field Mapping Rules
Each MOE form field is mapped by a CSS selector or `name`/`id` attribute.
Rules are keyed by hostname.

```ts
interface FieldMapping {
  host: string;              // e.g. "idme.moe.gov.my"
  fieldId: string;           // logical name, e.g. "nama_lengkap"
  selector: string;          // CSS selector, e.g. "#full_name"
  source: "identity" | "rph"; // data source
  sourceKey: string;         // key in the profile or RPH object
  transform?: "upper" | "lower" | "ic2dob"; // optional transform
}
```

### 1.4 Supported MOE Portals
| Portal | Hostname | Key Fields |
|---|---|---|
| IDMe SSO | `idme.moe.gov.my` | IC, password, nama, email, phone |
| SGMy (Teacher Cert) | `sgmy.moe.gov.my` | IC number, password, print |
| MySST | `mysst.moe.gov.my` | School code, teacher ID, class |
| APDM | `apdmkpm.moe.gov.my` | Student lists, attendance |

### 1.5 Permissions (Manifest V3)
- `activeTab` — inject content scripts on demand
- `scripting` — execute fill script
- `storage` — sync profiles and mappings
- `identity` — (optional) OAuth if needed for future token refresh

### 1.6 UI
- Popup (320x480): profile selector, fill button, status indicator
- Options page: manage profiles, edit field mappings, view fill log

## 2. AI Content Generator

### 2.1 Endpoint
Serverless function at `/api/generate-content` (Vercel Functions or
Cloudflare Workers). Compatible with both runtimes.

### 2.2 Request Schema
```ts
interface GenerateRequest {
  subject: string;     // "BM", "BI", "MT", etc.
  year: number;        // 1–6
  language: "bm" | "en" | "zh";
  week: number;        // current RPT week
  sk: string[];        // selected Standard Kandungan codes
  sp: string[];        // selected Standard Pembelajaran codes
  theme: string;       // RPT theme
  unit: string;        // RPT unit
  topic: string;       // RPT topic
  studentCount: number; // for scaling activities
  existingReflections?: string; // for re-generation
}
```

### 2.3 Response Schema
```ts
interface GenerateResponse {
  objectives: string[];
  successCriteria: string[];
  activities: {
    setInduction: string;
    preLesson: string;
    development: string;
    postLesson: string;
    closure: string;
  };
  remedial: string[];       // 3 activities (weaker students)
  reflection: string;       // TP-aware reflection text
  tpInterventions: {
    low: string;      // TP 1–2
    medium: string;   // TP 3–4
    high: string;     // TP 5–6
  };
  creditsUsed: number;
}
```

### 2.4 LLM Integration
- Provider: OpenRouter (`https://openrouter.ai/api/v1/chat/completions`)
- Model: `inclusionai/ling-3.0-flash-sante:free`
- API key: stored as `OPENROUTER_API_KEY` env var (serverless)
- The model prompt is language-aware: BM for BM/PK/PI, EN for BI, ZH
  for BC, and ZH for all others by default (matching erph-pm's teacher
  language rules).
- `AiCredits` tracking: the function tracks usage per-key and returns
  `creditsUsed`.

### 2.5 Prompt Template (core)
The prompt includes:
- DSKP SK/SP context (from `curriculum-db.js`)
- RPT weekly theme/unit
- Language rules (BM/EN/ZH per subject)
- KSSR activity format (5-phase:  Set Induction, Pre-lesson,
  Development, Post-lesson, Closure)
- TP (Tahap Penguasaan) levels 1–6 with intervention language

## 3. Face Attendance Module

### 3.1 Overview
Vanilla JavaScript face recognition module using:
- MediaPipe BlazeFace for face detection
- FaceAPI.js / FaceMesh for face recognition (feature extraction)
- No server backend — all processing in-browser
- Templates stored as base64 face descriptors in localStorage

### 3.2 Domain Model
```ts
interface FaceTemplate {
  studentId: string;
  studentName: string;
  class: string;        // "Year 3" etc.
  faceDescriptor: number[]; // 128-dim face embedding
  createdAt: number;
}
```

### 3.3 API
```ts
class FaceAttendance {
  init(camera: HTMLVideoElement): Promise<void>;  // detect + track
  enroll(student: FaceTemplate): Promise<void>;   // add new face
  recognize(): Promise<FaceRecognitionResult>;     // attendance scan
  exportTemplates(): FaceTemplate[];               // backup
  importTemplates(templates: FaceTemplate[]): void; // restore
}
```

### 3.4 Integration
- Embeds in the erph-pm web app via a new "Attendance" tab
- Exports/imports with the existing `erph-backup-*.json` format
- Attendance results feed into the existing Prestasi tab

## 4. Deployment

| Component | Where |
|---|---|
| Chrome Extension | `heat-a11y/erph-pm-extension` (Chrome Web Store) |
| AI Content API | Added to `erph-pm` Vercel project |
| Face Attendance | Added to `erph-pm` web app |

## 5. Acceptance Criteria
- [ ] Chrome extension loads, stores a profile, fills a form on any test page
- [ ] AI content generator returns valid structured JSON under 3s
- [ ] Face attendance module loads FaceAPI.js, detects faces, exports templates
- [ ] All TypeScript compiles, all tests pass
- [ ] Everything committed and pushed to GitHub
