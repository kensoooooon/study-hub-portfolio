from __future__ import annotations

from dataclasses import dataclass

from vocab_trainer.services.student_availability import has_vocab_progress

_VOCAB_REQUIRED = {"read_textbook", "read_eiken", "listening_textbook", "listening_eiken"}
_ALL_VALID = {"student_home"} | _VOCAB_REQUIRED


@dataclass
class LearningLinkAvailability:
    allowed: bool
    reason: str = ""  # ログ・デバッグ用。UI に直接出す前提にしない。


def check_learning_link_availability(student, destination: str) -> LearningLinkAvailability:
    """学習リンク送信の可否を判定する。

    フォーム choices 制御・フォーム clean・send_notification の3箇所で呼ぶ共通判定。

    Rules (evaluated in order):
        1. destination が空  → allowed=False
        2. student.email なし → allowed=False
        3. destination が未知 → allowed=False
        4. student_home       → allowed=True（email さえあれば許可）
        5. read/listening 系  → has_vocab_progress(student) で決定
    """
    if not destination:
        return LearningLinkAvailability(allowed=False)

    if not student.email:
        # reason に "メールアドレスがありません" を含める（既存テスト log.output チェックのため）
        return LearningLinkAvailability(
            allowed=False,
            reason=(
                f"student {getattr(student, 'id', '?')} にメールアドレスがありません"
                f" (destination={destination})"
            ),
        )

    if destination not in _ALL_VALID:
        return LearningLinkAvailability(
            allowed=False,
            reason=f"不明な destination: {destination!r}",
        )

    if destination == "student_home":
        return LearningLinkAvailability(allowed=True)

    # read/listening 系: vocab 進捗が必要
    if has_vocab_progress(student):
        return LearningLinkAvailability(allowed=True)
    return LearningLinkAvailability(
        allowed=False,
        reason=(
            f"student {getattr(student, 'id', '?')} は語彙学習の進捗がありません"
            f" (destination={destination})"
        ),
    )
