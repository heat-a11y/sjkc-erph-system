// AI Content Generator — produces KSSR-aligned RPH content via LLM
//
// This module provides:
//   1. Prompt template builder (language-aware, DSKP-aligned)
//   2. Credit tracking (mirrors ez-rph's aiCreditsRemaining system)
//   3. OpenRouter API client (uses inclusionai/ling-3.0-flash-sante:free)
//   4. Response parser with schema validation
//
// Usage in erph-pm web app:
//   const { objectives, activities, ... } = await generateContent({
//     subject: "BM", year: 3, language: "bm", week: 5,
//     sk: ["1.1", "2.1"], sp: ["1.1.1", "2.1.1"],
//     theme: "Sayangi Keluarga", unit: "Saya Sayang akan Keluarga",
//     topic: "PKJR", studentCount: 25
//   });

import type {
  AIContentRequest,
  AIContentResponse,
  AIActivities,
  AITpInterventions,
  SubjectCode,
} from "../../shared/types";

// ---------------------------------------------------------------------------
// Subject → Language mapping (KSSR rule)
// ---------------------------------------------------------------------------

export function subjectLanguage(subject: SubjectCode): "bm" | "en" | "zh" {
  switch (subject) {
    case "BM": return "bm";
    case "BI": return "en";
    case "BC": return "zh";
    case "PI": return "bm";
    case "MA": return "zh";
    default: return "zh";
  }
}

// ---------------------------------------------------------------------------
// Credits Tracker — mirrors ez-rph's AI_RATE_LIMIT / aiCreditsRemaining
// ---------------------------------------------------------------------------

export interface CreditBalance {
  includedRemaining: number;
  topUpRemaining: number;
  usedToday: number;
}

export class CreditsTracker {
  private static readonly DAILY_LIMIT = 20;
  private static readonly STORAGE_KEY = "erph_ai_credits";

  private balance: CreditBalance & { __date?: string } = {
    includedRemaining: CreditsTracker.DAILY_LIMIT,
    topUpRemaining: 0,
    usedToday: 0,
    __date: undefined,
  };

  load(): CreditBalance {
    const today = new Date().toDateString();
    const raw = localStorage.getItem(CreditsTracker.STORAGE_KEY);
    if (raw) {
      const saved = JSON.parse(raw) as CreditBalance & { __date?: string };
      // Reset daily at midnight (Malaysia time UTC+8)
      if (saved.__date !== today) {
        this.balance = {
          includedRemaining: CreditsTracker.DAILY_LIMIT,
          topUpRemaining: saved.topUpRemaining ?? 0,
          usedToday: 0,
          __date: today,
        };
      } else {
        this.balance = saved;
      }
    } else {
      this.balance = {
        includedRemaining: CreditsTracker.DAILY_LIMIT,
        topUpRemaining: 0,
        usedToday: 0,
        __date: today,
      };
    }
    return { ...this.balance };
  }

  canGenerate(count: number = 1): boolean {
    const b = this.balance;
    const total = b.includedRemaining + b.topUpRemaining;
    return total >= count;
  }

  deduct(count: number = 1): void {
    if (!this.canGenerate(count)) {
      throw new Error("AI_RATE_LIMIT");
    }
    this.balance.usedToday += count;
    if (this.balance.includedRemaining > 0) {
      this.balance.includedRemaining = Math.max(0, this.balance.includedRemaining - count);
    } else {
      this.balance.topUpRemaining = Math.max(0, this.balance.topUpRemaining - count);
    }
    localStorage.setItem(CreditsTracker.STORAGE_KEY, JSON.stringify(this.balance));
  }

  getRemaining(): number {
    return this.balance.includedRemaining + this.balance.topUpRemaining;
  }
}

// ---------------------------------------------------------------------------
// Prompt Builder — constructs the LLM prompt
// ---------------------------------------------------------------------------

export interface PromptContext {
  subject: SubjectCode;
  year: number;
  language: "bm" | "en" | "zh";
  week: number;
  sk: string[];
  sp: string[];
  theme: string;
  unit: string;
  topic: string;
  studentCount: number;
}

export interface PromptTemplate {
  system: string;
  user: string;
}

const LANG_LABELS: Record<string, string> = {
  bm: "Bahasa Melayu (KSSR)",
  en: "English (KSSR)",
  zh: "Bahasa Cina (KSSR)",
};

const SUBJECT_LABELS: Record<SubjectCode, string> = {
  BM: "Bahasa Melayu",
  BC: "Bahasa Cina",
  BI: "Bahasa Inggeris",
  MT: "Matematik",
  SN: "Sains",
  SJ: "Sejarah",
  RBT: "Reka Bentuk dan Teknologi",
  PJ: "Pendidikan Jasmani",
  PK: "Pendidikan Kesihatan",
  PSV: "Pendidikan Seni Visual",
  MZ: "Pendidikan Muzik",
  PM: "Pendidikan Moral",
  PI: "Pendidikan Islam",
  MA: "Matematik Awal (Prasekolah)",
};

