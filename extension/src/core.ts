import { type IdentityProfile, type FieldMapping, type FillResult, STORAGE_KEYS } from "../../shared/types";

// ---------------------------------------------------------------------------
// Profile Store — wraps chrome.storage.sync with typed accessors
// ---------------------------------------------------------------------------

export class ProfileStore {
  private profiles: IdentityProfile[] = [];
  private activeId: string | null = null;
  private ready: Promise<void>;

  constructor() {
    this.ready = this.load();
  }

  async load(): Promise<void> {
    const data = await chrome.storage.sync.get([
      STORAGE_KEYS.profiles,
      STORAGE_KEYS.activeProfileId,
    ]);
    this.profiles = data[STORAGE_KEYS.profiles] ?? [];
    this.activeId = data[STORAGE_KEYS.activeProfileId] ?? null;
  }

  async save(): Promise<void> {
    await this.ready;
    await chrome.storage.sync.set({
      [STORAGE_KEYS.profiles]: this.profiles,
      [STORAGE_KEYS.activeProfileId]: this.activeId,
    });
  }

  list(): IdentityProfile[] {
    this.profiles ??= [];
    return [...this.profiles];
  }

  get(id: string): IdentityProfile | undefined {
    return this.profiles.find(p => p.id === id);
  }

  getActive(): IdentityProfile | undefined {
    return this.activeId ? this.get(this.activeId) : undefined;
  }

  setActive(id: string): void {
    if (!this.profiles.some(p => p.id === id)) {
      throw new Error(`Unknown profile id: ${id}`);
    }
    this.activeId = id;
  }

  add(profile: IdentityProfile): void {
    if (this.profiles.some(p => p.id === profile.id)) {
      throw new Error(`Profile already exists: ${profile.id}`);
    }
    this.profiles.push(profile);
  }

  update(profile: IdentityProfile): void {
    const idx = this.profiles.findIndex(p => p.id === profile.id);
    if (idx < 0) {
      throw new Error(`Profile not found: ${profile.id}`);
    }
    this.profiles[idx] = profile;
  }

  remove(id: string): void {
    this.profiles = this.profiles.filter(p => p.id !== id);
    if (this.activeId === id) this.activeId = this.profiles[0]?.id ?? null;
  }
}

// ---------------------------------------------------------------------------
// Field Mapper — manages field-mapping rules per hostname
// ---------------------------------------------------------------------------

export class FieldMapper {
  private mappings: FieldMapping[] = [];
  private ready: Promise<void>;

  constructor(private storeKey = STORAGE_KEYS.fieldMappings) {
    this.ready = this.load();
  }

  async load(): Promise<void> {
    const data = await chrome.storage.sync.get(this.storeKey);
    this.mappings = data[this.storeKey] ?? [];
  }

  async save(): Promise<void> {
    await this.ready;
    await chrome.storage.sync.set({ [this.storeKey]: this.mappings });
  }

  list(): FieldMapping[] {
    return [...this.mappings];
  }

  getByHost(host: string): FieldMapping[] {
    return this.mappings
      .filter(m => host === m.host || host.endsWith("." + m.host))
      .sort((a, b) => a.fieldId.localeCompare(b.fieldId));
  }

  add(mapping: FieldMapping): void {
    if (this.mappings.some(m => m.id === mapping.id)) {
      throw new Error(`Mapping already exists: ${mapping.id}`);
    }
    this.mappings.push(mapping);
  }

  remove(id: string): void {
    this.mappings = this.mappings.filter(m => m.id !== id);
  }
}

// ---------------------------------------------------------------------------
// Filler — reads DOM, applies transforms, writes values
// ---------------------------------------------------------------------------

function resolvePath(obj: object, path: string): unknown {
  return path.split(".").reduce<unknown>((acc, key) => {
    if (acc && typeof acc === "object" && key in acc) {
      return (acc as Record<string, unknown>)[key];
    }
    return undefined;
  }, obj);
}

