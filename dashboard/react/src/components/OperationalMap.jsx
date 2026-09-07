import { useState, useRef, useEffect } from "react";
import { MapContainer, TileLayer, Marker, Polyline, Circle, Tooltip, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

/* ── district icon sizes ───────────────────────────────────── */
const ICON_OBS  = { width: 22, height: 22 };
const ICON_FC   = { width: 20, height: 20 };
const ICON_DEST = { width: 16, height: 16 };
const ICON_STN  = { width: 16, height: 16 };

/* ── Indian Research Station coordinates (Government of India, MoES) ── */
const STATIONS = [
  { id: "BHARATI", name: "BHARATI", subtitle: "Indian Research Station",
    lat: -69.406833, lon: 76.195333,
    location: "Larsemann Hills, Antarctica",
    dmsLat: "69°24.41′ S", dmsLon: "76°11.72′ E" },
  { id: "MAITRI", name: "MAITRI", subtitle: "Indian Research Station",
    lat: -70.764444, lon: 11.734167,
    location: "Schirmacher Oasis, Antarctica",
    dmsLat: "70°45′52″ S", dmsLon: "11°44′03″ E" },
];

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
const DEFAULT_ZOOM = 6;
const FLY_ZOOM = 7;
const FLY_OPTS = { animate: true, duration: 1.2 };

/* ── State-based fly-to: watches a target and calls map.flyTo ── */
function MapFlyTo({ target }) {
  const map = useMap();
  if (target) map.flyTo(target.center, target.zoom ?? FLY_ZOOM, FLY_OPTS);
  return null;
}

/* ── Station marker component ──────────────────────────────── */
function StationMarker({ station }) {
  const isBharati = station.id === "BHARATI";
  return (
    <Marker
      position={[station.lat, station.lon]}
      icon={L.divIcon({
        className: "",
        html: `<div class="hds-icon hds-icon--station ${isBharati ? "hds-icon--bharati" : "hds-icon--maitri"}">${station.id}</div>`,
        iconSize: [ICON_STN.width, ICON_STN.height],
        iconAnchor: [ICON_STN.width / 2, ICON_STN.height / 2],
      })}
    >
      <Tooltip permanent direction="top" offset={[0, -14]}>
        <span className="text-[9px] font-mono font-bold text-hds-cyan bg-[#0f1724] px-1.5 rounded">
          {station.name}
        </span>
      </Tooltip>
      <Tooltip direction="right" offset={[10, 0]}>
        <div className="bg-hds-panel border border-hds-border rounded px-2 py-1.5 min-w-[160px]">
          <div className="font-bold text-hds-text text-[10px]">{station.name}</div>
          <div className="text-hds-dim text-[9px]">{station.subtitle}</div>
          <div className="text-hds-dim text-[9px] mt-0.5">{station.location}</div>
          <div className="text-hds-dim text-[9px] mt-0.5 font-mono">
            {station.dmsLat}<br/>{station.dmsLon}
          </div>
          <div className="text-hds-dim text-[9px] mt-0.5 font-mono">
            {station.lat.toFixed(6)}, {station.lon.toFixed(6)}
          </div>
        </div>
      </Tooltip>
    </Marker>
  );
}

/* ── component ─────────────────────────────────────────────── */
export default function OperationalMap({ obs, fc, risk, route, layers, routeVariants, selectedRoute }) {
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
  const showStations = layers.stations;

  /* metres for risk circles */
  const envelopeR = hasRisk ? risk.envelopeKm * 1000 : 0;
  const corridorR = hasCorr ? risk.corridorKm * 1000 : 0;

  /* ── Station fly-to state ─────────────────────────────── */
  const [flyTarget, setFlyTarget] = useState(null);
  const flyToApi = useRef({ flyToStation: () => {}, flyToDefault: () => {} });

  useEffect(() => {
    flyToApi.current = {
      flyToStation: (stnId) => {
        const stn = STATIONS.find(s => s.id === stnId);
        if (stn) setFlyTarget({ center: [stn.lat, stn.lon], zoom: FLY_ZOOM });
      },
      flyToDefault: () => setFlyTarget({ center: CENTER, zoom: DEFAULT_ZOOM }),
    };
  }, []);

  return (
    <MapContainer
      center={CENTER}
      zoom={DEFAULT_ZOOM}
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

      {/* ── State-based fly-to controller ─────────────────────── */}
      <MapFlyTo target={flyTarget} />

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

      {/* ── Phase 7F: three route variant polylines ──────────── */}
      {/* Rendered ONLY when routeVariants exist. Each variant uses its own color.
          Identical geometries overlap honestly — the selected variant is drawn last
          (on top) and never perturbed to force visual divergence. */}
      {Array.isArray(routeVariants) && routeVariants.map(v => {
        const isSelected = v.variant === selectedRoute;
        if (!Array.isArray(v.waypoints) || v.waypoints.length < 2) return null;
        const color = v.variant === "SAFEST" ? "#00e676"
                    : v.variant === "TIME"    ? "#00d4ff"
                    :                           "#ffb300";
        return (
          <Polyline
            key={v.variant}
            positions={v.waypoints.map(wp => [wp.lat, wp.lon])}
            pathOptions={{
              color,
              weight: isSelected ? 4 : 2,
              opacity: isSelected ? 1.0 : 0.35,
              dashArray: isSelected ? null : "6 4",
            }}
          />
        );
      })}

      {/* ── Phase 7H: Indian Research Stations ───────────────── */}
      {showStations && STATIONS.map(stn => (
        <StationMarker key={stn.id} station={stn} />
      ))}
    </MapContainer>
  );
}
