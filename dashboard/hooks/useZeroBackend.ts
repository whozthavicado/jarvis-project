"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useDashboardData } from "@/hooks/useDashboardData";
import { ActivityEntry } from "@/lib/types";

export type ConnectionState = "connecting" | "open" | "closed";
export type CoreStatus = "idle" | "thinking" | "speaking";

interface UseZeroBackend {
  connectionState: ConnectionState;
  coreStatus: CoreStatus;
  activityFeed: ActivityEntry[];
  lastReply: string | null;
  sendChat: (text: string) => void;
}

const DEFAULT_WS_URL = "ws://localhost:8765";
const MAX_BACKOFF_MS = 30_000;
const INITIAL_BACKOFF_MS = 1_000;
const MAX_LIVE_ENTRIES = 50;

function wsUrl(): string {
  return process.env.NEXT_PUBLIC_ZERO_WS_URL || DEFAULT_WS_URL;
}

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

export function useZeroBackend(): UseZeroBackend {
  const mockData = useDashboardData();

  const [connectionState, setConnectionState] = useState<ConnectionState>("connecting");
  const [coreStatus, setCoreStatus] = useState<CoreStatus>("idle");
  const [liveActivityFeed, setLiveActivityFeed] = useState<ActivityEntry[] | null>(null);
  const [lastReply, setLastReply] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(INITIAL_BACKOFF_MS);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmountedRef = useRef(false);

  useEffect(() => {
    unmountedRef.current = false;

    function connect() {
      if (unmountedRef.current) return;
      setConnectionState("connecting");
      const socket = new WebSocket(wsUrl());
      socketRef.current = socket;

      socket.onopen = () => {
        backoffRef.current = INITIAL_BACKOFF_MS;
        setConnectionState("open");
        socket.send(JSON.stringify({ type: "history" }));
      };

      socket.onmessage = (event) => {
        let message: any;
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
            actor: message.actor,
            description: message.description,
            minutesAgo: minutesAgo(message.timestamp),
          };
          setLiveActivityFeed((prev) => [entry, ...(prev ?? [])].slice(0, MAX_LIVE_ENTRIES));
        } else if (message?.type === "history" && Array.isArray(message.entries)) {
          const entries: ActivityEntry[] = message.entries.map((e: any) => ({
            id: nextEntryId(),
            actor: e.role === "assistant" ? "Z.E.R.O" : "User",
            description: e.text,
            minutesAgo: 0,
          }));
          setLiveActivityFeed(entries.reverse());
        } else if (message?.type === "reply" && typeof message.text === "string") {
          setLastReply(message.text);
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

  return {
    connectionState,
    coreStatus,
    activityFeed: liveActivityFeed ?? mockData.activityFeed,
    lastReply,
    sendChat,
  };
}
