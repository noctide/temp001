// 外观的平台默认（我的设置 › 外观；规则和原型 assets/look.js 一致）。
// 现在只有平台默认：电脑字号 14、手机字号 15（整页缩放）。部门默认、个人设置接通后在这里叠加。
import "./look.css";

const MOBILE_MAX = 720; // 和 mono.css 手机版断点一致
const PLATFORM = { size: 14, mobileSize: 15 };

export function applyLook(): void {
  const root = document.documentElement;
  const size = window.innerWidth <= MOBILE_MAX ? PLATFORM.mobileSize : PLATFORM.size;
  root.style.zoom = size === 14 ? "" : String(size / 14);
  root.style.setProperty("--tl-zoom", String(size / 14));
  if (size === 14) root.removeAttribute("data-tl-zoom");
  else root.setAttribute("data-tl-zoom", "");
}

let timer: number | undefined;
export function watchLook(): void {
  applyLook();
  window.addEventListener("resize", () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(applyLook, 150);
  });
}
