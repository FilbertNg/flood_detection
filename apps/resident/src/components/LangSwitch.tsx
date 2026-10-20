import type { Lang } from '@floodready/shared';

const OPTIONS: { lang: Lang; short: string; name: string }[] = [
  { lang: 'en', short: 'EN', name: 'English' },
  { lang: 'ms', short: 'BM', name: 'Bahasa Melayu' },
];

/** Quiet two-option switch: both languages always visible, the current one raised. */
export function LangSwitch({ lang, onChange }: { lang: Lang; onChange: (lang: Lang) => void }) {
  return (
    <div className="lang-switch" role="group" aria-label="Language / Bahasa">
      {OPTIONS.map((o) => (
        <button
          key={o.lang}
          type="button"
          aria-pressed={lang === o.lang}
          aria-label={o.name}
          lang={o.lang}
          onClick={() => lang !== o.lang && onChange(o.lang)}
        >
          {o.short}
        </button>
      ))}
    </div>
  );
}
