"""
line_channelで定義されたモデルへのアクセス権限を一括管理するモジュール

- ユーザーは個別にpermissionを付与できる
- グループに所属した場合は、そのグループのpermissionを利用できる
- ユーザーをグループに追加する場合は、
    g = Group.objects.get(name="ops_line_channels")
    user.groups.add(group)
    で追加する
"""
from __future__ import annotations
from typing import Iterable, Optional
import logging

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
# ---------------------------
# LINE Channels（Ops: 全組織OK）
# ---------------------------

def require_can_manage_line_channels_or_404(user, *, log_dict: Optional[dict] = None) -> None:
    _require_perms_or_404(user, ["line_channels.manage_line_channels"], log_dict=log_dict)


def require_can_view_line_channel_secret_metadata_or_404(user, *, log_dict: Optional[dict] = None) -> None:
    _require_perms_or_404(user, ["line_channels.view_line_channel_secret_metadata"], log_dict=log_dict)
