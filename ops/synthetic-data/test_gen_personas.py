"""Titanloom 合成数据人设表 —— 单元测试。

覆盖 M0-06 人设表验收用例：
- 同一种子两次生成逐字节相同
- 各部门在职人数与规格一致
- 规格里有名有姓的人一个不少、字段一致
- 只有两个「王磊」重名
- 严述没有平台账户
- 张燕两份档案分别是在职和离职

运行：
    python -m unittest ops/synthetic-data/test_gen_personas.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import gen_personas  # noqa: E402

SEED = 20261016
EXPECTED_HEADCOUNTS = {
    "装配一部": 58,
    "装配二部": 54,
    "质检部": 31,
    "仓储物流": 28,
    "人事行政": 11,
    "信息部": 8,
}


def _expected_roles(spec: dict) -> list[str]:
    """规格里的具体角色 +（在职且有账户时的）基础「员工」角色。"""
    if spec["status"] == "active" and spec["account"] == "active":
        return [gen_personas.BASE_ROLE] + list(spec.get("platform_roles") or [])
    return []


class PersonasTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.personas = gen_personas.load_personas()
        cls.data = gen_personas.generate(SEED, cls.personas)
        cls.people = cls.data["people"]
        cls.by_id = {p["id"]: p for p in cls.people}

    def test_same_seed_byte_identical(self):
        a = gen_personas.render(gen_personas.generate(SEED, self.personas))
        b = gen_personas.render(gen_personas.generate(SEED, self.personas))
        self.assertEqual(a, b)

    def test_department_headcounts(self):
        active = [p for p in self.people if p["status"] == "active"]
        counts = Counter(p["department"] for p in active)
        self.assertEqual(counts, Counter(EXPECTED_HEADCOUNTS))

    def test_totals(self):
        active = [p for p in self.people if p["status"] == "active"]
        resigned = [p for p in self.people if p["status"] == "resigned"]
        self.assertEqual(len(self.people), 196)
        self.assertEqual(len(active), 190)
        self.assertEqual(len(resigned), 6)
        no_account = [p for p in active if p["account"] == "none"]
        self.assertEqual(len(no_account), 1)

    def test_named_people_present(self):
        for spec in self.personas["people"]:
            if spec.get("id"):
                self.assertIn(spec["id"], self.by_id, spec["name"])
                person = self.by_id[spec["id"]]
            else:
                matches = [
                    p
                    for p in self.people
                    if p["name"] == spec["name"]
                    and p["department"] == spec["department"]
                ]
                self.assertEqual(len(matches), 1, spec["name"])
                person = matches[0]

            self.assertEqual(person["name"], spec["name"])
            self.assertEqual(person["department"], spec["department"])
            self.assertEqual(person["position"], spec["position"])
            self.assertEqual(person["status"], spec["status"])
            self.assertEqual(person["account"], spec["account"])
            self.assertEqual(person["platform_roles"], _expected_roles(spec))
            self.assertEqual(person["note"], spec["note"])

            if spec.get("hire_date"):
                self.assertEqual(person["hire_date"], spec["hire_date"])
            else:
                self.assertTrue(person["hire_date"])
            self.assertEqual(person.get("resign_date"), spec.get("resign_date"))

    def test_only_two_wanglei(self):
        # 王磊是唯一"重名"（两个不同的人同名），恰好两个、分部不同。
        wanglei = [p for p in self.people if p["name"] == "王磊"]
        self.assertEqual(len(wanglei), 2)
        self.assertEqual({p["id"] for p in wanglei}, {"A0077", "W0015"})
        # 其余名字除「张燕」外都不重复；张燕是同一人离职再入职的两份档案（非重名）。
        duplicates = {
            name: count
            for name, count in Counter(p["name"] for p in self.people).items()
            if count > 1
        }
        self.assertEqual(duplicates, {"王磊": 2, "张燕": 2})

    def test_yanshu_no_account(self):
        yanshu = [p for p in self.people if p["name"] == "严述"]
        self.assertEqual(len(yanshu), 1)
        self.assertEqual(yanshu[0]["status"], "active")
        self.assertEqual(yanshu[0]["account"], "none")
        self.assertEqual(yanshu[0]["platform_roles"], [])

    def test_zhangyan_two_archives(self):
        zhangyan = [p for p in self.people if p["name"] == "张燕"]
        self.assertEqual(len(zhangyan), 2)
        statuses = {p["id"]: p["status"] for p in zhangyan}
        self.assertEqual(statuses, {"A0102": "resigned", "A0219": "active"})
        self.assertEqual(self.by_id["A0102"]["resign_date"], "2025-11-30")

    def test_cli_writes_people_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            result = subprocess.run(
                [
                    sys.executable,
                    str(HERE / "gen_personas.py"),
                    "--seed",
                    str(SEED),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            out_file = out / "people.json"
            self.assertTrue(out_file.exists())
            data = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertEqual(len(data["people"]), 196)
            self.assertEqual(data["seed"], SEED)


if __name__ == "__main__":
    unittest.main()
