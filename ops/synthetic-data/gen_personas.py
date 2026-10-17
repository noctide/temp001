"""Titanloom 合成数据生成器 —— 人设表（M0-06 第一部分）。

读取同目录下的 personas.json（组织与"有名有姓"的人），按固定随机种子把每个
叶子部门补足到规定人数，输出 people.json：在职 190 人（其中 1 人无平台账户）、
离职档案 6 份，合计 196 人。

只用 Python 3.12 标准库。生成器固定种子，同一种子两次生成逐字节相同。

用法：
    python gen_personas.py --seed 20261016 --out <输出目录>
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
PERSONAS_PATH = HERE / "personas.json"

# 生成人名的姓（常见单姓）与名用字（常见双字名用字）。合成数据，非真实人员。
SURNAMES = (
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚"
    "谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳酆鲍史唐费廉"
    "岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹"
)
GIVEN_CHARS = (
    "伟芳娜敏静丽强磊军洋勇艳杰娟涛明超秀霞平刚桂英华玉兰鑫辉建林成坤文"
    "宇轩阳晨浩博健立雪梅红燕飞志国永春晓东光海江山云龙凤天雨思嘉欣婷子俊"
    "佳凡然若安宁慧琳丹琪瑶悦怡彤心书涵诗雅睿哲泽铭瑞昊楠辰"
)

# 生成人的入职 / 离职日期区间（最少假设，见 README）。
HIRE_START = date(2019, 1, 1)
HIRE_END = date(2026, 9, 30)
RESIGN_HIRE_START = date(2018, 1, 1)
RESIGN_HIRE_END = date(2024, 6, 30)
RESIGN_DATE_START = date(2024, 7, 1)
RESIGN_DATE_END = date(2026, 9, 30)

# 离职档案总数（规格：6 份）。具名的一份是 张燕 A0102，其余由生成器补足。
RESIGNED_TOTAL = 6

# 全体在职且"有平台账户"的人另有基础角色「员工」；严述（无账户）与离职档案除外。
BASE_ROLE = "员工"


def load_personas(path: Path = PERSONAS_PATH) -> dict:
    """读取 personas.json。"""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _rand_date(rng: random.Random, start: date, end: date) -> str:
    days = (end - start).days + 1
    return (start + timedelta(days=rng.randrange(days))).isoformat()


def _final_roles(specific_roles: list[str], status: str, account: str) -> list[str]:
    """在职且有账户者：基础角色「员工」+ 具体角色；其余无角色。"""
    if status == "active" and account == "active":
        return [BASE_ROLE, *specific_roles]
    return []


class _Gen:
    """生成器的状态：随机数、编号计数、已用人名。"""

    def __init__(self, seed: int, personas: dict) -> None:
        self.rng = random.Random(seed)  # 合成数据，固定种子即可，不用于安全
        self.named = personas["people"]
        leaf = [d for d in personas["departments"] if d.get("is_space")]
        self.leaf_order = [d["name"] for d in leaf]
        self.by_name = {d["name"]: d for d in leaf}
        # 编号续编：每个部门前缀从现有最大号 +1 起。
        self.counters: dict[str, int] = {}
        for d in leaf:
            nums = [int(p["id"][1:]) for p in self.named if p.get("id") and p["department"] == d["name"]]
            self.counters[d["prefix"]] = max(nums) if nums else 0
        # 生成名：三字名（单姓 + 双名），不与规格里的人重名、彼此不重名。
        self.used: set[str] = {p["name"] for p in self.named}

    def next_id(self, prefix: str) -> str:
        self.counters[prefix] += 1
        return f"{prefix}{self.counters[prefix]:04d}"

    def gen_name(self) -> str:
        while True:
            name = self.rng.choice(SURNAMES) + self.rng.choice(GIVEN_CHARS) + self.rng.choice(GIVEN_CHARS)
            if name not in self.used:
                self.used.add(name)
                return name

    def named_people(self) -> list[dict]:
        """规格里有名有姓的人：补齐缺失的编号与入职日期，套用「员工」角色规则。"""
        out = []
        for spec in self.named:
            person = dict(spec)
            if not person.get("id"):
                person["id"] = self.next_id(self.by_name[person["department"]]["prefix"])
            if not person.get("hire_date"):
                person["hire_date"] = _rand_date(self.rng, HIRE_START, HIRE_END)
            person["platform_roles"] = _final_roles(
                person.get("platform_roles") or [], person["status"], person["account"]
            )
            out.append(person)
        return out

    def fill_departments(self) -> list[dict]:
        """每个叶子部门补足到规定在职人数（补出来的人为基线岗位的「员工」）。"""
        out = []
        for dname in self.leaf_order:
            d = self.by_name[dname]
            named_active = sum(1 for p in self.named if p["department"] == dname and p["status"] == "active")
            for _ in range(d["headcount"] - named_active):
                out.append(
                    {
                        "id": self.next_id(d["prefix"]),
                        "name": self.gen_name(),
                        "department": dname,
                        "position": d["base_position"],
                        "hire_date": _rand_date(self.rng, HIRE_START, HIRE_END),
                        "resign_date": None,
                        "status": "active",
                        "account": "active",
                        "platform_roles": [BASE_ROLE],
                        "note": None,
                    }
                )
        return out

    def fill_resigned(self) -> list[dict]:
        """离职档案：除具名的一份外，按种子补足到 6 份。"""
        out = []
        named_resigned = sum(1 for p in self.named if p["status"] == "resigned")
        for _ in range(RESIGNED_TOTAL - named_resigned):
            dname = self.rng.choice(self.leaf_order)
            d = self.by_name[dname]
            out.append(
                {
                    "id": self.next_id(d["prefix"]),
                    "name": self.gen_name(),
                    "department": dname,
                    "position": d["base_position"],
                    "hire_date": _rand_date(self.rng, RESIGN_HIRE_START, RESIGN_HIRE_END),
                    "resign_date": _rand_date(self.rng, RESIGN_DATE_START, RESIGN_DATE_END),
                    "status": "resigned",
                    "account": "disabled",
                    "platform_roles": [],
                    "note": None,
                }
            )
        return out


def generate(seed: int, personas: dict) -> dict:
    """按固定种子生成全部 196 人，返回 {"seed": ..., "people": [...]}。顺序与旧版一致，同一种子结果逐字节不变。"""
    g = _Gen(seed, personas)
    people = g.named_people() + g.fill_departments() + g.fill_resigned()
    people.sort(key=lambda p: p["id"])
    return {"seed": seed, "people": people}


def render(data: dict) -> bytes:
    """把生成结果序列化为确定性的 UTF-8 字节（用于逐字节一致比较）。"""
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, required=True, help="固定随机种子")
    parser.add_argument("--out", type=Path, required=True, help="输出目录（写入 people.json）")
    args = parser.parse_args(argv)

    personas = load_personas()
    data = generate(args.seed, personas)
    args.out.mkdir(parents=True, exist_ok=True)
    out_path = args.out / "people.json"
    out_path.write_bytes(render(data))
    print(f"wrote {len(data['people'])} people -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
