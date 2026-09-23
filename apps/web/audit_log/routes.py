from __future__ import annotations

from flask import Blueprint, render_template, request

from apps.web.auth.session import load_current_user, login_required, vendor_required
from licensing.database import get_scoped_session
from licensing.services import audit as audit_service

bp = Blueprint("audit", __name__)


@bp.route("/audit", methods=["GET"])
@login_required
@vendor_required()
def index():
    db = get_scoped_session()
    user = load_current_user()
    event_type = request.args.get("event_type") or None
    page = request.args.get("page", default=1, type=int)
    page_result = audit_service.list_events(db, actor=user, event_type=event_type, page=page)
    event_types = audit_service.list_event_types(db, actor=user)
    return render_template(
        "audit/list.html",
        page_result=page_result,
        event_type=event_type or "",
        event_types=event_types,
    )
