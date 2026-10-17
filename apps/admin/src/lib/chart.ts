/** Linear map from a domain to a range; a flat domain maps to the range's middle. */
export function linearScale([d0, d1]: [number, number], [r0, r1]: [number, number]) {
  return (v: number): number => (d1 === d0 ? (r0 + r1) / 2 : r0 + ((v - d0) / (d1 - d0)) * (r1 - r0));
}

/** Sum of the last `n` values at each index; null (missing) counts as nothing. */
export function rollingSum(values: (number | null)[], n: number): number[] {
  return values.map((_, i) => {
    let total = 0;
    for (let j = Math.max(0, i - n + 1); j <= i; j++) total += values[j] ?? 0;
    return total;
  });
}

/** Move an ISO time that carries +08:00 by whole or fractional hours, keeping the offset. */
export function shiftIso(iso: string, hours: number): string {
  const shifted = new Date(new Date(iso).getTime() + hours * 3_600_000 + 8 * 3_600_000);
  return `${shifted.toISOString().slice(0, 19)}+08:00`;
}

/** "09:30" from an ISO time in MYT. */
export function hhmm(iso: string): string {
  return iso.slice(11, 16);
}

/** "12 Nov 2024, 09:00" */
export function dayTime(iso: string): string {
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const [y, m, d] = iso.slice(0, 10).split('-');
  return `${Number(d)} ${months[Number(m) - 1]} ${y}, ${hhmm(iso)}`;
}
