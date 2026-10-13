import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  subjectLanguage,
  CreditsTracker,
  buildPrompt,
  parseAIResponse,
  callOpenRouter,
  generateContent,
} from "../src/index";
import type { AIContentRequest } from "../../shared/types";

describe("subjectLanguage", () => {
  it("returns bm for BM and PI", () => {
    expect(subjectLanguage("BM")).toBe("bm");
    expect(subjectLanguage("PI")).toBe("bm");
  });
  it("returns en for BI", () => {
    expect(subjectLanguage("BI")).toBe("en");
  });
  it("returns zh for BC, MT, SN, SJ, RBT, PJ, PK, PSV, MZ, PM, MA", () => {
    for (const s of ["BC", "MT", "SN", "SJ", "RBT", "PJ", "PK", "PSV", "MZ", "PM", "MA"]) {
      expect(subjectLanguage(s as any)).toBe("zh");
    }
  });
});

describe("CreditsTracker", () => {
  const makeReq = (override: Partial<AIContentRequest> = {}): AIContentRequest => ({
    subject: "BM",
    year: 3,
    language: "bm",
    week: 5,
    sk: ["1.1"],
    sp: ["1.1.1"],
    theme: "Sayangi Keluarga",
    unit: "Saya Sayang akan Keluarga",
    topic: "PKJR",
    studentCount: 25,
    ...override,
  });

  beforeEach(() => {
    vi.stubGlobal("localStorage", {
      store: {} as Record<string, string>,
      getItem(k: string) { return this.store[k] ?? null; },
      setItem(k: string, v: string) { this.store[k] = v; },
      removeItem(k: string) { delete this.store[k]; },
      clear() { this.store = {}; },
    });
    (localStorage as any).store = {};
  });

  it("starts with 20 daily credits", () => {
    const credits = new CreditsTracker();
    const bal = credits.load();
    expect(bal.includedRemaining).toBe(20);
    expect(credits.canGenerate()).toBe(true);
  });

  it("deducts credits on use", () => {
    const credits = new CreditsTracker();
    credits.load();
    expect(credits.getRemaining()).toBe(20);
    credits.deduct();
    expect(credits.getRemaining()).toBe(19);
    expect(credits.load().usedToday).toBe(1);
  });

  it("blocks when limit exhausted", () => {
    const credits = new CreditsTracker();
    credits.load();
    for (let i = 0; i < 20; i++) credits.deduct();
    expect(credits.canGenerate()).toBe(false);
    expect(() => credits.deduct()).toThrow("AI_RATE_LIMIT");
  });

  it("persists to localStorage", () => {
    const credits = new CreditsTracker();
    credits.load();
    credits.deduct(3);
    // New instance should recover state
    const credits2 = new CreditsTracker();
    const bal = credits2.load();
    expect(bal.includedRemaining).toBe(17);
    expect(bal.usedToday).toBe(3);
  });
});

describe("buildPrompt", () => {
  it("includes subject, theme, and SK in the system prompt", () => {
    const prompt = buildPrompt({
      subject: "BM",
      year: 3,
      language: "bm",
      week: 5,
      sk: ["1.1 Mendengar"],
      sp: ["1.1.1 Menamakan"],
      theme: "Sayangi Keluarga",
      unit: "Saya Sayang",
      topic: "PKJR",
      studentCount: 25,
    });
    expect(prompt.system).toContain("Bahasa Melayu");
    expect(prompt.system).toContain("Sayangi Keluarga");
    expect(prompt.system).toContain("Saya Sayang");
    expect(prompt.system).toContain("strict JSON");
  });

  it("includes JSON structure in the user prompt", () => {
    const prompt = buildPrompt({
      subject: "BI",
      year: 1,
      language: "en",
      week: 1,
      sk: ["1.1"],
      sp: ["1.1.1"],
      theme: "Transport",
      unit: "My Family",
      topic: "PKJR",
      studentCount: 20,
    });
    expect(prompt.user).toContain("objectives");
    expect(prompt.user).toContain("successCriteria");
    expect(prompt.user).toContain("activities");
    expect(prompt.user).toContain("remedial");
    expect(prompt.user).toContain("tpInterventions");
  });

  it("defaults to 'Saya Sayang akan Keluarga' theme when theme is empty", () => {
    const prompt = buildPrompt({
      subject: "PM",
      year: 4,
      language: "bm",
      week: 3,
      sk: [],
      sp: [],
      theme: "",
      unit: "",
      topic: "Moral",
      studentCount: 30,
    });
    expect(prompt.system).toContain("Bahasa Melayu (KSSR)");
    expect(prompt.user).toContain("Pendidikan Moral");
  });
});

