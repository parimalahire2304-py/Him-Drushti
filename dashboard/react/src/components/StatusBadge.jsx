import React from "react";

const COLORS = {
  FRESH:            "bg-hds-green",
  STALE:            "bg-hds-amber",
  LAST_KNOWN_STATE: "bg-hds-red",
};

const LABELS = {
  FRESH:            "FRESH",
  STALE:            "STALE",
  LAST_KNOWN_STATE: "LAST-KNOWN-STATE",
};

export default function StatusBadge({ state, className = "" }) {
  const dot = COLORS[state] ?? "bg-hds-dim";
  const label = LABELS[state] ?? state ?? "—";
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-mono ${className}`}>
      <span className={`w-2 h-2 rounded-full ${dot}`} />
      {label}
    </span>
  );
}
