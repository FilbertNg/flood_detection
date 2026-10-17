import 'leaflet/dist/leaflet.css';
import type { Feature } from 'geojson';
import type { PathOptions } from 'leaflet';
import { CircleMarker, GeoJSON, MapContainer, TileLayer, Tooltip } from 'react-leaflet';
import { LEVEL_STYLE, type Level, type Station, type StreetCollection, type StreetProperties } from '@floodready/shared';

import { STALE_GREY } from '../lib/colours';

const CENTRE: [number, number] = [3.0852, 101.4377];

/** Streets coloured by level; rain gauges (circles) and river gauges (squares-ish, larger) with stale ones grey. */
export function OpsMapView({ streets, stations, onSelect }: {
  streets: StreetCollection;
  stations: Station[];
  onSelect: (streetId: string) => void;
}) {
  const style = (feature?: Feature): PathOptions => {
    const level: Level = (feature?.properties as StreetProperties | undefined)?.level ?? 'normal';
    return { color: LEVEL_STYLE[level].line, weight: level === 'normal' ? 2 : 5, opacity: level === 'normal' ? 0.55 : 0.95 };
  };
  const key = streets.features.map((f) => f.properties.level[0]).join('');
  return (
    <MapContainer center={CENTRE} zoom={13} className="map" scrollWheelZoom>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors · JPS · MET · Open-Meteo'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <GeoJSON
        key={key}
        data={streets as unknown as GeoJSON.FeatureCollection}
        style={style}
        onEachFeature={(feature, layer) => {
          const p = feature.properties as StreetProperties;
          layer.bindTooltip(`${p.name} · ${p.level}`, { sticky: true });
          layer.on('click', () => onSelect(p.street_id));
        }}
      />
      {stations.map((s) => (
        <CircleMarker
          key={s.graph_id}
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
