import React from "react";

const LEGEND_ITEMS = [
  { label: "OBS — observation (amber)", swatch: "hds-icon hds-icon--obs",   text: "O" },
  { label: "FC — 7-day forecast (cyan)", swatch: "hds-icon hds-icon--fc",   text: "F" },
  { label: "Route waypoint (green)",    swatch: "hds-icon hds-icon--route", text: "D" },
  { label: "Trajectory line",           swatch: "line line--traj" },
  { label: "Uncertainty envelope",      swatch: "ring ring--env" },
  { label: "Risk corridor",             swatch: "ring ring--corr" },
  { label: "SAFEST route (green)",      swatch: "line line--route" },
  { label: "TIME route (cyan)",         swatch: "line line--time" },
  { label: "FUEL route (amber)",        swatch: "line line--fuel" },
  { label: "Bharati station (cyan)",    swatch: "hds-icon hds-icon--station hds-icon--bharati", text: "B" },
  { label: "Maitri station (cyan)",     swatch: "hds-icon hds-icon--station hds-icon--maitri",  text: "M" },
];

export default function MapLegend() {
  return (
    <div className="rounded-md border border-hds-border bg-hds-panel p-3">
      <h3 className="mb-2 text-xs font-bold tracking-widest uppercase text-white flex items-center gap-2">
        <span className="text-hds-cyan">≡</span> Map Legend
      </h3>
      <ul className="space-y-1">
        {LEGEND_ITEMS.map(({ label, swatch, text }) => (
          <li key={label} className="flex items-center gap-2 text-[10px] font-mono text-hds-text">
            <span className="legend-swatch">
              {swatch.startsWith("hds-icon") ? (
                <span className={`${swatch}`}>{text}</span>
              ) : (
                <span className={swatch} />
              )}
            </span>
            <span>{label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}