import { LEVEL_LABEL, LEVEL_STYLE, type Lang, type Level } from '@floodready/shared';

export function LevelBadge({ level, lang, large = false }: { level: Level; lang: Lang; large?: boolean }) {
  const style = LEVEL_STYLE[level];
  return (
    <span className={`badge${large ? ' badge-large' : ''}`} style={{ background: style.bg, color: style.fg }}>
      {LEVEL_LABEL[lang][level]}
    </span>
  );
}
