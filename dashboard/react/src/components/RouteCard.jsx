import React from "react";
import { fmt } from "../lib/payloadAdapter";

function Row({ label, value, accent }) {
  return (
    <tr className="border-b border-hds-border/40 last:border-0">
      <td className="py-1 pr-4 text-[10px] font-mono uppercase text-hds-dim whitespace-nowrap">{label}</td>
      <td className={`py-1 text-xs font-mono text-right whitespace-nowrap ${accent ?? "text-hds-text"}`}>{value}</td>
    </tr>
  );
}

export default function RouteCard({ route }) {
  if (!route) return <PanelEmpty />;

  const noRoute = route.status === "NO_SAFE_ROUTE_FOUND";
  const hasGeo = Array.isArray(route.waypoints) && route.waypoints.length >= 2;

  return (
    <div
      className={
        "rounded-md border p-3 " +
        (noRoute ? "border-hds-red/50 bg-hds-red/8" : "border-hds-border bg-hds-panel")
      }
    >
      <h3
        className={
          "mb-2 text-xs font-bold tracking-widest uppercase flex items-center gap-2 " +
          (noRoute ? "text-hds-red" : "text-white")
        }
      >
        <span>{noRoute ? "✕" : "⌖"}</span> Route Decision
      </h3>

      {/* status badge */}
      <div
        className={
          "mb-2 px-2 py-1 rounded text-[10px] font-mono font-bold tracking-widest border " +
          (noRoute
            ? "text-hds-red bg-hds-red/10 border-hds-red/40"
            : route.status === "CAUTION"
              ? "text-hds-amber bg-hds-amber/8 border-hds-amber/30"
              : "text-hds-green bg-hds-green/8 border-hds-green/30")
        }
      >
        {noRoute ? "NO SAFE ROUTE FOUND" : route.status}
      </div>

      {noRoute ? (
        <div className="mt-1 mb-2 px-2 py-2 rounded bg-hds-red/10 border border-hds-red/30">
          <p className="text-[10px] font-mono text-hds-red leading-relaxed">
            No safe route exists between the origin and destination under the
            current risk assessment. <b>No route is drawn.</b>
          </p>
        </div>
      ) : null}

      <table className="w-full">
        <tbody>
          <Row label="Route Label" value={fmt(route.label, "", "—")} />
          <Row label="Route Dist"  value={fmt(route.distKm, "km", "—")} />
          <Row label="Direct Dist" value={fmt(route.directKm, "km", "—")} />
          <Row label="Overhead"    value={fmt(route.overheadPct, "%", "—")} />
          <Row label="Travel Time" value={fmt(route.travelHrs, "h (est.)", "—")} />
          <Row label="Max Risk"    value={fmt(route.maxRisk, "/100", "—")} />
          <Row label="Waypoints"   value={Array.isArray(route.waypoints) ? String(route.waypoints.length) : "—"} />
          <Row label="Freshness"   value={fmt(route.freshness, "", "—")} />
        </tbody>
      </table>

      {!noRoute && hasGeo && (
        <div className="mt-2 pt-2 border-t border-hds-border">
          <p className="text-[9px] font-mono uppercase text-hds-dim mb-1">Waypoints (route polyline)</p>
          <div className="max-h-20 overflow-y-auto space-y-0.5">
            {route.waypoints.map((wp, i, arr) => (
              <div key={i} className="flex justify-between text-[10px] font-mono text-hds-text">
                <span className="text-hds-dim">
                  {i === 0 ? "START" : i === arr.length - 1 ? "DEST" : `WP-${i}`}
                </span>
                <span>
                  {wp.lat != null ? wp.lat.toFixed(3) : "—"},&nbsp;
                  {wp.lon != null ? wp.lon.toFixed(3) : "—"}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function PanelEmpty() {
  return (
    <div className="rounded-md border border-hds-border bg-hds-panel p-3">
      <h3 className="text-xs font-bold tracking-widest uppercase text-hds-dim">Route Decision</h3>
      <p className="mt-2 text-[10px] font-mono text-hds-dim">Awaiting route data…</p>
    </div>
  );
}