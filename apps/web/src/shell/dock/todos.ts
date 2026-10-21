// 待办（全平台）的取数与排序。现在用开发态示例数据；facilities.api 待办接通后换成接口，调用方不用改。
import { DUE_ORDER, ITEMS, type Todo } from "./todos.dev";

export type DockRole = "admin" | "member";

/** 等我处理的：按身份过滤，逾期 → 今天 → 近 7 天 → 无期限。 */
export function pendingFor(role: DockRole, items: Todo[] = ITEMS): Todo[] {
  return items
    .filter((x) => x.role === "all" || x.role === role)
    .sort((a, b) => DUE_ORDER[a.due.k] - DUE_ORDER[b.due.k]);
}
