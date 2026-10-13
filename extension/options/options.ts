// Options page logic — manage identity profiles and field mapping rules
import { ProfileStore, FieldMapper } from "../src/core";
import type { IdentityProfile, FieldMapping } from "../../shared/types";

// Use the browser/Chrome crypto API for UUID generation (no external dep)
const uuidv4 = (): string => crypto.randomUUID();

document.addEventListener("DOMContentLoaded", async () => {
  const store = new ProfileStore();
  await store.load();
  const mapper = new FieldMapper();
  await mapper.load();

  const profileForm = document.getElementById("profileForm") as HTMLFormElement;
  const profileModal = document.getElementById("profileModal") as HTMLElement;
  const mappingForm = document.getElementById("mappingForm") as HTMLFormElement;
  const mappingModal = document.getElementById("mappingModal") as HTMLElement;

  // --- Tab navigation ---
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      const tab = btn.getAttribute("data-tab") + "Tab";
      document.querySelectorAll(".tab-content").forEach(tc => tc.classList.add("hidden"));
      document.getElementById(tab)?.classList.remove("hidden");
    });
  });

  // --- Render profiles ---
  function renderProfiles() {
    const list = document.getElementById("profilesList") as HTMLElement;
    list.innerHTML = "";
    store.list().forEach(p => {
      const card = document.createElement("div");
      card.className = "list-item";
      card.innerHTML = `
        <div class="item-info">
          <strong>${p.name}</strong>
          <small>IC: ${p.ic} | ID: ${p.teacherId} | ${p.email}</small>
        </div>
        <div class="item-actions">
          <button data-action="edit" data-id="${p.id}">✏️</button>
          <button data-action="delete" data-id="${p.id}">🗑️</button>
        </div>
      `;
      list.appendChild(card);
    });
  }

  // --- Render mappings ---
  function renderMappings() {
    const list = document.getElementById("mappingsList") as HTMLElement;
    list.innerHTML = "";
    mapper.list().forEach(m => {
      const card = document.createElement("div");
      card.className = "list-item";
      card.innerHTML =
        `<div class="item-info"><strong>${m.host}</strong><small>${m.selector} → ${m.source}.${m.sourceKey} (${m.transform || "none"})</small></div>` +
        `<div class="item-actions"><button data-action="edit-map" data-id="${m.id}">✏️</button><button data-action="delete-map" data-id="${m.id}">🗑️</button></div>`;
      list.appendChild(card);
    });
  }

  // --- Profile CRUD ---
  document.getElementById("addProfile")?.addEventListener("click", () => openProfileModal());

  profileForm?.addEventListener("submit", e => {
    e.preventDefault();
    const fd = new FormData(profileForm);
    const profile: IdentityProfile = {
      id: profileForm.querySelector("input[name=id]")?.value || uuidv4(),
      name: fd.get("name") as string,
      ic: fd.get("ic") as string,
      schoolCode: fd.get("schoolCode") as string,
      schoolName: fd.get("schoolName") as string,
      teacherId: fd.get("teacherId") as string,
      email: fd.get("email") as string,
      phone: fd.get("phone") as string,
      department: fd.get("department") as string,
      position: fd.get("position") as string,
    };
    const existing = store.get(profile.id);
    if (existing) { store.update(profile); } else { store.add(profile); }
    store.save();
    renderProfiles();
    profileModal.classList.add("hidden");
  });

  function openProfileModal(id?: string) {
    profileForm.reset();
    if (id) {
      const p = store.get(id);
      if (!p) return;
      (profileForm.querySelector("[name=id]") as HTMLInputElement).value = p.id;
      Object.entries(p).forEach(([k, v]) => {
        const f = profileForm.querySelector(`[name="${k}"]`) as HTMLInputElement | HTMLSelectElement | null;
        if (f) (f as HTMLInputElement).value = v ?? "";
      });
    }
    profileModal.classList.remove("hidden");
  }

  document.getElementById("cancelProfile")?.addEventListener("click", () => {
    profileModal.classList.add("hidden");
  });

  // --- Mapping CRUD ---
  document.getElementById("addMapping")?.addEventListener("click", () => openMappingModal());

  mappingForm?.addEventListener("submit", e => {
    e.preventDefault();
    const fd = new FormData(mappingForm);
    const mapping: FieldMapping = {
      id: mappingForm.querySelector("input[name=id]")?.value || uuidv4(),
      host: fd.get("host") as string,
      fieldId: fd.get("fieldId") as string,
      selector: fd.get("selector") as string,
      source: fd.get("source") as "identity" | "rph",
      sourceKey: fd.get("sourceKey") as string,
      transform: ((fd.get("transform") as string) || undefined) as unknown as FieldMapping["transform"],
    };
    const existing = mapper.list().find(m => m.id === mapping.id);
    if (existing) {
      mapper.remove(mapping.id);
    }
    mapper.add(mapping);
    mapper.save();
    renderMappings();
    mappingModal.classList.add("hidden");
  });

  function openMappingModal(id?: string) {
    mappingForm.reset();
    if (id) {
      const m = mapper.list().find(x => x.id === id);
      if (!m) return;
      (mappingForm.querySelector("[name=id]") as HTMLInputElement).value = m.id;
      Object.entries(m).forEach(([k, v]) => {
        const f = mappingForm.querySelector(`[name="${k}"]`) as HTMLInputElement | HTMLSelectElement | null;
        if (f) (f as HTMLInputElement).value = v ?? "";
      });
    }
    mappingModal.classList.remove("hidden");
  }

  document.getElementById("cancelMapping")?.addEventListener("click", () => {
    mappingModal.classList.add("hidden");
  });

  // --- Event delegation for edit/delete buttons ---
  document.getElementById("profilesList")?.addEventListener("click", (e) => {
    const target = e.target as HTMLElement;
    if (target.tagName !== "BUTTON") return;
    const id = target.closest(".list-item")?.querySelector("button")?.dataset.id;
    const action = target.dataset.action;
    if (action === "edit") openProfileModal(id);
    if (action === "delete") {
      store.remove(id!);
      store.save();
      renderProfiles();
    }
  });

  document.getElementById("mappingsList")?.addEventListener("click", (e) => {
    const target = e.target as HTMLElement;
    if (target.tagName !== "BUTTON") return;
    const id = target.dataset.id;
    const action = target.dataset.action;
    if (action === "edit-map") openMappingModal(id);
    if (action === "delete-map") {
      mapper.remove(id!);
      mapper.save();
      renderMappings();
    }
  });

  renderProfiles();
  renderMappings();
});
