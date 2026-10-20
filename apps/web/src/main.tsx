// 前端入口（架构维护）。领域页面按路由懒加载（工程规范 2.3、实施路线 5.1）。
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
// 公共样式从高保真原型同步（tl.py fidelity --sync），不在这里另写
import "./shared/ui/generated/mono-fonts.css";
import "./shared/ui/generated/mono.css";
import { watchLook } from "./shared/ui/look";
import { App } from "./shell/App";

watchLook();

const el = document.getElementById("root");
if (el) {
  createRoot(el).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
