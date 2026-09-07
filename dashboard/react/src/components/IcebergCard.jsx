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

export default function IcebergCard({ obs }) {
  if (!obs) return <PanelEmpty label="Iceberg Intelligence" />;

  const fmtCoord = (v, pos, neg) => {
    if (v == null) return "N/A";
    const dir = v >= 0 ? pos : neg;
    return `${Math.abs(v).toFixed(4)}° ${dir}`;
  };

  return (
    <div className="rounded-md border border-hds-border bg-hds-panel p-3">
      <h3 className="mb-2 text-xs font-bold tracking-widest uppercase text-white flex items-center gap-2">
        <span className="text-hds-amber">▣</span> Iceberg Intelligence
      </h3>
      <table className="w-full">
        <tbody>
          <Row label="Iceberg ID"  value={<span className="text-hds-amber font-semibold">{obs.icebergId}</span>} />
          <Row label="Latitude"    value={fmtCoord(obs.lat, "S", "N")} />
          <Row label="Longitude"   value={fmtCoord(obs.lon, "E", "W")} />
          <Row label="Obs Time"    value={obs.obsTime !== "—" ? new Date(obs.obsTime).toLocaleString("en-GB", { timeZone: "UTC", dateStyle: "short", timeStyle: "short" }) : "—"} />
          <Row label="Source"      value={obs.dataSource} />
          <Row label="Length"      value={fmt(obs.lengthNm, "nm")} />
          <Row label="Width"       value={fmt(obs.widthNm, "nm")} />
        </tbody>
      </table>
    </div>
  );
}

function PanelEmpty({ label }) {
  return (
    <div className="rounded-md border border-hds-border bg-hds-panel p-3">
      <h3 className="text-xs font-bold tracking-widest uppercase text-hds-dim">{label}</h3>
      <p className="mt-2 text-[10px] font-mono text-hds-dim">Awaiting observation data…</p>
    </div>
  );
}