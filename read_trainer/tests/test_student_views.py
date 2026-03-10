from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from accounts.models import (
    Student,
    Organization,
    Classroom,
)
from read_trainer.models import ReadingPassage, ReadingQuestion


class BaseStudentReadingQuizTest(TestCase):
    """
    生徒用長文クイズビュー共通セットアップ
    - Organization / Classroom / Student を実際のモデルで作成
    - is_student(user) (= user.role == "student") を満たすユーザーでログイン
    """

    def setUp(self):
        # 組織 & 教室
        self.org = Organization.objects.create(name="テスト組織")
        self.classroom = Classroom.objects.create(
            name="テスト教室",
            organization=self.org,
        )

        # 生徒ユーザー（ログイン主体）
        self.student = Student.objects.create_user(
            email="student@example.com",
            password="studentpass",
            role="student",
            organization=self.org,
        )
        self.student.classrooms.add(self.classroom)

        logged_in = self.client.login(
            email="student@example.com",
            password="studentpass",
        )
        assert logged_in, "ログインに失敗しました（テスト前提が崩れています）"


class StudentReadingQuizDispatcherViewTests(BaseStudentReadingQuizTest):
    """
    StudentReadingQuizDispatcherView.post の挙動テスト
    """

    @patch("read_trainer.views.student_views.generate_eiken_passage_with_questions")
    @patch("read_trainer.views.student_views.softmax_permute_contexts_from_progresses")
    @patch("read_trainer.views.student_views.StudentContextProgress.objects.filter")
    def test_eiken_new_redirects_on_success(
        self,
        mock_scprogress_filter,
        mock_softmax,
        mock_generate_eiken,
    ):
        """
        quiz_type=eiken_new のとき:
        - 語彙が存在し、
        - 英検長文生成が成功する
        → student_solve への 302 リダイレクトになること
        """
        # StudentContextProgress.objects.filter(...).select_related("context")
        mock_scprogress_filter.return_value.select_related.return_value = ["dummy_progress"]
        # softmax_sort_progresses が空でないリストを返す
        mock_softmax.return_value = ["sorted_ctx1"]

        # 実際の長文オブジェクトを用意（created_by はログイン生徒）
        dummy_passage = ReadingPassage.objects.create(
            title="英検長文",
            content="dummy content",
            created_by=self.student,
            source_type="eiken",
        )
        # generate_eiken_passage_with_questions は (passage, batch_id) を返す
        mock_generate_eiken.return_value = (dummy_passage, 3)

        url = reverse("read_trainer:quiz_student_dispatch")
        response = self.client.post(
            url,
            {
                "quiz_type": "eiken_new",
                "eiken_level": "pre2",
            },
        )

        self.assertEqual(response.status_code, 302)
        expected_solve_url = reverse(
            "read_trainer:student_solve", args=[dummy_passage.id]
        )
        self.assertIn(expected_solve_url, response.url)
        self.assertIn("batch_id=3", response.url)
        self.assertIn("is_eiken=1", response.url)

    def test_missing_quiz_type_returns_generation_failed(self):
        """
        quiz_type が送信されなかった場合、
        generation_failed テンプレートが返されること
        """
        url = reverse("read_trainer:quiz_student_dispatch")
        response = self.client.post(url, {})  # quiz_type を送らない

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "read_trainer/for_student/generation_failed.html"
        )


