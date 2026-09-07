import React from "react";
import { fmt } from "../lib/payloadAdapter";

function Row({ label, value }) {
  return (
    <tr className="border-b border-hds-border/40 last:border-0">
      <td className="py-1 pr-4 text-[10px] font-mono uppercase text-hds-dim whitespace-nowrap">{label}</td>
      <td className="py-1 text-xs font-mono text-hds-text text-right whitespace-nowrap">{value}</td>
    </tr>
  );
}

export default function ForecastCard({ fc }) {
  if (!fc) return <PanelEmpty />;

  const methodColor =
    fc.method === "MOTION_AWARE_XGBOOST"
      ? "text-hds-cyan"
      : fc.method === "PERSISTENCE_FALLBACK"
        ? "text-hds-amber"
        : "text-hds-text";

  const horizonDays = fc.horizonHrs != null ? (fc.horizonHrs / 24).toFixed(0) : null;

  const fmtCoord = (v, pos, neg) => {
    if (v == null) return "N/A";
    return `${Math.abs(v).toFixed(4)}° ${v >= 0 ? pos : neg}`;
  };

  return (
    <div className="rounded-md border border-hds-border bg-hds-panel p-3">
      <h3 className="mb-2 text-xs font-bold tracking-widest uppercase text-white flex items-center gap-2">
        <span className={methodColor}>➤</span> Trajectory Forecast
      </h3>

      {/* method banner */}
      <div
        className={
          "mb-2 px-2 py-1 rounded text-[10px] font-mono font-bold tracking-widest uppercase border " +
          (fc.method === "MOTION_AWARE_XGBOOST"
            ? "text-hds-cyan bg-hds-cyan/8 border-hds-cyan/25"
            : "text-hds-amber bg-hds-amber/8 border-hds-amber/25")
        }
      >
        {fc.method}
        {fc.fallback && <span className="ml-2 opacity-60 normal-case">fallback: {fmt(fc.fallbackReason, "", "—")}</span>}
      </div>

      <table className="w-full">
        <tbody>
          <Row label="Forecast Lat"   value={fmtCoord(fc.fcLat, "S", "N")} />
          <Row label="Forecast Lon"   value={fmtCoord(fc.fcLon, "E", "W")} />
          <Row label="Horizon"        value={horizonDays ? `${horizonDays} days (${fmt(fc.horizonHrs, "h")})` : "—"} />
          <Row label="Predecessor"    value={fmt(fc.predecessor != null ? (fc.predecessor ? "YES" : "NO") : null, "", "—")} />
          <Row label="Model"          value={fmt(fc.modelUsed, "", "—")} />
          <Row label="Data Freshness" value={fmt(fc.freshness, "", "—")} />
        </tbody>
      </table>
    </div>
  );
}

function PanelEmpty() {
  return (
    <div className="rounded-md border border-hds-border bg-hds-panel p-3">
      <h3 className="text-xs font-bold tracking-widest uppercase text-hds-dim">Trajectory Forecast</h3>
      <p className="mt-2 text-[10px] font-mono text-hds-dim">Awaiting forecast data…</p>
    </div>
  );
}