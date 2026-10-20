// 应用外壳（Shell 子方案 6）：左侧导航 + 顶栏 + 页面区。结构、类名与高保真原型逐个对应，样式全部来自 mono.css。
import type { ReactNode } from "react";
import { K } from "../shared/base/reg";
import { t } from "../shared/base/i18n";
import { Icon } from "../shared/ui/icons";
import { NAV_BOTTOM, NAV_MAIN, type NavItem } from "./nav";
import type { ShellSession } from "./devSession";

function RailLink({ it, on }: { it: NavItem; on: boolean }) {
  return (
    <a href={it.href} className={on ? "on" : undefined} aria-current={on ? "page" : undefined}>
      <Icon name={it.icon} />
      {t(it.label)}
    </a>
  );
}

export function Rail({ active }: { active: string | null }) {
  return (
    <nav className="m-rail" aria-label={t(K.shell.rail.label)}>
      <div className="m-logo" aria-hidden="true">
        <Icon name="logo" />
      </div>
      {NAV_MAIN.map((it) => (
        <RailLink key={it.id} it={it} on={it.id === active} />
      ))}
      <span style={{ flex: 1 }} />
      {NAV_BOTTOM.map((it) => (
        <RailLink key={it.id} it={it} on={it.id === active} />
      ))}
    </nav>
  );
}

export function TopBar({ session }: { session: ShellSession }) {
  return (
    <header className="m-top">
      {/* 文字之间的空格和原型一致（行内排版会影响宽度） */}
      <button className="m-space" type="button" aria-haspopup="menu">
        {session.space} <span className="sl">/</span> {session.scope} <Icon name="chevronDown" />
      </button>
      <label className="m-search" style={{ flex: "1 1 240px", maxWidth: 460, margin: "0 auto" }}>
        <Icon name="search" />
        <input aria-label={t(K.shell.top.search.label)} placeholder={t(K.shell.top.search.placeholder)} />
        <span className="m-key">{t(K.shell.top.search.shortcut)}</span>
      </label>
      <button className="m-ib" type="button" aria-label={t(K.shell.top.messages.label, { count: session.unread })}>
        <Icon name="bell" />
        {session.unread > 0 && <span className="m-count">{session.unread}</span>}
      </button>
      <button className="m-ib" type="button" aria-label={t(K.shell.top.language.label)}>
        <Icon name="globe" />
      </button>
      <span className="m-ava solid" style={{ marginLeft: 6 }}>
        {session.avatar}
      </span>
    </header>
  );
}

export function AppShell({ active, session, children }: { active: string | null; session: ShellSession; children?: ReactNode }) {
  return (
    <div className="m-app">
      <Rail active={active} />
      <div className="m-main">
        <TopBar session={session} />
        <main className="m-page">{children}</main>
      </div>
    </div>
  );
}
