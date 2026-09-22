from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import SelectField, StringField
from wtforms.validators import DataRequired, Email, Length, Regexp

_SLUG_MESSAGE = "Lowercase letters, numbers, and hyphens only (e.g. 'acme-labs')."


class OrganizationForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=200)])
    slug = StringField(
        "Slug",
        validators=[
            DataRequired(),
            Length(max=200),
            Regexp(r"^[a-z0-9]+(-[a-z0-9]+)*$", message=_SLUG_MESSAGE),
        ],
    )


class AddMembershipForm(FlaskForm):
    email = StringField("Member email", validators=[DataRequired(), Email()])
    role = SelectField(
        "Role",
        choices=[
            ("organization_admin", "Administrator"),
            ("organization_member", "Member"),
        ],
    )
