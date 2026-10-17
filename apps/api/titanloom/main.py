"""主程序入口（后端详细设计·总图 1：一个主程序 + 一个后台程序）。

启动：uv run uvicorn titanloom.main:app --reload
各模块的路由由各自 api 层提供，在这里统一挂载（M1 起逐个加入）。
"""

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Titanloom", version="0.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json")

    @app.get("/api/health", tags=["platform"])
    def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok"}

    return app


app = create_app()
