// 左侧主导航（Shell 子方案 6.1；顺序与高保真一致）。以后由 shell 接口按权限返回，这里是出厂顺序。
import { K } from "../shared/base/reg";
import type { IconName } from "../shared/ui/icons";

export interface NavItem {
  id: string;
  href: string;
  icon: IconName;
  label: string; // 文案键
}

export const NAV_MAIN: NavItem[] = [
  { id: "home", href: "/", icon: "home", label: K.shell.rail.home },
  { id: "workbench", href: "/workbench", icon: "workbench", label: K.shell.rail.workbench },
  { id: "forms", href: "/forms", icon: "forms", label: K.shell.rail.forms },
  { id: "attendance", href: "/attendance", icon: "attendance", label: K.shell.rail.attendance },
  { id: "automation", href: "/automation", icon: "automation", label: K.shell.rail.automation },
  { id: "data", href: "/data", icon: "data", label: K.shell.rail.data },
  { id: "studio", href: "/studio", icon: "studio", label: K.shell.rail.studio },
  { id: "knowledge", href: "/knowledge", icon: "knowledge", label: K.shell.rail.knowledge },
];

export const NAV_BOTTOM: NavItem[] = [
  { id: "agent", href: "/agent", icon: "agent", label: K.shell.rail.agent },
  { id: "plugins", href: "/plugins", icon: "plugins", label: K.shell.rail.plugins },
  { id: "admin", href: "/admin", icon: "admin", label: K.shell.rail.admin },
];

/** 当前地址落在哪个导航项（首页只认根路径，其余认前缀）。 */
export function activeNav(path: string): string | null {
  for (const it of [...NAV_MAIN, ...NAV_BOTTOM]) {
    if (it.href === "/" ? path === "/" : path === it.href || path.startsWith(it.href + "/")) return it.id;
  }
  return null;
}
