import { useParams } from 'react-router';
import type { Lang } from '@floodready/shared';
import { ChangeLocation } from '../components/ChangeLocation';
import { MapFab } from '../components/MapFab';
import { StreetView } from '../components/StreetView';
import { t } from '../lib/i18n';
import { FindStreetPage } from './FindStreet';

interface Props {
  lang: Lang;
  deviceId: string;
  /** Saved streets on this device. The app keeps one; an older phone may still hold several, and then the first is "my street". */
  saved: string[];
  onSave: (ids: string[]) => void;
  /** This visit has been through the onboarding screen (see lib/visit.ts). */
  introDone: boolean;
  onIntroDone: () => void;
}

/**
 * Home for `/` and `/street/:id`: one street, no swiping. No saved street, or the first screen of a visit:
 * the onboarding screen.
 * `/` or my own street: my street. Another street (from the map, a share or a push for an older
 * saved street): that street with "Set as my street", which replaces mine. "Change location" is always
 * there, so a resident can move to another street without the map.
 */
export function StreetHome({ lang, deviceId, saved, onSave, introDone, onIntroDone }: Props) {
  const { id } = useParams();
  const mine = saved[0];
  // `/` opens on the onboarding screen once per visit; a street link (`/street/:id`, e.g. a push) opens directly.
  if (!id && (!mine || !introDone)) return <FindStreetPage lang={lang} onSave={onSave} mine={mine} onOpen={onIntroDone} />;
  const shown = id ?? mine!;
  const other = shown !== mine;
  return (
    <div className="street-home">
      <StreetView
        key={shown}
        id={shown}
        lang={lang}
        deviceId={deviceId}
        showBack={false}
        topLeft={other ? <button type="button" className="add-street" onClick={() => onSave([shown])}>{t(lang, 'setStreet')}</button> : undefined}
        belowHero={<ChangeLocation lang={lang} mine={saved} deviceId={deviceId} onSave={onSave} />}
      />
      <MapFab lang={lang} />
    </div>
  );
}
