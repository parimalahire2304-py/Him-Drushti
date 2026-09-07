import React from "react";

const NAV = [
  { id: "overview", label: "Overview",               icon: "◈" },
  { id: "iceberg",  label: "Iceberg Intelligence",   icon: "▣" },
  { id: "forecast", label: "Trajectory Forecast",    icon: "➤" },
  { id: "risk",     label: "Risk & Uncertainty",     icon: "⚠" },
  { id: "comm",     label: "Communication",          icon: "⇄" },
  { id: "route",    label: "Route Decision",         icon: "⌖" },
];

export default function Sidebar({ active, onSelect, data }) {
  /* System health — DATA AVAILABLE only when a live observation is present,
     never "ONLINE". */
  const hasObs = Boolean(data?.obs);
  const health = hasObs ? "DATA AVAILABLE" : "AWAITING DATA";

  return (
    <aside className="w-52 shrink-0 border-r border-hds-border bg-hds-panel flex flex-col">
      <nav className="flex-1 py-3">
        <ul className="space-y-1 px-2">
          {NAV.map((item) => {
            const isActive = active === item.id;
            return (
              <li key={item.id}>
                <button
                  onClick={() => onSelect(item.id)}
                  className={
                    "cursor-pointer w-full flex items-center gap-2.5 px-3 py-2 text-left text-xs font-mono transition-colors border-l-2 " +
                    (isActive
                      ? "border-hds-cyan text-hds-cyan bg-hds-blue/10"
                      : "border-transparent text-hds-text hover:text-white hover:bg-hds-blue/5")
                  }
                  aria-current={isActive ? "page" : undefined}
                >
                  <span className="text-sm w-4 text-center opacity-70">{item.icon}</span>
                  <span className="truncate">{item.label}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </nav>
      <div className="px-4 py-3 border-t border-hds-border">
        <p className="text-[9px] font-mono text-hds-dim leading-relaxed">
          MQTT = prototype / SATCOM
          <br />
          emulation · EPSG:4326
          <br />
          East Prydz Bay
        </p>
        <div className="mt-2 pt-2 border-t border-hds-border">
          <p className="text-[9px] font-mono uppercase text-hds-dim mb-1">System Health</p>
          <span
            className={
              "inline-flex items-center gap-1.5 px-2 py-0.5 rounded border text-[9px] font-mono font-bold tracking-wider uppercase " +
              (hasObs
                ? "text-hds-green border-hds-green/30 bg-hds-green/8"
                : "text-hds-amber border-hds-amber/30 bg-hds-amber/8")
            }
          >
            <span
              className={"inline-block w-1.5 h-1.5 rounded-full " + (hasObs ? "bg-hds-green" : "bg-hds-amber")}
            />
            {health}
          </span>
        </div>
      </div>
    </aside>
  );
}