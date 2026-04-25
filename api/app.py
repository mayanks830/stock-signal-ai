import os
import hashlib
import secrets
from fastapi import FastAPI, Request, Response, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from api.routes import signals, performance, scanner, reports, search, watchlist, congress, contact
from database import (
    create_user, authenticate_user, get_all_users,
    approve_user, delete_user, get_user_count,
)

FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
_COOKIE_SECRET = os.getenv("COOKIE_SECRET", secrets.token_hex(32))
# If true, new registrations are auto-approved. Otherwise admin must approve.
AUTO_APPROVE = os.getenv("AUTO_APPROVE_USERS", "true").lower() == "true"


def _make_token(username: str) -> str:
    return hashlib.sha256(f"{_COOKIE_SECRET}:{username}".encode()).hexdigest()


def _get_user_from_cookie(request: Request) -> str | None:
    """Return username if valid auth cookie present, else None."""
    token = request.cookies.get("auth")
    username = request.cookies.get("user")
    if token and username and token == _make_token(username):
        return username
    return None


# ── HTML templates ────────────────────────────────────────────────────────────

_STYLE = """
  *{margin:0;padding:0;box-sizing:border-box}
  body{background:#030712;color:#fff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-height:100vh}

  /* Layout */
  .landing{display:flex;flex-direction:column;min-height:100vh}
  @media(min-width:900px){.landing{flex-direction:row}}

  /* Left panel — login form */
  .left-form{display:flex;align-items:center;justify-content:center;padding:2.5rem;min-height:100vh;
    background:radial-gradient(ellipse at 50% 40%,#0f172a 0%,#030712 70%);position:relative}
  @media(min-width:900px){.left-form{width:40%;position:sticky;top:0;height:100vh}}
  .card{background:#111827;border:1px solid #1f2937;border-radius:16px;padding:2.5rem;width:100%;max-width:380px;position:relative;z-index:1}
  .brand{text-align:center;margin-bottom:2rem}
  .brand h1{font-size:1.5rem;font-weight:800;letter-spacing:-.01em}
  .brand .sub{color:#6b7280;font-size:.8rem;margin-top:.3rem}
  .brand .logo{font-size:.7rem;color:#4b5563;margin-bottom:.5rem;text-transform:uppercase;letter-spacing:.1em}
  input{width:100%;background:#030712;border:1px solid #374151;border-radius:8px;padding:.75rem 1rem;color:#fff;font-size:.9rem;outline:none;margin-bottom:.75rem;transition:border-color .2s}
  input:focus{border-color:#3b82f6}
  button,.btn{width:100%;background:#2563eb;border:none;border-radius:8px;padding:.75rem;color:#fff;font-size:.9rem;font-weight:600;cursor:pointer;display:block;text-align:center;text-decoration:none;transition:background .2s}
  button:hover,.btn:hover{background:#3b82f6}
  .err{color:#f87171;font-size:.8rem;margin-bottom:.75rem}
  .ok{color:#4ade80;font-size:.8rem;margin-bottom:.75rem}
  .link{color:#60a5fa;font-size:.85rem;text-align:center;margin-top:1rem;display:block;text-decoration:none}
  .link:hover{color:#93c5fd}

  /* Right panel — marketing */
  .right-mkt{padding:3rem 2.5rem;display:none}
  @media(min-width:900px){.right-mkt{display:flex;flex-direction:column;justify-content:center;width:60%;min-height:100vh;padding:3.5rem 4rem}}

  /* Badge */
  .badge{display:inline-flex;align-items:center;gap:6px;background:rgba(59,130,246,.08);border:1px solid rgba(59,130,246,.15);border-radius:999px;padding:4px 14px;font-size:.7rem;color:#60a5fa;margin-bottom:1.25rem}
  .dot{width:7px;height:7px;border-radius:50%;background:#4ade80;animation:pulse 2s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}

  /* Hero */
  .hero-title{font-size:2.4rem;font-weight:800;letter-spacing:-.03em;margin-bottom:.5rem;line-height:1.1}
  .hero-sub{color:#9ca3af;font-size:.95rem;margin-bottom:2rem;line-height:1.6;max-width:500px}

  /* Features — horizontal row */
  .features{display:grid;grid-template-columns:repeat(3,1fr);gap:.75rem;margin-bottom:2rem}
  .feat{background:#111827;border:1px solid #1f2937;border-radius:10px;padding:1rem;transition:border-color .2s}
  .feat:hover{border-color:rgba(59,130,246,.3)}
  .feat-icon{width:32px;height:32px;border-radius:7px;display:flex;align-items:center;justify-content:center;font-size:.95rem;margin-bottom:.6rem}
  .feat h4{font-size:.8rem;font-weight:600;margin-bottom:.25rem}
  .feat p{font-size:.68rem;color:#6b7280;line-height:1.45}
  .feat-blue .feat-icon{background:rgba(59,130,246,.15)}
  .feat-purple .feat-icon{background:rgba(139,92,246,.15)}
  .feat-green .feat-icon{background:rgba(16,185,129,.15)}

  /* Founder */
  .founder{display:flex;gap:.75rem;align-items:center;margin-bottom:1.5rem;padding:1rem;background:#111827;border:1px solid #1f2937;border-radius:10px}
  .avatar{width:44px;height:44px;border-radius:50%;background:linear-gradient(135deg,#3b82f6,#8b5cf6);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.85rem;flex-shrink:0;box-shadow:0 0 16px rgba(59,130,246,.15)}
  .founder-info{flex:1;min-width:0}
  .founder-info h4{font-size:.8rem;font-weight:700;margin-bottom:1px}
  .founder-info .role{font-size:.65rem;color:#60a5fa;font-weight:600;margin-bottom:.25rem}
  .founder-info .bio{font-size:.68rem;color:#6b7280;line-height:1.45}
  .founder-info .bio b{color:#d1d5db;font-weight:600}
  .linkedin-link{display:inline-flex;align-items:center;gap:3px;font-size:.65rem;color:#60a5fa;text-decoration:none;margin-left:.75rem;flex-shrink:0}
  .linkedin-link:hover{color:#93c5fd}

  /* Certs */
  .certs{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:1.5rem}
  .cert{font-size:.58rem;color:#6b7280;background:rgba(31,41,55,.6);border:1px solid rgba(55,65,81,.4);border-radius:999px;padding:2px 8px}

  /* Tech stack */
  .tech{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:1.5rem}
  .pill{font-size:.62rem;font-weight:500;padding:2px 9px;border-radius:999px;border:1px solid}
  .pill-ai{background:rgba(139,92,246,.1);border-color:rgba(139,92,246,.25);color:#c4b5fd}
  .pill-be{background:rgba(59,130,246,.08);border-color:rgba(59,130,246,.2);color:#93c5fd}
  .pill-fe{background:rgba(16,185,129,.08);border-color:rgba(16,185,129,.2);color:#6ee7b7}
  .pill-data{background:rgba(245,158,11,.08);border-color:rgba(245,158,11,.2);color:#fcd34d}
  .pill-infra{background:rgba(239,68,68,.08);border-color:rgba(239,68,68,.2);color:#fca5a5}

  .disclaimer{font-size:.62rem;color:#374151;line-height:1.5}
"""


