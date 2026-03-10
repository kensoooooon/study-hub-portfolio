import random
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from chem_trainer.models import Element, ElementalSubstance, Compound, ChemicalEquation
from chem_trainer.models import StudentElementProgress, StudentSubstanceProgress, StudentCompoundProgress, StudentEquationProgress
from chem_trainer.models import ElementDifficulty, SubstanceDifficulty, CompoundDifficulty, EquationDifficulty

import random

from django.db.models import Q

from accounts.models import Student

from processors.chemical_explanation_processor import ChemicalExplanationProcessor

from django.urls import reverse

import re


def generate_question_item(student, model, progress_model, field_name):
    """新規学習・復習優先度の高いもの・過去に学習したものを適度に混ぜて出題"""

    # ✅ 1. 新規学習（40%）
    new_items = model.objects.exclude(
        id__in=progress_model.objects.filter(student=student).values_list(field_name, flat=True)
    ).order_by('?')[:8]

    # ✅ 2. 復習優先度が高いもの（40%）
    high_priority_items = progress_model.objects.filter(
        student=student
    ).order_by('-review_priority')[:8]

    # ✅ 3. ランダムに過去の学習内容（20%）
    random_review_items = progress_model.objects.filter(
        student=student,
        accuracy_rate__gt=0  # 一度は正解したことがある
    ).order_by('?')[:4]

    # ✅ 出題対象をランダムに選択
    question_progress = random.choice(
        list(new_items) + list(high_priority_items) + list(random_review_items)
    )

    # ✅ 選択された要素を取得
    question_item = getattr(question_progress, field_name) if isinstance(question_progress, progress_model) else question_progress

    return question_item


@login_required
def elemental_quiz(request):
    """元素記号クイズ"""
    student = Student.objects.get(pk=request.user.pk)
    question_item = generate_question_item(student, Element, StudentElementProgress, 'element')
    question_id = question_item.id
    quiz_type = random.choice(['name_to_symbol', 'symbol_to_name', 'atomic_number_to_element', 'element_to_atomic_number'])

    if quiz_type == 'name_to_symbol':
        question_text = f"{question_item.name_jp}の元素記号は?"
        correct_answer = question_item.get_latex()
        wrong_answers = [e.get_latex() for e in Element.objects.exclude(symbol=question_item.symbol).order_by('?')[:3]]
        choices = [correct_answer] + wrong_answers

    elif quiz_type == 'symbol_to_name':
        question_text = f"{question_item.get_latex()}の元素名は?"
        correct_answer = question_item.name_jp
        wrong_answers = list(Element.objects.exclude(name_jp=correct_answer).order_by('?')[:3])
        choices = [correct_answer] + [w.name_jp for w in wrong_answers]

    elif quiz_type == 'atomic_number_to_element':
        question_text = f"{question_item.atomic_number}番の元素は?"
        correct_answer = random.choice([question_item.get_latex(), question_item.name_jp])
        wrong_answers = list(Element.objects.exclude(atomic_number=question_item.atomic_number).order_by('?')[:3])
        choices = [correct_answer] + [random.choice([w.get_latex(), w.name_jp]) for w in wrong_answers]

    elif quiz_type == 'element_to_atomic_number':
        question_text = f"{random.choice([question_item.get_latex(), question_item.name_jp])}の原子番号は?"
        correct_answer = str(question_item.atomic_number)
        wrong_answers = list(Element.objects.exclude(atomic_number=question_item.atomic_number).order_by('?')[:3])
        choices = [correct_answer] + [str(w.atomic_number) for w in wrong_answers]

    # 選択肢をシャッフル
    random.shuffle(choices)

    return render(request, 'chem_trainer/quiz.html', {
        'quiz_type': quiz_type, 'category': 'element',
        'question_text': question_text, 'choices': choices,
        'correct_answer': correct_answer, 'question_id': question_id
    })

@login_required
def substance_quiz(request, question_item=None):
    """単体クイズ"""
    if question_item is None:
        student = Student.objects.get(pk=request.user.pk)
        question_item = generate_question_item(student, ElementalSubstance, StudentSubstanceProgress, 'substance')
    question_id = question_item.id

    # ✅ ランダムにクイズタイプを決定
    quiz_type = random.choice(['formula_to_name', 'name_to_formula'])

    if quiz_type == 'formula_to_name':
        # ✅ 化学式 → 日本語名
        question_text = f"{question_item.get_latex()}の日本語名は?"
        correct_answer = question_item.name_jp
        wrong_answers = list(ElementalSubstance.objects.exclude(name_jp=correct_answer).order_by('?')[:3])
        choices = [correct_answer] + [w.name_jp for w in wrong_answers]

    elif quiz_type == 'name_to_formula':
        # ✅ 日本語名 → 化学式
        question_text = f"{question_item.name_jp}の化学式は?"
        correct_answer = question_item.get_latex()
        wrong_answers = list(ElementalSubstance.objects.exclude(formula=question_item.formula).order_by('?')[:3])
        choices = [correct_answer] + [w.get_latex() for w in wrong_answers]

    # ✅ 選択肢をシャッフル
    random.shuffle(choices)

    return render(request, 'chem_trainer/quiz.html', {
        'quiz_type': quiz_type, 'category': 'substance',
        'question_text': question_text, 'choices': choices,
        'correct_answer': correct_answer, 'question_id': question_id
    })


