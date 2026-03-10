from itertools import zip_longest
from typing import Any


def group_into_tuples(problems: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any] | None]]:
    """返ってきたproblemのリストを、左右に分割する整形用関数

    Args:
        problems (list[dict[str, Any]]): problem_text, answer_text, metadataなどの表示用データを含む

    Returns:
        list[tuple[dict[str, Any], dict[str, Any] | None]]: 上記を2列に整形している
    
    Notes:
        奇数問題のときはNoneが右側に入る点に注意
    """
    it = iter(problems)
    return list(zip_longest(it, it, fillvalue=None))