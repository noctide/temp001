// 开发态待办示例（合成数据，从高保真原型 assets/dock.js 原样搬来，"今天" = 2026-10-03 星期六 09:12）。
// 待办接口（facilities.api 待办）接通前，悬浮球角标、待办小窗和抽屉用它；接通后删掉本文件。

export type DueKind = "over" | "today" | "week" | "none";
export interface Todo {
  id: string; src: string; act: string; title: string; who: string; at: string; step: string;
  due: { k: DueKind; t: string }; mode: string; role: "all" | "admin" | "member";
  rows?: [string, string][]; href: string; hrefLabel: string; batch?: string; why?: string; until?: string; no?: string;
}
export interface MineItem { id: string; role: "all" | "admin" | "member"; src: string; title: string; meta: string; status: string; note?: string; st: string; urge?: boolean; href: string }

export const DUE_ORDER = {over:0, today:1, week:2, none:3};
export const ITEMS: Todo[] = [
  {id:'o1', src:'考勤', act:'确认', title:'9 月工时确认 · 本人', who:'考勤管理员发起', at:'9 月 30 日', step:'月度工时确认', due:{k:'over',t:'逾期 1 天'}, mode:'confirm', role:'all',
   rows:[['统计周期','9 月 1 日 – 9 月 30 日'],['出勤','21 天 · 168.0 小时'],['加班','12.5 小时（已审批）'],['异常','无']], href:'Attendance.html?role=emp&tab=sheet', hrefLabel:'在考勤中查看明细'},
  {id:'f1', src:'表单平台', act:'审批', title:'质量异常上报 · 林晓', who:'林晓 · 装配一部', at:'今天 08:20', step:'质量主管审批', due:{k:'today',t:'18:00'}, mode:'full', role:'admin', href:'FormFill.html', hrefLabel:'在表单平台打开', no:'QI-20261003-0002'},
  {id:'a1', src:'考勤', act:'审核', title:'补卡申报 · 陈思远', who:'陈思远 · 质检部', at:'今天 07:58', step:'团队审核', due:{k:'today',t:'18:00'}, mode:'approve', batch:'补卡审核', role:'admin',
   rows:[['补卡时间','10 月 2 日 17:32 下班卡'],['原因','打卡机离线，未记录'],['佐证','A 线工位出站记录 17:30'],['本月补卡','第 1 次（上限 3 次）']], href:'Attendance.html?tab=report', hrefLabel:'在考勤中打开'},
  {id:'f4', src:'表单平台', act:'审批', title:'加班申请 · 王磊', who:'王磊 · 仓储物流', at:'昨天 17:40', step:'主管审批', due:{k:'today',t:'18:00'}, mode:'approve', role:'admin',
   rows:[['加班日期','10 月 3 日 08:00–17:00（国庆值班）'],['时长','8.00 小时'],['补偿方式','加班工资'],['事由','节前订单出库收尾']], href:'FormFill.html', hrefLabel:'在表单平台打开'},
  {id:'a3', src:'考勤', act:'确认', title:'10 月 8 日起新排班 · 装配一部', who:'人事行政部发布', at:'10 月 2 日', step:'排班确认', due:{k:'week',t:'10-06'}, mode:'confirm', role:'admin',
   rows:[['变更','执行四班三运转'],['生效','10 月 8 日起'],['涉及人数','52 人'],['你的班次','10-08 起 甲班：白白夜夜休休休']], href:'Attendance.html?tab=sheet&layer=plan', hrefLabel:'在排班表中查看'},
  {id:'g1', src:'智能管家', act:'确认', title:'管家拟提交 3 条工时', who:'你发起', at:'今天 10:22', step:'等待你确认', due:{k:'none',t:''}, mode:'jump', role:'all',
   rows:[['内容','10 月 2 日 A 线 3 段工作'],['合计','5.00 小时'],['项目','A 线设备改造 P-2607 · 新员工带教 P-2611'],['状态','未提交，确认前不会写入']], href:'AgentPanel.html?task=hours', hrefLabel:'去智能管家确认', why:'管家代你写入工时，需要在管家里逐条核对来源后再确认。'},
  {id:'d1', src:'数据处理', act:'修补', title:'隔离区 14 行 · 月度工时汇总', who:'9 月工时上传 · 工时效率模型', at:'今天 06:10', step:'隔离区修补', due:{k:'none',t:''}, mode:'jump', role:'admin',
   rows:[['隔离行数','14 行（共 4,862 行）'],['原因','工号不存在 9 行 · 单日时长超过 24 小时 5 行'],['影响','这 14 行未进入汇总，其余已正常产出'],['负责人','你（流程维护人）']], href:'Pipeline.html?tab=q', hrefLabel:'去数据处理修补', why:'修补要对照原始数据逐行修改并重新校验，只能在数据处理的隔离区里完成。'},
  {id:'f2', src:'表单平台', act:'审核', title:'工时登记 12 条 · 孙悦', who:'孙悦 · 质检部', at:'昨天 18:10', step:'部门审核', due:{k:'none',t:''}, mode:'approve', batch:'工时登记审核', role:'admin',
   rows:[['业务日期','9 月 28 日 – 9 月 30 日'],['条数','12 条'],['合计','94.5 小时'],['来源入口','粘贴表格']], href:'FormFill.html', hrefLabel:'在表单平台打开'},
  {id:'f6', src:'表单平台', act:'审核', title:'工时登记 5 条 · 彭越', who:'彭越 · 设备维护', at:'昨天 17:02', step:'部门审核', due:{k:'none',t:''}, mode:'approve', batch:'工时登记审核', role:'admin',
   rows:[['业务日期','10 月 1 日 – 10 月 2 日'],['条数','5 条'],['合计','38.0 小时'],['来源入口','手机填报']], href:'FormFill.html', hrefLabel:'在表单平台打开'},
  {id:'a2', src:'考勤', act:'审核', title:'调班申请 · 孙悦', who:'孙悦 · 质检部', at:'昨天 15:05', step:'团队审核', due:{k:'none',t:''}, mode:'approve', role:'admin',
   rows:[['调出','10 月 8 日 夜班 20:00–次日 08:00'],['调入','10 月 9 日 白班 08:00–17:00'],['互换对象','唐宁（已同意）'],['冲突检查','无连续超时']], href:'Attendance.html?tab=report', hrefLabel:'在考勤中打开'},
  {id:'v1', src:'可视化', act:'审核', title:'看板发布 · 产线效率周报 v3', who:'王可欣 申请', at:'昨天 11:30', step:'发布审核', due:{k:'none',t:''}, mode:'jump', role:'admin',
   rows:[['变更','新增「一次通过率」趋势图'],['可见范围','生产运营全员'],['数据来源','月度工时汇总 · 质检结果'],['当前版本','v2']], href:'Studio.html?review=eff', hrefLabel:'去可视化审核', why:'发布审核要预览新旧版本差异和数据权限，需要在 Studio 里查看。'},
  {id:'f3', src:'表单平台', act:'确认', title:'物品借用归还 · 彭越', who:'彭越 · 设备维护', at:'10 月 1 日', step:'归还确认', due:{k:'none',t:''}, mode:'confirm', role:'admin',
   rows:[['物品','手持扫码枪 × 1'],['借出','9 月 26 日'],['归还','10 月 1 日'],['外观','借用人自报完好']], href:'FormFill.html', hrefLabel:'在表单平台打开'},
  {id:'r1', src:'表单平台', act:'归还', title:'归还登记 · 游标卡尺', who:'你 9 月 26 日借出', at:'10 月 3 日', step:'归还登记', due:{k:'week',t:'10-09'}, mode:'jump', role:'admin',
   rows:[['物品','游标卡尺 · 0–150 mm × 1'],['借出时间','2026-09-26 14:05'],['预计归还','10 月 9 日'],['状态','借出中']], href:'FormFill.html?form=br&state=ret', hrefLabel:'去填归还登记', why:'归还要填实际数量、物品状况，有损坏时要拍照，在表单里填写。'},
  {id:'m2', src:'表单平台', act:'填报', title:'10 月安全自查 · 仓储物流班组', who:'安全生产月', at:'10 月 1 日', step:'班组自查', due:{k:'week',t:'10-08'}, mode:'jump', role:'member',
   rows:[['检查项','18 项'],['填报人','本班组任一成员'],['截止','10 月 8 日'],['进度','未开始']], href:'FormFill.html', hrefLabel:'去填写', why:'自查表需要逐项拍照上传，在表单平台填写更方便。'}
];
export const SNOOZED_SEED: Todo[] = [{id:'s1', src:'表单平台', act:'审核', title:'设备点检表 · 彭越', who:'彭越 · 设备维护', at:'10 月 2 日', step:'复核', due:{k:'none',t:''}, mode:'approve', role:'admin', until:'周一 09:00',
  rows:[['点检设备','装配线 A2'],['异常项','1 项：气压表读数偏低'],['处理','已更换，待复核'],['附件','照片 1 张']], href:'FormFill.html', hrefLabel:'在表单平台打开'}];
