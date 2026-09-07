import React, { useRef, useState } from "react";
import Header from "./components/Header";
import Sidebar from "./components/Sidebar";
import EnvironmentConditions from "./components/EnvironmentConditions";
import IcebergCard from "./components/IcebergCard";
import ForecastCard from "./components/ForecastCard";
import RiskCard from "./components/RiskCard";
import RouteCard from "./components/RouteCard";
import RouteOptions from "./components/RouteOptions";
import CommunicationCard from "./components/CommunicationCard";
import QuickLayers from "./components/QuickLayers";
import MapLegend from "./components/MapLegend";
import OperationalMap from "./components/OperationalMap";
import useSSE from "./hooks/useSSE";
import { adaptRouteOptions } from "./lib/payloadAdapter";

/* section ids used by the nav + scroll-to */
const SECTIONS = [
  { id: "iceberg", label: "Iceberg Intelligence" },
  { id: "forecast", label: "Trajectory Forecast" },
  { id: "risk", label: "Risk & Uncertainty" },
  { id: "route", label: "Route Decision" },
  { id: "comm", label: "Communication" },
];

export default function App() {
  const { data, live } = useSSE();
  const [active, setActive] = useState("overview");
  const [selectedRoute, setSelectedRoute] = useState("SAFEST");
  const [layers, setLayers] = useState({
    obs: true, trajLine: true, envelope: true, corridor: true, route: true, stations: true,
  });

  const sectionRefs = useRef({});

  /* Phase 7F: derive route variants from the raw payload */
  const routeVariants = adaptRouteOptions(data?.route?._raw);

  /* nav → scroll to the matching card panel */
  function handleSelect(id) {
    setActive(id);
    if (id === "overview") {
      window.scrollTo?.({ top: 0, behavior: "smooth" });
      return;
    }
    sectionRefs.current[id]?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  }

  function toggleLayer(key) {
    setLayers((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  const obs = data?.obs;
  const fc = data?.fc;
  const risk = data?.risk;
  const route = data?.route;
  const comm = { commState: data?.commState, status: data?.status, connected: data?.connected, ageHrs: data?.ageHrs };

  return (
    <div className="h-screen flex flex-col bg-hds-bg text-hds-text overflow-hidden">
      {/* ── top bar ─────────────────────────────────────────────── */}
      <Header data={data} />

      <div className="flex-1 flex min-h-0">
        {/* ── left nav ─────────────────────────────────────────── */}
        <Sidebar active={active} onSelect={handleSelect} data={data} />

        {/* ── center: map + environment strip ──────────────────── */}
        <main className="flex-1 flex flex-col min-w-0 min-h-0">
          <div className="relative flex-1 min-h-0 border-b border-hds-border">
            <OperationalMap obs={obs} fc={fc} risk={risk} route={route} layers={layers} routeVariants={routeVariants} selectedRoute={selectedRoute} />

            {/* live badge (top-left above zoom control) */}
            <div className="absolute top-2 left-2 z-[1000] pointer-events-none flex items-center gap-2">
              <span
                className={
                  "flex items-center gap-1.5 px-2 py-1 rounded border font-mono text-[10px] " +
                  (live
                    ? "text-hds-green border-hds-green/30 bg-hds-bg/80"
                    : "text-hds-red border-hds-red/30 bg-hds-bg/80")
                }
              >
                <span
                  className={
                    "inline-block w-2 h-2 rounded-full " +
                    (live ? "bg-hds-green animate-pulse" : "bg-hds-red")
                  }
                />
                {live ? "LIVE" : "DISCONNECTED"}
              </span>
            </div>

            {/* floating layer + legend (top-right) */}
            <div className="absolute top-2 right-2 z-[1000] w-48 space-y-2 pointer-events-none">
              <div className="pointer-events-auto">
                <QuickLayers layers={layers} onToggle={toggleLayer} />
              </div>
              <div className="pointer-events-auto">
                <MapLegend />
              </div>
            </div>
          </div>

          {/* environment strip below the map */}
          <div className="shrink-0 p-3">
            <EnvironmentConditions obs={obs} />
          </div>
        </main>

        {/* ── right decision column ─────────────────────────────── */}
        <aside className="w-[22rem] shrink-0 min-h-0 overflow-y-auto border-l border-hds-border space-y-3 p-3">
          <div ref={(el) => (sectionRefs.current.overview = el)}>
            <IcebergCard obs={obs} />
          </div>
          <div ref={(el) => (sectionRefs.current.forecast = el)}>
            <ForecastCard fc={fc} />
          </div>
          <div ref={(el) => (sectionRefs.current.risk = el)}>
            <RiskCard risk={risk} />
          </div>
          <div ref={(el) => (sectionRefs.current.route = el)}>
            <RouteCard route={route} />
          </div>
          <div ref={(el) => (sectionRefs.current.routeOptions = el)}>
            <RouteOptions route={route} routeVariants={routeVariants} selectedRoute={selectedRoute} onSelectRoute={setSelectedRoute} />
          </div>
          <div ref={(el) => (sectionRefs.current.comm = el)}>
            <CommunicationCard data={comm} />
          </div>

          <p className="text-[9px] font-mono text-hds-dim leading-relaxed px-1 pt-1">
            All values displayed are sourced from the live MQTT payload stream.
            Missing fields are shown as N/A — no blanks, no fabrication.
          </p>
        </aside>
      </div>
    </div>
  );
}