def _marketing_panel() -> str:
    return """<div class="right-mkt">
  <div class="badge"><span class="dot"></span> Live &amp; Scanning Markets Daily</div>
  <h2 class="hero-title">Trading Signals</h2>
  <p class="hero-sub">Institutional-grade market intelligence powered by AI &mdash; built for investors who want an edge.</p>

  <div class="features">
    <div class="feat feat-blue">
      <div class="feat-icon">&#x1f916;</div>
      <h4>AI-Powered Signals</h4>
      <p>Claude AI scans S&amp;P 500 stocks daily &mdash; analyzing price action, volume, news catalysts, technicals, and insider activity to find high-conviction buy signals.</p>
    </div>
    <div class="feat feat-purple">
      <div class="feat-icon">&#x1f3db;</div>
      <h4>Congress Tracking</h4>
      <p>Real-time monitoring of congressional stock trades with $500k+ alerts. See what senators are buying and selling before the market reacts.</p>
    </div>
    <div class="feat feat-green">
      <div class="feat-icon">&#x1f4ca;</div>
      <h4>Full Transparency</h4>
      <p>Every signal tracked with entry price, target, and stop loss. Real-time P&amp;L, win/loss outcomes, and complete historical performance.</p>
    </div>
  </div>

  <div class="founder">
    <div class="avatar">MS</div>
    <div class="founder-info">
      <h4>Mayank Sethi</h4>
      <div class="role">Founder &amp; CEO</div>
      <div class="bio"><b>17+ yrs</b> in fintech. Former <b>PIMCO</b>, now <b>Group1001</b>. <b>$2T+</b> AUM managed.</div>
    </div>
    <a class="linkedin-link" href="https://www.linkedin.com/in/mayank-sethi-b8682613/" target="_blank" rel="noopener noreferrer">
      <svg width="12" height="12" fill="currentColor" viewBox="0 0 24 24"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.064 2.064 0 11-.001-4.128 2.064 2.064 0 01.001 4.128zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
    </a>
  </div>

  <div class="certs">
    <span class="cert">Oracle Cloud GenAI</span>
    <span class="cert">SnowPro Advanced</span>
    <span class="cert">AWS Database</span>
    <span class="cert">AWS Solutions Architect</span>
    <span class="cert">ITIL v3</span>
  </div>

  <div class="tech">
    <span class="pill pill-ai">Claude AI</span>
    <span class="pill pill-be">Python</span>
    <span class="pill pill-be">FastAPI</span>
    <span class="pill pill-fe">React</span>
    <span class="pill pill-fe">TypeScript</span>
    <span class="pill pill-data">Yahoo Finance</span>
    <span class="pill pill-data">Capitol Trades</span>
    <span class="pill pill-infra">Railway</span>
  </div>

  <p class="disclaimer">This tool is for informational purposes only. Not financial advice. Always do your own research before making investment decisions.<br>&copy; 2026 Trading Signals. All rights reserved.</p>
</div>"""


