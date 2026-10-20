import 'leaflet/dist/leaflet.css';
import type { Feature } from 'geojson';
import { canvas, type LeafletMouseEvent, type Path, type PathOptions } from 'leaflet';
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { GeoJSON, MapContainer, Popup, TileLayer, useMap, useMapEvents } from 'react-leaflet';
import { LEVEL_STYLE, type Level, type StreetCollection, type StreetFeature, type StreetProperties } from '@floodready/shared';
import { focusedStreet, nearestStreet, REVEAL_ZOOM, type Place } from '../lib/geo';

const CENTRE: [number, number] = [3.0852, 101.4377];
/** Pixels either side of a street line that still count as a tap on it (a finger is wider than a 2 px line). */
const TAP_TOLERANCE = 14;

/**
 * Reports the street under the map centre after every move or zoom (null while zoomed out or off a
 * street), and whether the map is zoomed in far enough to show the crosshair.
 */
function FocusWatcher({ data, onFocus, onReveal, onPoint }: {
  data: StreetCollection;
  onFocus: (id: string | null) => void;
  onReveal: (on: boolean) => void;
  onPoint: (p: Place | null) => void;
}) {
  const last = useRef<string | null>(null);
  const map = useMap();
  const check = () => {
    const c = map.getCenter();
    const z = map.getZoom();
    onReveal(z >= REVEAL_ZOOM);
    const hit = focusedStreet({ lat: c.lat, lon: c.lng }, z, data.features);
    onPoint(hit?.point ?? null);
    const id = hit?.street.street_id ?? null;
    if (id !== last.current) {
      last.current = id;
      onFocus(id);
    }
  };
  useMapEvents({ moveend: check, zoomend: check });
  // Street data refreshes every few seconds; the focus is checked again against the new collection.
  useEffect(check, [data]);
  return null;
}

/** Redraws the map when its box changes size (full screen, or the credits opening below it). */
function Resize() {
  const map = useMap();
  useEffect(() => {
    if (typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(map.getContainer());
    return () => observer.disconnect();
  }, [map]);
  return null;
}

/** Tapping a street line zooms in on it, so the street comes under the centre and its popup opens. */
function TapToZoom({ target }: { target: [number, number] | null }) {
  const map = useMap();
  useEffect(() => {
    if (target) map.flyTo(target, Math.max(map.getZoom(), REVEAL_ZOOM), { duration: 0.6 });
  }, [target, map]);
  return null;
}

/**
 * All township streets coloured by level; followed streets drawn thicker. The focused street is drawn
 * heavier in its level colour, and `children` (the street card) opens in a popup whose tail points at
 * the spot on that street nearest the map centre.
 */
export function StreetMap({ data, mine, focused, onFocus, children }: {
  data: StreetCollection;
  mine: string[];
  focused: string | null;
  onFocus: (streetId: string | null) => void;
  children?: ReactNode;
}) {
  const [reveal, setReveal] = useState(false);
  const [point, setPoint] = useState<Place | null>(null);
  // Canvas, not SVG: only the canvas renderer has a hit tolerance around thin lines.
  const renderer = useMemo(() => canvas({ tolerance: TAP_TOLERANCE }), []);
  const [tap, setTap] = useState<[number, number] | null>(null);
  const style = (feature?: Feature): PathOptions => {
    const p = feature?.properties as StreetProperties | undefined;
    const level: Level = p?.level ?? 'normal';
    if (p && p.street_id === focused) return { color: LEVEL_STYLE[level].line, weight: 10, opacity: 1, lineCap: 'round' };
    const followed = p ? mine.includes(p.street_id) : false;
    return { color: LEVEL_STYLE[level].line, weight: followed ? 7 : level === 'normal' ? 2 : 4, opacity: level === 'normal' ? 0.55 : 0.95 };
  };
  // A new key whenever levels or the focus change makes react-leaflet redraw the layer with fresh styles.
  const key = data.features.map((f) => f.properties.level[0]).join('') + mine.join(',') + (focused ?? '');
  return (
    <div className="map-box">
      <MapContainer center={CENTRE} zoom={14} className="map" scrollWheelZoom renderer={renderer}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors · JPS · MET · Open-Meteo'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <GeoJSON
          key={key}
          data={data as unknown as GeoJSON.FeatureCollection}
          style={style}
          onEachFeature={(feature, layer) => {
            const p = feature.properties as StreetProperties;
            layer.bindTooltip(p.name, { sticky: true });
            // A tap within the tolerance can land beside the line: zoom to the nearest point on the street
            // itself, or that small miss becomes tens of metres once zoomed in and nothing is picked.
            layer.on('click', (e: LeafletMouseEvent) => {
              const on = nearestStreet({ lat: e.latlng.lat, lon: e.latlng.lng }, [feature as StreetFeature])?.point;
              setTap(on ? [on.lat, on.lon] : [e.latlng.lat, e.latlng.lng]);
            });
            // The focused street is drawn over its neighbours.
            if (p.street_id === focused) layer.on('add', () => (layer as Path).bringToFront());
          }}
        />
        <FocusWatcher data={data} onFocus={onFocus} onReveal={setReveal} onPoint={setPoint} />
        {/* No auto-pan: moving the map would move the focus. The popup follows the map as it is dragged. */}
        {focused && point && children && (
          <Popup position={[point.lat, point.lon]} className="focus-popup" autoPan={false} closeButton={false}
            closeOnClick={false} closeOnEscapeKey={false} autoClose={false} minWidth={220} maxWidth={260} offset={[0, 12]}>
            {children}
          </Popup>
        )}
        <TapToZoom target={tap} />
        <Resize />
      </MapContainer>
      {/* Crosshair while zoomed in but off a street; on a street the popup's tail marks the spot. */}
      {reveal && !focused && <span className="map-cross" aria-hidden="true" />}
    </div>
  );
}
