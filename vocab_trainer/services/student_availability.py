from vocab_trainer.models import StudentContextProgress
from accounts.models import Student


def has_vocab_progress(student: Student) -> bool:
    """生徒が vocab_trainer で学習済みの語彙コンテキストを持つか判定する。

    Args:
        student (Student): チェックしたい生徒
    
    Returns:
        (bool): 学習済みのコンテキストを持つか否か
    
    Note:
        呼び出し箇所のdispatcher 側の生成条件（with_active_student + total_count > 0）と揃えないと、条件が変わってしまうので注意
    """
    return StudentContextProgress.objects.with_active_student().filter(
        student=student, total_count__gt=0
    ).exists()
