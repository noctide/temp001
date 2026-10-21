// 公共图标（架构维护）：内联描边 SVG，线宽、端点由 mono.css 按所在位置给（.m-rail a svg、.m-ib svg ……）。
// 图形和高保真原型逐笔一致；新增图标先加进原型，再搬到这里。
import type { ReactElement } from "react";

const SHAPES = {
  logo: <path d="M4 6h16M12 6v14M7 12h10M9 18h6" />,
  home: <path d="M3 10.5 12 3l9 7.5V21h-6v-6H9v6H3z" />,
  workbench: (
    <>
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </>
  ),
  forms: (
    <>
      <rect x="5" y="3" width="14" height="18" rx="2" />
      <path d="M9 8h6M9 12h6M9 16h4" />
    </>
  ),
  attendance: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  automation: <path d="M13 2 4 14h7l-1 8 9-12h-7z" />,
  data: (
    <>
      <ellipse cx="12" cy="5" rx="8" ry="3" />
      <path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5" />
      <path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" />
    </>
  ),
  studio: <path d="M3 21h18M6 17V10M11 17V5M16 17v-4M21 17V8" />,
  knowledge: (
    <>
      <path d="M4 5a2 2 0 0 1 2-2h14v16H6a2 2 0 0 0-2 2z" />
      <path d="M20 19v2H6" />
    </>
  ),
  agent: (
    <>
      <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />
      <path d="M19 17l.7 1.8 1.8.7-1.8.7L19 22l-.7-1.8-1.8-.7 1.8-.7z" />
    </>
  ),
  plugins: (
    <>
      <path d="M9 3v4M15 3v4" />
      <rect x="6" y="7" width="12" height="7" rx="2" />
      <path d="M12 14v4a3 3 0 0 1-3 3" />
    </>
  ),
  admin: (
    <>
      <path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1" />
      <circle cx="15" cy="6" r="2" />
      <circle cx="9" cy="12" r="2" />
      <circle cx="17" cy="18" r="2" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </>
  ),
  bell: (
    <>
      <path d="M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8" />
      <path d="M10 20a2 2 0 0 0 4 0" />
    </>
  ),
  globe: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3" />
    </>
  ),
  chevronDown: <path d="m6 9 6 6 6-6" />,
  spark: <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />,
  x: <path d="M6 6l12 12M18 6 6 18" />,
} satisfies Record<string, ReactElement>;

export type IconName = keyof typeof SHAPES;

/** className 和 hidden 按原型对应位置给（导航、顶栏里的图标原型没有这两个属性；悬浮窗里的是 class="dk-i" aria-hidden）。 */
export function Icon({ name, className, hidden }: { name: IconName; className?: string; hidden?: boolean }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden={hidden ? true : undefined}>
      {SHAPES[name]}
    </svg>
  );
}
