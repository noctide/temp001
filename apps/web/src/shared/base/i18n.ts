// 文案（架构维护；国际化规范 3–5、9）。界面上只用文案键：t(K.shell.rail.home)。
// 现在用出厂默认文案（reg/i18n.seed.ts）兜底；语言包服务接通后改为按语言、命名空间加载已发布的语言包，调用方不用改。
import i18next from "i18next";
import { SEED } from "./reg/i18n.seed";

export const LANGS = ["zh-CN", "en-US"] as const;
export type Lang = (typeof LANGS)[number];

function initialLang(): Lang {
  const q = new URLSearchParams(location.search).get("lang");
  return LANGS.find((l) => l === q) ?? "zh-CN";
}

const resources = Object.fromEntries(Object.entries(SEED).map(([lng, msgs]) => [lng, { translation: msgs }]));

// 键里的点是层级（国际化规范 3），这里整串当一个键查，所以关掉 i18next 自己的分隔
void i18next.init({
  lng: initialLang(),
  fallbackLng: "zh-CN",
  resources,
  keySeparator: false,
  nsSeparator: false,
  interpolation: { escapeValue: false }, // React 自己转义
  returnNull: false,
});

/** 取文案。缺了回退到 zh-CN，再缺就显示键本身（国际化规范 9）。 */
export function t(key: string, params?: Record<string, string | number>): string {
  return i18next.t(key, params ?? {});
}

export function lang(): Lang {
  return (LANGS.find((l) => l === i18next.language) ?? "zh-CN") as Lang;
}
