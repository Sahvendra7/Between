"""The Between web app. `uvicorn between.web.app:app` builds it from the environment on first use."""
from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from between import db
from between.config import Settings, load
from between.money import fmt_usd
from between.web import present

HERE = Path(__file__).parent
CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
       "form-action 'self' https://www.sandbox.paypal.com; frame-ancestors 'none'; base-uri 'none'")


def create_app(settings: Settings, engine: sa.Engine, ai=None, pp=None) -> FastAPI:
    app = FastAPI(title="Between", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings, app.state.engine, app.state.ai, app.state.pp = settings, engine, ai, pp
    templates = Jinja2Templates(directory=str(HERE / "templates"))
    templates.env.globals.update(settings=settings, category_name=present.category_name, describe=present.describe_rule,
                                 status_words=present.STATUS_WORDS, reason_words=present.REASON_WORDS)
    templates.env.filters["usd"] = fmt_usd
    app.state.templates = templates
    app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", CSP)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    from starlette.exceptions import HTTPException as StarletteHTTPException

    titles = {400: "That didn't work", 403: "Not available to you", 404: "Not found", 409: "This changed",
              502: "PayPal didn't answer", 503: "Not available right now"}

    @app.exception_handler(StarletteHTTPException)
    async def friendly_errors(request: Request, exc: StarletteHTTPException):
        if request.url.path.startswith("/webhooks/"):
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        detail = exc.detail if isinstance(exc.detail, str) else "Something went wrong."
        return templates.TemplateResponse(request, "error.html", {"title": titles.get(exc.status_code, "Error"), "detail": detail},
                                          status_code=exc.status_code)

    from between.web import routes_agreement, routes_family, routes_rules
    for module in (routes_family, routes_agreement, routes_rules):
        app.include_router(module.router)
    for name in ("routes_expenses", "routes_pay", "routes_webhooks", "routes_record", "routes_demo", "routes_calendar"):
        try:  # later tasks add these routers
            module = __import__(f"between.web.{name}", fromlist=["router"])
        except ModuleNotFoundError:
            continue
        app.include_router(module.router)
    return app


def build_from_env() -> FastAPI:
    settings = load()
    engine = db.make_engine(settings.database_url)
    db.init_db(engine)
    ai = pp = None
    if settings.gemini_api_key:  # takes precedence: the owner's Anthropic account has no credits
        from between.gemini import Gemini
        ai = Gemini(settings.gemini_api_key)
    elif settings.anthropic_api_key:
        import anthropic
        ai = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    if settings.paypal_client_id and settings.paypal_client_secret:
        from between.payments import PayPal
        pp = PayPal(settings.paypal_client_id, settings.paypal_client_secret)
    app = create_app(settings, engine, ai=ai, pp=pp)
    try:
        from between import demo
        if hasattr(demo, "seed"):
            with engine.begin() as conn:
                demo.seed(conn, settings)  # idempotent: creates the base demo family only if missing
    except Exception as exc:  # the demo seed must never stop the app starting
        import logging
        logging.getLogger("between").warning("demo seed skipped: %s", type(exc).__name__)
    return app


_app = None


def __getattr__(name):
    global _app
    if name == "app":
        if _app is None:
            _app = build_from_env()
        return _app
    raise AttributeError(name)
