from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch
from uuid import uuid4

from accounts.models import Student, OrganizationAdministrator
from accounts.models import Organization, Classroom
from listening_trainer.models import ListeningPassage, ListeningQuestion


# ---------------------------------------------------------
# 共通セットアップ
# ---------------------------------------------------------
class BaseAdminListeningQuizTest(TestCase):
    """
    リスニング管理者ビューのテスト基底クラス。
    - 組織管理者のユーザーを作成
    - 組織と教室を作成
    """

    def setUp(self):
        # Organization
        self.organization = Organization.objects.create(
            name="Test Organization",
        )

        # Classroom
        self.classroom = Classroom.objects.create(
            name="Aクラス",
            organization=self.organization,
        )

        # Admin user
        self.admin_user = OrganizationAdministrator.objects.create_user(
            email="admin@example.com",
            password="testpass",
            username="Admin",
            role="organization_administrator",
        )
        self.admin_user.organizations.add(self.organization)

        # ログイン
        self.client.login(email="admin@example.com", password="testpass")


# ---------------------------------------------------------
# クイズ Dispatcher のテスト
# ---------------------------------------------------------
class AdminListeningQuizDispatcherTests(BaseAdminListeningQuizTest):

    @patch("listening_trainer.views.admin_views.softmax_permute_contexts_from_progresses")
    @patch("listening_trainer.views.admin_views.StudentContextProgress.objects.filter")
    def test_missing_quiz_type_returns_generation_failed(
        self,
        mock_scprogress_filter,
        mock_softmax,
    ):
        """
        quiz_type が指定されない → generation_failed.html を返す
        """
        url = reverse("listening_trainer:quiz_admin_dispatch")
        res = self.client.post(url, {})

        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "listening_trainer/for_admin/generation_failed.html")

    @patch("listening_trainer.views.admin_views.generate_eiken_passage_with_questions")
    @patch("listening_trainer.views.admin_views.softmax_permute_contexts_from_progresses")
    @patch("listening_trainer.views.admin_views.StudentContextProgress.objects.filter")
    def test_eiken_new_redirects_on_success(
        self,
        mock_scprogress_filter,
        mock_softmax,
        mock_generate_eiken,
    ):
        """
        eiken_new 正常系 → student_solve_admin にリダイレクト
        """
        # Progress モック
        mock_scprogress_filter.return_value.select_related.return_value = ["ctx1"]
        mock_softmax.return_value = ["ctx_sorted"]

        # 生徒作成（実データ）
        student = Student.objects.create_user(
            email="taro@example.com",
            password="testpass",
            username="Taro",
            organization=self.organization,
        )
        student.classrooms.add(self.classroom)

        # Passage 作成（実データ）
        passage = ListeningPassage.objects.create(
            title="Test",
            content="dummy",
            created_by=student,
            source_type="textbook",
        )

        mock_generate_eiken.return_value = (passage, 3)

        url = reverse("listening_trainer:quiz_admin_dispatch")
        res = self.client.post(url, {
            "quiz_type": "eiken_new",
            "eiken_level": "pre2",
            "target_student_id": str(student.id),
            "classroom_id": str(self.classroom.id)
        })

        self.assertEqual(res.status_code, 302)

        expected = reverse("listening_trainer:admin_solve", args=[passage.id])
        self.assertIn(expected, res.url)
        self.assertIn("batch_id=3", res.url)
        self.assertIn("is_eiken=1", res.url)


# ---------------------------------------------------------
# 管理者 SolveView のテスト
# ---------------------------------------------------------
class AdminListeningSolveViewTests(BaseAdminListeningQuizTest):

    @patch("listening_trainer.views.admin_views.process_listening_answers")
    @patch("listening_trainer.views.admin_views.get_object_or_404")
    def test_post_success_redirects(
        self,
        mock_get_object,
        mock_process,
    ):
        """
        正常 POST:
        - scoring 結果が返り
        - admin_result へリダイレクト
        """

        # Student
        student = Student.objects.create(
            id=uuid4(),
            username="Result Test",
        )
        student.classrooms.add(self.classroom)

        # Passage（DBに作成）
        passage = ListeningPassage.objects.create(
            title="Listening Test Passage",
            content="content",
            created_by=student,
            source_type="textbook",
        )

        # Question（DBに作成）
        q = ListeningQuestion.objects.create(
            passage=passage,
            batch_id=3,
            question_text="Q?",
            option_a="A1",
            option_b="B1",
            option_c="C1",
            option_d="D1",
            correct_option="A",
        )

        # get_object_or_404 → passage を返す
        mock_get_object.side_effect = lambda model, *args, **kwargs: passage

        # process_listening_answers の返り値
        mock_process.return_value = [
            {
                "question": q,
                "selected_option": "A",
                "is_correct": True,
                "target_student_id": str(student.id),
                "classroom_id": str(self.classroom.id)
            }
        ]

        url = reverse("listening_trainer:admin_solve", args=[passage.id])
        res = self.client.post(url, {
            "batch_id": "3",
            "is_eiken": "0",
            "student_id": str(student.id),          # ★必須
            "classroom_id": str(self.classroom.id), # ★セッション保存にも使う
            "audio_file_names": "",                 # ★任意（でも安全）
            f"question_{q.id}": "A",
        })

        self.assertEqual(res.status_code, 302)
        self.assertIn(reverse("listening_trainer:admin_result"), res.url)


# ---------------------------------------------------------
# 結果画面のテスト
# ---------------------------------------------------------
class AdminListeningQuizResultViewTests(BaseAdminListeningQuizTest):

    @patch("listening_trainer.views.admin_views.get_object_or_404")
    def test_result_view_renders_and_consumes_session(self, mock_get_object):
        """
        セッションに listening_quiz_result がある → 正常表示される
        """

        # Student（実データ）
        student = Student.objects.create(
            id=uuid4(),
            username="Result Test",
        )
        student.classrooms.add(self.classroom)

        # Passage（実データ）
        passage = ListeningPassage.objects.create(
            title="ResultPassage",
            content="dummy",
            created_by=student,
            source_type="textbook",
        )

        # Question（実データ）
        q = ListeningQuestion.objects.create(
            passage=passage,
            batch_id=3,
            question_text="Q?",
            option_a="A1",
            option_b="B1",
            option_c="C1",
            option_d="D1",
            correct_option="A",
        )

        # get_object_or_404 モックは実オブジェクト返す
        def _fake_get_object(model, *args, **kwargs):
            if model is ListeningPassage:
                return passage
            if model is Student:
                return student
            raise AssertionError()

        mock_get_object.side_effect = _fake_get_object

        # セッションへ書き込み
        session = self.client.session
        session["listening_quiz_result"] = {
            "passage_id": passage.id,
            "classroom_id": str(self.classroom.id),
            "audio_file_names": "",
            "student_id": str(student.id),
            "is_eiken": False,
            "batch_id": 3,
            "result_data": [
                {
                    "question_id": q.id,
                    "selected_option": "A",
                    "is_correct": True,
                }
            ],
        }
        session.save()

        url = reverse("listening_trainer:admin_result")
        res = self.client.get(url)

        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "listening_trainer/for_admin/result.html")

        # pop されていることを確認
        self.assertIsNone(self.client.session.get("listening_quiz_result"))
