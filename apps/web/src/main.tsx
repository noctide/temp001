// 前端入口（架构维护）。领域页面按路由懒加载（工程规范 2.3、实施路线 5.1）。
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./shell/App";

const el = document.getElementById("root");
if (el) {
  createRoot(el).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
