// Background service worker — handles extension lifecycle and fill requests
// Runs in the extension background context (no DOM access)

import { ProfileStore, FieldMapper } from "./core";
import type { IdentityProfile, FillSession } from "../../shared/types";

const MOE_HOSTS = [
  "idme.moe.gov.my",
  "idme.gov.my",
  "sgmy.moe.gov.my",
  "mysst.moe.gov.my",
  "apdmkpm.moe.gov.my",
];

// Check if the current tab URL is an MOE portal
function isMOESite(url: string): boolean {
  try {
    const host = new URL(url).hostname;
    return MOE_HOSTS.some(h => host === h || host.endsWith(".moe.gov.my") || host.endsWith(".kpm.gov.my"));
  } catch {
    return false;
  }
}

// Log a fill session to chrome.storage.local (not sync — keep sync lean)
async function logSession(session: FillSession): Promise<void> {
  const data = await chrome.storage.local.get("erph_fill_log");
  const log: FillSession[] = (data["erph_fill_log"] as FillSession[]) ?? [];
  log.unshift(session);
  if (log.length > 100) log.pop();
  await chrome.storage.local.set({ erph_fill_log: log });
}

// Main entry: receive fill command from popup, inject content script, run fill
async function executeFill(tabId: number, profile: IdentityProfile): Promise<void> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.url || !tab.id) throw new Error("No active tab");

  const host = new URL(tab.url).hostname;
  const mapper = new FieldMapper();
  await mapper.load();
  const mappings = mapper.getByHost(host);

  if (mappings.length === 0) {
    console.warn("[eRPH-PM] No field mappings for", host);
    return;
  }

  // Send fill command to the content script via messaging
  const response = await chrome.tabs.sendMessage(tab.id, {
    type: "ERPH_FILL_FIELDS",
    profile,
    mappings,
  });

  const results = response?.result ?? [];

  await logSession({
    host,
    timestamp: Date.now(),
    profile,
    results: results as any,
  });
}

// Listen for extension install
chrome.runtime.onInstalled.addListener(() => {
  console.log("[eRPH-PM] Extension installed");
});

// Listen for fill requests from the popup
chrome.runtime.onMessage.addListener((msg: any, _sender: unknown, sendResponse: (r: any) => void) => {
  if (msg.action === "FILL") {
    executeFill(msg.tabId, msg.profile)
      .then(() => sendResponse({ ok: true }))
      .catch(e => sendResponse({ ok: false, error: e instanceof Error ? e.message : String(e) }));
    return true; // async response
  }
  if (msg.action === "IS_MOE_SITE") {
    sendResponse({ isMOE: isMOESite(msg.url) });
  }
});

export { isMOESite, logSession, executeFill };
