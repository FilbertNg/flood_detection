import { useParams } from 'react-router';
import type { Lang } from '@floodready/shared';
import { StreetView } from '../components/StreetView';

/** Route wrapper: one street by its id in the URL. The swipe home renders StreetView directly. */
export function StreetPage({ lang, deviceId }: { lang: Lang; deviceId: string }) {
  const { id = '' } = useParams();
  return <StreetView id={id} lang={lang} deviceId={deviceId} />;
}
