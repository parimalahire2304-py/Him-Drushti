import React from "react";
import StatusBadge from "./StatusBadge";

export default function Header({ data }) {
  const commState = data?.commState ?? "—";
  const lastUpdate = data?.lastUpdate;
  const ageHrs = data?.ageHrs;
  const method = data?.fc?.method;

  return (
    <header className="flex items-center justify-between px-5 py-3 bg-hds-panel border-b border-hds-border">
      {/* left: title */}
      <div className="flex items-baseline gap-3 min-w-0">
        <h1 className="text-sm font-bold tracking-widest uppercase text-white">
          HIM-DRUSHTI
        </h1>
        <span className="text-[10px] font-mono text-hds-dim tracking-wide uppercase hidden sm:inline">
          Antarctic Maritime Decision Support
        </span>
      </div>

      {/* right: live indicators */}
      <div className="flex items-center gap-5 text-xs font-mono text-hds-dim shrink-0">
        {/* model badge */}
        {method && (
          <span
            className={
              "px-2 py-0.5 rounded border text-[10px] font-semibold tracking-wider uppercase " +
              (method === "MOTION_AWARE_XGBOOST"
                ? "border-hds-cyan/30 text-hds-cyan bg-hds-cyan/8"
                : "border-hds-amber/30 text-hds-amber bg-hds-amber/8")
            }
          >
            {method === "MOTION_AWARE_XGBOOST" ? "XGBOOST" : "PERSISTENCE"}
          </span>
        )}

        {/* comm state */}
        <div className="flex flex-col items-end gap-0.5">
          <span className="text-[10px] text-hds-dim tracking-wide uppercase">Comms</span>
          <StatusBadge state={commState} />
        </div>

        {/* last update */}
        {lastUpdate && (
          <div className="flex flex-col items-end gap-0.5">
            <span className="text-[10px] text-hds-dim tracking-wide uppercase">Last Update</span>
            <span className="text-xs text-hds-text">
              {new Date(lastUpdate).toLocaleTimeString("en-GB", {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
                timeZone: "UTC",
              })}
              <span className="text-hds-dim ml-1">UTC</span>
            </span>
          </div>
        )}

        {/* message age */}
        {ageHrs != null && (
          <div className="flex flex-col items-end gap-0.5">
            <span className="text-[10px] text-hds-dim tracking-wide uppercase">Age</span>
            <span
              className={
                "text-xs font-semibold " +
                (ageHrs > 168
                  ? "text-hds-red"
                  : ageHrs > 48
                    ? "text-hds-amber"
                    : "text-hds-green")
              }
            >
              {ageHrs < 1 ? `${(ageHrs * 60).toFixed(0)}m` : `${ageHrs.toFixed(1)}h`}
            </span>
          </div>
        )}
      </div>
    </header>
  );
}
