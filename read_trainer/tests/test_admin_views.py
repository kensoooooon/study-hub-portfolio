from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from accounts.models import (
    Student,
    Teacher,
    Organization,
    Classroom,
)
from read_trainer.models import ReadingPassage, ReadingQuestion  # :contentReference[oaicite:0]{index=0}


class BaseAdminReadingQuizTest(TestCase):
    """
    管理者用（講師含む）長文クイズビュー共通セットアップ
    - Organization / Classroom / Teacher / Student を実際のモデルで作成
    - Teacher.can_manage_student(student) が True になるよう関連付け
    """

    def setUp(self):
        # 組織 & 教室
        self.org = Organization.objects.create(name="テスト組織")  # :contentReference[oaicite:1]{index=1}
        self.classroom = Classroom.objects.create(
            name="テスト教室",
            organization=self.org,
        )

        # 講師ユーザー（ログイン主体）
        self.teacher = Teacher.objects.create_user(
            email="teacher@example.com",
            password="testpass",
            role="teacher",
            organization=self.org,
        )
        self.teacher.classrooms.add(self.classroom)

        # 生徒ユーザー（問題の作成者）
        self.student = Student.objects.create_user(
            email=None,  # 生徒は email なしでもOK
            password="studentpass",
            role="student",
            organization=self.org,
        )
        self.student.classrooms.add(self.classroom)
        # 担当講師として紐付け（Teacher.can_manage_student が True になる）
        self.student.teachers.add(self.teacher)

        # ログイン（USERNAME_FIELD は email）
        logged_in = self.client.login(
            email="teacher@example.com",
            password="testpass",
        )
        assert logged_in, "ログインに失敗しました（テスト前提が崩れています）"


