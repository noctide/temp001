"""后台程序入口（后端详细设计·总图 4、命令与任务）：领取任务、定时、消息发件箱。

启动：uv run python -m titanloom.runner
M1 由 execution 模块实现领取循环；这里只保留入口。
"""

import sys


def main() -> int:
    print("titanloom runner：还没有任务通道（M1 execution 落成）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
