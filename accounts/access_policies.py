"""
accountsに定義されたモデルのうち、Organizationに関連するアクセス制御を集約
"""

from __future__ import annotations
import logging
from typing import Optional, Iterable


from django.http import Http404


logger = logging.getLogger(__name__)


def _raise_404(log_dict: Optional[dict] = None) -> None:
    if log_dict:
        msg = "permission denied (masked as 404)"
        logger.warning(msg, extra={"ctx": log_dict})
    raise Http404


def _require_perms_or_404(user, perms: Iterable[str], *, log_dict: Optional[dict] = None) -> None:
    if not user.is_authenticated:
        _raise_404(log_dict)

    for p in perms:
        if not user.has_perm(p):
            ctx = dict(log_dict or {})
            ctx.update({"missing_perm": p})
            _raise_404(ctx)


def require_can_assign_organization_administrator(user, *, log_dict: Optional[dict] = None) -> None:
    _require_perms_or_404(user, ["accounts.assign_organization_administrator"], log_dict=log_dict)


def require_can_add_organization(user, *, log_dict: Optional[dict] = None) -> None:
    _require_perms_or_404(user, ["accounts.add_organization"], log_dict=log_dict)
    

def require_can_view_organization(user, *, log_dict: Optional[dict] = None) -> None:
    _require_perms_or_404(user, ["accounts.view_organization"], log_dict=log_dict)

def require_can_invite_organization_administrator(user, *, log_dict: Optional[dict] = None) -> None:
    _require_perms_or_404(user, ["accounts.invite_organization_administrator"], log_dict=log_dict)
