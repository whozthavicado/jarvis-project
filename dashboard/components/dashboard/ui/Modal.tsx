"use client";

import { useEffect } from "react";
import { X } from "lucide-react";

interface ModalProps {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}

export function Modal({ title, onClose, children }: ModalProps) {
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-zero border border-zero-border bg-zero-surface p-5 shadow-2xl"
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="hud-label text-xs text-white">{title}</h3>
          <button
            onClick={onClose}
            aria-label="Close"
            className="text-zero-text-muted hover:text-white"
          >
            <X size={16} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
