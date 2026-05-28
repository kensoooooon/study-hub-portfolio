from read_trainer.models import ReadingAnswer, StudentReadingPassageProgress
from django.utils import timezone

from django.db import transaction


@transaction.atomic
def process_reading_answers(student, passage, questions, post_data):
    if passage.created_by_id != student.id:
        raise ValueError("生徒と長文の作成者が一致しません。")
    results = []
    number_of_problems = 0
    number_of_correct = 0
    for question in questions:
        selected = post_data.get(f"question_{question.id}")
        if selected not in ['A', 'B', 'C', 'D']:
            raise ValueError("選択肢が不正です")
        correct = selected == question.correct_option
        ReadingAnswer.objects.create(
            student=student,
            question=question,
            selected_option=selected,
            is_correct=correct
        )
        number_of_problems += 1
        if correct:
            number_of_correct += 1
        results.append({
            "question": question,
            "selected_option": selected,
            "is_correct": correct,
            "correct_option": question.correct_option,
            "options": [
                ("A", question.option_a),
                ("B", question.option_b),
                ("C", question.option_c),
                ("D", question.option_d),
            ],
        })

    # 進捗更新
    obj, _ = StudentReadingPassageProgress.objects.get_or_create(
        student=student, passage=passage
    )
    correct_rate = number_of_correct / number_of_problems if number_of_problems else 0.0
    obj.update_review_priority_by_solving(correct_rate=correct_rate)
    return results
