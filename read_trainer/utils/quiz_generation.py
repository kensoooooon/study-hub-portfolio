from __future__ import annotations

"""
問題作成に必要なユーティリティ関数群

# 問題と設計の思想
モデル構造より、長文と問題は1:M構成
出題は4問1セットとなっており、バッチIDで管理を行う

# 各種関数群
- generate_and_save_passage_with_questions
    長文の新規作成と問題の新規作成。バッチIDは常に新規であるため1

- append_questions_to_existing_passage
    与えられた既存の長文に対し、新たな問題を作成。バッチIDはすでに紐づいたIDよりも1だけ大きいものを設定

- select_latest_existing_passage_and_batch
    ランダムに長文を選び、その中での最新のバッチIDが付与された問題を通す
"""
from read_trainer.models import ReadingPassage, ReadingQuestion
from processors.reading_passage_generator import ReadingPassageGenerator, EikenPassageGenerator

# 型アノテーション用
from accounts.models import Student
from vocab_trainer.models import WordMeaningContext


import logging
logger = logging.getLogger(__name__)

valid_choices = {"A", "B", "C", "D"}


def generate_and_save_passage_with_questions(student: Student, vocab_contexts: list[WordMeaningContext]) -> tuple[ReadingPassage, int]:
    """
    学習済み語彙情報から長文と問題（questions）を新規生成し、DB に保存する。

    Args:
        student: 長文の作成対象となる生徒。
        vocab_contexts: 出題に反映したい語彙コンテキストのリスト。

    Returns:
        passage: 作成された ReadingPassage インスタンス。
        batch_id: 作成された問題群に付与されたバッチID（常に 1）。

    Raises:
        ValueError: ChatGPT 応答の JSON に questions が含まれないなど、
            問題生成に失敗した場合。
        Exception: ReadingPassageGenerator 内部で起きた予期しない例外。
    """
    logger.info(
        "Start generate_and_save_passage_with_questions (student_id=%s, vocab_contexts=%d)",
        student.id, len(vocab_contexts),
    )
    batch_id = 1  # 新規なのでバッチIDは常に1
    generator = ReadingPassageGenerator(student=student)
    result = generator.generate_passage_with_questions(vocab_contexts)
    if not result or "questions" not in result:
        raise ValueError("AIからの問題生成に失敗しました。")
    passage = ReadingPassage.objects.create(
        created_by=student,
        title=result.get("title", ""),
        content=result["passage"],
        japanese_translation=result.get("translation", "")
    )
    try:
        q = None
        for q in result["questions"]:
            if not isinstance(q.get("options"), list) or len(q["options"]) != 4:
                raise ValueError(f"[Error] optionsの形式が不正: {q.get('options')}")
            raw_answer = q.get("answer", "").strip().upper()

            if raw_answer not in valid_choices:
                logger.error("無効な正答値: raw_answer: %s, → スキップされました", raw_answer)
                raise ValueError(f"[Error] 無効な正答値: '{raw_answer}' → 問題生成に失敗しました")
            ReadingQuestion.objects.create(
                passage=passage,
                question_text=q["question"],
                option_a=q["options"][0],
                option_b=q["options"][1],
                option_c=q["options"][2],
                option_d=q["options"][3],
                correct_option=raw_answer,
                explanation=q["explanation"],
                batch_id=batch_id,
            )
    except Exception:
        logger.exception("問題の登録に失敗: (ListeningQuestion: %s)", q)
        raise  # 上位に通知してエラーページ遷移へ

    return passage, batch_id


def append_questions_to_existing_passage(student: Student, passage: ReadingPassage, vocab_contexts: list[WordMeaningContext]) -> tuple[ReadingPassage, int]:
    """
    既存の長文 (passage) に新しい問題を追加し、新しい batch_id を自動採番して保存する。

    Args:
        student: 出題対象の生徒。
        passage: 問題を追加したい既存の長文。
        vocab_contexts: 出題に反映したい語彙コンテキストのリスト。

    Returns:
        passage: 問題追加後も同じ ReadingPassage インスタンス。
        next_batch: 新たに割り当てられたバッチID。

    Raises:
        ValueError: ChatGPT 応答から問題リストが取得できなかった場合。
        Exception: ReadingPassageGenerator 内部で起きた予期しない例外。
    """
    logger.info(
        "Start append_questions_to_existing_passage (student_id=%s, passage_id=%s, vocab_contexts=%d)",
        student.id, passage.id, len(vocab_contexts),
    )
    generator = ReadingPassageGenerator(student)
    questions = generator.generate_questions_for_existing_passage(passage, vocab_contexts)
    if not questions:
        raise ValueError("AIからの問題生成に失敗しました。")
    existing_batches = passage.questions.values_list('batch_id', flat=True)
    next_batch = max(existing_batches or [0]) + 1

    try:
        q = None
        for q in questions:
            if not isinstance(q.get("options"), list) or len(q["options"]) != 4:
                raise ValueError(f"[Error] optionsの形式が不正: {q.get('options')}")
            
            raw_answer = q.get("answer", "").strip().upper()

            if raw_answer not in valid_choices:
                logger.error("無効な正答値: 'raw_answer: %s' → スキップされました", raw_answer)
                raise ValueError(f"[Error] 無効な正答値: '{raw_answer}' → 問題生成に失敗しました")
            ReadingQuestion.objects.create(
                passage=passage,
                question_text=q["question"],
                option_a=q["options"][0],
                option_b=q["options"][1],
                option_c=q["options"][2],
                option_d=q["options"][3],
                correct_option=raw_answer,
                explanation=q["explanation"],
                batch_id=next_batch,
            )
    except Exception:
        logger.exception(f"問題の登録に失敗: {q}")
        raise  # 上位に通知してエラーページ遷移へ

    return passage, next_batch


