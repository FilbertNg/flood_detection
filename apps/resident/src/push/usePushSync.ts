import { useEffect, useRef } from 'react';
import type { Lang } from '@floodready/shared';
import { syncPush } from './subscribe';

/** When streets or language change, re-post them for a device that is already subscribed. */
export function usePushSync({ deviceId, streets, lang }: { deviceId: string; streets: string[]; lang: Lang }): void {
  const key = `${lang}|${streets.join(',')}`;
  const last = useRef(key);
  useEffect(() => {
    if (last.current === key) return;
    last.current = key;
    void syncPush({ deviceId, streetIds: streets, lang });
  }, [key, deviceId, streets, lang]);
}
