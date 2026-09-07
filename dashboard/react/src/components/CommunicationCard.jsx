import React from "react";
import StatusBadge from "./StatusBadge";
import { fmt } from "../lib/payloadAdapter";

function Row({ label, value, children }) {
  return (
    <tr className="border-b border-hds-border/40 last:border-0">
      <td className="py-1 pr-4 text-[10px] font-mono uppercase text-hds-dim whitespace-nowrap">{label}</td>
      <td className="py-1 text-xs font-mono text-right whitespace-nowrap text-hds-text">{children ?? value}</td>
    </tr>
  );
}

export default function CommunicationCard({ data }) {
  const commState = data?.commState ?? "—";
  const status = data?.status;
  const ageHrs = data?.ageHrs;
  const connected = data?.connected;

  return (
    <div className="rounded-md border border-hds-border bg-hds-panel p-3">
      <h3 className="mb-2 text-xs font-bold tracking-widest uppercase text-white flex items-center gap-2">
        <span className="text-hds-cyan">⇄</span> Communication
      </h3>

      <table className="w-full">
        <tbody>
          <Row label="State">
            <StatusBadge state={commState} />
          </Row>
          <Row label="Last Timestamp" value={
            status?.lastTs
              ? new Date(status.lastTs).toLocaleString("en-GB", {
                  timeZone: "UTC",
                  dateStyle: "short",
                  timeStyle: "medium",
                }) + " UTC"
              : "—"
          } />
          <Row label="Message Age" value={
            ageHrs != null ? (
              <span
                className={
                  "font-semibold " +
                  (ageHrs > 168 ? "text-hds-red" : ageHrs > 48 ? "text-hds-amber" : "text-hds-green")
                }
              >
                {ageHrs < 1 ? `${(ageHrs * 60).toFixed(0)} min` : `${ageHrs.toFixed(1)} h`}
              </span>
            ) : "—"
          } />
          <Row label="Broker" value={
            <span className={connected ? "text-hds-green" : "text-hds-red"}>
              {connected ? "Connected" : "Disconnected"}
            </span>
          } />
          <Row label="Reason" value={status?.reason ?? "—"} />
        </tbody>
      </table>

      {/* comm-state guide */}
      <div className="mt-2.5 pt-2 border-t border-hds-border">
        <p className="text-[9px] font-mono text-hds-dim leading-relaxed">
          STALE = 48-168 h · LAST-KNOWN-STATE = &gt;168 h · recovery event → FRESH
        </p>
      </div>
    </div>
  );
}