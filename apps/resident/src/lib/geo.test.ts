import { describe, expect, it } from 'vitest';
import { streets } from '@floodready/shared/mocks';
import type { StreetFeature } from '@floodready/shared';
import bbrRaw from '../../../../assets/geo/bbr_streets.geojson?raw';
import { focusedStreet, nearestStreet, REVEAL_ZOOM } from './geo';

/** The committed BBR street map (943 OSM streets) as the app's /streets geometry. */
const bbr = (JSON.parse(bbrRaw) as { features: StreetFeature[] }).features;

describe('nearestStreet', () => {
  it('finds the street a point lies on, using the real BBR street map', () => {
    const f = bbr[100];
    const [lon, lat] = (f.geometry.coordinates as number[][])[0];
    const hit = nearestStreet({ lat, lon }, bbr)!;
    expect(hit.distanceM).toBeLessThan(1);
    // A point on a junction can touch two streets; the hit must be one of the streets through it.
    const through = bbr.filter((s) => (s.geometry.coordinates as number[][]).some(([x, y]) => x === lon && y === lat)).map((s) => s.properties.street_id);
    expect(through).toContain(hit.street.street_id);
  });

  it('measures to the line between vertices, not only to the vertices', () => {
    // Midway along the second segment of Jalan Makyong, about 20 m to the north.
    const hit = nearestStreet({ lat: 3.0902 + 0.00018, lon: 101.42585 }, streets.features)!;
    expect(hit.street.street_id).toBe('BBR-jalan-makyong');
    expect(hit.distanceM).toBeGreaterThan(10);
    expect(hit.distanceM).toBeLessThan(30);
  });

  it('reports a large distance for a place far outside the township', () => {
    const hit = nearestStreet({ lat: 3.139, lon: 101.6869 }, bbr)!; // Kuala Lumpur city centre
    expect(hit.distanceM).toBeGreaterThan(20_000);
  });

  it('handles MultiLineString streets and an empty list', () => {
    const multi: StreetFeature = {
      type: 'Feature',
      geometry: { type: 'MultiLineString', coordinates: [[[101.0, 3.0], [101.001, 3.0]], [[101.5, 3.5], [101.501, 3.5]]] },
      properties: { ...streets.features[0].properties, street_id: 'multi' },
    };
    expect(nearestStreet({ lat: 3.5001, lon: 101.5005 }, [multi])!.distanceM).toBeLessThan(15);
    expect(nearestStreet({ lat: 3, lon: 101 }, [])).toBeNull();
  });
});

describe('focusedStreet (the street under the map centre once zoomed in)', () => {
  // A point on Jalan Makyong's second segment.
  const onMakyong = { lat: 3.0902, lon: 101.42585 };

  it('is the street under the centre at the reveal zoom or closer', () => {
    expect(focusedStreet(onMakyong, REVEAL_ZOOM, streets.features)?.street.street_id).toBe('BBR-jalan-makyong');
    expect(focusedStreet(onMakyong, REVEAL_ZOOM + 2, streets.features)?.street.street_id).toBe('BBR-jalan-makyong');
  });

  it('gives the point on the street line nearest the centre, for the popup to point at', () => {
    const hit = focusedStreet({ lat: onMakyong.lat + 0.0001, lon: onMakyong.lon }, REVEAL_ZOOM, streets.features)!;
    const back = nearestStreet(hit.point, streets.features)!;
    expect(back.street.street_id).toBe('BBR-jalan-makyong');
    expect(back.distanceM).toBeLessThan(0.5);
    expect(nearestStreet({ lat: onMakyong.lat + 0.0001, lon: onMakyong.lon }, streets.features)!.point).toEqual(hit.point);
  });

  it('is nothing while zoomed out', () => {
    expect(focusedStreet(onMakyong, REVEAL_ZOOM - 1, streets.features)).toBeNull();
  });

  it('is nothing when no street is close to the centre', () => {
    expect(focusedStreet({ lat: 3.139, lon: 101.6869 }, REVEAL_ZOOM, streets.features)).toBeNull();
  });
});