export const MINE: MineItem[] = [
  {id:'m1', role:'admin', src:'表单平台', title:'物品借用 · BR-20260929-0012', meta:'主管审批 · 刘畅 · 9 月 29 日', status:'已退回', note:'请补充借用用途后重新提交', st:'bad', href:'FormFill.html'},
  {id:'m2', role:'admin', src:'表单平台', title:'工时登记 · WH-20260930-0105', meta:'部门审核 · 刘畅 · 已等待 2 天', status:'审批中', st:'warn', urge:true, href:'FormFill.html'},
  {id:'m3', role:'admin', src:'考勤', title:'补卡申报 · 10 月 2 日下班卡', meta:'未提交 · 下班卡缺失，保存于今天 08:05', status:'草稿', st:'hollow', href:'Attendance.html?role=emp&bq=1'},
  {id:'m4', role:'admin', src:'考勤', title:'调休申报 · 10 月 9 日 8 小时', meta:'团队审核 · 考勤管理员 · 昨天提交', status:'审批中', st:'warn', href:'Attendance.html?role=emp&tab=sheet'},
  {id:'m5', role:'admin', src:'表单平台', title:'加班申请 · OT-20260927-0031', meta:'9 月 27 日 · 4.00 小时 · 刘畅 同意', status:'已完成', st:'good', href:'FormFill.html'},
  {id:'m6', role:'member', src:'表单平台', title:'加班申请 · OT-20261002-0047', meta:'主管审批 · 刘畅 · 昨天 17:40', status:'审批中', st:'warn', urge:true, href:'FormFill.html'},
  {id:'m7', role:'member', src:'表单平台', title:'物品借用 · 叉车钥匙', meta:'未提交 · 保存于 10 月 1 日', status:'草稿', st:'hollow', href:'FormFill.html'},
  {id:'m8', role:'member', src:'考勤', title:'补卡申报 · 9 月 30 日上班卡', meta:'团队审核 · 刘畅 同意 · 昨天 17:05', status:'已完成', st:'good', href:'Attendance.html?role=emp&tab=sheet'}
];
export const DONE_SEED = [
  {title:'加班申请 · 孙悦', src:'表单平台', result:'已同意', at:'昨天 18:30'},
  {title:'补卡申报 · 唐宁', src:'考勤', result:'已同意', at:'昨天 17:05'},
  {title:'工时登记 3 条 · 陈思远', src:'表单平台', result:'已退回', at:'10 月 1 日'}
];
export const CC = [{title:'采购申请 · 防护手套 200 副', meta:'周宁 发起 · 仓储物流审批中 · 抄送你', at:'今天 08:05'}];
export const PEOPLE = ['赵一鸣 · 质检部负责人（代）','彭越 · 设备维护','陈思远 · 质检部','孙悦 · 质检部'];
