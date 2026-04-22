"use client";

/**
 * Minimal right-click context menu for the Files panel.
 *
 * Not building a Radix-based one because the standard component expects
 * to be mounted as a wrapper around the target element; we want
 * cursor-positioned invocation across a tree of many rows without
 * wiring every row individually. The caller passes the click coords and
 * an array of items; we portal a small fixed-position menu into <body>.
 *
 * Closes on:
 *   - click anywhere outside the menu
 *   - Escape
 *   - picking an item (the item handler is responsible for the action
 *     — the menu just calls it and closes)
 *
 * Positioning clamps to viewport so right-clicks near the bottom/right
 * edge don't put the menu off-screen.
 */

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export type FileContextMenuItem = {
  label: string;
  onSelect: () => void;
  /** Danger styling (red hover). */
  destructive?: boolean;
  /** Disable an item (still renders, muted). */
  disabled?: boolean;
};

export function FileContextMenu({
  x,
  y,
  items,
  onClose,
}: {
  x: number;
  y: number;
  items: FileContextMenuItem[];
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [pos, setPos] = useState<{ left: number; top: number }>({
    left: x,
    top: y,
  });
  const [mounted, setMounted] = useState(false);

  // Portal needs a DOM target — wait for client mount.
  useEffect(() => setMounted(true), []);

  // After paint, measure and clamp into viewport so the menu doesn't
  // spill off-screen when right-clicking near bottom/right edges.
  useLayoutEffect(() => {
    if (!ref.current) return;
    const r = ref.current.getBoundingClientRect();
    const pad = 4;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const left = Math.min(x, vw - r.width - pad);
    const top = Math.min(y, vh - r.height - pad);
    setPos({ left: Math.max(pad, left), top: Math.max(pad, top) });
  }, [x, y]);

  // Close on outside click / Escape.
  useEffect(() => {
    const onDocMouseDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    // Listen on capture so we beat other handlers that might stopPropagation.
    document.addEventListener("mousedown", onDocMouseDown, true);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocMouseDown, true);
      document.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  if (!mounted) return null;

  return createPortal(
    <div
      ref={ref}
      role="menu"
      aria-orientation="vertical"
      className="fixed z-[9999] min-w-[160px] rounded-md border border-[var(--border)] bg-[var(--bg-secondary)] shadow-lg py-1 text-sm"
      style={{ left: pos.left, top: pos.top }}
      // Stop context-menu-on-the-menu so users can right-click within
      // our menu without opening the browser's native one.
      onContextMenu={(e) => e.preventDefault()}
    >
      {items.map((it, i) => (
        <button
          key={i}
          type="button"
          role="menuitem"
          disabled={it.disabled}
          onClick={() => {
            if (it.disabled) return;
            it.onSelect();
            onClose();
          }}
          className={
            "w-full text-left px-3 py-1.5 text-[13px] transition-colors " +
            (it.disabled
              ? "text-[var(--text-secondary)] opacity-50 cursor-not-allowed"
              : it.destructive
                ? "text-[var(--red)] hover:bg-[var(--red)]/15"
                : "text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)]")
          }
        >
          {it.label}
        </button>
      ))}
    </div>,
    document.body,
  );
}
