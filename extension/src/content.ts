// Content script — listens for fill commands from the background service worker.
// Runs in the page's isolated world (DOM access available).
import { fillFields } from "./core";
import type { IdentityProfile, FieldMapping, FillResult } from "../../shared/types";

chrome.runtime.onMessage.addListener((
  msg: { type?: string; profile?: IdentityProfile; mappings?: FieldMapping[] },
  _sender: chrome.runtime.MessageSender,
  sendResponse: (res: { result?: FillResult[]; error?: string }) => void,
) => {
  if (msg.type === "ERPH_FILL_FIELDS" && msg.profile && msg.mappings) {
    try {
      const result = fillFields(msg.mappings, msg.profile);
      sendResponse({ result });
    } catch (e) {
      sendResponse({ error: e instanceof Error ? e.message : String(e) });
    }
    return true; // keep channel open for async response
  }
  return false;
});

const MOE_HOSTS = [
  "idme.moe.gov.my", "idme.gov.my", "sgmy.moe.gov.my",
  "mysst.moe.gov.my", "apdmkpm.moe.gov.my",
];

function isMOESite(): boolean {
  if (!location.hostname) return false;
  return (
    MOE_HOSTS.includes(location.hostname) ||
    location.hostname.endsWith(".moe.gov.my") ||
    location.hostname.endsWith(".kpm.gov.my")
  );
}

if (isMOESite()) {
  const badge = document.createElement("div");
  badge.id = "erph-badge";
  badge.textContent = "🇲🇾";
  badge.title = "eRPH-PM AutoFill";
  badge.style.cssText = `
    position: fixed; bottom: 16px; right: 16px; z-index: 99999;
    width: 36px; height: 36px; border-radius: 50%;
    background: #C4956A; display: flex; align-items: center;
    justify-content: center; font-size: 20px; cursor: pointer;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3); border: 2px solid #fff;
  `;
  badge.onclick = () => {
    chrome.runtime.sendMessage({ action: "POPUP_OPEN" });
  };
  document.addEventListener("DOMContentLoaded", () => {
    document.body.appendChild(badge);
  });
}

console.log("[eRPH-PM] Content script loaded for", location.hostname);
