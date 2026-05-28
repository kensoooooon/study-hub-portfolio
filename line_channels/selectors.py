"""
可視範囲のクエリセットを規定する

    現在は、権限持ち=全体を見られる構成
"""
from line_channels.models import LineChannel
from accounts.models import Organization


def visible_line_channels_qs(user):
    """あるユーザーに対し、最大可視範囲のラインチャンネルクエリセットを返す

    Args:
        user: 対象ユーザー

    Returns:
        (QuerySet): 最大可視範囲のラインチャンネル群
    """
    if not user.is_authenticated:
        return LineChannel.objects.none()
    if user.groups.filter(name="ops_line_channels").exists() and user.has_perm("line_channels.manage_line_channels"):
        return LineChannel.objects.all()
    else:
        return LineChannel.objects.none()


def manageable_organizations_for_line_channels(user):
    """LINEチャンネル作成対象にできる組織群を返す。

    Note:
        この selector は、呼び出し元で
        require_can_add_line_channels_or_404() による
        ops_line_channels グループ + add_linechannel 権限チェックを
        済ませている前提で使う。

        selector 内では group 名を直接見ず、
        対象スコープを permission ベースで返す。
    """
    if not user.is_authenticated:
        return Organization.objects.none()
    if user.has_perm("line_channels.add_linechannel"):
        return Organization.objects.all()
    return Organization.objects.none()
