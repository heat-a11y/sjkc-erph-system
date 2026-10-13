import { describe, it, expect, vi, beforeEach } from "vitest";
import { ProfileStore, FieldMapper, fillFields } from "../src/core";
import type { IdentityProfile, FieldMapping, RPHData } from "../../shared/types";

// Mock chrome.storage.sync
const mockStorage: Record<string, Record<string, unknown>> = {};
const mockChrome = {
  storage: {
    sync: {
      get: vi.fn(async (keys: string | string[]) => {
        if (typeof keys === "string") {
          return { [keys]: mockStorage[keys] ?? undefined };
        }
        const result: Record<string, unknown> = {};
        for (const k of keys) result[k] = mockStorage[k] ?? undefined;
        return result;
      }),
      set: vi.fn(async (items: Record<string, unknown>) => {
        Object.assign(mockStorage, items);
      }),
    },
  },
};
(globalThis as any).chrome = mockChrome;

const makeProfile = (override: Partial<IdentityProfile> = {}): IdentityProfile => ({
  id: "test-uuid-1",
  name: "TEOH BOON SIM",
  ic: "630101121234",
  schoolCode: "0001",
  schoolName: "SJKC PIN MIN, BIDOR",
  teacherId: "G123456",
  email: "teoh@sjkc-pinmin.edu.my",
  phone: "012-3456789",
  department: "Bahasa Melayu",
  position: "Guru",
  ...override,
});

describe("ProfileStore", () => {
  beforeEach(() => {
    mockChrome.storage.sync.get.mockClear();
    mockChrome.storage.sync.set.mockClear();
    for (const k of Object.keys(mockStorage)) delete mockStorage[k];
  });

  it("starts empty", async () => {
    const store = new ProfileStore();
    await store.load();
    expect(store.list()).toEqual([]);
  });

  it("adds and retrieves profiles", async () => {
    const store = new ProfileStore();
    await store.load();
    store.add(makeProfile());
    expect(store.list()).toHaveLength(1);
    expect(store.get("test-uuid-1")?.name).toBe("TEOH BOON SIM");
  });

  it("throws on duplicate id", async () => {
    const store = new ProfileStore();
    await store.load();
    store.add(makeProfile());
    expect(() => store.add(makeProfile())).toThrow("already exists");
  });

  it("updates a profile", async () => {
    const store = new ProfileStore();
    await store.load();
    const p = makeProfile();
    store.add(p);
    p.name = "LEE SHU WEN";
    store.update(p);
    expect(store.get("test-uuid-1")?.name).toBe("LEE SHU WEN");
  });

  it("removes a profile", async () => {
    const store = new ProfileStore();
    await store.load();
    store.add(makeProfile());
    store.remove("test-uuid-1");
    expect(store.list()).toEqual([]);
  });

  it("falls back to remaining profile when active is removed", async () => {
    const store = new ProfileStore();
    await store.load();
    store.add(makeProfile({ id: "a" }));
    store.add(makeProfile({ id: "b" }));
    store.setActive("b");
    expect(store.getActive()?.id).toBe("b");
    store.remove("b");
    // Falls back to the first remaining profile
    expect(store.getActive()?.id).toBe("a");
    // Removing the last profile clears the active id
    store.remove("a");
    expect(store.getActive()).toBeUndefined();
  });

  it("persists to chrome.storage.sync", async () => {
    const store = new ProfileStore();
    await store.load();
    store.add(makeProfile());
    await store.save();
    expect(mockStorage["erph_profiles"]).toBeDefined();
    expect((mockStorage["erph_profiles"] as IdentityProfile[]).length).toBe(1);
  });
});

describe("FieldMapper", () => {
  beforeEach(() => {
    for (const k of Object.keys(mockStorage)) delete mockStorage[k];
  });

  it("starts empty", async () => {
    const fm = new FieldMapper();
    await fm.load();
    expect(fm.list()).toEqual([]);
  });

  it("stores and retrieves mappings", async () => {
    const fm = new FieldMapper();
    await fm.load();
    const m: FieldMapping = {
      id: "m1",
      host: "idme.moe.gov.my",
      fieldId: "nama_lengkap",
      selector: "#nama_penuh",
      source: "identity",
      sourceKey: "name",
    };
    fm.add(m);
    expect(fm.list()).toHaveLength(1);
    const byHost = fm.getByHost("idme.moe.gov.my");
    expect(byHost).toHaveLength(1);
    expect(byHost[0].fieldId).toBe("nama_lengkap");
  });

  it("matches subdomains", async () => {
    const fm = new FieldMapper();
    await fm.load();
    fm.add({ id: "m1", host: "moe.gov.my", fieldId: "f1", selector: "#x", source: "identity", sourceKey: "name" });
    expect(fm.getByHost("idme.moe.gov.my")).toHaveLength(1);
  });

  it("removes mappings", async () => {
    const fm = new FieldMapper();
    await fm.load();
    fm.add({ id: "m1", host: "x.gov.my", fieldId: "f1", selector: "#x", source: "identity", sourceKey: "name" });
    fm.remove("m1");
    expect(fm.list()).toEqual([]);
  });
});

