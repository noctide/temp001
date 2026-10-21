// Shell 外壳（shell 项目）。导航、顶栏、悬浮球已按高保真落成；领域页面以后按路由懒加载进 <main>。
import { AppShell } from "./AppShell";
import { Dock } from "./dock/Dock";
import { devSession } from "./devSession";
import { activeNav } from "./nav";

export function App() {
  const session = devSession();
  return (
    <>
      <AppShell active={activeNav(location.pathname)} session={session} />
      <Dock role={session.dockRole} />
    </>
  );
}
