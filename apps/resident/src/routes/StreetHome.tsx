import { useParams } from 'react-router';
import type { Lang } from '@floodready/shared';
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
}

/**
 * Home for `/` and `/street/:id`: one street, no swiping. No saved street: the start screen.
 * `/` or my own street: my street. Another street (from the map, a share or a push for an older
 * saved street): that street with "Set as my street", which replaces mine.
 */
export function StreetHome({ lang, deviceId, saved, onSave }: Props) {
  const { id } = useParams();
  const mine = saved[0];
  if (!id && !mine) return <FindStreetPage lang={lang} onSave={onSave} />;
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
      />
      <MapFab lang={lang} />
    </div>
  );
}
