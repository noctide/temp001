// 开发态示例会话（合成数据，和高保真原型同一份人设）。
// access / shell 接口接通前，顶栏的部门、头像、未读数从这里取；地址加 ?role=member / ?role=zym 切换，和原型一致，
// 这样高保真比对两边才是同一个人。接口接通后删掉本文件。

export interface ShellSession {
  space: string; // 空间名
  scope: string; // 当前部门 / 项目
  avatar: string; // 头像上的字
  unread: number; // 未读消息
  dockRole: "admin" | "member"; // 待办按哪类身份取（原型 dock.js 的 S.role）
}

const PERSONAS: Record<string, ShellSession> = {
  lead: { space: "示例空间", scope: "装配一部", avatar: "刘", unread: 3, dockRole: "admin" }, // 刘畅 · 部门负责人
  member: { space: "示例空间", scope: "仓储物流", avatar: "王", unread: 3, dockRole: "member" }, // 王磊 · 普通成员
  zym: { space: "示例空间", scope: "质检部", avatar: "赵", unread: 3, dockRole: "admin" }, // 赵一鸣 · 表单管理员
};

export function devSession(search: string = location.search): ShellSession {
  const role = new URLSearchParams(search).get("role") ?? "lead";
  return PERSONAS[role] ?? (PERSONAS.lead as ShellSession);
}
