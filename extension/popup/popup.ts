// Popup UI logic — communicates with background.ts to trigger fill
import { ProfileStore } from "../src/core";
import type { IdentityProfile, FillResult } from "../shared/types";

document.addEventListener("DOMContentLoaded", async () => {
  const store = new ProfileStore();
  await store.load();

  const profileSelect = document.getElementById("profileSelect") as HTMLSelectElement;
  const fillBtn = document.getElementById("fillBtn") as HTMLButtonElement;
  const statusText = document.getElementById("statusText") as HTMLElement;
  const spinner = document.getElementById("spinner") as HTMLElement;
  const logContainer = document.getElementById("logContainer") as HTMLElement;
  const openOptions = document.getElementById("openOptions") as HTMLButtonElement;

  function renderProfiles() {
    profileSelect.innerHTML = "";
    store.list().forEach((p: IdentityProfile) => {
      const opt = document.createElement("option");
      opt.value = p.id;
      opt.textContent = `${p.name} (${p.teacherId || "—"})`;
      if (store.getActive()?.id === p.id) opt.selected = true;
      profileSelect.appendChild(opt);
    });
    if (store.list().length === 0) {
      profileSelect.innerHTML = '<option value="">Tiada profil — buka &amp; Tetapan</option>';
    }
    profileSelect.disabled = store.list().length === 0;
  }

  function log(msg: string, cls = "") {
    const el = document.createElement("div");
    el.className = `log-item ${cls}`;
    el.textContent = `${new Date().toLocaleTimeString("ms-MY")} — ${msg}`;
    logContainer.insertBefore(el, logContainer.firstChild);
    while (logContainer.children.length > 20) {
      logContainer.removeChild(logContainer.lastChild!);
    }
  }

  function logEmpty() {}

  renderProfiles();

  fillBtn.onclick = async () => {
    const profile = store.getActive();
    if (!profile) {
      log("Tiada profil aktif.", "error");
      return;
    }
    statusText.textContent = "Mengisi...";
    spinner.classList.add("active");
    log("Memulai pengisian otomatis...");

    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab?.id || !tab.url) {
        log("Buka portal IDMe terlebih dahulu.", "error");
        return;
      }
      const host = new URL(tab.url).hostname;
      const result = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: fillOnPage,
        args: [profile, host],
      });
      const results = result?.[0]?.result as FillResult[] | undefined;
      if (results) {
        const ok = results.filter(r => r.filled).length;
        const fail = results.filter(r => !r.found).length;
        log(`Berhasil: ${ok}, Gagal: ${fail}`);
        if (fail > 0) log("Buka & Tetapan untuk edit medan.", "error");
      }
    } catch (e) {
      log(`Ralat: ${e instanceof Error ? e.message : String(e)}`, "error");
    } finally {
      statusText.textContent = "Siap";
      spinner.classList.remove("active");
    }
  };

  openOptions.onclick = () => {
    chrome.runtime.openOptionsPage();
  };
});

// Injected function — runs in the page context
function fillOnPage(profile: IdentityProfile, host: string): FillResult[] {
  const results: FillResult[] = [];
  const selectors: Array<[string, keyof IdentityProfile]> = [
    ("#nama_penuh, [name=nama_penuh], #nama_lengkap, #name"),
    ("#no_ic, [name=no_ic], #ic_number, #no_ic_no"),
    ("#nombor_guru, [name=teacherId], #teacher_id"),
    ("#kod_sekolah, [name=schoolCode], #school_code"),
    ("#email, [name=email], #user_email"),
    ("#phone, [name=phone], #telephone"),
  ];

  // Simplified inline mapping for popup (full mapping managed in Options)
  const fieldMap: Array<[string, string]> = [
    ["#nama_penuh", profile.name],
    ["#no_ic", profile.ic],
    ["#nombor_guru", profile.teacherId],
    ["#kod_sekolah", profile.schoolCode],
    ["#email", profile.email],
    ["#phone", profile.phone],
  ];

  for (const [selector, value] of fieldMap) {
    const el = document.querySelector(selector);
    if (el) {
      const input = el as HTMLInputElement;
      input.value = value;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
      results.push({ selector, fieldId: selector, value, found: true, filled: true });
    } else {
      results.push({ selector, fieldId: selector, value, found: false, filled: false, error: "Element not found" });
    }
  }

  return results;
}
