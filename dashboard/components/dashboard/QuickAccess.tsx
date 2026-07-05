"use client";

import { useMemo, useState } from "react";
import { Star, LayoutDashboard, BarChart3, Settings, Plus } from "lucide-react";
import { Panel } from "./ui/Panel";
import { Modal } from "./ui/Modal";
import { useNavigation } from "@/hooks/useNavigation";
import { useSettings } from "@/hooks/useSettings";
import { useFavorites } from "@/hooks/useFavorites";
import { useDashboardData } from "@/hooks/useDashboardData";
import { useZeroBackend } from "@/hooks/useZeroBackend";
import { useToast } from "@/hooks/useToast";

function FavoritesModal({ onClose }: { onClose: () => void }) {
  const { favorites, toggle } = useFavorites();
  const { activeModules, keyProjects } = useDashboardData();

  const items = useMemo(() => {
    return favorites
      .map((favId) => {
        const [kind, id] = favId.split(":");
        if (kind === "module") {
          const mod = activeModules.find((m) => m.id === id);
          return mod ? { favId, label: mod.name, kind: "Module" } : null;
        }
        if (kind === "project") {
          const project = keyProjects.find((p) => p.id === id);
          return project ? { favId, label: project.name, kind: "Project" } : null;
        }
        return null;
      })
      .filter((x): x is { favId: string; label: string; kind: string } => x !== null);
  }, [favorites, activeModules, keyProjects]);

  return (
    <Modal title="Favorites" onClose={onClose}>
      {items.length === 0 ? (
        <p className="hud-label text-[10px] text-zero-text-muted">
          No favorites yet -- star a module or project to pin it here.
        </p>
      ) : (
        <ul className="space-y-2">
          {items.map((item) => (
            <li key={item.favId} className="flex items-center justify-between">
              <span className="text-xs text-white">
                {item.label} <span className="hud-label text-zero-text-muted">· {item.kind}</span>
              </span>
              <button
                onClick={() => toggle(item.favId)}
                className="text-zero-accent hover:text-white"
                aria-label="Unfavorite"
              >
                <Star size={14} fill="currentColor" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </Modal>
  );
}

function AddNoteModal({ onClose }: { onClose: () => void }) {
  const { remember } = useZeroBackend();
  const { showToast } = useToast();
  const [text, setText] = useState("");
  const [saving, setSaving] = useState(false);

  async function save() {
    const trimmed = text.trim();
    if (!trimmed) return;
    setSaving(true);
    const added = await remember(trimmed);
    setSaving(false);
    showToast(added ? "Saved to Z.E.R.O's memory" : "Already remembered");
    onClose();
  }

  return (
    <Modal title="Add a Quick Note" onClose={onClose}>
      <textarea
        autoFocus
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="What should Z.E.R.O remember?"
        rows={3}
        className="mb-3 w-full resize-none rounded-lg border border-zero-border bg-transparent px-3 py-2 text-xs text-white outline-none"
      />
      <div className="flex justify-end gap-2">
        <button
          onClick={onClose}
          className="hud-label rounded-lg border border-zero-border px-3 py-2 text-[10px] text-zero-text-muted hover:text-white"
        >
          Cancel
        </button>
        <button
          onClick={save}
          disabled={saving || !text.trim()}
          className="hud-label rounded-lg bg-zero-accent px-3 py-2 text-[10px] text-black hover:opacity-90 disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save"}
        </button>
      </div>
    </Modal>
  );
}

export function QuickAccess() {
  const { goTo } = useNavigation();
  const { open: openSettings } = useSettings();
  const [showFavorites, setShowFavorites] = useState(false);
  const [showAddNote, setShowAddNote] = useState(false);

  const ITEMS = [
    { icon: Star, label: "Favorites", onClick: () => setShowFavorites(true) },
    { icon: LayoutDashboard, label: "Dashboard", onClick: () => goTo("dashboard") },
    { icon: BarChart3, label: "Analytics", onClick: () => goTo("analysis") },
    { icon: Settings, label: "Config", onClick: openSettings },
    { icon: Plus, label: "Add", onClick: () => setShowAddNote(true) },
  ];

  return (
    <Panel label="Quick Access">
      <div className="flex gap-2">
        {ITEMS.map(({ icon: Icon, label, onClick }) => (
          <button
            key={label}
            aria-label={label}
            onClick={onClick}
            className="flex h-10 w-10 items-center justify-center rounded-lg border border-zero-border text-zero-text-muted hover:text-zero-accent"
          >
            <Icon size={16} />
          </button>
        ))}
      </div>

      {showFavorites && <FavoritesModal onClose={() => setShowFavorites(false)} />}
      {showAddNote && <AddNoteModal onClose={() => setShowAddNote(false)} />}
    </Panel>
  );
}
