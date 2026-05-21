"""Domain profiles — specialize the generic pipeline for one application area."""

from quorum_backend.domains.base import DomainProfile, ReportSectionSpec, RosterMember
from quorum_backend.domains.registry import (
    DEFAULT_DOMAIN_KEY,
    get_domain,
    is_valid_domain,
    list_domains,
)

__all__ = [
    "DomainProfile",
    "ReportSectionSpec",
    "RosterMember",
    "DEFAULT_DOMAIN_KEY",
    "get_domain",
    "is_valid_domain",
    "list_domains",
]
