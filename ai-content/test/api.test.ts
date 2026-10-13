import { describe, it, expect } from "vitest";
import { validateRequest } from "../api/generate-content";
import type { AIContentRequest } from "../../shared/types";

describe("validateRequest", () => {
  const validReq: AIContentRequest = {
    subject: "BM",
    year: 3,
    language: "bm",
    week: 5,
    sk: ["1.1"],
    sp: ["1.1.1"],
    theme: "Sayangi Keluarga",
    unit: "Saya Sayang",
    topic: "PKJR",
    studentCount: 25,
  };

  it("accepts a valid request", () => {
    const req = validateRequest(validReq);
    expect(req.subject).toBe("BM");
    expect(req.year).toBe(3);
  });

  it("throws on missing subject", () => {
    const bad = { ...validReq, subject: undefined as any };
    expect(() => validateRequest(bad)).toThrow("Invalid subject");
  });

  it("throws on invalid subject code", () => {
    const bad = { ...validReq, subject: "XX" as any };
    expect(() => validateRequest(bad)).toThrow("Invalid subject");
  });

  it("throws on year out of range (0)", () => {
    const bad = { ...validReq, year: 0 };
    expect(() => validateRequest(bad)).toThrow("Invalid year");
  });

  it("throws on year out of range (7)", () => {
    const bad = { ...validateRequest(validReq), year: 7 };
    expect(() => validateRequest(bad)).toThrow("Invalid year");
  });

  it("throws on missing theme", () => {
    const bad = { ...validReq, theme: "" };
    expect(() => validateRequest(bad)).toThrow("Missing theme");
  });

  it("throws on missing unit", () => {
    const bad = { ...validReq, unit: "" };
    expect(() => validateRequest(bad)).toThrow("Missing unit");
  });

  it("throws when sk is not an array", () => {
    const bad = { ...validReq, sk: "not array" as any };
    expect(() => validateRequest(bad)).toThrow("sk must be an array");
  });

  it("throws when sp is not an array", () => {
    const bad = { ...validReq, sp: null as any };
    expect(() => validateRequest(bad)).toThrow("sp must be an array");
  });

  it("throws on invalid studentCount", () => {
    const bad = { ...validReq, studentCount: 0 };
    expect(() => validateRequest(bad)).toThrow("Invalid studentCount");
  });

  it("allows omitting topic", () => {
    const { topic, ...noTopic } = validReq;
    const req = validateRequest(noTopic);
    expect(req.topic).toBe("");
  });

  it("allows omitting language (falls back to subject default)", () => {
    const { language, ...noLang } = validReq;
    const req = validateRequest(noLang);
    expect(req.language).toBe("bm");
  });
});
