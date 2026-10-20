import 'leaflet/dist/leaflet.css';
import type { Feature } from 'geojson';
import type { LeafletMouseEvent, Path, PathOptions } from 'leaflet';
import L from 'leaflet';
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { CircleMarker, GeoJSON, MapContainer, Popup, TileLayer, Tooltip, useMap, useMapEvents } from 'react-leaflet';
import { LEVEL_STYLE, type Level, type Station, type StreetCollection, type StreetFeature, type StreetProperties } from '@floodready/shared';

import { STALE_GREY } from '../lib/colours';
import { focusedStreet, nearestStreet, REVEAL_ZOOM, type Place } from '../lib/geo';

const CENTRE: [number, number] = [3.0852, 101.4377];
/** Pixels either side of a street line that still count as a click on it (same as the resident map). */
const TAP_TOLERANCE = 14;

/** Zoom to the streets once, when they first arrive. */
function FitStreets({ streets }: { streets: StreetCollection }) {
  const map = useMap();
  const done = useRef(false);
  useEffect(() => {
    if (done.current || streets.features.length === 0) return;
    const bounds = L.geoJSON(streets as unknown as GeoJSON.FeatureCollection).getBounds();
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [20, 20] });
      done.current = true;
    }
  }, [map, streets]);
  return null;
}

/** Reports the street under the map centre after every move or zoom (null while zoomed out or off a street). */
function FocusWatcher({ streets, onFocus, onPoint }: { streets: StreetCollection; onFocus: (id: string | null) => void; onPoint: (p: Place | null) => void }) {
  const last = useRef<string | null>(null);
  const map = useMap();
  const check = () => {
    const c = map.getCenter();
    const hit = focusedStreet({ lat: c.lat, lon: c.lng }, map.getZoom(), streets.features);
    onPoint(hit?.point ?? null);
    const id = hit?.street.street_id ?? null;
    if (id !== last.current) {
      last.current = id;
      onFocus(id);
    }
  };
  useMapEvents({ moveend: check, zoomend: check });
  useEffect(check, [streets]);
  return null;
}

/** Clicking a street line zooms in on the nearest point of that street, so its popup opens. */
function TapToZoom({ target }: { target: [number, number] | null }) {
  const map = useMap();
  useEffect(() => {
    if (target) map.flyTo(target, Math.max(map.getZoom(), REVEAL_ZOOM), { duration: 0.6 });
  }, [target, map]);
  return null;
}

/**
 * Streets coloured by level; rain gauges (circles) and river gauges (squares-ish, larger) with stale ones
 * grey. As on the resident map, zooming in on a street (or clicking one, which zooms in) draws it heavier
 * in its level colour and opens `children` in a popup pointing at it.
 */
export function OpsMapView({ streets, stations, focused, onFocus, children }: {
  streets: StreetCollection;
  stations: Station[];
  focused: string | null;
  onFocus: (streetId: string | null) => void;
  children?: ReactNode;
}) {
  const [point, setPoint] = useState<Place | null>(null);
  const [tap, setTap] = useState<[number, number] | null>(null);
  // Canvas, not SVG: only the canvas renderer has a hit tolerance around thin lines.
  const renderer = useMemo(() => L.canvas({ tolerance: TAP_TOLERANCE }), []);
  const style = (feature?: Feature): PathOptions => {
    const p = feature?.properties as StreetProperties | undefined;
    const level: Level = p?.level ?? 'normal';
    if (p && p.street_id === focused) return { color: LEVEL_STYLE[level].line, weight: 10, opacity: 1, lineCap: 'round' };
    return { color: LEVEL_STYLE[level].line, weight: level === 'normal' ? 2 : 5, opacity: level === 'normal' ? 0.55 : 0.95 };
  };
  const key = streets.features.map((f) => f.properties.level[0]).join('') + (focused ?? '');
  return (
    <MapContainer center={CENTRE} zoom={13} className="map" scrollWheelZoom renderer={renderer}>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors · JPS · MET · Open-Meteo'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitStreets streets={streets} />
      <GeoJSON
        key={key}
        data={streets as unknown as GeoJSON.FeatureCollection}
        style={style}
        onEachFeature={(feature, layer) => {
          const p = feature.properties as StreetProperties;
          layer.bindTooltip(`${p.name} · ${p.level}`, { sticky: true });
          layer.on('click', (e: LeafletMouseEvent) => {
            const on = nearestStreet({ lat: e.latlng.lat, lon: e.latlng.lng }, [feature as StreetFeature])?.point;
            setTap(on ? [on.lat, on.lon] : [e.latlng.lat, e.latlng.lng]);
          });
          if (p.street_id === focused) layer.on('add', () => (layer as Path).bringToFront());
        }}
      />
      <FocusWatcher streets={streets} onFocus={onFocus} onPoint={setPoint} />
      <TapToZoom target={tap} />
      {/* No auto-pan: moving the map would move the focus. */}
      {focused && point && children && (
        <Popup position={[point.lat, point.lon]} className="focus-popup" autoPan={false} closeButton={false}
          closeOnClick={false} closeOnEscapeKey={false} autoClose={false} minWidth={220} maxWidth={260} offset={[0, 12]}>
          {children}
        </Popup>
      )}
      {stations.map((s) => (
        <CircleMarker
          key={`${s.graph_id}:${s.kind}`}
          center={[s.lat, s.lon]}
          radius={s.kind === 'wl' ? 8 : 6}
          pathOptions={{
            color: s.is_stale ? STALE_GREY : '#0b3d91',
            fillColor: s.is_stale ? STALE_GREY : s.kind === 'wl' ? '#0b3d91' : '#1e88e5',
            fillOpacity: s.is_stale ? 0.5 : 0.9,
            weight: 2,
            dashArray: s.is_stale ? '3 3' : undefined,
          }}
        >
          <Tooltip>{s.name} · {s.kind === 'wl' ? 'river' : 'rain'}{s.is_stale ? ' · stale' : ''}</Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
