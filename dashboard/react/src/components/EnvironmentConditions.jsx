import React from "react";
import {
  kelvinToC,
  degToDir,
  fracToPct,
  fmt,
} from "../lib/payloadAdapter";

function EnvCard({ icon, label, value, sub, ok }) {
  return (
    <div
      className={
        "rounded-md border px-3 py-2.5 " +
        (ok
          ? "bg-hds-bg/60 border-hds-border"
          : "bg-hds-bg/40 border-hds-border/60")
      }
    >
      <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wide text-hds-dim">
        <span className="text-hds-cyan/70">{icon}</span>
        {label}
      </div>
      <div
        className={
          "mt-1 text-sm font-mono font-semibold " +
          (ok ? "text-hds-text" : "text-hds-dim/80")
        }
      >
        {value}
      </div>
      {sub && <div className="text-[10px] font-mono text-hds-dim mt-0.5">{sub}</div>}
    </div>
  );
}

export default function EnvironmentConditions({ obs }) {
  /* All values sourced ONLY from the observation payload. No fabrication.
     Missing → "N/A — DATA NOT AVAILABLE". */
  const seaIce = fracToPct(obs?.seaIceConc);
  const airTempC = kelvinToC(obs?.temp2m);
  const windKt = obs?.windSpeed != null ? (obs.windSpeed * 1.9438).toFixed(1) : null;
  const windDirName = degToDir(obs?.windDir);

  return (
    <div className="rounded-md border border-hds-border bg-hds-panel p-3">
      <div className="mb-2.5 flex items-center justify-between">
        <h2 className="text-xs font-bold tracking-widest uppercase text-white">
          Environment Conditions
        </h2>
        <span className="text-[9px] font-mono text-hds-dim uppercase">
          obs payload · real values only
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2">
        {/* Sea-Ice */}
        <EnvCard
          icon="❄"
          label="Sea-Ice"
          value={seaIce ?? "N/A"}
          sub={seaIce != null ? "concentration" : "DATA NOT AVAILABLE"}
          ok={seaIce != null}
        />
        {/* Air Temperature */}
        <EnvCard
          icon="🌡"
          label="Air Temp"
          value={airTempC != null ? `${airTempC}°C` : "N/A"}
          sub={
            airTempC != null
              ? `${fmt(obs?.temp2m != null ? obs.temp2m.toFixed(1) : null, "K")} (2m)`
              : "DATA NOT AVAILABLE"
          }
          ok={airTempC != null}
        />
        {/* Wind */}
        <EnvCard
          icon="≋"
          label="Wind"
          value={windKt != null ? `${windKt} kt` : "N/A"}
          sub={
            windKt != null
              ? `${fmt(obs?.windSpeed != null ? obs.windSpeed.toFixed(2) : null, "m/s")} ${windDirName ? windDirName : ""}`
              : "DATA NOT AVAILABLE"
          }
          ok={windKt != null}
        />
        {/* Visibility */}
        <EnvCard
          icon="◍"
          label="Visibility"
          value="N/A"
          sub="DATA NOT AVAILABLE"
          ok={false}
        />
        {/* Wave Height */}
        <EnvCard
          icon="〜"
          label="Wave Height"
          value="N/A"
          sub="DATA NOT AVAILABLE"
          ok={false}
        />
        {/* Sea Temperature */}
        <EnvCard
          icon="∿"
          label="Sea Temp"
          value="N/A"
          sub="DATA NOT AVAILABLE"
          ok={false}
        />
      </div>

      {/* additional real fields from the observation payload */}
      <div className="mt-2.5 pt-2.5 border-t border-hds-border grid grid-cols-3 gap-x-3 gap-y-1 text-[10px] font-mono text-hds-dim">
        <span>
          MSLP{" "}
          <b className="text-hds-text font-semibold">
            {obs?.mslp != null ? `${(obs.mslp / 100).toFixed(1)} hPa` : "N/A"}
          </b>
        </span>
        <span>
          Ocean{" "}
          <b className="text-hds-text font-semibold">
            {obs?.oceanSpeed != null
              ? `${(obs.oceanSpeed * 1.9438).toFixed(1)} kt ${degToDir(obs.oceanDir) ?? "?"}`
              : "N/A"}
          </b>
        </span>
        <span>
          Exposed Water{" "}
          <b className="text-hds-text font-semibold">
            {fracToPct(obs?.exposedWater) ?? "N/A"}
          </b>
        </span>
      </div>
    </div>
  );
}