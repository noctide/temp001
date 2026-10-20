// Shell 外壳（shell 项目）。导航、顶栏已按高保真落成；领域页面以后按路由懒加载进 <main>。
import { AppShell } from "./AppShell";
import { devSession } from "./devSession";
import { activeNav } from "./nav";

export function App() {
  return <AppShell active={activeNav(location.pathname)} session={devSession()} />;
}