describe("parseAIResponse", () => {
  const validJSON = JSON.stringify({
    objectives: ["Obj 1", "Obj 2"],
    successCriteria: ["SC 1"],
    activities: {
      setInduction: "A1",
      preLesson: "A2",
      development: "A3",
      postLesson: "A4",
      closure: "A5",
    },
    remedial: ["R1", "R2", "R3"],
    reflection: "Great lesson!",
    tpInterventions: { low: "L", medium: "M", high: "H" },
  });

  it("parses valid JSON response", () => {
    const result = parseAIResponse(validJSON);
    expect(result.objectives).toHaveLength(2);
    expect(result.activities.setInduction).toBe("A1");
    expect(result.tpInterventions.high).toBe("H");
  });

  it("strips markdown code fences", () => {
    const withFences = "```json\n" + validJSON + "\n```";
    const result = parseAIResponse(withFences);
    expect(result.objectives[0]).toBe("Obj 1");
  });

  it("throws on missing required field", () => {
    const broken = JSON.stringify({ objectives: ["x"] }); // missing activities etc
    expect(() => parseAIResponse(broken)).toThrow("Missing required field");
  });

  it("throws on missing activity sub-field", () => {
    const broken = JSON.stringify({
      objectives: ["x"],
      successCriteria: ["x"],
      activities: { setInduction: "A1", preLesson: "A2", development: "A3", postLesson: "A4" }, // missing closure
      remedial: ["x"],
      reflection: "x",
      tpInterventions: { low: "L", medium: "M", high: "H" },
    });
    expect(() => parseAIResponse(broken)).toThrow("Missing activity field: closure");
  });

  it("throws on invalid JSON", () => {
    expect(() => parseAIResponse("{ not json }")).toThrow();
  });
});

describe("callOpenRouter", () => {
  it("sends correct request format", async () => {
    const mockJson = {
      id: "test-1",
      choices: [{ message: { content: '{"objectives":["test"]}' } }],
      usage: { prompt_tokens: 100, completion_tokens: 50, total_tokens: 150 },
    };
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockJson,
    } as any);

    const prompt = buildPrompt({
      subject: "BM", year: 3, language: "bm", week: 5,
      sk: ["1.1"], sp: ["1.1.1"], theme: "T", unit: "U", topic: "TP",
      studentCount: 25,
    });
    const res = await callOpenRouter(prompt, "fake-key", "test/model");

    expect(fetch).toHaveBeenCalledWith(
      "https://openrouter.ai/api/v1/chat/completions",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Authorization": "Bearer fake-key",
          "X-Title": "eRPH-PM",
        }),
      }),
    );
    expect(res.choices[0].message.content).toBe('{"objectives":["test"]}');
  });

  it("throws on HTTP error", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      text: async () => "Rate limited",
    } as any);

    await expect(callOpenRouter({ system: "", user: "" }, "key")).rejects.toThrow("429");
  });
});

describe("generateContent", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", {
      store: {} as Record<string, string>,
      getItem(k: string) { return this.store[k] ?? null; },
      setItem(k: string, v: string) { this.store[k] = v; },
      removeItem(k: string) { delete this.store[k]; },
      clear() { this.store = {}; },
    });
    (localStorage as any).store = {};
  });

  it("returns AI_RATE_LIMIT error when credits exhausted", async () => {
    const credits = new CreditsTracker();
    credits.load();
    for (let i = 0; i < 20; i++) credits.deduct();

    const req: AIContentRequest = {
      subject: "BM", year: 3, language: "bm", week: 5,
      sk: ["1.1"], sp: ["1.1.1"], theme: "T", unit: "U", topic: "TP",
      studentCount: 25,
    };

    await expect(generateContent(req, "fake-key")).rejects.toThrow("AI_RATE_LIMIT");
  });

  it("generates content successfully", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: "test",
        choices: [{ message: { content: JSON.stringify({
          objectives: ["Obj 1"],
          successCriteria: ["SC 1"],
          activities: { setInduction: "A1", preLesson: "A2", development: "A3", postLesson: "A4", closure: "A5" },
          remedial: ["R1"],
          reflection: "Reflection",
          tpInterventions: { low: "L", medium: "M", high: "H" },
        }) } }],
        usage: { prompt_tokens: 100, completion_tokens: 50, total_tokens: 150 },
      }),
    } as any);

    const req: AIContentRequest = {
      subject: "BM", year: 3, language: "bm", week: 5,
      sk: ["1.1"], sp: ["1.1.1"], theme: "T", unit: "U", topic: "TP",
      studentCount: 25,
    };

    const result = await generateContent(req, "fake-key");
    expect(result.objectives).toHaveLength(1);
    expect(result.creditsUsed).toBe(1);
  });
});
