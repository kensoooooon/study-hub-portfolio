"""問題作成に必要なユーティリティ関数群

# 問題と設計の思想
モデル構造より、長文と問題は1:M構成
出題は4問1セットとなっており、バッチIDで管理を行う
"""
from django.db import transaction

from listening_trainer.models import ListeningPassage, ListeningQuestion
from processors.listening_passage_generator import ListeningPassageGenerator, EikenListeningPassageGenerator

# 型アノテーション用
from accounts.models import Student
from vocab_trainer.models import WordMeaningContext


import logging
logger = logging.getLogger(__name__)


valid_choices = {"A", "B", "C", "D"}

@transaction.atomic
def generate_and_save_passage_with_questions(student: Student, vocab_contexts: list[WordMeaningContext]) -> tuple[ListeningPassage, int]:
    """
    学習済み語彙情報から長文と問題（questions）を新規生成し、DB に保存する。

    Args:
        student: 長文の作成対象となる生徒。
        vocab_contexts: 出題に反映したい語彙コンテキストのリスト。

    Returns:
        passage: 作成された ListeningPassage インスタンス。
        batch_id: 作成された問題群に付与されたバッチID（常に 1）。

    Raises:
        ValueError: ChatGPT 応答の JSON に questions が含まれないなど、
            問題生成に失敗した場合。
        Exception: ListeningPassageGenerator 内部で起きた予期しない例外。
    """
    logger.info(
        "Start generate_and_save_passage_with_questions (student_id=%s, vocab_contexts=%d)",
        student.id, len(vocab_contexts),
    )
    batch_id = 1
    generator = ListeningPassageGenerator(student=student)
    result = generator.generate_passage_with_questions(vocab_contexts)
    if not result or "questions" not in result:
        raise ValueError("AIからの問題生成に失敗しました。")
    passage = ListeningPassage.objects.create(
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
            ListeningQuestion.objects.create(
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


@transaction.atomic
def append_questions_to_existing_passage(student, passage, vocab_contexts):
    """
    既存の長文 (passage) に新しい問題を追加し、新しい batch_id を自動採番して保存。
    """
    generator = ListeningPassageGenerator(student)
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
                logger.error(f"無効な正答値: '{raw_answer}' → スキップされました")
                raise ValueError(f"[Error] 無効な正答値: '{raw_answer}' → 問題生成に失敗しました")
            ListeningQuestion.objects.create(
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


def get_latest_batch_for_passage(passage: ListeningPassage) -> int | None:
    """指定された長文に対して、最新のbatch_idを取得し返す"""
    latest = passage.questions.order_by('-batch_id').first()
    return latest.batch_id if latest else None

@transaction.atomic
def generate_eiken_passage_with_questions(student, level: str, vocab_contexts=None):
    generator = EikenListeningPassageGenerator(student, level, vocab_contexts)
    result = generator.generate_passage_with_questions()
    if not result or "questions" not in result:
        raise ValueError("AIからの問題生成に失敗しました。")
    passage = ListeningPassage.objects.create(
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
                logger.error(f"無効な正答値: '{raw_answer}' → スキップされました")
                raise ValueError(f"[Error] 無効な正答値: '{raw_answer}' → 問題生成に失敗しました")
            ListeningQuestion.objects.create(
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


@transaction.atomic
def append_questions_to_existing_eiken_passage(student, passage, level, vocab_contexts):
    generator = EikenListeningPassageGenerator(student, level, vocab_contexts)
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
                logger.error(f"無効な正答値: '{raw_answer}' → スキップされました")
                raise ValueError(f"[Error] 無効な正答値: '{raw_answer}' → 問題生成に失敗しました")
            ListeningQuestion.objects.create(
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
        logger.exception("問題の登録に失敗: (ListeningQuestion: %s)", q)
        raise  # 上位に通知してエラーページ遷移へ
    return passage, next_batch
