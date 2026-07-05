"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

export const WS_URL_STORAGE_KEY = "zero.wsUrl";
export const WS_URL_CHANGED_EVENT = "zero:ws-url-changed";

interface SettingsValue {
  wsUrl: string;
  defaultWsUrl: string;
  setWsUrl: (url: string) => void;
  isOpen: boolean;
  open: () => void;
  close: () => void;
}

const SettingsContext = createContext<SettingsValue | null>(null);

function defaultWsUrl(): string {
  return process.env.NEXT_PUBLIC_ZERO_WS_URL || "ws://localhost:8765";
}

export function readStoredWsUrl(): string {
  if (typeof window === "undefined") return defaultWsUrl();
  return window.localStorage.getItem(WS_URL_STORAGE_KEY) || defaultWsUrl();
}

export function SettingsProvider({ children }: { children: React.ReactNode }) {
  const [wsUrl, setWsUrlState] = useState<string>(defaultWsUrl());
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    // Deliberate: reading localStorage during the initial render (instead of
    // after mount) would make the client's first paint diverge from the
    // server-rendered HTML and trigger a hydration mismatch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setWsUrlState(readStoredWsUrl());
  }, []);

  const setWsUrl = useCallback((url: string) => {
    const trimmed = url.trim();
    if (!trimmed) return;
    window.localStorage.setItem(WS_URL_STORAGE_KEY, trimmed);
    setWsUrlState(trimmed);
    window.dispatchEvent(new CustomEvent(WS_URL_CHANGED_EVENT, { detail: trimmed }));
  }, []);

  return (
    <SettingsContext.Provider
      value={{
        wsUrl,
        defaultWsUrl: defaultWsUrl(),
        setWsUrl,
        isOpen,
        open: () => setIsOpen(true),
        close: () => setIsOpen(false),
      }}
    >
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings(): SettingsValue {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error("useSettings must be used within SettingsProvider");
  return ctx;
}
