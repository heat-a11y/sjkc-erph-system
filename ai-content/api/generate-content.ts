// Serverless API endpoint — deploy to Vercel / Cloudflare Workers / Netlify
//
// POST /api/generate-content
// Body: AIContentRequest (see shared/types)
// Env:  OPENROUTER_API_KEY
//
// Response: AIContentResponse | { error: string }

import { generateContent, parseAIResponse, buildPrompt, CreditsTracker, subjectLanguage } from "../src/index";
import type { AIContentRequest, AIContentResponse } from "../../shared/types";

/** Request schema for validation — mirrors shared/types but as a plain object
 *  so it can be used both in serverless and browser contexts.
 */
export function validateRequest(body: unknown): AIContentRequest {
  const r = body as Partial<AIContentRequest>;

  if (!r.subject || !/^(BM|BC|BI|MT|SN|SJ|RBT|PJ|PK|PSV|MZ|PM|PI|MA)$/.test(r.subject)) {
    throw new Error("Invalid subject");
  }
  if (!r.year || r.year < 1 || r.year > 6) {
    throw new Error("Invalid year");
  }
  if (!r.theme) throw new Error("Missing theme");
  if (!r.unit) throw new Error("Missing unit");
  if (!Array.isArray(r.sk)) throw new Error("sk must be an array");
  if (!Array.isArray(r.sp)) throw new Error("sp must be an array");
  if (!r.studentCount || r.studentCount < 1) throw new Error("Invalid studentCount");

  return {
    subject: r.subject,
    year: r.year,
    language: r.language ?? subjectLanguage(r.subject),
    week: r.week ?? 0,
    sk: r.sk,
    sp: r.sp,
    theme: r.theme,
    unit: r.unit,
    topic: r.topic ?? "",
    studentCount: r.studentCount,
    model: r.model,
  };
}

export async function handleGenerateContent(
  body: unknown,
  apiKey: string,
): Promise<AIContentResponse | { error: string }> {
  try {
    const req = validateRequest(body);
    const result = await generateContent(req, apiKey);
    return result;
  } catch (e) {
    const err = e as Error;
    if (err.message === "AI_RATE_LIMIT" || (err as any).code === "AI_RATE_LIMIT") {
      return { error: "AI_RATE_LIMIT: Daily credit limit reached. Try again tomorrow." };
    }
    return { error: err.message };
  }
}

// --- Vercel Functions handler ---
export default async function handler(req: Request): Promise<Response> {
  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), { status: 405 });
  }

  const apiKey = process.env.OPENROUTER_API_KEY ?? "";
  if (!apiKey) {
    return new Response(JSON.stringify({ error: "OPENROUTER_API_KEY not set" }), { status: 500 });
  }

  let body: unknown;
  try { body = await req.json(); } catch { return new Response(JSON.stringify({ error: "Invalid JSON" }), { status: 400 }); }

  const result = await handleGenerateContent(body, apiKey);
  const isError = "error" in result;
  return new Response(JSON.stringify(result), {
    status: isError ? 400 : 200,
    headers: { "Content-Type": "application/json" },
  });
}
