"use client";

import { createContext, useCallback, useContext, useState } from "react";

export const SECTION_IDS = {
  dashboard: "top",
  system: "section-system",
  analysis: "section-analysis",
  projects: "section-projects",
  communications: "section-communications",
  automation: "section-automation",
  resources: "section-resources",
  security: "section-security",
} as const;

export type SectionKey = keyof typeof SECTION_IDS;

interface NavigationValue {
  activeSection: SectionKey;
  goTo: (section: SectionKey) => void;
}

const NavigationContext = createContext<NavigationValue | null>(null);

export function NavigationProvider({ children }: { children: React.ReactNode }) {
  const [activeSection, setActiveSection] = useState<SectionKey>("dashboard");

  const goTo = useCallback((section: SectionKey) => {
    setActiveSection(section);
    const id = SECTION_IDS[section];
    if (id === "top") {
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  return (
    <NavigationContext.Provider value={{ activeSection, goTo }}>
      {children}
    </NavigationContext.Provider>
  );
}

export function useNavigation(): NavigationValue {
  const ctx = useContext(NavigationContext);
  if (!ctx) throw new Error("useNavigation must be used within NavigationProvider");
  return ctx;
}
