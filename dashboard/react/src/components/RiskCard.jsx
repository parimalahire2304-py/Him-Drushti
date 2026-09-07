import React from "react";
import { fmt } from "../lib/payloadAdapter";
import RiskBadge from "./RiskBadge";

function Row({ label, value, accent }) {
  return (
    <tr className="border-b border-hds-border/40 last:border-0">
      <td className="py-1 pr-4 text-[10px] font-mono uppercase text-hds-dim whitespace-nowrap">{label}</td>
      <td className={`py-1 text-xs font-mono text-right whitespace-nowrap ${accent ?? "text-hds-text"}`}>
        {value}
      </td>
    </tr>
  );
}

export default function RiskCard({ risk }) {
  if (!risk) return <PanelEmpty />;

  const riskAccent =
    risk.level === "HIGH"
      ? "text-hds-red"
      : risk.level === "MODERATE"
        ? "text-hds-amber"
        : "text-hds-text";

  return (
    <div className="rounded-md border border-hds-border bg-hds-panel p-3">
      <h3 className="mb-2 text-xs font-bold tracking-widest uppercase text-white flex items-center gap-2">
        <span className="text-hds-amber">⚠</span> Risk & Uncertainty
      </h3>

      <div className="mb-2">
        <RiskBadge level={risk.level} score={risk.score} />
      </div>

      <table className="w-full">
        <tbody>
          <Row label="Risk Score"    value={fmt(risk.score, "/100", "—")} accent={riskAccent} />
          <Row label="Separation"    value={fmt(risk.separationKm, "km", "—")} />
          <Row label="Eff. Separation" value={fmt(risk.separationEff, "km", "—")} />
          <Row label="Uncertainty σ" value={fmt(risk.sigmaKm, "km", "—")} />
          <Row label="Envelope R"    value={fmt(risk.envelopeKm, "km", "—")} />
          <Row label="Corridor R"    value={fmt(risk.corridorKm, "km", "—")} />
          <Row label="Anchor"        value={fmt(risk.anchorTag, "", "—")} />
          <Row label="Data Freshness" value={fmt(risk.freshness, "", "—")} />
        </tbody>
      </table>
    </div>
  );
}

function PanelEmpty() {
  return (
    <div className="rounded-md border border-hds-border bg-hds-panel p-3">
      <h3 className="text-xs font-bold tracking-widest uppercase text-hds-dim">Risk & Uncertainty</h3>
      <p className="mt-2 text-[10px] font-mono text-hds-dim">Awaiting risk data…</p>
    </div>
  );
}