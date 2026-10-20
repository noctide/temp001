from __future__ import annotations

import json
import random
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from titanloom.access import api
from titanloom.access.api import AccessFilter, Predicate, ScopeRef, Target
from titanloom.access.api.testing import (
    Cond,
    InMemoryAccess,
    NotRegistered,
    RegistrationConflict,
    as_principal,
)
from titanloom.access.tests.conftest import CREATE, READ
from titanloom.kernel.errors import AppError
from titanloom.kernel.reg.errors import ErrorCode

CONTRACTS = Path(__file__).resolve().parents[5] / "packages" / "contracts"


def validator(name: str) -> Any:
    return Draft202012Validator(json.loads((CONTRACTS / f"{name}.schema.json").read_text(encoding="utf-8")))


def test_no_provider_is_loud() -> None:
    with pytest.raises(RuntimeError, match="还没装入"):
        api.whoami()


def test_fixture_restores_provider(access_stub: InMemoryAccess) -> None:
    assert api._provider.provider() is access_stub  # pyright: ignore[reportPrivateUsage]


def test_provider_not_leaked_between_tests() -> None:
    with pytest.raises(RuntimeError):
        api.check(READ)


def test_whoami_from_context_with_secondary_dept(access_stub: InMemoryAccess) -> None:
    access_stub.add_person("X1", "孙兼", "qa", account="acc-X1", extra_depts=["wh"])
    with as_principal("acc-X1"):
        me = api.whoami()
    assert me.person_id == "X1"
    assert {(d.id, d.is_primary) for d in me.departments} == {("qa", True), ("wh", False)}


def test_whoami_without_principal(access_stub: InMemoryAccess) -> None:
    with pytest.raises(AppError) as e:
        api.whoami()
    assert e.value.code == ErrorCode.AUTHENTICATION_REQUIRED


def test_deny_wins_and_no_allow_denies(registered: InMemoryAccess) -> None:
    with as_principal("acc-A0004"):
        d = api.check(READ)
        assert not d.allowed and d.failed_step == "grant" and d.can_request is True
    registered.grant("acc-A0004", READ)
    with as_principal("acc-A0004"):
        assert api.check(READ).allowed
    registered.grant("acc-A0004", READ, Cond.dept("deptId", "asm1"), effect="deny")
    with as_principal("acc-A0004"):
        assert api.check(READ).allowed  # 没有对象时，只有无条件的拒绝才算数
        d = api.check(READ, Target(dept_id="asm1"))
        assert not d.allowed and d.failed_step == "grant"
        assert api.check(READ, Target(dept_id="wh")).allowed


def test_check_for_other_subject_needs_no_diagnostic_right(registered: InMemoryAccess) -> None:
    """R2-3：subject= 是进程内可信调用（facilities 筛收件人用），当前主体没有任何授权也不报错、不要求诊断资格。"""
    registered.grant("acc-A0004", READ)
    with as_principal("acc-A0077"):  # A0077 没有任何授权
        assert api.check(READ, subject="acc-A0004").allowed
        assert not api.check(READ).allowed
    assert "诊断资格" in (api.check.__doc__ or "")  # 口径写在 docstring 里


def test_steps_after_failure_not_checked(registered: InMemoryAccess) -> None:
    d = registered.check(READ, subject="acc-nobody")
    assert d.failed_step == "identity"
    assert [s.result for s in d.steps] == ["fail"] + ["not_checked"] * 5


def test_identity_failures_map_to_error_codes(registered: InMemoryAccess) -> None:
    registered.set_account_status("acc-A0004", "locked")
    with pytest.raises(AppError) as e:
        registered.check(READ, subject="acc-A0004").require()
    assert e.value.code == ErrorCode.ACCOUNT_LOCKED
    registered.set_account_status("acc-A0004", "disabled")
    with pytest.raises(AppError) as e:
        registered.check(READ, subject="acc-A0004").require()
    assert e.value.code == ErrorCode.AUTHENTICATION_REQUIRED
    assert e.value.details == {"failedStep": "identity", "reasonKey": "access.identity.authRequired"}


def test_feature_gate(registered: InMemoryAccess) -> None:
    registered.grant("acc-A0004", CREATE)
    d = registered.check(CREATE, subject="acc-A0004")
    assert d.failed_step == "feature"
    with pytest.raises(AppError) as e:
        d.require()
    assert e.value.code == ErrorCode.FEATURE_NOT_OPEN
    registered.open_feature("attendance.leave")
    assert registered.check(CREATE, subject="acc-A0004").allowed


def test_data_scope_denial_is_access_denied_without_names(registered: InMemoryAccess) -> None:
    registered.grant("acc-A0004", READ, Cond.own_dept("deptId"))
    d = registered.check(READ, Target(dept_id="wh", object_id="r-secret-1"), subject="acc-A0004")
    assert d.failed_step == "data_scope"
    with pytest.raises(AppError) as e:
        d.require()
    assert e.value.code == ErrorCode.ACCESS_DENIED
    assert "r-secret-1" not in json.dumps(e.value.details) and "wh" not in json.dumps(e.value.details)