@login_required
def compound_quiz(request, question_item=None):
    """化合物クイズ（化学式↔日本語名）"""
    if question_item is None:
        student = Student.objects.get(pk=request.user.pk)
        question_item = generate_question_item(student, Compound, StudentCompoundProgress, 'compound')
    question_id = question_item.id  # ✅ question_id を渡す

    # ✅ ランダムにクイズタイプを決定
    quiz_type = random.choice(['formula_to_name', 'name_to_formula'])

    if quiz_type == 'formula_to_name':
        # ✅ 化学式 → 日本語名
        question_text = f"{question_item.get_latex()}の日本語名は?"
        correct_answer = question_item.name_jp
        wrong_answers = list(Compound.objects.exclude(name_jp=correct_answer).order_by('?')[:3])
        choices = [correct_answer] + [w.name_jp for w in wrong_answers]

    elif quiz_type == 'name_to_formula':
        # ✅ 日本語名 → 化学式
        question_text = f"{question_item.name_jp}の化学式は?"
        correct_answer = question_item.get_latex()
        wrong_answers = list(Compound.objects.exclude(formula=question_item.formula).order_by('?')[:3])
        choices = [correct_answer] + [w.get_latex() for w in wrong_answers]

    # ✅ 選択肢をシャッフル
    random.shuffle(choices)

    return render(request, 'chem_trainer/quiz.html', {
        'quiz_type': quiz_type, 'category': 'compound',
        'question_text': question_text, 'choices': choices,
        'correct_answer': correct_answer, 'question_id': question_id
    })


@login_required
def equation_quiz(request, question_item=None):
    """化学反応式クイズ（3種類の形式）"""
    if question_item is None:
        student = Student.objects.get(pk=request.user.pk)
        question_item = generate_question_item(student, ChemicalEquation, StudentEquationProgress, 'chemical_equation')
    question_id = question_item.id

    # ✅ ランダムにクイズタイプを決定
    quiz_type = random.choice(['fill_coefficients', 'guess_equation', 'complete_equation'])

    if quiz_type == 'fill_coefficients':
        # ✅ 係数を削除した化学式の問題を生成
        question_text = f"{question_item.get_latex_without_coefficients()} の正しい係数は？"
        correct_answer = question_item.get_latex()
        wrong_answers = question_item.generate_wrong_answers_for_fill_coefficients()
        choices = [correct_answer] + wrong_answers

    elif quiz_type == 'guess_equation':
        # ✅ ChemicalEquation のデータを活用
        reactants = ', '.join([s.name_jp for s in question_item.reactant_substances.all()] + [c.name_jp for c in question_item.reactant_compounds.all()])
        products = ', '.join([s.name_jp for s in question_item.product_substances.all()] + [c.name_jp for c in question_item.product_compounds.all()])
        question_text = f"{reactants} から {products} が生成される反応式は？"
        correct_answer = question_item.get_latex()
        wrong_answers = [eq.get_latex() for eq in ChemicalEquation.objects.exclude(id=question_id).order_by('?')[:3]]
        choices = [correct_answer] + wrong_answers

    elif quiz_type == 'complete_equation':
        reactants = [s.get_latex() for s in question_item.reactant_substances.all()] + [c.get_latex() for c in question_item.reactant_compounds.all()]
        products = [s.get_latex() for s in question_item.product_substances.all()] + [c.get_latex() for c in question_item.product_compounds.all()]

        # ✅ ここで `hide_part` を決定し、統一する
        hide_part = random.choice(['reactants', 'products'])

        if hide_part == 'reactants':
            question_text = f"? → {' + '.join(products)}"
            correct_answer = ' + '.join(reactants)
        else:
            question_text = f"{' + '.join(reactants)} → ?"
            correct_answer = ' + '.join(products)

        # ✅ `hide_part` を渡して誤答を生成
        wrong_answers = question_item.generate_wrong_answers_for_complete_equation(hide_part)

        # ✅ 選択肢をシャッフル
        choices = [correct_answer] + wrong_answers
        random.shuffle(choices)

        return render(request, 'chem_trainer/quiz.html', {
            'quiz_type': quiz_type, 'category': 'equation',
            'question_text': question_text, 'choices': choices,
            'correct_answer': correct_answer, 'question_id': question_id
        })


@login_required
def random_quiz(request):
    """完全ランダムクイズ"""
    student = Student.objects.get(pk=request.user.pk)
    category = random.choice(['element', 'substance', 'equation'])

    if category == 'element':
        return elemental_quiz(request)
    elif category == 'substance':
        return substance_quiz(request)
    else:
        return equation_quiz(request)
    

