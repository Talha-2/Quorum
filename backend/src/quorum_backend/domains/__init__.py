"""Domain profiles — specialize the generic pipeline for one application area."""

from quorum_backend.domains.base import DomainProfile
from quorum_backend.domains.registry import (
    DEFAULT_DOMAIN_KEY,
    get_domain,
    is_valid_domain,
    list_domains,
)

__all__ = [
    "DomainProfile",
    "DEFAULT_DOMAIN_KEY",
    "get_domain",
    "is_valid_domain",
    "list_domains",
]
