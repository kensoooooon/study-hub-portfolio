from listening_trainer.models import ListeningAnswer, StudentListeningPassageProgress

from django.utils import timezone


def process_listening_answers(student, passage, questions, post_data):
    results = []
    number_of_problems = 0
    number_of_correct = 0
    for question in questions:
        selected = post_data.get(f"question_{question.id}")
        if selected not in ['A', 'B', 'C', 'D']:
            raise ValueError("選択肢が不正です")
        correct = selected == question.correct_option
        ListeningAnswer.objects.create(
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
    obj, _ = StudentListeningPassageProgress.objects.get_or_create(
        student=student, passage=passage
    )
    correct_rate = number_of_correct / number_of_problems if number_of_problems else 0.0
    print(f"correct_rate in process_listening_answers: {correct_rate:.4f}")
    obj.update_review_priority_by_solving(correct_rate=correct_rate)
    return results
