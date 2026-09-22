"""web — Flask, browser-facing admin portal. Run under Gunicorn.

Application factory pattern with blueprints, per section 9 of the spec.
Imports domain code from src/licensing only; contains no business logic
itself (see docs/architecture.md layering rules).
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from flask import Flask, g, request, send_from_directory
from sqlalchemy import select

import licensing
from apps.web.extensions import csrf
from licensing.config import get_settings
from licensing.database import get_scoped_session
from licensing.models.enums import MembershipStatus
from licensing.models.organizations import OrganizationMembership

_RESOURCES_DIR = Path(licensing.__file__).resolve().parent / "resources"


def create_app() -> Flask:
    settings = get_settings()
    settings.validate_for_production()

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=settings.flask_secret_key,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=settings.session_cookie_secure,
        PERMANENT_SESSION_LIFETIME=60 * 60 * 8,  # 8 hours absolute cap; idle
        # timeout (Settings.session_idle_timeout_minutes) is enforced
        # separately in apps/web/auth/session.py's login_required.
    )

    logging.basicConfig(level=settings.log_level)

    csrf.init_app(app)

    from apps.web.template_filters import (
        membership_role_label,
        user_organizations_label,
        user_role_label,
    )

    app.jinja_env.filters["membership_role_label"] = membership_role_label
    app.jinja_env.filters["user_role_label"] = user_role_label
    app.jinja_env.filters["user_organizations_label"] = user_organizations_label

    if settings.trusted_proxy_count > 0:
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(  # type: ignore[method-assign]
            app.wsgi_app,
            x_for=settings.trusted_proxy_count,
            x_proto=settings.trusted_proxy_count,
            x_host=settings.trusted_proxy_count,
        )

    @app.before_request
    def _assign_request_id() -> None:
        g.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

    @app.after_request
    def _security_headers(response):  # type: ignore[no-untyped-def]
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers["X-Request-ID"] = g.get("request_id", "")
        return response

    @app.teardown_appcontext
    def _remove_session(exception: BaseException | None) -> None:
        get_scoped_session().remove()

    @app.get("/favicon.ico")
    def favicon():
        return send_from_directory(_RESOURCES_DIR, "icon.png", mimetype="image/png")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    from apps.web.account_links import bp as account_links_bp
    from apps.web.activate import bp as activate_bp
    from apps.web.auth import bp as auth_bp
    from apps.web.auth.session import load_current_user
    from apps.web.dashboard import bp as dashboard_bp
    from apps.web.errors import register_error_handlers
    from apps.web.licenses import bp as licenses_bp
    from apps.web.organizations import bp as organizations_bp
    from apps.web.users import bp as users_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(activate_bp)
    app.register_blueprint(account_links_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(organizations_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(licenses_bp)
    register_error_handlers(app)

    @app.context_processor
    def _inject_nav() -> dict[str, object]:
        user = load_current_user()
        is_vendor = user is not None and user.vendor_role is not None
        nav_memberships: list[OrganizationMembership] = []
        if user is not None and not is_vendor:
            db = get_scoped_session()
            nav_memberships = list(
                db.execute(
                    select(OrganizationMembership).where(
                        OrganizationMembership.user_id == user.id,
                        OrganizationMembership.status == MembershipStatus.ACTIVE,
                    )
                ).scalars()
            )
        return {
            "current_user": user,
            "is_vendor": is_vendor,
            "nav_memberships": nav_memberships,
        }

    @app.get("/")
    def index():
        from flask import redirect, url_for

        user = load_current_user()
        if user is None:
            return redirect(url_for("auth.login"))
        if user.vendor_role is not None:
            return redirect(url_for("dashboard.index"))
        db = get_scoped_session()
        membership = db.execute(
            select(OrganizationMembership).where(
                OrganizationMembership.user_id == user.id,
                OrganizationMembership.status == MembershipStatus.ACTIVE,
            )
        ).scalars().first()
        if membership is not None:
            return redirect(
                url_for("organizations.detail", organization_id=membership.organization_id)
            )
        return redirect(url_for("activate.confirm"))

    return app


app = create_app()
