import { useCallback, useState } from "react";

// Favorites are a per-browser convenience, so they live in localStorage rather than the database.
const KEY = "limber_favorites";

function load(): string[] {
  try { return JSON.parse(localStorage.getItem(KEY) ?? "[]"); } catch { return []; }
}

export function useFavorites() {
  const [ids, setIds] = useState<string[]>(load);
  const toggle = useCallback((id: string) => {
    setIds((prev) => {
      const next = prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id];
      try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* ignore */ }
      return next;
    });
  }, []);
  return { ids, has: (id: string) => ids.includes(id), toggle };
}
