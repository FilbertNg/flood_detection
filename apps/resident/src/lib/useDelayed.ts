import { useEffect, useState } from 'react';

/** True once `on` has stayed true for `ms`; false again as soon as `on` is false. Keeps fast loads from flashing a loader. */
export function useDelayed(on: boolean, ms: number): boolean {
  const [late, setLate] = useState(false);
  useEffect(() => {
    if (!on) {
      setLate(false);
      return;
    }
    const timer = setTimeout(() => setLate(true), ms);
    return () => clearTimeout(timer);
  }, [on, ms]);
  return on && late;
}
