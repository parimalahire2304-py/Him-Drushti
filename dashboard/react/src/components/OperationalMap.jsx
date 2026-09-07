import React from "react";
import { MapContainer, TileLayer, Marker, Polyline, Circle, Tooltip } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

/* ── district icon sizes ───────────────────────────────────── */
const ICON_OBS  = { width: 22, height: 22 };
const ICON_FC   = { width: 20, height: 20 };
const ICON_DEST = { width: 16, height: 16 };

function makeIcon(label, cls, size) {
  return L.divIcon({
    className: "",
    html: `<div class="hds-icon ${cls}">${label}</div>`,
    iconSize: [size.width, size.height],
    iconAnchor: [size.width / 2, size.height / 2],
  });
}

const ICOBS  = makeIcon("O", "hds-icon--obs",  ICON_OBS);
const ICOFC  = makeIcon("F", "hds-icon--fc",   ICON_FC);

/* ── default center (East Prydz Bay center) ────────────────── */
const CENTER = [-68.0, 76.0];

/* ── component ─────────────────────────────────────────────── */
export default function OperationalMap({ obs, fc, risk, route, layers }) {
  const oLat = obs?.lat;
  const oLon = obs?.lon;
  const fLat = fc?.fcLat;
  const fLon = fc?.fcLon;

  const hasObs  = oLat != null && oLon != null;
  const hasFc   = fLat != null && fLon != null;
  const hasRisk = layers.envelope && risk?.envelopeKm != null && hasObs;
  const hasCorr = layers.corridor && risk?.corridorKm != null && hasObs;
  const hasLine = layers.trajLine && hasObs && hasFc;
  const hasRte  = layers.route && Array.isArray(route?.waypoints) && route.waypoints.length >= 2;

  /* metres for risk circles */
  const envelopeR = hasRisk ? risk.envelopeKm * 1000 : 0;
  const corridorR = hasCorr ? risk.corridorKm * 1000 : 0;

  return (
    <MapContainer
      center={CENTER}
      zoom={6}
      scrollWheelZoom={true}
      zoomControl={true}
      className="w-full h-full"
      style={{ background: "#070c14" }}
    >
      {/* ── tiles ─────────────────────────────────────────────── */}
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {/* ── observation marker (amber) ───────────────────────── */}
      {hasObs && (
        <Marker position={[oLat, oLon]} icon={ICOBS}>
          <Tooltip permanent direction="top" offset={[0, -14]}>
            <span className="text-[10px] font-mono font-bold text-amber-500 bg-[#0f1724] px-1 rounded">
              {obs.icebergId} OBS
            </span>
          </Tooltip>
        </Marker>
      )}

      {/* ── forecast marker (cyan) ───────────────────────────── */}
      {hasFc && (
        <Marker position={[fLat, fLon]} icon={ICOFC}>
          <Tooltip permanent direction="top" offset={[0, -14]}>
            <span className="text-[10px] font-mono font-bold text-cyan-400 bg-[#0f1724] px-1 rounded">
              FC
            </span>
          </Tooltip>
        </Marker>
      )}

      {/* ── trajectory line (cyan dashed) ────────────────────── */}
      {hasLine && (
        <Polyline
          positions={[[oLat, oLon], [fLat, fLon]]}
          pathOptions={{ color: "#00d4ff", weight: 2, dashArray: "8 6", opacity: 0.85 }}
        />
      )}

      {/* ── envelope (outer uncertainty ring — amber) ────────── */}
      {hasRisk && (
        <Circle
          center={[oLat, oLon]}
          radius={envelopeR}
          pathOptions={{ color: "#ffb300", weight: 1.5, dashArray: "5 4", fillColor: "#ffb300", fillOpacity: 0.06 }}
        />
      )}

      {/* ── corridor (inner risk ring — red) ─────────────────── */}
      {hasCorr && (
        <Circle
          center={[oLat, oLon]}
          radius={corridorR}
          pathOptions={{ color: "#ff3d4e", weight: 1.5, dashArray: "4 3", fillColor: "#ff3d4e", fillOpacity: 0.10 }}
        />
      )}

      {/* ── route polyline (green, solid) ────────────────────── */}
      {hasRte && (() => {
        const pts = route.waypoints.map(wp => [wp.lat, wp.lon]);
        return (
          <>
            <Polyline
              positions={pts}
              pathOptions={{ color: "#00e676", weight: 3, opacity: 0.9 }}
            />
            {/* destination icon */}
            <Marker
              position={pts[pts.length - 1]}
              icon={makeIcon("D", "hds-icon--route", ICON_DEST)}
            >
              <Tooltip permanent direction="top" offset={[0, -12]}>
                <span className="text-[10px] font-mono font-bold text-green-400 bg-[#0f1724] px-1 rounded">
                  DEST
                </span>
              </Tooltip>
            </Marker>
          </>
        );
      })()}
    </MapContainer>
  );
}