@login_required
def check_answer(request):
    """ クイズの回答をチェックし、進捗データを更新 """
    if request.method == 'POST':
        selected_answer = request.POST.get('selected_answer')
        correct_answer = request.POST.get('correct_answer')
        category = request.POST.get('category')
        question_id = request.POST.get('question_id')  # ✅ `question_id` を取得

        is_correct = (selected_answer == correct_answer)
        student = Student.objects.get(pk=request.user.pk)

        # ✅ モデルごとに異なる Progress/Difficulty をマッピング
        category_map = {
            'element': (Element, StudentElementProgress, ElementDifficulty, 'element', 'chem_trainer:elemental_quiz'),
            'substance': (ElementalSubstance, StudentSubstanceProgress, SubstanceDifficulty, 'substance', 'chem_trainer:substance_quiz'),
            'compound': (Compound, StudentCompoundProgress, CompoundDifficulty, 'compound', 'chem_trainer:compound_quiz'),
            'equation': (ChemicalEquation, StudentEquationProgress, EquationDifficulty, 'chemical_equation', 'chem_trainer:equation_quiz')
        }

        if category not in category_map:
            return JsonResponse({'error': 'Invalid category'}, status=400)

        model, progress_model, difficulty_model, field_name, next_question_view = category_map[category]

        # ✅ `question_id` を使って `question_item` を取得
        try:
            question_item = model.objects.get(id=question_id)
        except model.DoesNotExist:
            return JsonResponse({'error': 'Invalid question ID'}, status=400)

        explanation = "説明がありません。"
        if question_item:
            # ✅ 学習進捗を更新（適切なフィールド名を使用）
            progress, created = progress_model.objects.get_or_create(student=student, **{field_name: question_item})
            progress.update_progress(is_correct)

            # ✅ 難易度を更新
            difficulty, created = difficulty_model.objects.get_or_create(**{field_name: question_item})
            difficulty.update_difficulty(is_correct)

            # ✅ ChatGPT を利用して解説を生成
            explanation_processor = ChemicalExplanationProcessor()
            explanation = explanation_processor.generate_explanation(question_item.get_latex())
            print(f"explanation: {explanation}")

        # ✅ カテゴリごとに適切な「次の問題へ」のURLを設定
        next_question_url = reverse(next_question_view)

        return JsonResponse({
            'is_correct': is_correct,
            'correct_answer': correct_answer,
            'selected_answer':  selected_answer,
            'explanation': explanation,
            'next_question_url': next_question_url
        })

    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def review_quiz(request):
    """ 復習用のクイズを表示（化学）"""
    student = Student.objects.get(pk=request.user.pk)

    # ✅ 単体, 化合物, 反応式の進捗データを取得
    substance_progresses = StudentSubstanceProgress.objects.filter(student=student).select_related('substance__substance_difficulty')
    compound_progresses = StudentCompoundProgress.objects.filter(student=student).select_related('compound__compound_difficulty')
    equation_progresses = StudentEquationProgress.objects.filter(student=student).select_related('chemical_equation__equation_difficulty')

    all_progresses = list(substance_progresses) + list(compound_progresses) + list(equation_progresses)

    # ✅ 優先度の計算
    for progress in all_progresses:
        difficulty = 1
        if hasattr(progress, 'substance') and hasattr(progress.substance, 'substance_difficulty'):
            difficulty = progress.substance.substance_difficulty.level
        elif hasattr(progress, 'compound') and hasattr(progress.compound, 'compound_difficulty'):
            difficulty = progress.compound.compound_difficulty.level
        elif hasattr(progress, 'chemical_equation') and hasattr(progress.chemical_equation, 'equation_difficulty'):
            difficulty = progress.chemical_equation.equation_difficulty.level
        
        progress.combined_priority = progress.review_priority * difficulty

    # ✅ 優先度順にソート
    sorted_progresses = sorted(all_progresses, key=lambda x: x.combined_priority, reverse=True)

    if not sorted_progresses:
        return render(request, 'chem_trainer/review_quiz.html', {'message': '学習履歴がありません。'})

    # ✅ 最も優先度の高いものを取得
    question_progress = sorted_progresses[0]
    relation = (
        question_progress.substance if hasattr(question_progress, 'substance') else
        question_progress.compound if hasattr(question_progress, 'compound') else
        question_progress.chemical_equation
    )

    # ✅ 物質の種類に応じて出題方法を決定
    if isinstance(relation, ElementalSubstance):
        return substance_quiz(request, relation)
    elif isinstance(relation, Compound):
        return compound_quiz(request, relation)
    elif isinstance(relation, ChemicalEquation):
        return equation_quiz(request, relation)
    else:
        return render(request, 'chem_trainer/review_quiz.html', {'message': '無効なデータです。'})
