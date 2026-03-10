from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from chem_trainer.models import StudentSubstanceProgress, StudentCompoundProgress, StudentEquationProgress

# ✅ 例文生成を追加
from processors.chemical_explanation_processor import ChemicalExplanationProcessor


def is_student(user):
    return user.role == "student"


@login_required
@user_passes_test(is_student)
def study_card(request, type, relation_id):
    """ 学習用カードの表示 """

    # student = request.user.student  # ログイン中の生徒を取得
    student = request.user.get_role_object()

    # ✅ type を基に適切なモデルを取得
    progress = None
    if type == "substance":
        progress = get_object_or_404(StudentSubstanceProgress, substance_id=relation_id, student=student)
    elif type == "compound":
        progress = get_object_or_404(StudentCompoundProgress, compound_id=relation_id, student=student)
    elif type == "equation":
        progress = get_object_or_404(StudentEquationProgress, chemical_equation_id=relation_id, student=student)
    else:
        return render(request, "error.html", {"message": "無効な学習タイプです。"})

    # ✅ 確認学習を行った場合は、復習優先度を少し下げる
    progress.review_priority *= 0.9  # 優先度を 10% 減少
    progress.last_answered_at = timezone.now()  # 最終確認日を更新
    progress.save()

    # ✅ relation を取得
    relation = None
    if hasattr(progress, 'substance') and progress.substance:
        relation = progress.substance
    elif hasattr(progress, 'compound') and progress.compound:
        relation = progress.compound
    elif hasattr(progress, 'chemical_equation') and progress.chemical_equation:
        relation = progress.chemical_equation

    if not relation:
        return render(request, "error.html", {"message": "関連する学習項目が見つかりません。"})

    # ✅ ChemicalExplanationProcessor に渡す情報を決定
    chemical_name = relation.name_jp if hasattr(relation, 'name_jp') else relation.equation

    # ✅ ChatGPT を利用して解説を生成
    explanation_processor = ChemicalExplanationProcessor()
    explanation = explanation_processor.generate_explanation(chemical_name)
    print(f"explanation: {explanation}")

    # ✅ コンテキストに追加
    context = {
        'relation': relation,
        'progress': progress,
        'explanation': explanation
    }
    return render(request, 'chem_trainer/study_card.html', context)
