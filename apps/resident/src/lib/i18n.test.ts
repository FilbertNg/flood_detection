import { describe, expect, it } from 'vitest';
import source from './i18n.ts?raw';
import { t } from './i18n';

describe('i18n source encoding', () => {
  it('decodes as UTF-8 without replacement or C1 control characters', () => {
    expect(source).not.toContain('�');
    expect(source).not.toContain('\u0085');
  });
  it('uses the real ellipsis in the busy labels', () => {
    expect(t('en', 'notifBusy')).toContain('…');
    expect(t('ms', 'notifBusy')).toContain('…');
  });
});
