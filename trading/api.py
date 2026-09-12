"""FastAPI control-plane boundary with secure session and CSRF handling."""
from __future__ import annotations

import json
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .auth import AuthenticationService
from .health import HealthChecker
from .http_security import CookiePolicy, CsrfToken, constant_time_token_match
from .kill_switch import KillSwitch

SESSION_COOKIE = CookiePolicy()
CSRF_COOKIE = "tte_csrf"


def _json_error(status: int, code: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code})


async def _credentials(request: Request) -> tuple[str, str]:
    """Accept JSON and browser urlencoded forms without logging request bodies."""
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    body = await request.body()
    if content_type == "application/json":
        try:
            data = json.loads(body or b"{}")
        except (TypeError, ValueError):
            return "", ""
    else:
        try:
            values = parse_qs(body.decode("utf-8"), keep_blank_values=True)
        except UnicodeDecodeError:
            return "", ""
        data = {key: values.get(key, [""])[0] for key in ("user_id", "password")}
    if not isinstance(data, dict):
        return "", ""
    user_id = data.get("user_id", data.get("username", ""))
    password = data.get("password", "")
    return (user_id, password) if isinstance(user_id, str) and isinstance(password, str) else ("", "")


def _csrf_valid(request: Request) -> bool:
    supplied = request.headers.get("x-csrf-token", "")
    cookie = request.cookies.get(CSRF_COOKIE, "")
    return bool(supplied and cookie and constant_time_token_match(cookie, supplied))


def _authenticated_session(request: Request, auth: AuthenticationService):
    return auth.sessions.get(request.cookies.get(SESSION_COOKIE.name, ""))


def create_app(
    auth: AuthenticationService,
    health: HealthChecker | None = None,
    kill_switch: KillSwitch | None = None,
) -> FastAPI:
    app = FastAPI(title="TTE Trading Control Plane", docs_url=None, redoc_url=None)
    checker = health or HealthChecker()
    switch = kill_switch or KillSwitch()

    @app.get("/health")
    def health_endpoint() -> dict[str, object]:
        return checker.liveness().to_dict()

    @app.get("/ready")
    def ready_endpoint() -> JSONResponse:
        report = checker.readiness()
        return JSONResponse(status_code=200 if report.status == "ok" else 503, content=report.to_dict())

    @app.get("/csrf")
    def csrf_endpoint() -> JSONResponse:
        token = CsrfToken.generate().value
        response = JSONResponse({"csrf_token": token})
        response.set_cookie(CSRF_COOKIE, token, secure=True, httponly=False, samesite="lax", path="/")
        return response

    @app.post("/login")
    async def login(request: Request) -> JSONResponse:
        user_id, password = await _credentials(request)
        result = auth.authenticate(user_id, password, request_id=request.headers.get("x-request-id", ""))
        if not result.authenticated or result.session is None:
            status = 429 if result.audit_event and result.audit_event.outcome == "blocked" else 401
            return _json_error(status, "authentication_failed")
        response = JSONResponse({"authenticated": True})
        response.set_cookie(
            SESSION_COOKIE.name,
            result.session.token,
            secure=SESSION_COOKIE.secure,
            httponly=SESSION_COOKIE.httponly,
            samesite=SESSION_COOKIE.samesite,
            path=SESSION_COOKIE.path,
        )
        return response

    @app.post("/logout")
    async def logout(request: Request) -> JSONResponse:
        if not _csrf_valid(request):
            return _json_error(403, "csrf_failed")
        token = request.cookies.get(SESSION_COOKIE.name, "")
        auth.logout(token)
        response = JSONResponse({"authenticated": False})
        response.delete_cookie(SESSION_COOKIE.name, path=SESSION_COOKIE.path)
        return response

    @app.post("/control/step-up")
    async def step_up(request: Request) -> JSONResponse:
        if not _csrf_valid(request):
            return _json_error(403, "csrf_failed")
        token = request.cookies.get(SESSION_COOKIE.name, "")
        user_id, password = await _credentials(request)
        # user_id is ignored deliberately: the authenticated session is the authority.
        del user_id
        result = auth.step_up(token, password, request_id=request.headers.get("x-request-id", ""))
        if not result.authenticated or result.session is None:
            return _json_error(401, "step_up_failed")
        response = JSONResponse({"elevated": True})
        response.set_cookie(
            SESSION_COOKIE.name,
            result.session.token,
            secure=SESSION_COOKIE.secure,
            httponly=SESSION_COOKIE.httponly,
            samesite=SESSION_COOKIE.samesite,
            path=SESSION_COOKIE.path,
        )
        return response

    @app.get("/control/session")
    def session_status(request: Request) -> JSONResponse:
        session = _authenticated_session(request, auth)
        if session is None:
            return _json_error(401, "authentication_required")
        return JSONResponse({"authenticated": True, "user_id": session.user_id, "step_up": session.step_up_active()})

    @app.get("/dashboard/status")
    def dashboard_status(request: Request) -> JSONResponse:
        """Return only non-sensitive dashboard state; never expose credentials."""
        session = _authenticated_session(request, auth)
        if session is None:
            return _json_error(401, "authentication_required")
        kill_state = switch.snapshot()
        return JSONResponse({
            "mode": "PAPER",
            "live_trading": False,
            "kill_switch": kill_state.enabled,
            "kill_switch_reason": kill_state.reason,
            "adapters": [
                {"name": "Spot", "enabled": False, "balance": "—", "trades": 0, "pnl": "—"},
                {"name": "Cross Margin", "enabled": False, "balance": "—", "trades": 0, "pnl": "—"},
                {"name": "Isolated Margin", "enabled": False, "balance": "—", "trades": 0, "pnl": "—"},
                {"name": "USDⓈ-M Futures", "enabled": False, "balance": "—", "trades": 0, "pnl": "—"},
                {"name": "COIN-M Futures", "enabled": False, "balance": "—", "trades": 0, "pnl": "—"},
                {"name": "Alpha", "enabled": False, "balance": "—", "trades": 0, "pnl": "—"},
                {"name": "Stocks", "enabled": False, "balance": "—", "trades": 0, "pnl": "—"},
            ],
            "risk": {"per_trade_pct": 0.5, "daily_loss_pct": 2.0, "max_open": 5, "min_score": 85},
        })

    return app
