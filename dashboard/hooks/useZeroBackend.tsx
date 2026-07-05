"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { useDashboardData } from "@/hooks/useDashboardData";
import { readStoredWsUrl, WS_URL_CHANGED_EVENT } from "@/hooks/useSettings";
import { ActivityEntry } from "@/lib/types";

export type ConnectionState = "connecting" | "open" | "closed";
export type CoreStatus = "idle" | "thinking" | "speaking";

interface UseZeroBackend {
  connectionState: ConnectionState;
  coreStatus: CoreStatus;
  activityFeed: ActivityEntry[];
  lastReply: string | null;
  sendChat: (text: string) => void;
  remember: (text: string) => Promise<boolean>;
}

const MAX_BACKOFF_MS = 30_000;
const INITIAL_BACKOFF_MS = 1_000;
const MAX_LIVE_ENTRIES = 50;

function minutesAgo(timestamp: string): number {
  const then = new Date(timestamp).getTime();
  if (Number.isNaN(then)) return 0;
  return Math.max(0, Math.floor((Date.now() - then) / 60_000));
}

let entryCounter = 0;
function nextEntryId(): string {
  entryCounter += 1;
  return `live-${Date.now()}-${entryCounter}`;
}

function useZeroBackendConnection(): UseZeroBackend {
  const mockData = useDashboardData();

  const [connectionState, setConnectionState] = useState<ConnectionState>("connecting");
  const [coreStatus, setCoreStatus] = useState<CoreStatus>("idle");
  const [liveActivityFeed, setLiveActivityFeed] = useState<ActivityEntry[] | null>(null);
  const [lastReply, setLastReply] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(INITIAL_BACKOFF_MS);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmountedRef = useRef(false);
  const rememberQueueRef = useRef<Array<(added: boolean) => void>>([]);

  useEffect(() => {
    function onWsUrlChanged() {
      // Reconnecting picks up the new URL via readStoredWsUrl() inside
      // connect() -- closing here just makes it happen immediately instead
      // of waiting for a network-level disconnect.
      backoffRef.current = INITIAL_BACKOFF_MS;
      socketRef.current?.close();
    }
    window.addEventListener(WS_URL_CHANGED_EVENT, onWsUrlChanged);
    return () => window.removeEventListener(WS_URL_CHANGED_EVENT, onWsUrlChanged);
  }, []);

  useEffect(() => {
    unmountedRef.current = false;

    function connect() {
      if (unmountedRef.current) return;
      setConnectionState("connecting");
      const socket = new WebSocket(readStoredWsUrl());
      socketRef.current = socket;

      socket.onopen = () => {
        backoffRef.current = INITIAL_BACKOFF_MS;
        setConnectionState("open");
        socket.send(JSON.stringify({ type: "history" }));
      };

      socket.onmessage = (event) => {
        let message: Record<string, unknown>;
        try {
          message = JSON.parse(event.data);
        } catch {
          return;
        }

        if (message?.type === "status" && typeof message.state === "string") {
          setCoreStatus(message.state as CoreStatus);
        } else if (message?.type === "activity") {
          const entry: ActivityEntry = {
            id: nextEntryId(),
            actor: message.actor as ActivityEntry["actor"],
            description: message.description as string,
            minutesAgo: minutesAgo(message.timestamp as string),
          };
          setLiveActivityFeed((prev) => [entry, ...(prev ?? [])].slice(0, MAX_LIVE_ENTRIES));
        } else if (message?.type === "history" && Array.isArray(message.entries)) {
          const entries: ActivityEntry[] = (
            message.entries as Array<{ role: string; text: string }>
          ).map((e) => ({
            id: nextEntryId(),
            actor: e.role === "assistant" ? "Z.E.R.O" : "User",
            description: e.text,
            minutesAgo: 0,
          }));
          setLiveActivityFeed(entries.reverse());
        } else if (message?.type === "reply" && typeof message.text === "string") {
          setLastReply(message.text);
        } else if (message?.type === "remember_ack") {
          const resolve = rememberQueueRef.current.shift();
          resolve?.(Boolean(message.added));
        }
      };

      socket.onclose = () => {
        if (unmountedRef.current) return;
        setConnectionState("closed");
        const delay = backoffRef.current;
        backoffRef.current = Math.min(delay * 2, MAX_BACKOFF_MS);
        reconnectTimerRef.current = setTimeout(connect, delay);
      };

      socket.onerror = () => {
        socket.close();
      };
    }

    connect();

    return () => {
      unmountedRef.current = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      socketRef.current?.close();
    };
  }, []);

  const sendChat = useCallback((text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    const socket = socketRef.current;
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "chat", text: trimmed }));
    }
  }, []);

  const remember = useCallback((text: string): Promise<boolean> => {
    const trimmed = text.trim();
    const socket = socketRef.current;
    if (!trimmed || !socket || socket.readyState !== WebSocket.OPEN) {
      return Promise.resolve(false);
    }
    return new Promise((resolve) => {
      rememberQueueRef.current.push(resolve);
      socket.send(JSON.stringify({ type: "remember", text: trimmed }));
    });
  }, []);

  return {
    connectionState,
    coreStatus,
    activityFeed: liveActivityFeed ?? mockData.activityFeed,
    lastReply,
    sendChat,
    remember,
  };
}

// One real WebSocket for the whole dashboard -- every consumer reads from
// the same connection/state instead of each opening its own socket.
const ZeroBackendContext = createContext<UseZeroBackend | null>(null);

export function ZeroBackendProvider({ children }: { children: React.ReactNode }) {
  const value = useZeroBackendConnection();
  return <ZeroBackendContext.Provider value={value}>{children}</ZeroBackendContext.Provider>;
}

export function useZeroBackend(): UseZeroBackend {
  const ctx = useContext(ZeroBackendContext);
  if (!ctx) throw new Error("useZeroBackend must be used within ZeroBackendProvider");
  return ctx;
}
