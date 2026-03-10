from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone

from vocab_trainer.access_policies import get_accessible_progress_by_id_or_404

# ✅ 例文生成を追加
from processors.example_sentence_processor import ExampleSentenceProcessor


def is_student(user):
    return user.role == "student"


@login_required
@user_passes_test(is_student)
def study_card(request, progress_id):
    """ 学習用カードの表示 """
    progress = get_accessible_progress_by_id_or_404(request.user, progress_id)
    context_obj = progress.context
    relation = context_obj.relation

    # 優先度を更新
    progress.review_priority *= 0.9
    progress.last_answered_at = timezone.now()
    progress.save()

    # 例文生成（未登録時のみ）
    example_sentence = relation.example_sentence
    if not example_sentence:
        example_processor = ExampleSentenceProcessor()
        example_sentence = example_processor.generate_example_sentence(
            word=relation.english_word.word,
            japanese_meaning=relation.japanese_meaning,
            part_of_speech=", ".join([p.part_of_speech.display_name for p in relation.parts_of_speech.all()])
        )
        relation.example_sentence = example_sentence
        relation.save()

    context = {
        'relation': relation,
        'progress': progress,
        'context_obj': context_obj,  # ← チャプター等を参照可能に
        'example_sentence': example_sentence
    }
    return render(request, 'vocab_trainer/study_card.html', context)
