import { describe, expect, it } from 'vitest';
import { streets } from '@floodready/shared/mocks';
import { focusedStreet, nearestStreet, REVEAL_ZOOM } from './geo';

// A point on Jalan Makyong's second segment (same check as the resident app).
const onMakyong = { lat: 3.0902, lon: 101.42585 };

describe('focusedStreet', () => {
  it('is the street under the centre once zoomed in, with the point on it to anchor the popup', () => {
    const hit = focusedStreet(onMakyong, REVEAL_ZOOM, streets.features)!;
    expect(hit.street.street_id).toBe('BBR-jalan-makyong');
    expect(nearestStreet(hit.point, streets.features)!.distanceM).toBeLessThan(0.5);
  });

  it('is nothing while zoomed out or away from every street', () => {
    expect(focusedStreet(onMakyong, REVEAL_ZOOM - 1, streets.features)).toBeNull();
    expect(focusedStreet({ lat: 3.139, lon: 101.6869 }, REVEAL_ZOOM, streets.features)).toBeNull();
  });
});
