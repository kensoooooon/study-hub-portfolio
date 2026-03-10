"""
quiz_type_select.htmlへ飛ぶ際に必要なコンテキストを構築するための関数、クラス群
"""
from typing import TypedDict
from collections import defaultdict
import re


from vocab_trainer.models import Chapter, StudentContextProgress

class ProgressDict(TypedDict):
    """
    テンプレートでの進捗率表示用に計算された各種値
    
    Attributes:
        total (int): そのチャプターにも紐づいたWordMeaningContextの総数
        learned (int): そのチャプターに紐づいたWordMeaningContextのうち、すでに学習済みのもの
        percentage (float): 学習済みのものの割合
        retention (dict[str, int]): StudentContextProgress経由で取得した復習優先度のカテゴリごと(stable, warning, danger)のカウント数 
        retention_ratio (dict[str, float] | None): 復習優先度のカテゴリごとの全体に対する割合
    """
    total: int
    learned: int
    percentage: float
    retention: dict[str, int]
    retention_ratio: dict[str, float] | None


class ChapterProgress(TypedDict):
    """
    チャプターと紐づけられた進捗表示用の値との辞書
    
    Attributes:
        chapter (Chapter): チャプターの情報を管理するオブジェクト
        progress (ProgressDict): テンプレート表示用の値群
    """
    chapter: Chapter
    progress: ProgressDict


class ReviewLevel:
    """
    復習優先度を定数化するためのクラス
    """
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"
    

def _group_chapters_by_prefix(chapter_progress_data: list[ChapterProgress]) -> dict[str, list[ChapterProgress]]:
    """
    Unit 1やLesson 2など、チャプターの前半部分を基準として、チャプター群をグループ化するための関数
    
    Args:
        chapter_progress_data (list[dict[Chapter, StudentContextProgress]])
    
    Returns:
        (dict[str, list[Chapter]])
    """
    groups = defaultdict(list)

    for entry in chapter_progress_data:
        chapter = entry["chapter"]
        title = chapter.title
        match = re.match(r"^([A-Za-z]+(?: [A-Za-z]+)? ?\d+)", title)
        key = match.group(1) if match else title
        groups[key].append(entry)

    return dict(groups)


def build_quiz_type_select_context(student, classroom_id):
    chapter_progress_data = []

    for chapter in Chapter.objects.filter(textbook=student.textbook).order_by('order'):
        progress = chapter.get_progress_for_student(student)
        chapter_progress_data.append({
            'chapter': chapter,
            'progress': progress,
        })

    grouped_chapter_progress = _group_chapters_by_prefix(chapter_progress_data)

    # 学習状況のまとめ表示用
    textbook_name = str(student.textbook)
    
    # review_priorityの最大値に応じてリスクレベルを設定
    highest_priority = max([c.review_priority for c in StudentContextProgress.objects.filter(
        student=student,
        context__chapter__textbook=student.textbook
    )], default=0.0)
        
    if highest_priority >= 0.75:
        review_level = ReviewLevel.VERY_HIGH
    elif highest_priority >= 0.5:
        review_level = ReviewLevel.HIGH
    elif highest_priority >= 0.25:
        review_level = ReviewLevel.MEDIUM
    elif highest_priority > 0:
        review_level = ReviewLevel.LOW
    else:
        review_level = ReviewLevel.NONE


    return {
        'student': student,
        # 'chapters': chapter_progress_data,
        'grouped_chapter_progress': grouped_chapter_progress,
        'classroom_id': classroom_id,
        'textbook_name': textbook_name,
        'review_level': review_level
    }
    