def test_decision_matches_contract(registered: InMemoryAccess) -> None:
    v: Any = validator("access-decision")
    registered.grant("acc-A0004", READ, Cond.own_dept("deptId"), mask=["idNumber"])
    for t in (Target(dept_id="asm1"), Target(dept_id="wh"), None):
        for who in ("acc-A0004", "acc-B0001", "acc-none"):
            v.validate(registered.check(READ, t, subject=who).to_contract())
    assert registered.check(READ, Target(dept_id="asm1"), subject="acc-A0004").constraints == {
        "maskColumns": ["idNumber"]
    }


def test_dept_subject_includes_descendants(registered: InMemoryAccess) -> None:
    registered.grant("dept:prod", READ)
    assert registered.check(READ, subject="acc-B0001").allowed  # 装配二部在生产中心下
    assert not registered.check(READ, subject="acc-I0002").allowed  # 信息部不在


def test_unregistered_names_raise(registered: InMemoryAccess) -> None:
    with pytest.raises(NotRegistered):
        registered.check("attendance.nope", subject="acc-A0004")
    registered.grant("acc-A0004", READ, Cond.self_("typo"))
    with pytest.raises(NotRegistered):
        registered.filter(READ, "record", subject="acc-A0004")


def test_register_idempotent_and_conflict(registered: InMemoryAccess) -> None:
    from titanloom.access.api import CapabilityDecl

    registered.register("attendance", capabilities=[CapabilityDecl(READ)])
    with pytest.raises(RegistrationConflict):
        registered.register("attendance", capabilities=[CapabilityDecl(READ, impact="high")])
    with pytest.raises(RegistrationConflict):
        registered.register("forms", capabilities=[CapabilityDecl("attendance.other")])


def test_policy_rev_bumps(registered: InMemoryAccess) -> None:
    before = registered.policy_rev
    registered.grant("acc-A0004", READ)
    assert registered.policy_rev == before + 1
    assert registered.check(READ, subject="acc-A0004").policy_rev == before + 1


# ---- filter ----


def test_filter_none_all_any(registered: InMemoryAccess) -> None:
    v: Any = validator("access-filter")

    def f(who: str) -> AccessFilter:
        flt = registered.filter(READ, "record", subject=who)
        v.validate(flt.to_contract())
        return flt

    assert f("acc-A0004").none
    registered.grant("acc-A0004", READ)
    assert f("acc-A0004").all
    registered.grant("acc-B0001", READ, Cond.own_dept("deptId", tree=True))
    assert f("acc-B0001").any == (Predicate("deptId", "in", ("asm2",)),)
    registered.grant("acc-B0001", READ, Cond.self_("ownerId"))
    registered.grant("acc-B0001", READ, Cond.dept("deptId", "prod", tree=True), effect="deny")
    flt = f("acc-B0001")
    assert flt.not_ == (Predicate("deptId", "in", ("asm1", "asm2", "prod", "qa", "wh")),)


def test_filter_expands_dept_tree_and_secondary_dept(registered: InMemoryAccess) -> None:
    registered.add_person("X1", "孙兼", "qa", account="acc-X1", extra_depts=["it"])
    registered.grant("dept:qa", READ, Cond.own_dept("deptId"))
    registered.grant("acc-X1", READ, Cond.own_dept("deptId"))
    flt = registered.filter(READ, "record", subject="acc-X1")
    assert flt.any == (Predicate("deptId", "in", ("it", "qa")),)


def test_filter_mask_columns_is_union_of_used_allows(registered: InMemoryAccess) -> None:
    """R2-2：filter 不能逐行判定，遮挡列取各允许条件之并，宁可多遮，不能露出别的部门的列。"""
    registered.grant("acc-A0004", READ, Cond.own_dept("deptId"), mask=["idNumber"])
    assert registered.filter(READ, "record", subject="acc-A0004").mask_columns == ("idNumber",)
    registered.grant("acc-A0004", READ, Cond.self_("ownerId"))
    assert registered.filter(READ, "record", subject="acc-A0004").mask_columns == ("idNumber",)


def test_filter_masks_what_check_masks_for_other_depts(registered: InMemoryAccess) -> None:
    """R2-2 复现：“全部（遮 idNumber）”+“本部门（不遮）”，对质检部的记录 check 要遮，filter 之前却是 ()。"""
    registered.grant("acc-A0004", READ, Cond.all(), mask=["idNumber"])
    registered.grant("acc-A0004", READ, Cond.own_dept("deptId"))
    assert registered.check(READ, Target(dept_id="qa"), subject="acc-A0004").constraints == {
        "maskColumns": ["idNumber"]
    }
    assert "idNumber" in registered.filter(READ, "record", subject="acc-A0004").mask_columns


