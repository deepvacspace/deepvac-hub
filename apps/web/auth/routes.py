from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from apps.web.audit import log_event
from apps.web.auth.forms import ChangePasswordForm, LoginForm, RegistrationForm
from apps.web.auth.session import load_current_user, login_required, login_user, logout_user
from licensing.database import get_scoped_session
from licensing.exceptions import LicensingError
from licensing.models.enums import UserStatus
from licensing.models.users import User
from licensing.security.passwords import verify_password
from licensing.services import registration as registration_service
from licensing.services import users as users_service

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    error = None
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        password = form.password.data
        db = get_scoped_session()
        user = db.query(User).filter(User.normalized_email == email).one_or_none()
        # Deliberately generic message for both "no such user" and "wrong
        # password" -- see docs/threat-model.md, never distinguish the two.
        if user is None or not verify_password(password, user.password_hash):
            error = "Incorrect email or password."
        elif user.status != UserStatus.ACTIVE:
            error = "This account is disabled."
        else:
            login_user(user.id)
            next_url = request.args.get("next") or url_for("activate.confirm")
            return redirect(next_url)
    return render_template("auth/login.html", form=form, error=error)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if load_current_user() is not None:
        return redirect(url_for("index"))
    db = get_scoped_session()
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            org, user = registration_service.register_organization_and_owner(
                db,
                organization_name=form.organization_name.data.strip(),
                email=form.email.data.strip(),
                display_name=form.display_name.data.strip(),
                password=form.password.data,
            )
            log_event(
                db,
                event_type="organization_self_registered",
                actor_user_id=user.id,
                organization_id=org.id,
                target_type="organization",
                target_id=str(org.id),
                metadata={"organization_slug": org.slug},
            )
            db.commit()
            login_user(user.id)
            flash(f"Welcome, {user.display_name}! {org.name} is ready.", "success")
            return redirect(url_for("organizations.detail", organization_id=org.id))
        except LicensingError as exc:
            db.rollback()
            flash(str(exc), "error")
    return render_template("auth/register.html", form=form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@bp.route("/account/password", methods=["GET", "POST"])
@login_required
def account_password():
    db = get_scoped_session()
    user = load_current_user()
    form = ChangePasswordForm()
    if form.validate_on_submit():
        try:
            users_service.change_own_password(
                db,
                user=user,
                current_password=form.current_password.data,
                new_password=form.new_password.data,
            )
            db.commit()
            flash("Password updated.", "success")
            return redirect(url_for("auth.account_password"))
        except LicensingError as exc:
            db.rollback()
            flash(str(exc), "error")
    return render_template("auth/account_password.html", form=form)
