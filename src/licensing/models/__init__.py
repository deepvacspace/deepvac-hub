"""Import every model module so licensing.database.Base.metadata is complete
for Alembic autogenerate and for tests that call Base.metadata.create_all().
"""

from licensing.models.account_links import AccountLinkRequest
from licensing.models.activation import ActivationRequest, RefreshChallenge
from licensing.models.alarm_rules import AlarmRule
from licensing.models.audit import AuditEvent
from licensing.models.certificates import IssuedLicenseCertificate, SigningKey
from licensing.models.chambers import Chamber
from licensing.models.devices import DeviceActivation
from licensing.models.licenses import OrganizationLicense
from licensing.models.organizations import Organization, OrganizationMembership
from licensing.models.products import Edition, EditionFeature, Feature, Product
from licensing.models.test_profiles import TestProfile, TestProfileStep
from licensing.models.users import User

__all__ = [
    "AccountLinkRequest",
    "ActivationRequest",
    "RefreshChallenge",
    "AlarmRule",
    "AuditEvent",
    "IssuedLicenseCertificate",
    "SigningKey",
    "Chamber",
    "DeviceActivation",
    "OrganizationLicense",
    "Organization",
    "OrganizationMembership",
    "Edition",
    "EditionFeature",
    "Feature",
    "Product",
    "TestProfile",
    "TestProfileStep",
    "User",
]