class AdminReadingQuizDispatcherViewTests(BaseAdminReadingQuizTest):
    """
    AdminReadingQuizDispatcherView.post の挙動テスト
    """

    @patch("read_trainer.views.admin_views.generate_eiken_passage_with_questions")
    @patch("read_trainer.views.admin_views.softmax_permute_contexts_from_progresses")
    @patch("read_trainer.views.admin_views.StudentContextProgress.objects.filter")
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
        → admin_solve への 302 リダイレクトになること
        """
        # StudentContextProgress.objects.filter(...).select_related("context")
        mock_scprogress_filter.return_value.select_related.return_value = ["dummy_progress"]
        # softmax_sort_progresses が空でないリストを返す
        mock_softmax.return_value = ["sorted_ctx1"]
        # (passage, batch_id) を返すようモック
        dummy_passage = ReadingPassage.objects.create(
            title="英検長文",
            content="dummy content",
            created_by=self.student,
            source_type="eiken",
        )
        mock_generate_eiken.return_value = (dummy_passage, 3)

        url = reverse("read_trainer:quiz_admin_dispatch")  # :contentReference[oaicite:2]{index=2}
        response = self.client.post(
            url,
            {
                "quiz_type": "eiken_new",
                "target_student_id": str(self.student.id),
                "classroom_id": str(self.classroom.id),
                "eiken_level": "pre2",
            },
        )

        self.assertEqual(response.status_code, 302)

        expected_solve_url = reverse(
            "read_trainer:admin_solve", args=[dummy_passage.id]
        )
        self.assertIn(expected_solve_url, response.url)
        self.assertIn("batch_id=3", response.url)
        self.assertIn("is_eiken=1", response.url)

    def test_missing_quiz_type_returns_generation_failed(self):
        """
        quiz_type が送信されなかった場合、
        generation_failed テンプレートが返されること
        （Student や Permission チェックには入らない）
        """
        url = reverse("read_trainer:quiz_admin_dispatch")
        response = self.client.post(
            url,
            {
                "target_student_id": str(self.student.id),
                "classroom_id": str(self.classroom.id),
                # "quiz_type" をあえて送らない
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "read_trainer/for_admin/generation_failed.html"
        )

    def test_inactive_student_cannot_access(self):
        """
        非アクティブ生徒はアクセス不可
        """
        self.client.logout()
        inactive_student = Student.objects.create_user(
            email="inactive_student@example.com",
            password="pass123456",
            line_user_id="inactive_student_line_user_id",
            is_active=False
        )
        self.client.force_login(inactive_student)
        url = reverse("read_trainer:quiz_admin_dispatch")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302) 

class AdminReadingQuizSolveViewTests(BaseAdminReadingQuizTest):
    """
    AdminReadingQuizSolveView.get/post の挙動テスト
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
        self.other_question = ReadingQuestion.objects.create(
            passage=self.passage,
            question_text="Other question?",
            option_a="A2",
            option_b="B2",
            option_c="C2",
            option_d="D2",
            correct_option="B",
            explanation="別説明",
            batch_id=4,
        )
        self.eiken_passage = ReadingPassage.objects.create(
            title="テスト長文",
            content="This is a test eiken passage.",
            created_by=self.student,
            source_type="eiken",
        )
        self.eiken_question = ReadingQuestion.objects.create(
            passage=self.eiken_passage,
            question_text="What is this?",
            option_a="A1",
            option_b="B1",
            option_c="C1",
            option_d="D1",
            correct_option="A",
            explanation="説明",
            batch_id=3,
        )

    @patch("read_trainer.views.admin_views.process_reading_answers")
    def test_post_success_saves_session_and_redirects(self, mock_process):
        """
        正常系:
        - batch_id が正しい
        - 問題が存在する
        - process_reading_answers が正常終了
        → セッションに read_quiz_result が保存され、admin_result にリダイレクト
        """
        mock_process.return_value = [
            {
                "question": self.question,
                "selected_option": "A",
                "is_correct": True,
            }
        ]

        url = reverse("read_trainer:admin_solve", args=[self.passage.id])
        response = self.client.post(
            url,
            {
                "classroom_id": str(self.classroom.id),
                "student_id": str(self.student.id),
                "is_eiken": "0",
                "batch_id": "3",
                # 実際の実装では question_{id} の形式
                f"question_{self.question.id}": "A",
            },
        )

        self.assertEqual(response.status_code, 302)
        result_url = reverse("read_trainer:admin_result")
        self.assertIn(result_url, response.url)

        session = self.client.session
        data = session.get("read_quiz_result")
        self.assertIsNotNone(data)
        self.assertEqual(data["passage_id"], self.passage.id)
        self.assertEqual(data["classroom_id"], str(self.classroom.id))
        self.assertEqual(data["student_id"], str(self.student.id))
        self.assertEqual(data["batch_id"], 3)
        self.assertEqual(len(data["result_data"]), 1)
        self.assertEqual(data["result_data"][0]["question_id"], self.question.id)
        self.assertEqual(data["result_data"][0]["selected_option"], "A")

    def test_post_invalid_batch_id_renders_scoring_failed(self):
        """
        batch_id が整数に変換できない場合、
        scoring_failed テンプレートが返されること
        """
        url = reverse("read_trainer:admin_solve", args=[self.passage.id])
        response = self.client.post(
            url,
            {
                "classroom_id": str(self.classroom.id),
                "student_id": str(self.student.id),
                "is_eiken": "0",
                "batch_id": "not-an-int",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "read_trainer/for_admin/scoring_failed.html"
        )
    
    # claude
    def test_get_with_teacher_display_quiz(self):
        """
        アクセス権を持つ講師のアクセスであれば、正しくクイズ画面が表示される処理が行われる
        """
        data = {
            "is_eiken": "0",
            "batch_id": "3",
            "classroom_id": self.classroom.id,
        }
        url = reverse("read_trainer:admin_solve", args=[self.passage.id])
        resp = self.client.get(
            url,
            data=data
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "read_trainer/for_admin/solve.html")
        self.assertEqual(resp.context["passage"].id, self.passage.id)
        self.assertEqual(resp.context["student"].id, self.student.id)
        self.assertEqual(resp.context["classroom_id"], str(self.classroom.id))
        self.assertEqual(list(resp.context["questions"]), [self.question])
        self.assertNotIn(self.other_question, resp.context["questions"])
        self.assertEqual(resp.context["batch_id"], 3)
        self.assertFalse(resp.context["is_eiken"])

    def test_get_without_batch_id_displays_all_questions(self):
        """
        バッチIDの指定がない場合は生成失敗用のテンプレートが利用される
        """
        url = reverse("read_trainer:admin_solve", args=[self.passage.id])

        resp = self.client.get(
            url,
            data={
                "is_eiken": "0",
                "classroom_id": str(self.classroom.id),
            },
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "read_trainer/for_admin/generation_failed.html")

    def test_is_eiken_1_make_source_type_eiken(self):
        """
        is_eikenが1で指定されれば、ソースタイプが英検のものが取得される
        """
        url = reverse("read_trainer:admin_solve", args=[self.eiken_passage.id])

        resp = self.client.get(
            url,
            data={
                "is_eiken": "1",
                "classroom_id": str(self.classroom.id),
                "batch_id": "3"
            },
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "read_trainer/for_admin/solve.html")
        self.assertEqual(resp.context["passage"].id, self.eiken_passage.id)
        self.assertEqual(resp.context["student"].id, self.student.id)
        self.assertEqual(resp.context["classroom_id"], str(self.classroom.id))
        self.assertEqual(list(resp.context["questions"]), [self.eiken_question])
        self.assertEqual(resp.context["batch_id"], 3)
        self.assertTrue(resp.context["is_eiken"])

    def test_different_source_type_raise_404(self):
        """
        英検かどうかと、長文のIDが一致していない場合は404
        """
        url = reverse("read_trainer:admin_solve", args=[self.passage.id])

        resp = self.client.get(
            url,
            data={
                "is_eiken": "1",
                "classroom_id": str(self.classroom.id),
                "batch_id": "3"
            },
        )

        self.assertEqual(resp.status_code, 404)
    
    def test_student_cannot_access(self):
        """
        生徒はたとえ自分自身の作成した長文を対象にしていても、アクセス不可
        """
        student = Student.objects.create_user(
            email="student@example.com",
            password="pass123456",
            line_user_id="student_line_user_id"
        )
        passage = ReadingPassage.objects.create(
                    title="テスト長文",
                    content="This is a test passage.",
                    created_by=student,
                    source_type="textbook",
                )
        self.client.logout()
        ok = self.client.login(email="student@example.com", password="pass123456")
        self.assertTrue(ok)
        url = reverse("read_trainer:admin_solve", args=[passage.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 403)

    def test_teacher_and_admins_cannot_access_inactive_student(self):
        """
        非アクティブ生徒が作成した長文にはアクセス不可
        """
        inactive_student = Student.objects.create_user(
            email="inactive_student@example.com",
            password="pass123456",
            line_user_id="inactive_student_line_user_id"
        )
        passage = ReadingPassage.objects.create(
                    title="テスト長文",
                    content="This is a test passage.",
                    created_by=inactive_student,
                    source_type="textbook",
                )
        url = reverse("read_trainer:admin_solve", args=[passage.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)
        resp = self.client.post(url, data={"student_id": inactive_student.id})
        self.assertEqual(resp.status_code, 404)


class AdminReadingQuizResultViewTests(BaseAdminReadingQuizTest):
    """
    admin_result_view の挙動テスト
    """

    def setUp(self):
        super().setUp()
        # 結果画面用の長文＆問題
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
        classroom_id / target_student_id / is_eiken に応じて
        クイズ選択画面にリダイレクトされる
        """
        url = reverse("read_trainer:admin_result")

        response = self.client.get(
            url,
            {
                "classroom_id": str(self.classroom.id),
                "target_student_id": str(self.student.id),
                "is_eiken": "0",
            },
        )
        self.assertEqual(response.status_code, 302)
        expected = reverse("read_trainer:quiz_type_select_with_admin")
        self.assertIn(expected, response.url)

        response = self.client.get(
            url,
            {
                "classroom_id": str(self.classroom.id),
                "target_student_id": str(self.student.id),
                "is_eiken": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        expected = reverse("read_trainer:eiken_quiz_type_select_with_admin")
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
            "classroom_id": str(self.classroom.id),
            "student_id": str(self.student.id),
            "is_eiken": False,
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

        url = reverse("read_trainer:admin_result")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "read_trainer/for_admin/result.html")

        # pop されていること
        session = self.client.session
        self.assertIsNone(session.get("read_quiz_result"))
