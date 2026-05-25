"""
Domain registry.

Maps a domain key to its :class:`DomainProfile`. The pipeline reads a
project's ``domain`` field and looks the profile up here to decide whether
to use a fixed ontology (and, in later phases, a fixed agent roster).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from quorum_backend.domains.base import DomainProfile
from quorum_backend.domains.engineering_rfc import ENGINEERING_RFC_DOMAIN
from quorum_backend.domains.general import GENERAL_DOMAIN

DEFAULT_DOMAIN_KEY = GENERAL_DOMAIN.key

_REGISTRY: Dict[str, DomainProfile] = {
    d.key: d for d in (GENERAL_DOMAIN, ENGINEERING_RFC_DOMAIN)
}


def get_domain(key: Optional[str]) -> DomainProfile:
    """Return the profile for ``key``.

    A missing or empty key resolves to the default (general) domain.
    An unrecognized key raises :class:`KeyError` so callers can surface a
    clear error rather than silently running the wrong domain.
    """
    if not key:
        return _REGISTRY[DEFAULT_DOMAIN_KEY]
    try:
        return _REGISTRY[key]
    except KeyError:
        raise KeyError(
            f"Unknown domain '{key}'. Known domains: {sorted(_REGISTRY)}"
        ) from None


def is_valid_domain(key: Optional[str]) -> bool:
    """True if ``key`` is empty (defaults) or a registered domain."""
    return not key or key in _REGISTRY


def list_domains() -> List[DomainProfile]:
    """All registered domains, default first."""
    ordered = [_REGISTRY[DEFAULT_DOMAIN_KEY]]
    ordered += [d for k, d in sorted(_REGISTRY.items()) if k != DEFAULT_DOMAIN_KEY]
    return ordered