def _auth_page(title: str, subtitle: str, form_html: str, page_title: str = "Trading Signals") -> str:
    marketing = _marketing_panel()
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{page_title}</title><style>{_STYLE}</style></head><body>
<div class="landing">
<div class="left-form"><div class="card">
<div class="brand"><p class="logo">Trading Signals</p><h1>{title}</h1><p class="sub">{subtitle}</p></div>
{form_html}
</div></div>
{marketing}
</div></body></html>"""


def _login_page(error: str = "", msg: str = "") -> str:
    err_html = f'<div class="err">{error}</div>' if error else ''
    msg_html = f'<div class="ok">{msg}</div>' if msg else ''
    form = f"""{err_html}{msg_html}
<form method="POST" action="/login">
<input type="text" name="username" placeholder="Username" required>
<input type="password" name="password" placeholder="Password" required>
<button type="submit">Log In</button></form>
<a class="link" href="/register">Don&#39;t have an account? Register</a>"""
    return _auth_page("Welcome back", "Log in to continue", form, "Trading Signals — Login")


def _register_page(error: str = "") -> str:
    err_html = f'<div class="err">{error}</div>' if error else ''
    form = f"""{err_html}
<form method="POST" action="/register">
<input type="text" name="username" placeholder="Username" required minlength="3" maxlength="30">
<input type="password" name="password" placeholder="Password" required minlength="4">
<button type="submit">Create Account</button></form>
<a class="link" href="/login">Already have an account? Log in</a>"""
    return _auth_page("Create Account", "Register to get started", form, "Trading Signals — Register")


def _pending_page() -> str:
    content = """<div style="text-align:center;padding:1rem 0">
<div style="font-size:2rem;margin-bottom:1rem">&#x23f3;</div>
<p style="color:#9ca3af;font-size:.85rem;line-height:1.6;margin-bottom:1.5rem">Your account has been created but needs admin approval before you can access the dashboard.</p>
<a class="link" href="/login">Try logging in again</a></div>"""
    return _auth_page("Account Pending", "Almost there!", content, "Trading Signals — Pending")


