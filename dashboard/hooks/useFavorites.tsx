"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

const STORAGE_KEY = "zero.favorites";

interface FavoritesValue {
  favorites: string[];
  isFavorite: (id: string) => boolean;
  toggle: (id: string) => void;
}

const FavoritesContext = createContext<FavoritesValue | null>(null);

function readStored(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

export function FavoritesProvider({ children }: { children: React.ReactNode }) {
  const [favorites, setFavorites] = useState<string[]>([]);

  useEffect(() => {
    // Deliberate: reading localStorage during the initial render (instead of
    // after mount) would make the client's first paint diverge from the
    // server-rendered HTML and trigger a hydration mismatch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFavorites(readStored());
  }, []);

  const toggle = useCallback((id: string) => {
    setFavorites((prev) => {
      const next = prev.includes(id) ? prev.filter((f) => f !== id) : [...prev, id];
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const isFavorite = useCallback((id: string) => favorites.includes(id), [favorites]);

  return (
    <FavoritesContext.Provider value={{ favorites, isFavorite, toggle }}>
      {children}
    </FavoritesContext.Provider>
  );
}

export function useFavorites(): FavoritesValue {
  const ctx = useContext(FavoritesContext);
  if (!ctx) throw new Error("useFavorites must be used within FavoritesProvider");
  return ctx;
}
