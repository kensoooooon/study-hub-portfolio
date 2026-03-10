"""
複数のアプリケーションで利用する共通の抽象ロジックを格納する。

- Django の Model / View に依存しない
    アプリケーション固有のオブジェクトを登場させない
- 純粋関数・アルゴリズム層のみを扱う
"""


from .weighted_sampling import softmax_weighted_permutation

__all__ = [
    "softmax_weighted_permutation",
]