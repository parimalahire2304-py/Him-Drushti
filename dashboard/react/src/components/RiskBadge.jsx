import React from "react";

const STYLES = {
  LOW:      "bg-hds-green/15 text-hds-green  border-hds-green/30",
  MODERATE: "bg-hds-amber/15 text-hds-amber  border-hds-amber/30",
  HIGH:     "bg-hds-red/15   text-hds-red    border-hds-red/30",
};

export default function RiskBadge({ level, score }) {
  const style = STYLES[level] ?? "bg-hds-dim/10 text-hds-dim border-hds-dim/30";
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-mono font-semibold border rounded ${style}`}>
      <span className="w-2 h-2 rounded-full bg-current opacity-60" />
      {level ?? "—"}
      {score != null && (
        <span className="opacity-60 ml-0.5">{typeof score === "number" ? score.toFixed(1) : score}</span>
      )}
    </span>
  );
}