def test_filter_mask_ignores_allows_that_match_nothing(registered: InMemoryAccess) -> None:
    registered.grant("acc-A0004", READ, Cond.own_dept("deptId"))
    registered.grant("acc-A0004", READ, Cond.dept("deptId", "qa"), mask=["idNumber"])
    assert registered.filter(READ, "record", subject="acc-A0004").mask_columns == ("idNumber",)
    registered.add_service("svc-x", "服务")  # 没有 person，“本人”条件匹配不上任何行，不该让它的遮挡列算进来
    registered.grant("svc-x", READ, Cond.own_dept("deptId"))
    registered.grant("svc-x", READ, Cond.self_("ownerId"), mask=["idNumber"])
    assert registered.filter(READ, "record", subject="svc-x").mask_columns == ()


def test_filter_all_minus_deny(registered: InMemoryAccess) -> None:
    registered.grant("acc-A0004", READ)
    registered.grant("acc-A0004", READ, Cond.own_dept("deptId"), effect="deny")
    flt = registered.filter(READ, "record", subject="acc-A0004")
    assert flt.all and len(flt.not_) == 1
    assert flt.to_contract()["not"] and "any" not in flt.to_contract()


def test_filter_agrees_with_check(registered: InMemoryAccess) -> None:
    """身份与权限 12 的属性测试：同一主体、同一批样本行，filter 放行的 = 逐条 check 允许的。"""
    rng = random.Random(20261020)  # noqa: S311
    depts = ["asm1", "asm2", "qa", "wh", "hr", "it", "prod"]
    people = {c: f"acc-{c}" for c in ("A0004", "A0077", "B0001", "Q0003", "W0003", "H0012", "I0002")}
    rows = [
        {
            "ownerId": rng.choice(list(people)),
            "deptId": rng.choice(depts[:6]),
            "projectId": rng.choice(["pr1", "pr2", None]),
        }
        for _ in range(60)
    ]
    for _ in range(40):
        registered._grants.clear()  # pyright: ignore[reportPrivateUsage]
        who = rng.choice(list(people.values()))
        for _ in range(rng.randint(0, 4)):
            kind = rng.choice(["self", "own_dept", "dept", "project", "all"])
            cond = {
                "self": Cond.self_("ownerId"),
                "own_dept": Cond.own_dept("deptId", tree=rng.random() < 0.5),
                "dept": Cond.dept("deptId", rng.choice(depts), tree=rng.random() < 0.5),
                "project": Cond.project("projectId", rng.choice(["pr1", "pr2"])),
                "all": Cond.all(),
            }[kind]
            effect = "deny" if rng.random() < 0.3 else "allow"
            mask = ["idNumber"] if effect == "allow" and rng.random() < 0.5 else []
            registered.grant(who, READ, cond, effect=effect, mask=mask)
        flt = registered.filter(READ, "record", subject=who)
        for row in rows:
            t = Target(owner_person_id=str(row["ownerId"]), dept_id=str(row["deptId"]), project_id=row["projectId"])  # pyright: ignore[reportArgumentType]
            decision = registered.check(READ, t, subject=who)
            assert flt.matches(row) == decision.allowed, (who, row)
            if decision.allowed:  # 列表页遮挡的列 ⊇ 逐行 check 要遮的列（R2-2）
                assert set(decision.constraints.get("maskColumns", ())) <= set(flt.mask_columns), (who, row)


# ---- members ----


def test_members_by_dept_with_duplicates_carry_dept(access_stub: InMemoryAccess) -> None:
    ms = api.members(ScopeRef("dept", "asm1"))
    assert [m.name for m in ms] == ["刘畅", "王磊", "张燕", "张燕"]
    assert all(m.dept_name == "装配一部" for m in ms)
    assert len(api.members(ScopeRef("dept", "prod"), include_descendants=True)) == 10


def test_members_on_date(access_stub: InMemoryAccess) -> None:
    access_stub.add_person("X1", "孙新", "qa", start=date(2026, 9, 1), end=date(2026, 9, 30))
    assert "孙新" not in [m.name for m in api.members(ScopeRef("dept", "qa"))]
    assert "孙新" in [m.name for m in api.members(ScopeRef("dept", "qa"), on=date(2026, 9, 15))]


def test_project_members_and_memberships(access_stub: InMemoryAccess) -> None:
    access_stub.add_project("pr1", "试产", {"A0004": "负责人", "B0001": None})
    ms = api.members(ScopeRef("project", "pr1"))
    assert [(m.name, m.dept_name, m.role) for m in ms] == [("刘畅", "装配一部", "负责人"), ("马骁", "装配二部", None)]
    kinds = {(m.kind, m.id) for m in api.memberships("A0004")}
    assert kinds == {("dept", "asm1"), ("project", "pr1")}


def test_demo_has_the_synthetic_cast(access_stub: InMemoryAccess) -> None:
    assert api.memberships("B0233") == (api.memberships("B0233")[0],)
    with as_principal("acc-I0002"):
        assert api.whoami().name == "顾远"
    assert "acc-B0233" not in access_stub._accounts  # pyright: ignore[reportPrivateUsage]