class StudentReadingQuizSolveViewTests(BaseStudentReadingQuizTest):
    """
    StudentReadingQuizSolveView.get/post の挙動テスト
    """

    def setUp(self):
        super().setUp()
        # テスト用の長文＆問題
        self.passage = ReadingPassage.objects.create(
            title="テスト長文",
            content="This is a test passage.",
            created_by=self.student,
            source_type="textbook",
        )
        self.question = ReadingQuestion.objects.create(
            passage=self.passage,
            question_text="What is this?",
            option_a="A1",
            option_b="B1",
            option_c="C1",
            option_d="D1",
            correct_option="A",
            explanation="説明",
            batch_id=3,
        )

    @patch("read_trainer.views.student_views.process_reading_answers")
    def test_post_success_saves_session_and_redirects(self, mock_process):
        """
        正常系:
        - batch_id が正しい
        - 問題が存在する
        - process_reading_answers が正常終了
        → セッションに read_quiz_result が保存され、student_result にリダイレクト
        """
        mock_process.return_value = [
            {
                "question": self.question,
                "selected_option": "A",
                "is_correct": True,
            }
        ]

        url = reverse("read_trainer:student_solve", args=[self.passage.id])
        response = self.client.post(
            url,
            {
                "is_eiken": "1",
                "batch_id": "3",
                "audio_file_names": "test.mp3",
                # 実装上は question_{id} の形式で POST される
                f"question_{self.question.id}": "A",
            },
        )

        self.assertEqual(response.status_code, 302)
        result_url = reverse("read_trainer:student_result")
        self.assertIn(result_url, response.url)
        self.assertIn("is_eiken=1", response.url)

        session = self.client.session
        data = session.get("read_quiz_result")
        self.assertIsNotNone(data)
        self.assertEqual(data["passage_id"], self.passage.id)
        self.assertEqual(data["student_id"], str(self.student.id))
        self.assertEqual(data["batch_id"], 3)
        self.assertEqual(data["audio_file_names"], "test.mp3")
        self.assertEqual(len(data["result_data"]), 1)
        self.assertEqual(data["result_data"][0]["question_id"], self.question.id)
        self.assertEqual(data["result_data"][0]["selected_option"], "A")

    def test_post_invalid_batch_id_renders_scoring_failed(self):
        """
        batch_id が整数に変換できない場合、
        scoring_failed テンプレートが返されること
        """
        url = reverse("read_trainer:student_solve", args=[self.passage.id])
        response = self.client.post(
            url,
            {
                "is_eiken": "0",
                "batch_id": "not-an-int",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "read_trainer/for_student/scoring_failed.html"
        )


class StudentReadingQuizResultViewTests(BaseStudentReadingQuizTest):
    """
    student_result_view の挙動テスト
    """

    def setUp(self):
        super().setUp()
        self.passage = ReadingPassage.objects.create(
            title="結果用長文",
            content="Result passage.",
            created_by=self.student,
            source_type="textbook",
        )
        self.question = ReadingQuestion.objects.create(
            passage=self.passage,
            question_text="Q?",
            option_a="A1",
            option_b="B1",
            option_c="C1",
            option_d="D1",
            correct_option="A",
            explanation="説明",
            batch_id=5,
        )

    def test_no_session_redirects_back_to_quiz_type_select(self):
        """
        セッションに read_quiz_result が無い場合:
        is_eiken パラメータに応じて
        クイズ選択画面にリダイレクトされること
        """
        url = reverse("read_trainer:student_result")

        # is_eiken=1 → 英検用クイズ選択
        response = self.client.get(url, {"is_eiken": "1"})
        self.assertEqual(response.status_code, 302)
        expected = reverse("read_trainer:eiken_quiz_type_select_for_student")
        self.assertIn(expected, response.url)

        # is_eiken=0 → 通常クイズ選択
        response = self.client.get(url, {"is_eiken": "0"})
        self.assertEqual(response.status_code, 302)
        expected = reverse("read_trainer:quiz_type_select_for_student")
        self.assertIn(expected, response.url)

    def test_result_view_renders_and_consumes_session(self):
        """
        セッションに read_quiz_result がある場合:
        - 結果画面が表示される
        - セッションの read_quiz_result は pop される
        """
        session = self.client.session
        session["read_quiz_result"] = {
            "passage_id": self.passage.id,
            "student_id": str(self.student.id),
            "is_eiken": True,
            "audio_file_names": "test.mp3",
            "batch_id": 5,
            "result_data": [
                {
                    "question_id": self.question.id,
                    "selected_option": "A",
                    "is_correct": True,
                }
            ],
        }
        session.save()

        url = reverse("read_trainer:student_result")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "read_trainer/for_student/result.html")

        # セッションからは pop されているはず
        session = self.client.session
        self.assertIsNone(session.get("read_quiz_result"))
