from __future__ import annotations

import uuid

from flask import Blueprint, flash, redirect, render_template, request, url_for

from apps.web.audit import log_event
from apps.web.auth.session import load_current_user, login_required, vendor_required
from apps.web.users.forms import SetPasswordForm, UserForm
from licensing.database import get_scoped_session
from licensing.exceptions import LicensingError
from licensing.models.enums import UserStatus, VendorRole
from licensing.services import auth as auth_service
from licensing.services import users as users_service

bp = Blueprint("users", __name__, url_prefix="/users")


def _flash_form_errors(form) -> None:  # type: ignore[no-untyped-def]
    for field_errors in form.errors.values():
        for error in field_errors:
            flash(error, "error")


@bp.route("", methods=["GET"])
@login_required
@vendor_required()
def list_view():
    db = get_scoped_session()
    user = load_current_user()
    q = request.args.get("q") or None
    status_raw = request.args.get("status") or None
    try:
        status = UserStatus(status_raw) if status_raw else None
    except ValueError:
        status = None
        status_raw = None
    page = request.args.get("page", default=1, type=int)
    page_result = users_service.list_users(db, actor=user, q=q, status=status, page=page)
    return render_template(
        "users/list.html", page_result=page_result, q=q or "", status=status_raw or ""
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
@vendor_required(write=True)
def new():
    db = get_scoped_session()
    user = load_current_user()
    form = UserForm()
    if form.validate_on_submit():
        try:
            new_user = users_service.create_user(
                db,
                actor=user,
                email=form.email.data.strip(),
                display_name=form.display_name.data.strip(),
                password=form.password.data,
            )
            log_event(
                db,
                event_type="user_created",
                actor_user_id=user.id,
                target_type="user",
                target_id=str(new_user.id),
            )
            db.commit()
            flash(f"User {new_user.email!r} created.", "success")
            return redirect(url_for("users.detail", user_id=new_user.id))
        except LicensingError as exc:
            db.rollback()
            flash(str(exc), "error")
    return render_template("users/form.html", form=form)


@bp.route("/<uuid:user_id>", methods=["GET"])
@login_required
@vendor_required()
def detail(user_id: uuid.UUID):
    db = get_scoped_session()
    user = load_current_user()
    target = users_service.get_user(db, actor=user, user_id=user_id)
    memberships = users_service.list_memberships_for_user(db, actor=user, user_id=user_id)
    can_write = auth_service.can_vendor_write(user)
    password_form = SetPasswordForm()
    return render_template(
        "users/detail.html",
        target=target,
        memberships=memberships,
        can_write=can_write,
        password_form=password_form,
        vendor_roles=VendorRole,
    )


def _set_status(  # type: ignore[no-untyped-def]
    user_id: uuid.UUID, *, status: UserStatus, event_type: str, message: str
):
    db = get_scoped_session()
    user = load_current_user()
    try:
        users_service.set_user_status(db, actor=user, user_id=user_id, status=status)
        log_event(
            db,
            event_type=event_type,
            actor_user_id=user.id,
            target_type="user",
            target_id=str(user_id),
        )
        db.commit()
        flash(message, "success")
    except LicensingError as exc:
        db.rollback()
        flash(str(exc), "error")
    return redirect(url_for("users.detail", user_id=user_id))


@bp.route("/<uuid:user_id>/disable", methods=["POST"])
@login_required
@vendor_required(write=True)
def disable(user_id: uuid.UUID):
    return _set_status(
        user_id, status=UserStatus.DISABLED, event_type="user_disabled", message="User disabled."
    )


@bp.route("/<uuid:user_id>/reactivate", methods=["POST"])
@login_required
@vendor_required(write=True)
def reactivate(user_id: uuid.UUID):
    return _set_status(
        user_id,
        status=UserStatus.ACTIVE,
        event_type="user_reactivated",
        message="User reactivated.",
    )


@bp.route("/<uuid:user_id>/password", methods=["POST"])
@login_required
@vendor_required(write=True)
def set_password(user_id: uuid.UUID):
    db = get_scoped_session()
    user = load_current_user()
    form = SetPasswordForm()
    if form.validate_on_submit():
        try:
            users_service.set_user_password(
                db, actor=user, user_id=user_id, new_password=form.new_password.data
            )
            log_event(
                db,
                event_type="user_password_reset_by_admin",
                actor_user_id=user.id,
                target_type="user",
                target_id=str(user_id),
            )
            db.commit()
            flash("Password updated.", "success")
        except LicensingError as exc:
            db.rollback()
            flash(str(exc), "error")
    else:
        _flash_form_errors(form)
    return redirect(url_for("users.detail", user_id=user_id))


@bp.route("/<uuid:user_id>/vendor-role", methods=["POST"])
@login_required
@vendor_required(write=True)
def set_vendor_role(user_id: uuid.UUID):
    db = get_scoped_session()
    user = load_current_user()
    raw = request.form.get("vendor_role", "")
    try:
        vendor_role = VendorRole(raw) if raw else None
        users_service.set_vendor_role(db, actor=user, user_id=user_id, vendor_role=vendor_role)
        log_event(
            db,
            event_type="user_vendor_role_changed",
            actor_user_id=user.id,
            target_type="user",
            target_id=str(user_id),
            metadata={"role": raw or "none"},
        )
        db.commit()
        flash("Vendor role updated.", "success")
    except (LicensingError, ValueError) as exc:
        db.rollback()
        flash(str(exc) or "Invalid vendor role.", "error")
    return redirect(url_for("users.detail", user_id=user_id))