function transformValue(value: string, transform?: string): string {
  switch (transform) {
    case "upper": return value.toUpperCase();
    case "lower": return value.toLowerCase();
    case "title": return value.replace(/\w\S*/g, t => t.charAt(0).toUpperCase() + t.slice(1).toLowerCase());
    case "ic2dob": {
      // IC format: YYMMDD-##-#### → YYYY-MM-DD
      // First 6 digits encode YYMMDD
      if (!/^\d{6,}/.test(value)) return value;
      const y = parseInt(value.slice(0, 2), 10);
      const year = y < 40 ? 2000 + y : 1900 + y;
      const mm = value.slice(2, 4);
      const dd = value.slice(4, 6);
      return `${year}-${mm}-${dd}`;
    }
    default: return value;
  }
}

export async function fillFields(
  mappings: FieldMapping[],
  profile: IdentityProfile,
  rphData?: Record<string, unknown>,
): Promise<FillResult[]> {
  const results: FillResult[] = [];

  for (const m of mappings) {
    let raw: unknown;
    if (m.source === "identity") {
      raw = resolvePath(profile, m.sourceKey);
    } else if (rphData) {
      raw = resolvePath(rphData, m.sourceKey);
    }

    const stringVal = raw != null ? String(raw) : "";
    const value = transformValue(stringVal, m.transform);

    let found = false;
    let filled = false;
    let error: string | undefined;

    try {
      // Try multiple selector strategies, each in its own try-catch so
      // an invalid CSS selector string never aborts the whole field.
      let el: Element | null = null;

      // 1. Direct CSS selector
      try { el ||= document.querySelector(m.selector); } catch { /* invalid selector, try fallbacks */ }

      // 2. Fallback: treat selector as name / id / class if not already an attribute selector
      if (!el && !m.selector.startsWith("[")) {
        try {
          el ||= document.querySelector(`[name="${CSS.escape(m.selector)}"]`);
        } catch {}
        if (!el) {
          try { el ||= document.querySelector(`#${CSS.escape(m.selector)}`); } catch {}
        }
        if (!el) {
          try { el ||= document.querySelector(`.${CSS.escape(m.selector)}`); } catch {}
        }
        if (!el) {
          // name attribute fallback (most robust for form inputs)
          const named = document.getElementsByName(m.selector);
          el ||= named[0] || null;
        }
      }

      if (!el) {
        error = "Element not found";
      } else {
        found = true;
        if (el instanceof HTMLInputElement) {
          if (el.type === "checkbox" || el.type === "radio") {
            el.checked = value === "true" || value === "1";
            filled = el.checked;
          } else if (el.type === "select-one" || el.tagName === "SELECT") {
            // select
            const sel = el as HTMLSelectElement;
            const option = Array.from(sel.options).find(o =>
              o.value === value || o.textContent?.trim() === value
            );
            if (option) { sel.value = option.value; filled = true; }
            else { error = `No matching option for value "${value}"`; }
          } else {
            el.value = value;
            // Trigger React/Vue/Alpine change events
            el.dispatchEvent(new Event("input", { bubbles: true }));
            el.dispatchEvent(new Event("change", { bubbles: true }));
            el.dispatchEvent(new Event("blur", { bubbles: true }));
            filled = true;
          }
        } else if (el instanceof HTMLTextAreaElement) {
          el.value = value;
          el.dispatchEvent(new Event("input", { bubbles: true }));
          el.dispatchEvent(new Event("change", { bubbles: true }));
          filled = true;
        } else if (el.tagName === "SELECT") {
          const sel = el as HTMLSelectElement;
          const option = Array.from(sel.options).find(o =>
            o.value === value || o.textContent?.trim() === value
          );
          if (option) { sel.value = option.value; filled = true; }
          else { error = `No matching option for value "${value}"`; }
        } else {
          // ContentEditable or other
          (el as HTMLElement).textContent = value;
          el.dispatchEvent(new Event("input", { bubbles: true }));
          filled = true;
        }
      }
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }

    results.push({
      selector: m.selector,
      fieldId: m.fieldId,
      value,
      found,
      filled,
      error,
    });
  }

  return results;
}
