import type { Lang, Level, Susceptibility, TimeWindow } from '@floodready/shared';
import { windowText } from './format';
import { t, tf, type StringKey } from './i18n';

export interface Step {
  title: string;
  note?: string;
}

/** A street "floods early" from flood-prone rating 4 of 5 (top two fifths of BBR streets). */
const FLOODS_EARLY = 4;

/** A step whose note is a fixed string key (or none). */
const step = (lang: Lang, title: StringKey, note?: StringKey): Step =>
  note === undefined ? { title: t(lang, title) } : { title: t(lang, title), note: t(lang, note) };

/** A step whose note is already filled in with street data. */
const stepWith = (lang: Lang, title: StringKey, note: string): Step => ({ title: t(lang, title), note });

/**
 * The "What to do now" checklist: 2 to 4 actions for the official level, made specific to the
 * street where the data allows (flood-prone rating, expected window).
 */
export function adviceSteps(level: Level, susceptibility: Susceptibility, window: TimeWindow | null, lang: Lang): Step[] {
  switch (level) {
    case 'normal':
      return [step(lang, 'aNothing', 'aNothingNote'), step(lang, 'aGoBag', 'aGoBagNote'), step(lang, 'aNumbers', 'aNumbersNote')];
    case 'watch':
      return [
        step(lang, 'aCharge'),
        step(lang, 'aBagDoor', 'aBagDoorNote'),
        susceptibility >= FLOODS_EARLY ? stepWith(lang, 'aCarWatch', tf(lang, 'aFloodsEarly', { n: susceptibility })) : step(lang, 'aCarWatch'),
        step(lang, 'aNeighbours'),
      ];
    case 'warning':
      return [
        step(lang, 'aCarNow'),
        step(lang, 'aLift'),
        window ? stepWith(lang, 'aLeave', tf(lang, 'aLeaveAt', { window: windowText(window, lang) })) : step(lang, 'aLeave', 'aLeaveNote'),
        step(lang, 'aNoDrive', 'aNoDriveNote'),
      ];
    case 'danger':
      // TODO(R5): name the nearest relief centre (PPS) once an official JKM / NADMA list for BBR is
      // sourced and cited; until then the wording stays generic so no place name is invented.
      return [step(lang, 'aUpstairs'), step(lang, 'aPower', 'aPowerNote'), step(lang, 'aNoWalk', 'aNoWalkNote'), step(lang, 'aTrapped')];
  }
}
