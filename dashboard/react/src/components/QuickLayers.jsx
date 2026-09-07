import React from "react";

const LAYER_DEFS = [
  { key: "obs",   label: "Observation marker", color: "bg-amber-500" },
  { key: "trajLine", label: "Forecast trajectory", color: "bg-cyan-400" },
  { key: "envelope", label: "Uncertainty envelope", color: "bg-amber-400" },
  { key: "corridor", label: "Risk corridor", color: "bg-red-500" },
  { key: "route",   label: "Route variants (3)", color: "bg-green-500" },
  { key: "stations", label: "Indian Research Stations", color: "bg-cyan-500" },
];

export default function QuickLayers({ layers, onToggle }) {
  const hasAnyData = Object.values(layers).some(Boolean);

  return (
    <div className="rounded-md border border-hds-border bg-hds-panel p-3">
      <h3 className="mb-2 text-xs font-bold tracking-widest uppercase text-white flex items-center gap-2">
        <span className="text-hds-cyan">◨</span> Quick Layers
      </h3>

      {!hasAnyData && (
        <p className="text-[9px] font-mono text-hds-dim mb-2">
          Overlays appear only with real live data — no blanks allowed.
        </p>
      )}

      <div className="grid grid-cols-1 gap-1">
        {LAYER_DEFS.map(({ key, label, color }) => {
          const enabled = layers[key];
          const active = enabled && hasAnyData;
          return (
            <button
              key={key}
              onClick={() => onToggle(key)}
              disabled={!hasAnyData}
              className={
                "flex items-center gap-2 px-2 py-1.5 rounded text-left text-[10px] font-mono " +
                "border transition " +
                (active
                  ? "bg-hds-blue/15 border-hds-blue/40 text-hds-text"
                  : "bg-transparent border-hds-border/40 text-hds-dim cursor-not-allowed")
              }
            >
              <span
                className={
                  "inline-block w-2.5 h-2.5 rounded-sm " + (active ? color : "bg-hds-border")
                }
              />
              <span className="flex-1">{label}</span>
              <span className={active ? "text-hds-green" : "text-hds-dim"}>
                {active ? "ON" : "OFF"}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}