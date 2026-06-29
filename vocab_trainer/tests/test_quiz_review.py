# tests/vocab_trainer/test_quiz_review.py
from __future__ import annotations

from types import SimpleNamespace
from dataclasses import dataclass
from unittest.mock import patch

from django.http import HttpResponse, HttpResponseRedirect
from django.test import TestCase, RequestFactory


# ====== ここはあなたのプロジェクト構成に合わせて調整してください ======
# 例1: from vocab_trainer.views.quiz_review import quiz_review_with_admin
# 例2: from vocab_trainer.quiz_review import quiz_review_with_admin
from vocab_trainer.views.quiz.for_admin.quiz_review import quiz_review_with_admin
# =====================================================================


# ------------------------------------------------------------
# テスト用の「最低限の」ダミーオブジェクト
# ------------------------------------------------------------
@dataclass
class DummyEnglishWord:
    word: str


@dataclass
class DummyJapaneseMeaning:
    meaning: str


@dataclass
class DummyRelation:
    english_word: DummyEnglishWord
    japanese_meaning: DummyJapaneseMeaning
    id: int = 999


@dataclass
class DummyWordMeaningContext:
    relation: DummyRelation
    id: int = 123


@dataclass
class DummyStudent:
    id: str = "student-db-id-001"
    textbook_id: int = 1


def _make_user(*, role: str = "teacher", user_id: str = "u-001"):
    """
    login_required / user_passes_test を通すための最小ユーザー。
    - login_required: request.user.is_authenticated を見る
    - is_admin_or_teacher: request.user.role を見る
    """
    return SimpleNamespace(id=user_id, role=role, is_authenticated=True)


def _fake_render(request, template_name, context=None, status=200):
    """
    django.shortcuts.render の代わり。
    テンプレ実体に依存せず、template名とcontextをテストで検査できるようにする。
    """
    res = HttpResponse("", status=status)
    res._template_name = template_name
    res._context_data = context or {}
    return res


def _fake_redirect(to, *args, **kwargs):
    """
    django.shortcuts.redirect の代わり。
    reverse せず、呼ばれた「to」をそのまま Location に入れる。
    （viewの分岐確認が目的なので、ここは軽量でOK）
    """
    return HttpResponseRedirect(f"/__redirect__/{to}")


class QuizReviewWithAdminTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    # -----------------------------
    # 1) POST以外は quiz_type_select にリダイレクト
    # -----------------------------
    @patch("vocab_trainer.views.quiz.for_admin.quiz_review.redirect", side_effect=_fake_redirect)
    def test_get_redirects_to_quiz_type_select(self, _redirect):
        req = self.factory.get("/dummy")
        req.user = _make_user(role="teacher")
        res = quiz_review_with_admin(req)
        self.assertEqual(res.status_code, 302)
        self.assertIn("vocab_trainer:quiz_type_select_with_admin", res["Location"])

    # -----------------------------
    # 2) target_student_id が無い → quiz_error
    # -----------------------------
    @patch("vocab_trainer.views.quiz.for_admin.quiz_review.render", side_effect=_fake_render)
    def test_missing_target_student_id_returns_quiz_error(self, _render):
        req = self.factory.post("/dummy", data={"classroom_id": "c-1"})
        req.user = _make_user(role="teacher")
        res = quiz_review_with_admin(req)
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res._template_name, "vocab_trainer/quiz/for_admin/quiz_error.html")
        self.assertEqual(res._context_data.get("classroom_id"), "c-1")

    # -----------------------------
    # 3) classroom_id が無い → quiz_error
    # -----------------------------
    @patch("vocab_trainer.views.quiz.for_admin.quiz_review.render", side_effect=_fake_render)
    @patch("vocab_trainer.views.quiz.for_admin.quiz_review.get_accessible_student_by_uuid_or_404", return_value=DummyStudent())
    def test_missing_classroom_id_returns_quiz_error(self, _get_student, _render):
        req = self.factory.post("/dummy", data={"target_student_id": "stu-uuid"})
        req.user = _make_user(role="teacher")
        res = quiz_review_with_admin(req)
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res._template_name, "vocab_trainer/quiz/for_admin/quiz_error.html")
        self.assertEqual(res._context_data.get("student_id"), "stu-uuid")

    # -----------------------------
    # 4) 復習対象が選べない（pick_review_context... が None）→ quiz_type_select
    # -----------------------------
    @patch("vocab_trainer.views.quiz.for_admin.quiz_review.render", side_effect=_fake_render)
    @patch("vocab_trainer.views.quiz.for_admin.quiz_review.build_quiz_type_select_context", return_value={"dummy": "ok"})
    @patch("vocab_trainer.views.quiz.for_admin.quiz_review.pick_review_context_by_softmax", return_value=None)
    @patch("vocab_trainer.views.quiz.for_admin.quiz_review.get_accessible_student_by_uuid_or_404", return_value=DummyStudent())
    def test_no_review_context_returns_quiz_type_select(
        self, _get_student, _pick, _build_ctx, _render
    ):
        req = self.factory.post("/dummy", data={"target_student_id": "stu-uuid", "classroom_id": "c-1"})
        req.user = _make_user(role="teacher")
        res = quiz_review_with_admin(req)

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res._template_name, "vocab_trainer/quiz/for_admin/quiz_type_select.html")
        self.assertEqual(res._context_data.get("dummy"), "ok")
        self.assertIn("error_message", res._context_data)

    # -----------------------------
    # 5) choices が 4未満 → quiz_error
    # -----------------------------
    @patch("vocab_trainer.views.quiz.for_admin.quiz_review.render", side_effect=_fake_render)
    @patch("vocab_trainer.views.quiz.for_admin.quiz_review.random.choice", return_value="jp_to_en")
    @patch("vocab_trainer.views.quiz.for_admin.quiz_review.get_choices", return_value=["a", "b", "c"])  # 3つ
    @patch("vocab_trainer.views.quiz.for_admin.quiz_review.pick_review_context_by_softmax")
    @patch("vocab_trainer.views.quiz.for_admin.quiz_review.get_accessible_student_by_uuid_or_404", return_value=DummyStudent())
    def test_choices_less_than_4_returns_quiz_error(
        self, _get_student, _pick, _get_choices, _rand_choice, _render
    ):
        rel = DummyRelation(DummyEnglishWord("apple"), DummyJapaneseMeaning("りんご"))
        _pick.return_value = DummyWordMeaningContext(relation=rel)

        req = self.factory.post("/dummy", data={"target_student_id": "stu-uuid", "classroom_id": "c-1"})
        req.user = _make_user(role="teacher")
        res = quiz_review_with_admin(req)

        self.assertEqual(res.status_code, 404)
        self.assertEqual(res._template_name, "vocab_trainer/quiz/for_admin/quiz_error.html")

    # -----------------------------
    # 6) 成功パス（jp_to_en）: question_text=日本語 meaning, correct_answer=英単語
    # -----------------------------
    @patch("vocab_trainer.views.quiz.for_admin.quiz_review.render", side_effect=_fake_render)
    @patch("vocab_trainer.views.quiz.for_admin.quiz_review.random.choice", return_value="jp_to_en")
    @patch("vocab_trainer.views.quiz.for_admin.quiz_review.get_choices", return_value=["apple", "orange", "banana", "grape"])
    @patch("vocab_trainer.views.quiz.for_admin.quiz_review.pick_review_context_by_softmax")
    @patch("vocab_trainer.views.quiz.for_admin.quiz_review.get_accessible_student_by_uuid_or_404", return_value=DummyStudent())
    def test_success_jp_to_en_renders_quiz(
        self, _get_student, _pick, _get_choices, _rand_choice, _render
    ):
        rel = DummyRelation(DummyEnglishWord("apple"), DummyJapaneseMeaning("りんご"))
        ctx = DummyWordMeaningContext(relation=rel, id=321)
        _pick.return_value = ctx

        req = self.factory.post("/dummy", data={"target_student_id": "stu-uuid", "classroom_id": "c-1"})
        req.user = _make_user(role="teacher")
        res = quiz_review_with_admin(req)

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res._template_name, "vocab_trainer/quiz/for_admin/quiz.html")

        c = res._context_data
        self.assertEqual(c["quiz_mode"], "review")
        self.assertEqual(c["quiz_type"], "jp_to_en")
        self.assertEqual(c["question_text"], "りんご")
        self.assertEqual(c["correct_answer"], "apple")
        self.assertEqual(c["classroom_id"], "c-1")
        self.assertEqual(c["context"].id, 321)
        self.assertEqual(len(c["choices"]), 4)

    # -----------------------------
    # 7) get_accessible_student... が Http404 → quiz_error（想定内の失敗）
    # -----------------------------
    @patch("vocab_trainer.views.quiz.for_admin.quiz_review.render", side_effect=_fake_render)
    @patch("vocab_trainer.views.quiz.for_admin.quiz_review.get_accessible_student_by_uuid_or_404", side_effect=__import__("django").http.Http404)
    def test_student_not_found_returns_quiz_error(self, _get_student, _render):
        req = self.factory.post("/dummy", data={"target_student_id": "stu-uuid", "classroom_id": "c-1"})
        req.user = _make_user(role="teacher")
        res = quiz_review_with_admin(req)

        self.assertEqual(res.status_code, 404)
        self.assertEqual(res._template_name, "vocab_trainer/quiz/for_admin/quiz_error.html")

    # -----------------------------
    # 8) 想定外例外 → quiz_error（status=500）
    # -----------------------------
    @patch("vocab_trainer.views.quiz.for_admin.quiz_review.render", side_effect=_fake_render)
    @patch("vocab_trainer.views.quiz.for_admin.quiz_review.get_accessible_student_by_uuid_or_404", return_value=DummyStudent())
    @patch("vocab_trainer.views.quiz.for_admin.quiz_review.pick_review_context_by_softmax", side_effect=RuntimeError("boom"))
    def test_unexpected_exception_returns_500(self, _pick, _get_student, _render):
        req = self.factory.post("/dummy", data={"target_student_id": "stu-uuid", "classroom_id": "c-1"})
        req.user = _make_user(role="teacher")
        res = quiz_review_with_admin(req)

        self.assertEqual(res.status_code, 500)
        self.assertEqual(res._template_name, "vocab_trainer/quiz/for_admin/quiz_error.html")

    # -----------------------------
    # 9) 権限チェック：roleが不正なら user_passes_test により 302
    # -----------------------------
    def test_role_not_allowed_returns_302(self):
        req = self.factory.post("/dummy", data={"target_student_id": "stu-uuid", "classroom_id": "c-1"})
        req.user = _make_user(role="student")  # is_admin_or_teacher に含まれない
        res = quiz_review_with_admin(req)
        self.assertEqual(res.status_code, 302)