def select_latest_existing_passage_and_batch(student: Student) -> tuple[ReadingPassage | None, int | None]:
    """
    指定された生徒の既存長文の中からランダムに1つ選び、
    その長文に紐づく最新（最大）の batch_id を取得する。

    Args:
        student: 対象となる生徒。

    Returns:
        (passage, latest_batch_id):
            passage: 見つかった ReadingPassage。存在しない場合は None。
            latest_batch_id: その passage に紐づく最新 batch_id。存在しない場合は None。
    """
    passage = ReadingPassage.objects.filter(created_by=student).order_by('?').first()
    if passage is None:
        return None, None
    latest_batch = passage.questions.order_by('-batch_id').first().batch_id
    return passage, latest_batch


def get_latest_batch_for_passage(passage: ReadingPassage) -> int | None:
    """
    指定された長文に対して、最新の batch_id を取得する。

    Args:
        passage: 対象の長文。

    Returns:
        最新の batch_id。問題が1つも存在しない場合は None。
    """
    latest = passage.questions.order_by('-batch_id').first()
    return latest.batch_id if latest else None


def generate_eiken_passage_with_questions(student: Student, level: str, vocab_contexts: list[WordMeaningContext] | None = None,) -> tuple[ReadingPassage, int]:
    """
    英検用の新規長文と問題を生成し、保存する。

    Args:
        student: 対象となる生徒。
        level: 英検の級（"5", "4", "3", "pre2", "2" など）。
        vocab_contexts: 問題や本文に反映したい語彙コンテキスト。

    Returns:
        passage: 作成された ReadingPassage（source_type="eiken"）。
        batch_id: 生成された問題に付与されたバッチID（常に 1）。

    Raises:
        ValueError: ChatGPT 応答の JSON に questions が含まれない場合など。
    """
    generator = EikenPassageGenerator(student, level, vocab_contexts)
    result = generator.generate_passage_with_questions()
    if not result or "questions" not in result:
        raise ValueError("AIからの問題生成に失敗しました。")
    passage = ReadingPassage.objects.create(
        created_by=student,
        title=result["title"],
        content=result["passage"],
        japanese_translation=result["translation"],
        source_type="eiken",
        eiken_level=level,
    )
    batch_id = 1
    try:
        q = None
        for q in result["questions"]:
            if not isinstance(q.get("options"), list) or len(q["options"]) != 4:
                raise ValueError(f"[Error] optionsの形式が不正: {q.get('options')}")
            
            raw_answer = q.get("answer", "").strip().upper()

            if raw_answer not in valid_choices:
                logger.error("無効な正答値: 'raw_answer: %s' → スキップされました", raw_answer)
                raise ValueError(f"[Error] 無効な正答値: '{raw_answer}' → 問題生成に失敗しました")
            ReadingQuestion.objects.create(
                passage=passage,
                question_text=q["question"],
                option_a=q["options"][0],
                option_b=q["options"][1],
                option_c=q["options"][2],
                option_d=q["options"][3],
                correct_option=raw_answer,
                explanation=q["explanation"],
                batch_id=batch_id,
            )
    except Exception:
        logger.exception("問題の登録に失敗: (ReadingQuestion: %s)", q)
        raise  # 上位に通知してエラーページ遷移へ
    return passage, batch_id



def append_questions_to_existing_eiken_passage(student: Student, passage: ReadingPassage, level: str, vocab_contexts: list[WordMeaningContext] | None = None,) -> tuple[ReadingPassage, int]:
    """
    既存の英検用長文に対して、新しい問題を追加する。

    Args:
        student: 対象となる生徒。
        passage: 英検用の既存長文（source_type="eiken"）。
        level: 英検の級。
        vocab_contexts: 問題に反映したい語彙コンテキスト。

    Returns:
        passage: 変わらず同じ ReadingPassage インスタンス。
        next_batch: 追加された問題に付与された batch_id。

    Raises:
        ValueError: ChatGPT 応答から questions が取得できなかった場合。
    """
    generator = EikenPassageGenerator(student, level, vocab_contexts)
    questions = generator.generate_questions_for_existing_passage(passage)
    if not questions:
        raise ValueError("AIからの問題生成に失敗しました。")
    existing_batches = passage.questions.values_list('batch_id', flat=True)
    next_batch = max(existing_batches or [0]) + 1
    try:
        q = None
        for q in questions:
            if not isinstance(q.get("options"), list) or len(q["options"]) != 4:
                raise ValueError(f"[Error] optionsの形式が不正: {q.get('options')}")            

            raw_answer = q.get("answer", "").strip().upper()

            if raw_answer not in valid_choices:
                logger.error("無効な正答値: 'raw_answer: %s' → スキップされました", raw_answer)
                raise ValueError(f"[Error] 無効な正答値: '{raw_answer}' → 問題生成に失敗しました")
            ReadingQuestion.objects.create(
                passage=passage,
                question_text=q["question"],
                option_a=q["options"][0],
                option_b=q["options"][1],
                option_c=q["options"][2],
                option_d=q["options"][3],
                correct_option=raw_answer,
                explanation=q["explanation"],
                batch_id=next_batch,
            )
    except Exception:
        logger.exception("問題の登録に失敗: (ReadingQuestion: %s)", q)
        raise  # 上位に通知してエラーページ遷移へ
    return passage, next_batch