describe("fillFields", () => {
  const profile = makeProfile();

  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("fills text inputs from identity profile", async () => {
    document.body.innerHTML = `<input id="nama_penuh" type="text">`;
    const mappings: FieldMapping[] = [
      { id: "m1", host: "test", fieldId: "nama_lengkap", selector: "#nama_penuh", source: "identity", sourceKey: "name" }
    ];
    const results = await fillFields(mappings, profile);
    expect(results[0].found).toBe(true);
    expect(results[0].filled).toBe(true);
    expect((document.querySelector("#nama_penuh") as HTMLInputElement).value).toBe("TEOH BOON SIM");
  });

  it("fills by [name] attribute when CSS selector fails", async () => {
    document.body.innerHTML = `<input name="no_ic" type="text">`;
    const mappings: FieldMapping[] = [
      { id: "m1", host: "test", fieldId: "ic", selector: "no_ic", source: "identity", sourceKey: "ic" }
    ];
    const results = await fillFields(mappings, profile);
    expect(results[0].found).toBe(true);
    expect(results[0].value).toBe("630101121234");
  });

  it("applies uppercase transform", async () => {
    document.body.innerHTML = `<input id="email" type="text">`;
    const mappings: FieldMapping[] = [
      { id: "m1", host: "test", fieldId: "email", selector: "#email", source: "identity", sourceKey: "email", transform: "upper" }
    ];
    const results = await fillFields(mappings, profile);
    const input = document.querySelector("#email") as HTMLInputElement;
    expect(input.value).toBe("TEOH@SJKC-PINMIN.EDU.MY");
  });

  it("applies ic2dob transform (YYMMDD → YYYY-MM-DD)", async () => {
    document.body.innerHTML = `<input id="dob" type="text">`;
    const mappings: FieldMapping[] = [
      { id: "m1", host: "test", fieldId: "dob", selector: "#dob", source: "identity", sourceKey: "ic", transform: "ic2dob" }
    ];
    await fillFields(mappings, profile);
    const input = document.querySelector("#dob") as HTMLInputElement;
    // IC = 630101121234 → 1963-01-01
    expect(input.value).toBe("1963-01-01");
  });

  it("fills select dropdowns by text content", async () => {
    document.body.innerHTML = `<select id="dept"><option value="">--</option><option value="BM">Bahasa Melayu</option><option value="BI">English</option></select>`;
    const mappings: FieldMapping[] = [
      { id: "m1", host: "test", fieldId: "department", selector: "#dept", source: "identity", sourceKey: "department" }
    ];
    const results = await fillFields(mappings, profile);
    const sel = document.querySelector("#dept") as HTMLSelectElement;
    expect(sel.value).toBe("BM");
    expect(results[0].filled).toBe(true);
  });

  it("reports element not found", async () => {
    const mappings: FieldMapping[] = [
      { id: "m1", host: "test", fieldId: "missing", selector: "#nonexistent", source: "identity", sourceKey: "name" }
    ];
    const results = await fillFields(mappings, profile);
    expect(results[0].found).toBe(false);
    expect(results[0].filled).toBe(false);
    expect(results[0].error).toBe("Element not found");
  });

  it("fills from RPH data source", async () => {
    document.body.innerHTML = `<input id="tema" type="text"><input id="unit" type="text">`;
    const rph: RPHData = {
      subject: "BM", year: 3, language: "bm", class: "Tahun 3", week: 5,
      theme: "Sayangi Keluarga", unit: "Saya Sayang akan Keluarga", topic: "PKJR",
      date: "2025-01-15", period: 2,
      sk: [{ code: "1.1", desc: "Mendengar" }], sp: [{ code: "1.1.1", desc: "Mengucapkan" }],
      objectives: [], activities: {} as any, successCriteria: [],
      bbm: "", moralValues: "", emk: "", remedial: [], reflection: "",
      studentCount: 25,
    };
    const mappings: FieldMapping[] = [
      { id: "m1", host: "test", fieldId: "theme", selector: "#tema", source: "rph", sourceKey: "theme" },
      { id: "m2", host: "test", fieldId: "unit", selector: "#unit", source: "rph", sourceKey: "unit" },
    ];
    const results = await fillFields(mappings, profile, rph as any);
    expect(results[0].value).toBe("Sayangi Keluarga");
    expect(results[1].value).toBe("Saya Sayang akan Keluarga");
  });

  it("dispatches input/change events for Alpine/Vue reactivity", async () => {
    document.body.innerHTML = `<input id="x" type="text">`;
    const eventSpy = vi.fn();
    const input = document.querySelector("#x")!;
    input.addEventListener("input", eventSpy);
    input.addEventListener("change", eventSpy);
    const mappings: FieldMapping[] = [
      { id: "m1", host: "test", fieldId: "test", selector: "#x", source: "identity", sourceKey: "name" }
    ];
    await fillFields(mappings, profile);
    expect(eventSpy).toHaveBeenCalled();
    expect(eventSpy).toHaveBeenCalledWith(expect.objectContaining({ type: "input" }));
    expect(eventSpy).toHaveBeenCalledWith(expect.objectContaining({ type: "change" }));
  });
});
