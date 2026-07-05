"use client";

import { useState } from "react";
import { Modal } from "./ui/Modal";
import { useSettings } from "@/hooks/useSettings";
import { useToast } from "@/hooks/useToast";

export function SettingsModal() {
  const { isOpen, close, wsUrl, defaultWsUrl, setWsUrl } = useSettings();
  const { showToast } = useToast();
  const [draft, setDraft] = useState(wsUrl);

  if (!isOpen) return null;

  function save() {
    setWsUrl(draft);
    showToast("Backend URL saved -- reconnecting");
    close();
  }

  function resetToDefault() {
    setDraft(defaultWsUrl);
  }

  return (
    <Modal title="Settings" onClose={close}>
      <label className="hud-label mb-1 block text-[9px] text-zero-text-muted">
        Z.E.R.O backend WebSocket URL
      </label>
      <input
        type="text"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") save();
        }}
        className="mb-1 w-full rounded-lg border border-zero-border bg-transparent px-3 py-2 text-xs text-white outline-none"
      />
      <button
        onClick={resetToDefault}
        className="hud-label mb-4 text-[9px] text-zero-text-muted hover:text-white"
      >
        Reset to default ({defaultWsUrl})
      </button>
      <div className="flex justify-end gap-2">
        <button
          onClick={close}
          className="hud-label rounded-lg border border-zero-border px-3 py-2 text-[10px] text-zero-text-muted hover:text-white"
        >
          Cancel
        </button>
        <button
          onClick={save}
          className="hud-label rounded-lg bg-zero-accent px-3 py-2 text-[10px] text-black hover:opacity-90"
        >
          Save & Reconnect
        </button>
      </div>
    </Modal>
  );
}
