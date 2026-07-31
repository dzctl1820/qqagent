import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db

BOT_START_TIME = time.time()


def register_admin_routes(app: FastAPI):
    static_dir = Path(__file__).parent / "static"

    def _check_auth(request: Request):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            token = request.query_params.get("token", "")
        config = db.load_config()
        expected = config.get("admin", {}).get("token", "admin123")
        if token != expected:
            raise HTTPException(status_code=401, detail="未授权")

    @app.get("/admin", response_class=HTMLResponse)
    @app.get("/admin/", response_class=HTMLResponse)
    async def admin_page():
        index = static_dir / "index.html"
        if index.exists():
            return HTMLResponse(index.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>Admin UI not found</h1>", status_code=404)

    # ===== 通用配置 API =====

    @app.get("/api/config")
    async def get_config(request: Request):
        _check_auth(request)
        config = db.load_config()
        safe = _safe_config(config)
        return JSONResponse(safe)

    @app.put("/api/config/{section}")
    async def update_config(section: str, request: Request):
        _check_auth(request)
        body = await request.json()
        updated = db.update_section(section, body)
        return {"ok": True, "section": section, "data": updated}

    # ===== AI 配置 =====

    @app.get("/api/ai")
    async def get_ai(request: Request):
        _check_auth(request)
        return db.get_section("ai")

    @app.put("/api/ai")
    async def update_ai(request: Request):
        _check_auth(request)
        body = await request.json()
        updated = db.update_section("ai", body)
        return {"ok": True, "data": _safe_ai(updated)}

    # ===== 群管理配置 =====

    @app.get("/api/group")
    async def get_group(request: Request):
        _check_auth(request)
        return db.get_section("group")

    @app.put("/api/group")
    async def update_group(request: Request):
        _check_auth(request)
        body = await request.json()
        updated = db.update_section("group", body)
        return {"ok": True, "data": updated}

    # ===== 定时任务 =====

    @app.get("/api/scheduler/jobs")
    async def get_jobs(request: Request):
        _check_auth(request)
        section = db.get_section("scheduler")
        return {"jobs": section.get("jobs", [])}

    @app.post("/api/scheduler/jobs")
    async def add_job(request: Request):
        _check_auth(request)
        body = await request.json()
        config = db.load_config()
        jobs = config.setdefault("scheduler", {}).setdefault("jobs", [])
        jobs.append(body)
        db.save_config(config)
        _reload_scheduler()
        return {"ok": True, "jobs": jobs}

    @app.put("/api/scheduler/jobs/{job_id}")
    async def update_job(job_id: str, request: Request):
        _check_auth(request)
        body = await request.json()
        config = db.load_config()
        jobs = config.get("scheduler", {}).get("jobs", [])
        found = False
        for i, j in enumerate(jobs):
            if str(j.get("id", "")) == job_id:
                jobs[i] = body
                found = True
                break
        if not found:
            raise HTTPException(status_code=404, detail="任务不存在")
        db.save_config(config)
        _reload_scheduler()
        return {"ok": True, "jobs": jobs}

    @app.delete("/api/scheduler/jobs/{job_id}")
    async def delete_job(job_id: str, request: Request):
        _check_auth(request)
        config = db.load_config()
        jobs = config.get("scheduler", {}).get("jobs", [])
        config["scheduler"]["jobs"] = [j for j in jobs if str(j.get("id", "")) != job_id]
        db.save_config(config)
        _reload_scheduler()
        return {"ok": True, "jobs": config["scheduler"]["jobs"]}

    # ===== Bot 状态 =====

    @app.get("/api/status")
    async def get_status(request: Request):
        _check_auth(request)
        uptime = int(time.time() - BOT_START_TIME)
        h, rem = divmod(uptime, 3600)
        m, s = divmod(rem, 60)
        from nonebot import get_bot
        bot_connected = False
        try:
            get_bot()
            bot_connected = True
        except Exception:
            pass
        return {
            "status": "running",
            "uptime": f"{h}h {m}m {s}s",
            "uptime_seconds": uptime,
            "bot_connected": bot_connected,
        }

    # ===== 日志 =====

    @app.get("/api/logs")
    async def get_logs_api(request: Request):
        _check_auth(request)
        from .log_store import get_logs
        limit = int(request.query_params.get("limit", 50))
        level = request.query_params.get("level", "")
        source = request.query_params.get("source", "")
        logs = get_logs(limit=limit, level=level, source=source)
        return {"logs": logs}

    @app.delete("/api/logs")
    async def clear_logs_api(request: Request):
        _check_auth(request)
        from .log_store import clear_logs
        clear_logs()
        return {"ok": True}

    # ===== 关键词管理 =====

    @app.post("/api/group/keywords")
    async def add_keyword(request: Request):
        _check_auth(request)
        body = await request.json()
        keyword = body.get("keyword", "").strip()
        reply = body.get("reply", "").strip()
        if not keyword or not reply:
            raise HTTPException(status_code=400, detail="关键词和回复不能为空")
        config = db.load_config()
        keywords = config.setdefault("group", {}).setdefault("keywords", {})
        keywords[keyword] = reply
        db.save_config(config)
        return {"ok": True, "keywords": keywords}

    @app.delete("/api/group/keywords/{keyword}")
    async def delete_keyword(keyword: str, request: Request):
        _check_auth(request)
        config = db.load_config()
        keywords = config.get("group", {}).get("keywords", {})
        if keyword in keywords:
            del keywords[keyword]
            db.save_config(config)
        return {"ok": True, "keywords": keywords}

    if static_dir.exists():
        app.mount("/admin/static", StaticFiles(directory=str(static_dir)), name="admin-static")


def _reload_scheduler():
    try:
        from plugins.scheduler.plugin import reload_jobs
        reload_jobs()
    except Exception:
        pass


def _safe_config(config: dict[str, Any]) -> dict[str, Any]:
    safe = {}
    for k, v in config.items():
        if k == "ai":
            safe[k] = _safe_ai(v)
        else:
            safe[k] = v
    return safe


def _safe_ai(ai_config: dict[str, Any]) -> dict[str, Any]:
    safe = ai_config.copy()
    if safe.get("api_key"):
        key = safe["api_key"]
        safe["api_key"] = key[:8] + "***" if len(key) > 8 else "***"
        safe["api_key_set"] = True
    else:
        safe["api_key_set"] = False
    return safe
