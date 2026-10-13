// Shared TypeScript interfaces for the Chrome Extension + AI Content + Face Attendance system.

// ---------------------------------------------------------------------------
// Identity Profile (Chrome Extension — stored in chrome.storage.sync)
// ---------------------------------------------------------------------------

export interface IdentityProfile {
  id: string;          // UUID v4
  name: string;        // Full name as on MyKad
  ic: string;          // 12-digit Malaysian IC number (without dashes)
  schoolCode: string;  // e.g. "0001" (SJKC Pin Min, Bidor)
  schoolName: string;  // e.g. "SJKC PIN MIN, BIDOR"
  teacherId: string;   // e.g. "G123456" (MOE guru ID)
  email: string;       // e.g. teacher@sjkc-pinmin.edu.my
  phone: string;       // e.g. "012-XXX-XXXX"
  department: string;  // e.g. "Bahasa Melayu"
  position: string;    // e.g. "Guru"
}

// ---------------------------------------------------------------------------
// Field Mapping (Chrome Extension — CSS selector → data source)
// ---------------------------------------------------------------------------

export type DataSource = "identity" | "rph";

export type FieldTransform =
  | "upper"
  | "lower"
  | "title"
  | "ic2dob"      // 12-digit IC → YYYY-MM-DD (first 6 digits after YYMMDD)
  | "ic2age"
  | "ic2state";

export interface FieldMapping {
  id: string;           // UUID
  host: string;         // e.g. "idme.moe.gov.my"
  fieldId: string;      // logical name
  selector: string;     // CSS selector or [name=...] / [id=...]
  source: DataSource;
  sourceKey: string;    // key path into the profile or RPH object (dot-separated)
  transform?: FieldTransform;
}

// ---------------------------------------------------------------------------
// RPH Data (shared between extension and AI content)
// ---------------------------------------------------------------------------

export type SubjectCode = "BM" | "BC" | "BI" | "MT" | "SN" | "SJ" | "RBT"
  | "PJ" | "PK" | "PSV" | "MZ" | "PM" | "PI" | "MA";

export type InterfaceLanguage = "bm" | "en" | "zh";

export interface RPHData {
  subject: SubjectCode;
  year: number;          // 1–6
  language: InterfaceLanguage;
  class: string;         // e.g. "Year 3" / "Tahun 3"
  week: number;
  theme: string;
  unit: string;
  topic: string;
  date: string;          // YYYY-MM-DD
  period: number;
  sk: { code: string; desc: string }[];
  sp: { code: string; desc: string }[];
  objectives: string[];
  activities: {
    setInduction: string;
    preLesson: string;
    development: string;
    postLesson: string;
    closure: string;
  };
  successCriteria: string[];
  bbm: string;
  moralValues: string;
  emk: string;
  remedial: string[];
  reflection: string;
  studentCount: number;
}

// ---------------------------------------------------------------------------
// Fill Result (for UI status)
// ---------------------------------------------------------------------------

export interface FillResult {
  selector: string;
  fieldId: string;
  value: string;
  found: boolean;       // was the element found in the DOM
  filled: boolean;      // was the value actually entered
  error?: string;       // reason if not filled
}

export interface FillSession {
  host: string;
  timestamp: number;     // JS epoch ms
  profile: IdentityProfile;
  results: FillResult[];
}

// ---------------------------------------------------------------------------
// Face Attendance (shared between extension and face-attendance module)
// ---------------------------------------------------------------------------

export interface FaceTemplate {
  studentId: string;
  studentName: string;
  className: string;          // e.g. "Year 3"
  faceDescriptor: number[];     // 128-dim face embedding
  createdAt: number;            // epoch ms
  updatedAt?: number;
}

export interface FaceRecognitionResult {
  recognized: boolean;
  template?: FaceTemplate;
  confidence: number;      // 0–1
  timestamp: number;
}

// ---------------------------------------------------------------------------
// AI Content Generator (serverless function schemas)
// ---------------------------------------------------------------------------

export interface AIContentRequest {
  subject: SubjectCode;
  year: number;
  language: InterfaceLanguage;
  week: number;
  sk: string[];
  sp: string[];
  theme: string;
  unit: string;
  topic: string;
  studentCount: number;
  existingReflections?: string;
  model?: string;         // override default model
}

export interface AIActivities {
  setInduction: string;
  preLesson: string;
  development: string;
  postLesson: string;
  closure: string;
}

export interface AITpInterventions {
  low: string;       // TP 1–2
  medium: string;    // TP 3–4
  high: string;      // TP 5–6
}

export interface AIContentResponse {
  objectives: string[];
  successCriteria: string[];
  activities: AIActivities;
  remedial: string[];
  reflection: string;
  tpInterventions: AITpInterventions;
  creditsUsed: number;
}

// ---------------------------------------------------------------------------
// Storage Keys (Chrome Extension)
// ---------------------------------------------------------------------------

export const STORAGE_KEYS = {
  profiles: "erph_profiles",
  activeProfileId: "erph_active_profile",
  fieldMappings: "erph_field_mappings",
  fillLog: "erph_fill_log",
  faceTemplates: "erph_face_templates",
  settings: "erph_settings",
} as const;
