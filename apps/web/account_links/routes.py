"""Browser-side account-link flow: the signed-in user approves linking their
local desktop profile to their hub identity."""

from __future__ import annotations

from flask import Blueprint, render_template, request

from apps.web.auth.session import load_current_user, login_required
from licensing.audit import record_event
from licensing.database import get_scoped_session
from licensing.exceptions import LicensingError
from licensing.models.organizations import Organization
from licensing.services import account_links as account_links_service

bp = Blueprint("account_links", __name__)


def _normalize_code(raw: str) -> str:
    return raw.strip().upper()


@bp.route("/link-account", methods=["GET"])
@login_required
def confirm():
    db = get_scoped_session()
    user = load_current_user()
    user_code = _normalize_code(request.args.get("user_code", ""))

    link_request = account_links_service.find_by_user_code(db, user_code) if user_code else None
    error = None
    organization = None
    status = None

    if link_request is None:
        error = "Invalid or missing link code. Check the code shown in the desktop app."
    else:
        status = account_links_service.effective_status(link_request).value
        if status != "pending":
            error = f"This link request is {status} and can no longer be approved."
        else:
            organization = db.get(Organization, link_request.requested_organization_id)

    return render_template(
        "account_links/confirm.html",
        user=user,
        user_code=user_code,
        link=link_request,
        organization=organization,
        error=error,
        status=status,
        approved=False,
    )


@bp.route("/link-account", methods=["POST"])
@login_required
def approve():
    db = get_scoped_session()
    user = load_current_user()
    user_code = _normalize_code(request.form.get("user_code", ""))

    link_request = account_links_service.find_by_user_code(db, user_code) if user_code else None
    error = None
    approved = False

    if link_request is None:
        error = "Invalid link code."
    else:
        try:
            account_links_service.approve_link(db, link_id=link_request.id, approving_user=user)
            record_event(
                db,
                event_type="account_link_approved",
                actor_user_id=user.id,
                organization_id=link_request.requested_organization_id,
                target_type="account_link_request",
                target_id=str(link_request.id),
                request_id=request.headers.get("X-Request-ID"),
                source_ip=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
            )
            db.commit()
            approved = True
        except LicensingError as exc:
            db.rollback()
            error = str(exc)

    return render_template(
        "account_links/confirm.html",
        user=user,
        user_code=user_code,
        link=link_request,
        organization=None,
        error=error,
        status=None,
        approved=approved,
    )
