import 'leaflet/dist/leaflet.css';
import type { Feature } from 'geojson';
import type { PathOptions } from 'leaflet';
import { GeoJSON, MapContainer, TileLayer } from 'react-leaflet';
import { LEVEL_STYLE, type Level, type StreetCollection, type StreetProperties } from '@floodready/shared';

const CENTRE: [number, number] = [3.0852, 101.4377];

/** All township streets coloured by level; followed streets drawn thicker. */
export function StreetMap({ data, mine, onSelect }: {
  data: StreetCollection;
  mine: string[];
  onSelect: (streetId: string) => void;
}) {
  const style = (feature?: Feature): PathOptions => {
    const p = feature?.properties as StreetProperties | undefined;
    const level: Level = p?.level ?? 'normal';
    const followed = p ? mine.includes(p.street_id) : false;
    return { color: LEVEL_STYLE[level].line, weight: followed ? 7 : level === 'normal' ? 2 : 4, opacity: level === 'normal' ? 0.55 : 0.95 };
  };
  // A new key whenever levels change makes react-leaflet redraw the layer with fresh styles.
  const key = data.features.map((f) => f.properties.level[0]).join('') + mine.join(',');
  return (
    <MapContainer center={CENTRE} zoom={14} className="map" scrollWheelZoom>
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
          layer.on('click', () => onSelect(p.street_id));
        }}
      />
    </MapContainer>
  );
}
