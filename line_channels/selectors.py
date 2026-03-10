"""
可視範囲のクエリセットを規定する

    現在は、権限持ち=全体を見られる構成
"""
from line_channels.models import LineChannel


def visible_line_channels_qs(user):
    return LineChannel.objects.all()
