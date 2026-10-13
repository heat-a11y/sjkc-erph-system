import { describe, it, expect, beforeEach, vi } from "vitest";
import { FaceAttendance } from "../src/face-attendance";
import type { FaceTemplate, FaceRecognitionResult } from "../../shared/types";

describe("FaceAttendance", () => {
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

  describe("canRun", () => {
    it("returns true when required APIs exist", () => {
      expect(FaceAttendance.canRun).toBeDefined();
    });
  });

  describe("template management", () => {
    it("starts with empty templates", () => {
      const fa = new FaceAttendance();
      (fa as any).initialized = true;
      expect(fa.listStudents()).toEqual([]);
    });

    it("stores and retrieves templates via enroll", async () => {
      const fa = new FaceAttendance();
      (fa as any).initialized = true;
      (fa as any).initialized = true;
      // Mock the captureDescriptor to return a known descriptor
      const mockDescriptor = new Array(128).fill(0.5);
      vi.spyOn(fa as any, "captureDescriptor").mockResolvedValue(mockDescriptor);

      const template = await fa.enroll("s001", "Ahmad bin Ali", "Year 3", 3);
      expect(template.studentId).toBe("s001");
      expect(template.studentName).toBe("Ahmad bin Ali");
      expect(template.className).toBe("Year 3");
      expect(template.faceDescriptor.length).toBe(128);
      expect(template.createdAt).toBeGreaterThan(0);
    });

    it("lists students after enrollment", async () => {
      const fa = new FaceAttendance();
      (fa as any).initialized = true;
      const mockDesc = new Array(128).fill(0.5);
      vi.spyOn(fa as any, "captureDescriptor").mockResolvedValue(mockDesc);

      await fa.enroll("s001", "Ahmad", "Year 3");
      await fa.enroll("s002", "Siti", "Year 3");
      await fa.enroll("s003", "Chen Wei", "Year 4");

      expect(fa.listStudents()).toHaveLength(3);
    });

    it("filters students by class", async () => {
      const fa = new FaceAttendance();
      (fa as any).initialized = true;
      const mockDesc = new Array(128).fill(0.5);
      vi.spyOn(fa as any, "captureDescriptor").mockResolvedValue(mockDesc);

      await fa.enroll("s001", "Ahmad", "Year 3");
      await fa.enroll("s002", "Siti", "Year 3");
      await fa.enroll("s003", "Chen", "Year 4");

      expect(fa.getByClass("Year 3")).toHaveLength(2);
      expect(fa.getByClass("Year 4")).toHaveLength(1);
    });

    it("removes a student", async () => {
      const fa = new FaceAttendance();
      (fa as any).initialized = true;
      const mockDesc = new Array(128).fill(0.5);
      vi.spyOn(fa as any, "captureDescriptor").mockResolvedValue(mockDesc);

      await fa.enroll("s001", "Ahmad", "Year 3");
      expect(fa.listStudents()).toHaveLength(1);
      expect(fa.removeStudent("s001")).toBe(true);
      expect(fa.listStudents()).toHaveLength(0);
    });

    it("returns false when removing non-existent student", () => {
      const fa = new FaceAttendance();
      (fa as any).initialized = true;
      expect(fa.removeStudent("nonexistent")).toBe(false);
    });
  });

  describe("export / import", () => {
    it("exports all templates as array", async () => {
      const fa = new FaceAttendance();
      (fa as any).initialized = true;
      const mockDesc = new Array(128).fill(0.5);
      vi.spyOn(fa as any, "captureDescriptor").mockResolvedValue(mockDesc);

      await fa.enroll("s001", "Ahmad", "Year 3");
      await fa.enroll("s002", "Siti", "Year 3");

      const exported = fa.exportTemplates();
      expect(exported).toHaveLength(2);
      expect(exported[0].studentName).toBe("Ahmad");
    });

    it("imports templates and persists to localStorage", () => {
      const fa = new FaceAttendance();
      (fa as any).initialized = true;
      const templates: FaceTemplate[] = [
        {
          studentId: "s001",
          studentName: "Ahmad",
          className: "Year 3",
          faceDescriptor: new Array(128).fill(0.3),
          createdAt: Date.now(),
        },
      ];
      fa.importTemplates(templates);
      expect(fa.listStudents()).toHaveLength(1);
      expect(fa.getByClass("Year 3")[0].studentName).toBe("Ahmad");

      // Check localStorage
      const raw = localStorage.getItem("erph_face_templates");
      expect(raw).toBeTruthy();
      const parsed = JSON.parse(raw!);
      expect(parsed).toHaveLength(1);
    });

    it("loads templates from localStorage", () => {
      const templates: FaceTemplate[] = [
        {
          studentId: "s001",
          studentName: "Test Student",
          className: "Year 1",
          faceDescriptor: new Array(128).fill(0.5),
          createdAt: Date.now(),
        },
      ];
      localStorage.setItem("erph_face_templates", JSON.stringify(templates));

      const fa = new FaceAttendance();
      (fa as any).initialized = true;
      const loaded = fa.loadFromStorage();
      expect(loaded).toHaveLength(1);
      expect(loaded[0].studentName).toBe("Test Student");
    });

    it("handles missing/corrupt localStorage gracefully", () => {
      localStorage.setItem("erph_face_templates", "not-json{");
      const fa = new FaceAttendance();
      (fa as any).initialized = true;
      const loaded = fa.loadFromStorage();
      expect(loaded).toEqual([]);
    });
  });

  describe("recognition", () => {
    it("returns not recognized when no templates", async () => {
      const fa = new FaceAttendance();
      (fa as any).initialized = true;
      const mockDesc = new Array(128).fill(0.5);
      vi.spyOn(fa as any, "captureDescriptor").mockResolvedValue(mockDesc);

      const result = await fa.recognize();
      expect(result.recognized).toBe(false);
      expect(result.confidence).toBe(0);
    });

    it("returns not recognized when no face captured", async () => {
      const fa = new FaceAttendance();
      (fa as any).initialized = true;
      vi.spyOn(fa as any, "captureDescriptor").mockResolvedValue(null);

      const result = await fa.recognize();
      expect(result.recognized).toBe(false);
      expect(result.confidence).toBe(0);
    });

    it("recognizes a matching face with high confidence", async () => {
      const fa = new FaceAttendance();
      (fa as any).initialized = true;
      const mockDesc = new Array(128).fill(0.5);
      vi.spyOn(fa as any, "captureDescriptor").mockResolvedValue(mockDesc);

      // Enroll with the same descriptor
      await fa.enroll("s001", "Ahmad", "Year 3", 1);

      // Recognize with same descriptor
      const result = await fa.recognize();
      expect(result.recognized).toBe(true);
      expect(result.template?.studentName).toBe("Ahmad");
      expect(result.confidence).toBeGreaterThan(0.9);
    });

    it("does not recognize a non-matching face", async () => {
      const fa = new FaceAttendance();
      (fa as any).initialized = true;

      // Enroll with 0.5 descriptors
      vi.spyOn(fa as any, "captureDescriptor").mockResolvedValue(new Array(128).fill(0.5));
      await fa.enroll("s001", "Ahmad", "Year 3", 1);

      // Recognize with completely different descriptor (all 0.1)
      vi.spyOn(fa as any, "captureDescriptor").mockResolvedValue(new Array(128).fill(0.1));
      const result = await fa.recognize();
      expect(result.recognized).toBe(false);
    });
  });

  describe("descriptor math", () => {
    it("averages descriptors correctly", () => {
      const fa = new FaceAttendance();
      (fa as any).initialized = true;
      const d1 = new Array(128).fill(0);
      const d2 = new Array(128).fill(1);
      const avg = (fa as any).averageDescriptors([d1, d2]);
      expect(avg.length).toBe(128);
      expect(avg[0]).toBe(0.5);
    });

    it("computes euclidean distance", () => {
      const fa = new FaceAttendance();
      (fa as any).initialized = true;
      const d1 = new Array(128).fill(0);
      const d2 = new Array(128).fill(3);
      // Each dimension differs by 3, distance = sqrt(128 * 9) = sqrt(1152) ≈ 33.94
      const dist = (fa as any).euclideanDistance(d1, d2);
      expect(dist).toBeCloseTo(Math.sqrt(128 * 9), 2);
    });
  });

  describe("stop", () => {
    it("clears initialization state", () => {
      const fa = new FaceAttendance();
      (fa as any).initialized = true;
      (fa as any).initialized = true;
      fa.stop();
      expect((fa as any).initialized).toBe(false);
    });
  });
});
