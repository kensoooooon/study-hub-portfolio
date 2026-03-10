from accounts.models import Student

from math_trainer.models import ProblemType, ProblemSession, ProblemInstance, GradeChoices
from math_trainer.math_process.base_generator import BaseProblemGenerator

from typing import Any, Type


def problem_generator(student: Student, problem_name: str,
                    problem_grade: GradeChoices, mode: str,
                    num_of_problem: int, generator_instance: Type[BaseProblemGenerator]) -> list[dict]:
    """
    DBへの処理とViewで利用するための情報の生成を合わせて行う

    Args:
        student (Student): 記録の対象となる生徒
        problem_name (str): 問題のタイプ
        problem_grade (GradeChoices): 問題の学年
        mode (str): 出題のタイプ(display or print)
        num_of_problem (int): 問題数(問題のタイプに応じて変更)
        generator_instance (Type[BaseProblemGenerator]):生成に利用されるインスタンス

    Returns:
        list[dict]: 問題を生成するために必要な諸情報(問題文や解答,描画に必要な情報など)
    
    Notes:
        GradeChoiceは、
        class GradeChoices(models.IntegerChoices):
            PRE_SCHOOL = 0, _('未就学児')
            ELEMENTARY_1 = 1, _('小学1年生')
            ELEMENTARY_2 = 2, _('小学2年生')
            ELEMENTARY_3 = 3, _('小学3年生')
            ELEMENTARY_4 = 4, _('小学4年生')
            ELEMENTARY_5 = 5, _('小学5年生')
            ELEMENTARY_6 = 6, _('小学6年生')
            JUNIOR_HIGH_1 = 7, _('中学1年生')
            JUNIOR_HIGH_2 = 8, _('中学2年生')
            JUNIOR_HIGH_3 = 9, _('中学3年生')
            HIGH_1 = 10, _('高校1年生')
            HIGH_2 = 11, _('高校2年生')
            HIGH_3 = 12, _('高校3年生')
            GAP_YEAR = 13, _('浪人生')
            WORKING = 14, _('社会人')
        から選択される
    """
    # 問題の生成
    generator_instance = generator_instance
    problems = generator_instance.generate_multiple(num_of_problem)
    # DB周りの処理
    problem_type, _ = ProblemType.objects.get_or_create(name=problem_name, grade=problem_grade)
    problem_session = ProblemSession.objects.create(student=student, problem_type=problem_type, mode=mode)
    # 保存処理
    for problem in problems:
        instance = ProblemInstance.objects.create(
            session=problem_session,
            problem_type=problem_type,
            question_text=problem["problem_text"],
            answer_text=problem["answer_text"],
            choice_texts=problem.get("choices", [problem["answer_text"]]),
            metadata = problem.get("metadata", {})
        )
        problem["instance_id"] = instance.id
    return problems, problem_session
