-- attendance 模块阶段 1 初始迁移：配置定义 + 配置版本
--
-- 子方案 5：每类“定义”+“版本”两张表；草稿 → 校验 → 发布不可变版本 → 按有效期启用。
-- 后端详细设计·考勤 2：schema `attendance`，只有考勤模块的数据库账号能写。
-- 版本表约束：(definition_id, version_no) 唯一；status ∈ draft/published/archived。
-- “同范围同优先级有效期重叠拒绝发布”由 store.config.assert_no_publish_overlap 在应用层校验。

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS attendance;

CREATE TABLE attendance.attendance_type (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    description VARCHAR(1000),
    scope VARCHAR(40) NOT NULL,           -- org / dept / person / employment
    priority INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE attendance.attendance_type IS '考勤配置定义：考勤类型（加班、请假、补签、外出等）';

CREATE TABLE attendance.attendance_type_version (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    definition_id UUID NOT NULL REFERENCES attendance.attendance_type(id) ON DELETE CASCADE,
    version_no INTEGER NOT NULL,
    effective_from TIMESTAMPTZ,            -- NULL = 从一开始
    effective_to TIMESTAMPTZ,              -- NULL = 永久有效
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    content JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ux_attendance_type_version_def_version UNIQUE (definition_id, version_no),
    CONSTRAINT ck_attendance_type_version_status CHECK (status IN ('draft','published','archived'))
);
COMMENT ON TABLE attendance.attendance_type_version IS '考勤配置版本：考勤类型，发布后不可改，按有效期启用';

CREATE TABLE attendance.attendance_shift (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    description VARCHAR(1000),
    scope VARCHAR(40) NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE attendance.attendance_shift IS '考勤配置定义：班次（白/夜等，含正常区间与休息区间）';

CREATE TABLE attendance.attendance_shift_version (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    definition_id UUID NOT NULL REFERENCES attendance.attendance_shift(id) ON DELETE CASCADE,
    version_no INTEGER NOT NULL,
    effective_from TIMESTAMPTZ,
    effective_to TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    content JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ux_attendance_shift_version_def_version UNIQUE (definition_id, version_no),
    CONSTRAINT ck_attendance_shift_version_status CHECK (status IN ('draft','published','archived'))
);
COMMENT ON TABLE attendance.attendance_shift_version IS '考勤配置版本：班次，发布后不可改，按有效期启用';

CREATE TABLE attendance.attendance_rule_set (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    description VARCHAR(1000),
    scope VARCHAR(40) NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE attendance.attendance_rule_set IS '考勤配置定义：规则集（规则条目、优先关系、适用条件）';

CREATE TABLE attendance.attendance_rule_set_version (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    definition_id UUID NOT NULL REFERENCES attendance.attendance_rule_set(id) ON DELETE CASCADE,
    version_no INTEGER NOT NULL,
    effective_from TIMESTAMPTZ,
    effective_to TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    content JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ux_attendance_rule_set_version_def_version UNIQUE (definition_id, version_no),
    CONSTRAINT ck_attendance_rule_set_version_status CHECK (status IN ('draft','published','archived'))
);
COMMENT ON TABLE attendance.attendance_rule_set_version IS '考勤配置版本：规则集，发布后不可改，按有效期启用';

CREATE TABLE attendance.attendance_plan (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    description VARCHAR(1000),
    scope VARCHAR(40) NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE attendance.attendance_plan IS '考勤配置定义：出勤方案（固定出勤 / 按排班，标准时长等）';

CREATE TABLE attendance.attendance_plan_version (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    definition_id UUID NOT NULL REFERENCES attendance.attendance_plan(id) ON DELETE CASCADE,
    version_no INTEGER NOT NULL,
    effective_from TIMESTAMPTZ,
    effective_to TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    content JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ux_attendance_plan_version_def_version UNIQUE (definition_id, version_no),
    CONSTRAINT ck_attendance_plan_version_status CHECK (status IN ('draft','published','archived'))
);
COMMENT ON TABLE attendance.attendance_plan_version IS '考勤配置版本：出勤方案，发布后不可改，按有效期启用';

CREATE TABLE attendance.attendance_checkin_policy (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    description VARCHAR(1000),
    scope VARCHAR(40) NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE attendance.attendance_checkin_policy IS '考勤配置定义：签到策略（签到方式、宽限、补签/补卡上限等）';

CREATE TABLE attendance.attendance_checkin_policy_version (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    definition_id UUID NOT NULL REFERENCES attendance.attendance_checkin_policy(id) ON DELETE CASCADE,
    version_no INTEGER NOT NULL,
    effective_from TIMESTAMPTZ,
    effective_to TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    content JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ux_attendance_checkin_policy_version_def_version UNIQUE (definition_id, version_no),
    CONSTRAINT ck_attendance_checkin_policy_version_status CHECK (status IN ('draft','published','archived'))
);
COMMENT ON TABLE attendance.attendance_checkin_policy_version IS '考勤配置版本：签到策略，发布后不可改，按有效期启用';
