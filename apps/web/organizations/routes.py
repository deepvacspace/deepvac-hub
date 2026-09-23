from __future__ import annotations

import uuid

from flask import Blueprint, flash, redirect, render_template, request, url_for

from apps.web.audit import log_event
from apps.web.auth.session import load_current_user, login_required, vendor_required
from apps.web.organizations.forms import AddMembershipForm, OrganizationForm
from licensing.database import get_scoped_session
from licensing.exceptions import ConflictError, LicensingError, NotFoundError
from licensing.models.enums import MembershipRole, OrganizationStatus
from licensing.services import alarm_rules as alarm_rules_service
from licensing.services import audit as audit_service
from licensing.services import auth as auth_service
from licensing.services import chambers as chambers_service
from licensing.services import licenses as licenses_service
from licensing.services import organizations as organizations_service
from licensing.services import test_profiles as test_profiles_service

bp = Blueprint("organizations", __name__, url_prefix="/organizations")


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
        status = OrganizationStatus(status_raw) if status_raw else None
    except ValueError:
        status = None
        status_raw = None
    page = request.args.get("page", default=1, type=int)
    page_result = organizations_service.list_organizations(
        db, actor=user, q=q, status=status, page=page
    )
    current_licenses = licenses_service.get_current_licenses_for_organizations(
        db, actor=user, organization_ids=[org.id for org in page_result.items]
    )
    can_write = auth_service.can_vendor_write(user)
    return render_template(
        "organizations/list.html",
        page_result=page_result,
        q=q or "",
        status=status_raw or "",
        current_licenses=current_licenses,
        can_write=can_write,
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
@vendor_required(write=True)
def new():
    db = get_scoped_session()
    user = load_current_user()
    form = OrganizationForm()
    if form.validate_on_submit():
        try:
            org = organizations_service.create_organization(
                db, actor=user, name=form.name.data.strip(), slug=form.slug.data.strip().lower()
            )
            log_event(
                db,
                event_type="organization_created",
                actor_user_id=user.id,
                organization_id=org.id,
                target_type="organization",
                target_id=str(org.id),
                metadata={"organization_slug": org.slug},
            )
            db.commit()
            flash(f"Organization {org.name!r} created.", "success")
            return redirect(url_for("organizations.detail", organization_id=org.id))
        except LicensingError as exc:
            db.rollback()
            flash(str(exc), "error")
    return render_template("organizations/form.html", form=form, mode="new")


@bp.route("/<uuid:organization_id>", methods=["GET"])
@login_required
def detail(organization_id: uuid.UUID):
    db = get_scoped_session()
    user = load_current_user()
    org = organizations_service.get_organization(db, actor=user, organization_id=organization_id)
    memberships = organizations_service.list_memberships(
        db, actor=user, organization_id=organization_id
    )
    org_licenses = licenses_service.list_licenses_for_org(
        db, actor=user, organization_id=organization_id
    )
    chambers = chambers_service.list_for_organization(db, organization_id)
    alarm_rules = alarm_rules_service.list_for_organization(db, organization_id)
    test_profiles = test_profiles_service.list_for_organization(db, organization_id)
    can_write = auth_service.can_vendor_write(user)
    can_admin = auth_service.can_org_admin(db, user, organization_id)
    edit_form = OrganizationForm(name=org.name, slug=org.slug)
    membership_form = AddMembershipForm()
    return render_template(
        "organizations/detail.html",
        org=org,
        memberships=memberships,
        org_licenses=org_licenses,
        chambers=chambers,
        alarm_rules=alarm_rules,
        test_profiles=test_profiles,
        can_write=can_write,
        can_admin=can_admin,
        edit_form=edit_form,
        membership_form=membership_form,
        membership_roles=MembershipRole,
    )


@bp.route("/<uuid:organization_id>/notifications", methods=["GET"])
@login_required
def notifications(organization_id: uuid.UUID):
    db = get_scoped_session()
    user = load_current_user()
    org = organizations_service.get_organization(db, actor=user, organization_id=organization_id)
    page = request.args.get("page", default=1, type=int)
    page_result = audit_service.list_chamber_events_for_organization(
        db, actor=user, organization_id=organization_id, page=page
    )
    return render_template(
        "organizations/notifications.html", org=org, page_result=page_result
    )


@bp.route("/<uuid:organization_id>/edit", methods=["POST"])
@login_required
@vendor_required(write=True)
def edit(organization_id: uuid.UUID):
    db = get_scoped_session()
    user = load_current_user()
    form = OrganizationForm()
    if form.validate_on_submit():
        try:
            organizations_service.update_organization(
                db,
                actor=user,
                organization_id=organization_id,
                name=form.name.data.strip(),
                slug=form.slug.data.strip().lower(),
            )
            log_event(
                db,
                event_type="organization_updated",
                actor_user_id=user.id,
                organization_id=organization_id,
                target_type="organization",
                target_id=str(organization_id),
            )
            db.commit()
            flash("Organization updated.", "success")
        except LicensingError as exc:
            db.rollback()
            flash(str(exc), "error")
    else:
        _flash_form_errors(form)
    return redirect(url_for("organizations.detail", organization_id=organization_id))


def _set_status(  # type: ignore[no-untyped-def]
    organization_id: uuid.UUID, *, status: OrganizationStatus, event_type: str, message: str
):
    db = get_scoped_session()
    user = load_current_user()
    try:
        organizations_service.set_organization_status(
            db, actor=user, organization_id=organization_id, status=status
        )
        log_event(
            db,
            event_type=event_type,
            actor_user_id=user.id,
            organization_id=organization_id,
            target_type="organization",
            target_id=str(organization_id),
        )
        db.commit()
        flash(message, "success")
    except LicensingError as exc:
        db.rollback()
        flash(str(exc), "error")
    return redirect(url_for("organizations.detail", organization_id=organization_id))


@bp.route("/<uuid:organization_id>/disable", methods=["POST"])
@login_required
@vendor_required(write=True)
def disable(organization_id: uuid.UUID):
    return _set_status(
        organization_id,
        status=OrganizationStatus.DISABLED,
        event_type="organization_disabled",
        message="Organization disabled.",
    )


@bp.route("/<uuid:organization_id>/reactivate", methods=["POST"])
@login_required
@vendor_required(write=True)
def reactivate(organization_id: uuid.UUID):
    return _set_status(
        organization_id,
        status=OrganizationStatus.ACTIVE,
        event_type="organization_reactivated",
        message="Organization reactivated.",
    )


@bp.route("/<uuid:organization_id>/memberships", methods=["POST"])
@login_required
def add_membership(organization_id: uuid.UUID):
    db = get_scoped_session()
    user = load_current_user()
    form = AddMembershipForm()
    if form.validate_on_submit():
        try:
            membership = organizations_service.add_membership(
                db,
                actor=user,
                organization_id=organization_id,
                user_email=form.email.data.strip(),
                role=MembershipRole(form.role.data),
            )
            log_event(
                db,
                event_type="membership_added",
                actor_user_id=user.id,
                organization_id=organization_id,
                target_type="organization_membership",
                target_id=str(membership.id),
                metadata={"role": membership.role.value},
            )
            db.commit()
            flash("Member added.", "success")
        except (ConflictError, NotFoundError) as exc:
            db.rollback()
            flash(str(exc), "error")
    else:
        _flash_form_errors(form)
    return redirect(url_for("organizations.detail", organization_id=organization_id))


@bp.route("/<uuid:organization_id>/memberships/<uuid:membership_id>/remove", methods=["POST"])
@login_required
def remove_membership(organization_id: uuid.UUID, membership_id: uuid.UUID):
    db = get_scoped_session()
    user = load_current_user()
    try:
        organizations_service.remove_membership(
            db, actor=user, organization_id=organization_id, membership_id=membership_id
        )
        log_event(
            db,
            event_type="membership_removed",
            actor_user_id=user.id,
            organization_id=organization_id,
            target_type="organization_membership",
            target_id=str(membership_id),
        )
        db.commit()
        flash("Member removed.", "success")
    except (ConflictError, NotFoundError) as exc:
        db.rollback()
        flash(str(exc), "error")
    return redirect(url_for("organizations.detail", organization_id=organization_id))


@bp.route("/<uuid:organization_id>/memberships/<uuid:membership_id>/role", methods=["POST"])
@login_required
def change_membership_role(organization_id: uuid.UUID, membership_id: uuid.UUID):
    db = get_scoped_session()
    user = load_current_user()
    role_raw = request.form.get("role", "")
    try:
        role = MembershipRole(role_raw)
        organizations_service.change_membership_role(
            db,
            actor=user,
            organization_id=organization_id,
            membership_id=membership_id,
            role=role,
        )
        log_event(
            db,
            event_type="membership_role_changed",
            actor_user_id=user.id,
            organization_id=organization_id,
            target_type="organization_membership",
            target_id=str(membership_id),
            metadata={"role": role.value},
        )
        db.commit()
        flash("Member role updated.", "success")
    except (ConflictError, NotFoundError, ValueError) as exc:
        db.rollback()
        flash(str(exc) or "Invalid role.", "error")
    return redirect(url_for("organizations.detail", organization_id=organization_id))
