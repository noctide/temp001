# Titanloom 建库脚本（Windows，PowerShell 7）。后端详细设计·总图 6：每个模块一个 schema，迁移用 owner 账号。
#
# 做什么（可重复运行，已有的跳过）：
#   1. 建数据库 titanloom（如不存在）
#   2. 建 owner 账号 titanloom_owner（拥有各 schema，tl.py db upgrade 用它）和运行账号 titanloom_app（主程序、后台程序用）
#   3. 每个有表的模块一个 schema（owner 持有），再建 search schema；运行账号只拿到读写权限，不能建表
# 密码：owner 与运行账号的密码由你在提示里输入，不进仓库、不写文件；postgres 超级用户密码同理。
# 之后把下面两行放进你本机的环境变量（或不入库的 .env.local）：
#   TITANLOOM_DB_URL=postgresql+psycopg://titanloom_app:<密码>@localhost:5432/titanloom
#   TITANLOOM_DB_OWNER_URL=postgresql+psycopg://titanloom_owner:<密码>@localhost:5432/titanloom
#
# 用法：pwsh ops/db/create.ps1 [-DbHost localhost] [-Port 5432] [-SuperUser postgres] [-Database titanloom] [-WhatIf]
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$DbHost = 'localhost',
    [int]$Port = 5432,
    [string]$SuperUser = 'postgres',
    [string]$Database = 'titanloom',
    [string]$PsqlPath = ''
)
$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..' '..')

function Find-Psql {
    if ($PsqlPath) { return $PsqlPath }
    $cmd = Get-Command psql -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $hit = Get-ChildItem 'C:\Program Files\PostgreSQL\*\bin\psql.exe' -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -First 1
    if ($hit) { return $hit.FullName }
    throw '找不到 psql。装好 PostgreSQL 16/17，或用 -PsqlPath 指定 psql.exe 的完整路径。'
}

function Read-Plain([string]$prompt) {
    $s = Read-Host -Prompt $prompt -AsSecureString
    [System.Net.NetworkCredential]::new('', $s).Password
}

function Quote-Literal([string]$v) { "'" + $v.Replace("'", "''") + "'" }

$psql = Find-Psql
$modules = @(& uv run --project $root python (Join-Path $root 'ops/tools/tl.py') db modules) | Where-Object { $_ }
$schemas = @($modules) + @('search')
Write-Host "模块 schema：$($schemas -join ', ')"

if (-not $PSCmdlet.ShouldProcess("$DbHost`:$Port/$Database", '建库、账号与 schema')) { return }

$env:PGPASSWORD = Read-Plain "$SuperUser 的密码"
$ownerPw = Read-Plain 'titanloom_owner 的新密码（迁移用）'
$appPw = Read-Plain 'titanloom_app 的新密码（程序运行用）'

function Invoke-Sql([string]$db, [string]$sql) {
    $sql | & $psql -h $DbHost -p $Port -U $SuperUser -d $db -v ON_ERROR_STOP=1 -q -X
    if ($LASTEXITCODE -ne 0) { throw "psql 执行失败（退出码 $LASTEXITCODE）" }
}

try {
    $roles = @"
DO `$`$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'titanloom_owner') THEN
    CREATE ROLE titanloom_owner LOGIN PASSWORD $(Quote-Literal $ownerPw);
  ELSE
    ALTER ROLE titanloom_owner PASSWORD $(Quote-Literal $ownerPw);
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'titanloom_app') THEN
    CREATE ROLE titanloom_app LOGIN PASSWORD $(Quote-Literal $appPw);
  ELSE
    ALTER ROLE titanloom_app PASSWORD $(Quote-Literal $appPw);
  END IF;
END `$`$;
"@
    Invoke-Sql 'postgres' $roles

    $exists = ("SELECT 1 FROM pg_database WHERE datname = $(Quote-Literal $Database)" |
        & $psql -h $DbHost -p $Port -U $SuperUser -d postgres -tA -X).Trim()
    if ($exists -ne '1') {
        Invoke-Sql 'postgres' "CREATE DATABASE `"$Database`" OWNER titanloom_owner ENCODING 'UTF8';"
        Write-Host "已建数据库 $Database"
    }

    $sql = New-Object System.Text.StringBuilder
    [void]$sql.AppendLine("REVOKE ALL ON DATABASE `"$Database`" FROM PUBLIC;")
    [void]$sql.AppendLine("GRANT CONNECT ON DATABASE `"$Database`" TO titanloom_app;")
    foreach ($s in $schemas) {
        [void]$sql.AppendLine("CREATE SCHEMA IF NOT EXISTS `"$s`" AUTHORIZATION titanloom_owner;")
        [void]$sql.AppendLine("GRANT USAGE ON SCHEMA `"$s`" TO titanloom_app;")
        [void]$sql.AppendLine("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA `"$s`" TO titanloom_app;")
        [void]$sql.AppendLine("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA `"$s`" TO titanloom_app;")
        [void]$sql.AppendLine("ALTER DEFAULT PRIVILEGES FOR ROLE titanloom_owner IN SCHEMA `"$s`" GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO titanloom_app;")
        [void]$sql.AppendLine("ALTER DEFAULT PRIVILEGES FOR ROLE titanloom_owner IN SCHEMA `"$s`" GRANT USAGE, SELECT ON SEQUENCES TO titanloom_app;")
    }
    Invoke-Sql $Database $sql.ToString()
    Write-Host '完成。下一步：设好 TITANLOOM_DB_URL / TITANLOOM_DB_OWNER_URL，运行 uv run python ops/tools/tl.py db upgrade'
}
finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    $ownerPw = $appPw = $null
}
