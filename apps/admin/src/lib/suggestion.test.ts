import { describe, expect, it } from 'vitest';
import { suggestions } from '@floodready/shared/mocks';
import type { Suggestion } from '@floodready/shared';
import { NEXT_STEPS, dateMonths, datesInWords, splitText, statTiles } from './suggestion';

const sug = (rule: Suggestion['rule'], evidence: Suggestion['evidence']): Suggestion => ({ ...suggestions[0], rule, evidence });

describe('splitText', () => {
  it('splits the action from the fixed screening suffix', () => {
    expect(splitText('Add Jalan Bakti to the pre-storm list. Screening suggestion; site survey needed.'))
      .toEqual({ action: 'Add Jalan Bakti to the pre-storm list.', caveat: 'Screening suggestion; site survey needed.' });
  });

  it('keeps the whole text as the action and still gives the caveat when the suffix is missing', () => {
    expect(splitText('Check the flap gates.')).toEqual({ action: 'Check the flap gates.', caveat: 'Screening suggestion; site survey needed.' });
  });
});

describe('statTiles', () => {
  it('builds SUG-5 tiles from the structured rank, episodes and river station', () => {
    const tiles = statTiles(sug('SUG-5', {
      rank: 5, eligible_streets: 79, episode_dates: ['2024-04-16', '2024-04-17', '2024-04-22'],
      river_station_name: 'P/A Pandamaran', eligible_streets_on_same_river_station: 53, notes: 'Rank 9 of 99 (ignored: notes are not parsed)',
    }));
    expect(tiles).toEqual([
      { key: 'rank', value: '5', of: 'of 79', label: 'Rank among eligible streets' },
      { key: 'episodes', value: '3', label: 'Separate alert episodes' },
      { key: 'station', value: 'P/A Pandamaran', label: 'River station driving the count, shared by 53 eligible streets', wide: true },
    ]);
  });

  it('builds flood, depth and rain tiles for SUG-1, the rain tile showing the heaviest onset', () => {
    const tiles = statTiles(sug('SUG-1', { flood_dates: ['2024-11-12', '2024-12-01'], rain_at_onset_mm: [42.5, 61.5], max_depth: 'knee_high' }));
    expect(tiles).toEqual([
      { key: 'floods', value: '2', label: 'Confirmed floods' },
      { key: 'depth', value: 'knee high', label: 'Deepest reported' },
      { key: 'rain', value: '61.5', of: 'mm', label: 'Heaviest rain at onset' },
    ]);
  });

  it('names the flood dates for what they are: days across a cluster (SUG-4) or resident reports (SUG-6)', () => {
    expect(statTiles(sug('SUG-4', { flood_dates: ['2024-11-12'] }))[0].label).toBe('Days with confirmed floods');
    expect(statTiles(sug('SUG-6', { flood_dates: ['2024-11-12'] }))[0].label).toBe('Resident-reported floods');
  });

  it('shows no tile for a missing or badly typed value, never an empty or 0 tile', () => {
    expect(statTiles(sug('SUG-7', { notes: 'stale' }))).toEqual([]);
    expect(statTiles(sug('SUG-5', { rank: 5, episode_dates: [], river_station_name: '', max_depth: null, rain_at_onset_mm: [] }))).toEqual([]);
    // Without the shared count the station tile drops that clause rather than inventing it.
    expect(statTiles(sug('SUG-5', { river_station_name: 'P/A Pandamaran' }))[0].label).toBe('River station driving the count');
  });
});

describe('dateMonths', () => {
  it('draws one strip per month, oldest first, newest last', () => {
    const months = dateMonths(['2024-05-02', '2024-04-16', '2024-04-17'])!;
    expect(months.map((m) => m.label)).toEqual(['April 2024', 'May 2024']);
    expect(months[0].days).toBe(30);
    expect(months[0].on).toEqual([16, 17]);
    expect(months[1].days).toBe(31);
  });

  it('falls back to a list (null) beyond three months', () => {
    expect(dateMonths(['2024-01-05', '2024-02-05', '2024-03-05', '2024-04-05'])).toBeNull();
  });

  it('knows leap Februaries', () => {
    expect(dateMonths(['2024-02-29'])![0].days).toBe(29);
  });
});

describe('datesInWords', () => {
  it('lists the dates per month in words', () => {
    expect(datesInWords(['2024-04-16', '2024-04-17', '2024-04-22', '2024-05-02'])).toBe('16, 17 and 22 April 2024; 2 May 2024');
  });
});

describe('NEXT_STEPS', () => {
  it('offers only the next step for each status', () => {
    expect(NEXT_STEPS.open.map((b) => [b.label, b.to])).toEqual([['Accept', 'accepted'], ['Dismiss', 'dismissed']]);
    expect(NEXT_STEPS.accepted.map((b) => [b.label, b.to])).toEqual([['Mark done', 'done'], ['Back to open', 'open']]);
    expect(NEXT_STEPS.dismissed.map((b) => [b.label, b.to])).toEqual([['Reopen', 'open']]);
    expect(NEXT_STEPS.done.map((b) => [b.label, b.to])).toEqual([['Reopen', 'open']]);
  });
});