def create_app() -> FastAPI:
    app = FastAPI(title="Trading Signal API", version="1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Auth middleware ───────────────────────────────────────────────────
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        path = request.url.path
        # Always allow auth routes and static assets
        public = ("/login", "/register", "/logout")
        if path in public or path.startswith("/assets"):
            return await call_next(request)

        user = _get_user_from_cookie(request)
        if not user:
            if path.startswith("/api/"):
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)
            return HTMLResponse(_login_page())

        # Admin routes
        if path.startswith("/admin") and user != "admin":
            return JSONResponse({"detail": "Forbidden"}, status_code=403)

        return await call_next(request)

    # ── Auth routes ───────────────────────────────────────────────────────
    @app.get("/login")
    async def login_page(request: Request):
        msg = request.query_params.get("msg", "")
        return HTMLResponse(_login_page(msg=msg))

    @app.post("/login")
    async def login(username: str = Form(...), password: str = Form(...)):
        user = authenticate_user(username, password)
        if not user:
            return HTMLResponse(_login_page(error="Invalid username or password"), status_code=401)
        if not user["is_approved"]:
            return HTMLResponse(_pending_page(), status_code=403)
        response = RedirectResponse(url="/", status_code=303)
        max_age = 60 * 60  # 60 minutes
        response.set_cookie("auth", _make_token(username),
                            httponly=True, samesite="lax", max_age=max_age)
        response.set_cookie("user", username,
                            httponly=True, samesite="lax", max_age=max_age)
        return response

    @app.get("/register")
    async def register_page():
        return HTMLResponse(_register_page())

    @app.post("/register")
    async def register(username: str = Form(...), password: str = Form(...)):
        if len(username.strip()) < 3:
            return HTMLResponse(_register_page("Username must be at least 3 characters"), status_code=400)
        if len(password) < 4:
            return HTMLResponse(_register_page("Password must be at least 4 characters"), status_code=400)
        # First user is always auto-approved (that's you, the admin)
        is_first = get_user_count() == 0
        result = create_user(username, password, auto_approve=is_first or AUTO_APPROVE)
        if not result:
            return HTMLResponse(_register_page("Username already taken"), status_code=400)
        if is_first or AUTO_APPROVE:
            return RedirectResponse(url="/login?msg=Account+created!+You+can+log+in+now.", status_code=303)
        return HTMLResponse(_pending_page())

    @app.get("/logout")
    async def logout():
        response = RedirectResponse(url="/login", status_code=303)
        response.delete_cookie("auth")
        response.delete_cookie("user")
        return response

    @app.get("/api/me")
    async def me(request: Request):
        user = _get_user_from_cookie(request)
        return {"username": user}

    # ── Admin: manage users ───────────────────────────────────────────────
    @app.get("/api/admin/users")
    async def list_users():
        return get_all_users()

    @app.post("/api/admin/approve/{username}")
    async def approve(username: str):
        if approve_user(username):
            return {"approved": username}
        return JSONResponse({"detail": "User not found"}, status_code=404)

    @app.delete("/api/admin/users/{username}")
    async def remove_user(username: str):
        if delete_user(username):
            return {"deleted": username}
        return JSONResponse({"detail": "User not found"}, status_code=404)

    # ── API routes ────────────────────────────────────────────────────────
    app.include_router(signals.router, prefix="/api")
    app.include_router(performance.router, prefix="/api")
    app.include_router(scanner.router, prefix="/api")
    app.include_router(reports.router, prefix="/api")
    app.include_router(search.router, prefix="/api")
    app.include_router(watchlist.router, prefix="/api")
    app.include_router(congress.router, prefix="/api")
    app.include_router(contact.router, prefix="/api")

    # Serve static assets (JS, CSS) at /assets
    if os.path.exists(FRONTEND_DIST):
        assets_dir = os.path.join(FRONTEND_DIST, "assets")
        if os.path.exists(assets_dir):
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        # SPA fallback — serve index.html for all non-API routes
        @app.get("/{full_path:path}")
        async def serve_spa(request: Request, full_path: str):
            index = os.path.join(FRONTEND_DIST, "index.html")
            if os.path.exists(index):
                return FileResponse(index)
            return {"detail": "Frontend not built"}

    return app


app = create_app()
