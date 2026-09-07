import React from "react";
import { fmt } from "../lib/payloadAdapter";

/* ── Route option card ──────────────────────────────────────────────── */
const VARIANT_STYLES = {
  SAFEST: {
    border: "border-hds-green/60",
    activeBorder: "border-hds-green",
    bg: "bg-hds-green/8",
    labelColor: "text-hds-green",
    tag: "RECOMMENDED",
    tagBorder: "border-hds-green/30",
  },
  TIME: {
    border: "border-hds-cyan/60",
    activeBorder: "border-hds-cyan",
    bg: "bg-hds-cyan/8",
    labelColor: "text-hds-cyan",
    tag: "TIME PRIORITY",
    tagBorder: "border-hds-cyan/30",
  },
  FUEL: {
    border: "border-hds-amber/60",
    activeBorder: "border-hds-amber",
    bg: "bg-hds-amber/8",
    labelColor: "text-hds-amber",
    tag: "FUEL PRIORITY",
    tagBorder: "border-hds-amber/30",
  },
};

/* Fuel estimation (Phase 7F documented assumption, NOT measured consumption):
   distance_nm = distance_km / 1.852
   estimated_fuel_litres = distance_nm × FUEL_RATE_L_PER_NM */
const FUEL_RATE_L_PER_NM = 2.5;

function estFuelLitres(distKm) {
  if (distKm == null || isNaN(distKm)) return null;
  return ((distKm / 1.852) * FUEL_RATE_L_PER_NM).toFixed(0);
}

function VariantCard({ v, selected, onSelect }) {
  const s = VARIANT_STYLES[v.variant] || VARIANT_STYLES.SAFEST;
  const noRoute = v.status === "NO_SAFE_ROUTE_FOUND";
  const fuel = estFuelLitres(v.distKm);

  return (
    <button
      onClick={onSelect}
      className={
        "w-full text-left rounded-md border px-3 py-2.5 transition-colors cursor-pointer " +
        (selected
          ? `${s.activeBorder} ${s.bg}`
          : `${s.border} bg-transparent hover:bg-hds-panel/60`)
      }
    >
      {/* header row */}
      <div className="flex items-center justify-between mb-1.5">
        <span className={`text-xs font-bold tracking-widest uppercase ${s.labelColor}`}>
          {v.variant}
        </span>
        <span
          className={
            "px-1.5 py-0.5 rounded text-[9px] font-mono font-bold tracking-wider border " +
            `${s.labelColor} ${s.tagBorder}`
          }
        >
          {s.tag}
        </span>
      </div>

      {noRoute ? (
        <p className="text-[10px] font-mono text-hds-red leading-relaxed">
          No safe route found for this variant.
        </p>
      ) : (
        <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[10px] font-mono">
          <div className="text-hds-dim">Dist</div>
          <div className="text-right text-hds-text">{fmt(v.distKm, "km")}</div>
          <div className="text-hds-dim">ETA</div>
          <div className="text-right text-hds-text">{fmt(v.travelHrs, "h")}</div>
          <div className="text-hds-dim">EST. FUEL</div>
          <div className="text-right text-hds-text">{fuel != null ? `${fuel} L` : "N/A"}</div>
          <div className="text-hds-dim">Max Risk</div>
          <div className="text-right text-hds-text">{fmt(v.maxRisk, "/100")}</div>
          <div className="text-hds-dim">Overhead</div>
          <div className="text-right text-hds-text">{fmt(v.overheadPct, "%")}</div>
          <div className="text-hds-dim">Waypoints</div>
          <div className="text-right text-hds-text">
            {Array.isArray(v.waypoints) ? v.waypoints.length : "—"}
          </div>
        </div>
      )}
    </button>
  );
}

/* ── Main component ─────────────────────────────────────────────────── */
export default function RouteOptions({ route, routeVariants, selectedRoute, onSelectRoute }) {
  if (!routeVariants || routeVariants.length === 0) return <PanelEmpty />;

  const selected = routeVariants.find(v => v.variant === selectedRoute) || routeVariants[0];
  const hasGeo = selected && Array.isArray(selected.waypoints) && selected.waypoints.length >= 1;

  return (
    <div className="rounded-md border border-hds-border bg-hds-panel p-3">
      <h3 className="mb-2 text-xs font-bold tracking-widest uppercase text-white flex items-center gap-2">
        <span className="text-hds-cyan">⌖</span> Route Options
      </h3>

      {/* three selectable cards */}
      <div className="space-y-2">
        {routeVariants.map(v => (
          <VariantCard
            key={v.variant}
            v={v}
            selected={v.variant === selectedRoute}
            onSelect={() => onSelectRoute(v.variant)}
          />
        ))}
      </div>

      {/* route assumptions */}
      <div className="mt-3 pt-2 border-t border-hds-border">
        <p className="text-[9px] font-mono uppercase text-hds-dim mb-1">Route Assumptions</p>
        <div className="space-y-1 text-[9px] font-mono text-hds-dim leading-relaxed">
          <p>
            <b className="text-hds-text">Fuel:</b>{" "}
            EST. FUEL = (route_km / 1.852) × {FUEL_RATE_L_PER_NM} L/nm — demonstration assumption, not measured consumption.
          </p>
          <p>
            <b className="text-hds-text">ETA:</b>{" "}
            Travel time = route_distance / vessel_speed (12 kn). Prototype estimate.
          </p>
          <p>
            <b className="text-hds-text">Weights:</b>{" "}
            SAFEST: safety=10, dist=1, time=3. TIME: safety=6, dist=1, time=3. FUEL: safety=6, dist=3, time=1.
          </p>
          <p>
            <b className="text-hds-text">Safety:</b>{" "}
            All routes respect critical_risk_threshold=50.0. HIGH-risk cells are impassable.
          </p>
        </div>
      </div>

      {/* waypoints for selected variant */}
      {hasGeo && (
        <div className="mt-2 pt-2 border-t border-hds-border">
          <p className="text-[9px] font-mono uppercase text-hds-dim mb-1">
            Waypoints — {selected.variant}
          </p>
          <div className="max-h-20 overflow-y-auto space-y-0.5">
            {selected.waypoints.map((wp, i, arr) => (
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
      <h3 className="text-xs font-bold tracking-widest uppercase text-hds-dim">Route Options</h3>
      <p className="mt-2 text-[10px] font-mono text-hds-dim">Awaiting route variants…</p>
    </div>
  );
}