export function buildPrompt(ctx: PromptContext): PromptTemplate {
  const langLabel = LANG_LABELS[ctx.language] || LANG_LABELS.bm;
  const subjLabel = SUBJECT_LABELS[ctx.subject] || ctx.subject;
  const skList = ctx.sk.map(s => `- ${s}`).join("\n");
  const spList = ctx.sp.map(s => `- ${s}`).join("\n");

  const system = `You are an expert KSSR primary school teacher in Malaysia. You generate high-quality, culturally-relevant Rancangan Pengajian Harian (RPH) lesson content for SJKC Pin Min, Bidor. Always respond with strict JSON only — no markdown, no commentary, no preamble.

Subject: ${subjLabel}
Year: ${ctx.year}
Language: ${langLabel}
Student count: ${ctx.studentCount}
Theme: ${ctx.theme}
Unit: ${ctx.unit}
Topic: ${ctx.topic}

The 5-phase activity structure is: Set Induction (Pembukaan), Pre-lesson (Aktiviti 2), Development (Aktiviti 3), Post-lesson (Aktiviti 4), Closure (Penutup).
TP levels: 1-2 = rendah (needs guidance), 3-4 = sederhana, 5-6 = cemerlang (needs enrichment).
Provide exactly 3 remedial activities for weaker students and TP-specific intervention text.`;

  const user = `Generate RPH content for ${subjLabel} Year ${ctx.year} (${langLabel}).

Learning Standards (SK):
${skList || "(none provided)"}

Learning Standards (SP):
${spList || "(none provided)"}

Requirements:
1. Generate 3-4 learning objectives based on the SP (in ${langLabel})
2. Generate 3-4 success criteria
3. Generate 5 activities (Set Induction, Pre-lesson, Development, Post-lesson, Closure)
4. Generate 3 remedial activities for weaker students (TP 1-2)
5. Generate a TP-aware reflection mentioning specific student names (use generic names like Ahmad, Siti, Chen, Mei Lin — match Chinese/Malay/Indian diversity)
6. Generate TP interventions:
   - low (TP 1-2): guidance for struggling students
   - medium (TP 3-4): support for average students
   - high (TP 5-6): enrichment for advanced students

Output STRICT JSON with this exact structure:
{
  "objectives": ["string"],
  "successCriteria": ["string"],
  "activities": {
    "setInduction": "string",
    "preLesson": "string",
    "development": "string",
    "postLesson": "string",
    "closure": "string"
  },
  "remedial": ["string"],
  "reflection": "string",
  "tpInterventions": {
    "low": "string",
    "medium": "string",
    "high": "string"
  }
}`;

  return { system, user };
}

// ---------------------------------------------------------------------------
// Response Parser — validates the LLM's JSON output
// ---------------------------------------------------------------------------

export function parseAIResponse(raw: string): Omit<AIContentResponse, "creditsUsed"> {
  const trimmed = raw.trim();
  // Strip code fences if the LLM wraps in markdown
  const cleaned = trimmed.replace(/^```json\s*/, "").replace(/\s*```$/, "");
  const parsed = JSON.parse(cleaned);

  // Validate required fields
  const required = ["objectives", "successCriteria", "activities", "remedial", "reflection", "tpInterventions"];
  for (const key of required) {
    if (!(key in parsed)) {
      throw new Error(`Missing required field: ${key}`);
    }
  }

  // Validate activities sub-structure
  const actKeys = ["setInduction", "preLesson", "development", "postLesson", "closure"];
  for (const key of actKeys) {
    if (!(key in parsed.activities)) {
      throw new Error(`Missing activity field: ${key}`);
    }
  }

  return parsed as Omit<AIContentResponse, "creditsUsed">;
}

// ---------------------------------------------------------------------------
// OpenRouter Client — sends request and returns parsed content
// ---------------------------------------------------------------------------

export interface OpenRouterResponse {
  id: string;
  choices: Array<{
    message: { content: string };
  }>;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

export async function callOpenRouter(
  prompt: PromptTemplate,
  apiKey: string,
  model: string = "inclusionai/ling-3.0-flash-sante:free",
): Promise<OpenRouterResponse> {
  const res = await fetch("https://openrouter.ai/api/v1/chat/completions", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${apiKey}`,
      "HTTP-Referer": "https://erph-pm.vercel.app",
      "X-Title": "eRPH-PM",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model,
      messages: [
        { role: "system", content: prompt.system },
        { role: "user", content: prompt.user },
      ],
      temperature: 0.7,
      max_tokens: 2048,
      response_format: { type: "json_object" },
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`OpenRouter API error ${res.status}: ${err}`);
  }

  return res.json() as Promise<OpenRouterResponse>;
}

// ---------------------------------------------------------------------------
// Main entry — builds prompt, calls LLM, parses response, tracks credits
// ---------------------------------------------------------------------------

export async function generateContent(
  req: AIContentRequest,
  apiKey: string,
): Promise<AIContentResponse> {
  const credits = new CreditsTracker();
  credits.load();

  if (!credits.canGenerate()) {
    const err = new Error("AI_RATE_LIMIT");
    (err as any).code = "AI_RATE_LIMIT";
    throw err;
  }

  const lang = req.language ?? subjectLanguage(req.subject);
  const ctx = {
    subject: req.subject,
    year: req.year,
    language: lang,
    week: req.week,
    sk: req.sk,
    sp: req.sp,
    theme: req.theme,
    unit: req.unit,
    topic: req.topic,
    studentCount: req.studentCount,
  };

  const prompt = buildPrompt(ctx);
  const apiRes = await callOpenRouter(prompt, apiKey, req.model);
  const content = parseAIResponse(apiRes.choices[0].message.content);

  credits.deduct();

  return {
    ...content,
    creditsUsed: 1,
  };
}
