"use client";

import { createContext, useCallback, useContext, useState } from "react";

interface Toast {
  id: number;
  message: string;
}

interface ToastValue {
  showToast: (message: string) => void;
}

const ToastContext = createContext<ToastValue | null>(null);

const TOAST_DURATION_MS = 2800;
let toastCounter = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string) => {
    toastCounter += 1;
    const id = toastCounter;
    setToasts((prev) => [...prev, { id, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, TOAST_DURATION_MS);
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-6 z-[60] flex flex-col items-center gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className="rounded-lg border border-zero-border bg-zero-surface px-4 py-2 text-xs text-white shadow-lg"
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
