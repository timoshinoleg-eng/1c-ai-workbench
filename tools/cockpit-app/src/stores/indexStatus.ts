/**
 * Index status store. Reflects the parent workbench's current index state.
 * Backed by TanStack Query (see `useIndexStatus`); this Zustand store is
 * for derived UI state only (e.g., last-seen index timestamp).
 */
import { create } from "zustand";

interface IndexStatusState {
  lastSeenAt: string | null;
  fileCount: number;
  setSnapshot: (snapshot: { lastSeenAt: string; fileCount: number }) => void;
}

export const useIndexStatus = create<IndexStatusState>((set) => ({
  lastSeenAt: null,
  fileCount: 0,
  setSnapshot: (snapshot) =>
    set({
      lastSeenAt: snapshot.lastSeenAt,
      fileCount: snapshot.fileCount,
    }),
}));
