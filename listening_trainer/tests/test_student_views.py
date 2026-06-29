from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from accounts.models import (
    Student,
    Organization,
    Classroom,
    Teacher,
    ClassroomAdministrator,
    OrganizationAdministrator,
)
from listening_trainer.models import ListeningPassage, ListeningQuestion


class BaseStudentListeningQuizTest(TestCase):
    """
    生徒用リスニングクイズビュー共通セットアップ
    - Organization / Classroom / Student を実際のモデルで作成
    - is_student(user) を満たすユーザーでログイン済み状態にする
    """

    def setUp(self):
        self.org = Organization.objects.create(name="テスト組織")
        self.classroom = Classroom.objects.create(
            name="テスト教室",
            organization=self.org,
        )
        self.student = Student.objects.create_user(
            email="student@example.com",
            password="studentpass",
            role="student",
            organization=self.org,
            is_first_login=False,
        )
        self.student.classrooms.add(self.classroom)

        logged_in = self.client.login(
            email="student@example.com",
            password="studentpass",
        )
        assert logged_in, "ログインに失敗しました（テスト前提が崩れています）"


class StudentListeningQuizDispatcherViewTests(BaseStudentListeningQuizTest):
    """
    StudentListeningQuizDispatcherView.post の挙動テスト
    """

    @patch("listening_trainer.views.student_views.generate_and_save_passage_with_questions")
    @patch("listening_trainer.views.student_views.softmax_permute_contexts_from_progresses")
    @patch("listening_trainer.views.student_views.StudentContextProgress.objects.with_active_student")
    def test_new_redirects_to_student_solve_with_required_information(
        self,
        mock_filter,
        mock_softmax,
        mock_generate,
    ):
        """
        quiz_type=new のとき:
        - 語彙が存在し、長文生成が成功する
        → student_solve への 302 リダイレクト、batch_id と is_eiken=0 が付与されること
        """
        mock_filter.return_value.select_related.return_value = ["ctx"]
        mock_softmax.return_value = ["sorted_ctx"]

        passage = ListeningPassage.objects.create(
            title="テスト長文",
            content="dummy content",
            created_by=self.student,
            source_type="textbook",
        )
        mock_generate.return_value = (passage, 5)

        resp = self.client.post(
            reverse("listening_trainer:quiz_student_dispatch"),
            data={"quiz_type": "new"},
        )

        self.assertEqual(resp.status_code, 302)
        expected_base = reverse("listening_trainer:student_solve", args=[passage.id])
        self.assertTrue(resp.url.startswith(expected_base))
        self.assertIn("batch_id=5", resp.url)
        self.assertIn("is_eiken=0", resp.url)

    @patch("listening_trainer.views.student_views.generate_eiken_passage_with_questions")
    @patch("listening_trainer.views.student_views.softmax_permute_contexts_from_progresses")
    @patch("listening_trainer.views.student_views.StudentContextProgress.objects.with_active_student")
    def test_eiken_new_redirects_on_success(
        self,
        mock_filter,
        mock_softmax,
        mock_generate_eiken,
    ):
        """
        quiz_type=eiken_new のとき:
        - 語彙が存在し、英検長文生成が成功する
        → student_solve への 302 リダイレクト、batch_id と is_eiken=1 が付与されること
        """
        mock_filter.return_value.select_related.return_value = ["ctx"]
        mock_softmax.return_value = ["sorted_ctx"]

        passage = ListeningPassage.objects.create(
            title="英検長文",
            content="dummy eiken content",
            created_by=self.student,
            source_type="eiken",
        )
        mock_generate_eiken.return_value = (passage, 3)

        resp = self.client.post(
            reverse("listening_trainer:quiz_student_dispatch"),
            data={"quiz_type": "eiken_new", "eiken_level": "pre2"},
        )

        self.assertEqual(resp.status_code, 302)
        expected_base = reverse("listening_trainer:student_solve", args=[passage.id])
        self.assertIn(expected_base, resp.url)
        self.assertIn("batch_id=3", resp.url)
        self.assertIn("is_eiken=1", resp.url)

    def test_missing_quiz_type_returns_generation_failed(self):
        """
        quiz_type が送信されなかった場合、
        generation_failed テンプレートが返されること
        """
        resp = self.client.post(
            reverse("listening_trainer:quiz_student_dispatch"),
            data={},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(
            resp, "listening_trainer/for_student/generation_failed.html"
        )

    def test_non_existent_quiz_type_returns_generation_failed(self):
        """
        存在しない quiz_type が送信された場合、
        generation_failed テンプレートが返され、エラーメッセージが含まれること
        """
        resp = self.client.post(
            reverse("listening_trainer:quiz_student_dispatch"),
            data={"quiz_type": "unknown_quiz_type"},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(
            resp, "listening_trainer/for_student/generation_failed.html"
        )
        self.assertIn("不明な出題タイプです。", resp.context["error_message"])

    def test_anonymous_user_redirect_to_login(self):
        """
        未ログインユーザーは GET/POST ともにログイン画面へリダイレクト
        """
        self.client.logout()
        url = reverse("listening_trainer:quiz_student_dispatch")

        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("accounts_auth:login"))

        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("accounts_auth:login"))

    def test_teacher_and_admin_cannot_access(self):
        """
        生徒でないユーザー（講師・教室管理者・組織管理者）は 403
        """
        teacher = Teacher.objects.create_user(
            email="teacher@example.com",
            password="pass123456",
            organization=self.org,
            is_first_login=False,
        )
        class_admin = ClassroomAdministrator.objects.create_user(
            email="class_admin@example.com",
            password="pass123456",
            organization=self.org,
            is_first_login=False,
        )
        org_admin = OrganizationAdministrator.objects.create_user(
            email="org_admin@example.com",
            password="pass123456",
        )
        org_admin.organizations.add(self.org)

        url = reverse("listening_trainer:quiz_student_dispatch")
        for email in [
            "teacher@example.com",
            "class_admin@example.com",
            "org_admin@example.com",
        ]:
            self.client.logout()
            with self.subTest(email=email):
                ok = self.client.login(email=email, password="pass123456")
                self.assertTrue(ok)
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 403)
                resp = self.client.post(url)
                self.assertEqual(resp.status_code, 403)

    def test_inactive_student_cannot_access(self):
        """
        非アクティブ生徒は ModelBackend により anonymous 扱いとなり、
        ログイン画面へリダイレクト（302）
        """
        self.client.logout()
        inactive_student = Student.objects.create_user(
            email="inactive_student@example.com",
            password="pass123456",
            line_user_id="inactive_student_line_user_id",
            organization=self.org,
            is_active=False,
        )
        self.client.force_login(inactive_student)

        url = reverse("listening_trainer:quiz_student_dispatch")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)

    @patch("accounts.models.BaseUser.get_role_object")
    def test_user_without_role_object_cannot_access(self, mock_role_object):
        """
        ロールオブジェクトを持たない不正なユーザーはアクセス不可（403）
        """
        mock_role_object.return_value = None

        resp = self.client.post(
            reverse("listening_trainer:quiz_student_dispatch"),
            data={"quiz_type": "new"},
        )
        self.assertEqual(resp.status_code, 403)


class StudentListeningQuizSolveViewTests(BaseStudentListeningQuizTest):
    """
    StudentListeningQuizSolveView.get / .post の挙動テスト
    """

    def setUp(self):
        super().setUp()

        # 教科書用 passage（batch_id=3 と batch_id=4 の問題を持つ）
        self.passage = ListeningPassage.objects.create(
            title="テスト長文",
            content="This is a test passage.",
            created_by=self.student,
            source_type="textbook",
        )
        self.question = ListeningQuestion.objects.create(
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
        self.other_question = ListeningQuestion.objects.create(
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

        # 英検用 passage
        self.eiken_passage = ListeningPassage.objects.create(
            title="英検テスト長文",
            content="This is a test eiken passage.",
            created_by=self.student,
            source_type="eiken",
        )
        self.eiken_question = ListeningQuestion.objects.create(
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

        # 別生徒の passage
        self.another_student = Student.objects.create_user(
            email="another_student@example.com",
            password="anotherpass",
            role="student",
            organization=self.org,
        )
        self.another_passage = ListeningPassage.objects.create(
            title="他生徒の長文",
            content="Another student's passage.",
            created_by=self.another_student,
            source_type="textbook",
        )

    def test_get_access_display_quiz(self):
        """
        アクセス権を持つ生徒のアクセスであれば、正しくクイズ画面が表示される
        - solve テンプレートが使われること
        - context に正しい passage / student / questions / batch_id / is_eiken が入ること
        - batch_id=3 の問題だけが返され、batch_id=4 の問題は含まれないこと
        """
        url = reverse("listening_trainer:student_solve", args=[self.passage.id])
        resp = self.client.get(url, data={"is_eiken": "0", "batch_id": "3"})

        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "listening_trainer/for_student/solve.html")
        self.assertEqual(resp.context["passage"].id, self.passage.id)
        self.assertEqual(resp.context["student"].id, self.student.id)
        self.assertEqual(list(resp.context["questions"]), [self.question])
        self.assertNotIn(self.other_question, resp.context["questions"])
        self.assertEqual(resp.context["batch_id"], 3)
        self.assertFalse(resp.context["is_eiken"])

    def test_get_without_batch_id_renders_scoring_failed(self):
        """
        batch_id が指定されていない場合は scoring_failed テンプレートが返される
        （read_trainer の generation_failed とは異なる）
        """
        url = reverse("listening_trainer:student_solve", args=[self.passage.id])
        resp = self.client.get(url, data={"is_eiken": "0"})

        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(
            resp, "listening_trainer/for_student/scoring_failed.html"
        )

    def test_is_eiken_1_make_source_type_eiken(self):
        """
        is_eiken=1 で指定されれば、source_type が英検の passage が取得される
        """
        url = reverse("listening_trainer:student_solve", args=[self.eiken_passage.id])
        resp = self.client.get(url, data={"is_eiken": "1", "batch_id": "3"})

        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "listening_trainer/for_student/solve.html")
        self.assertEqual(resp.context["passage"].id, self.eiken_passage.id)
        self.assertEqual(resp.context["student"].id, self.student.id)
        self.assertEqual(list(resp.context["questions"]), [self.eiken_question])
        self.assertEqual(resp.context["batch_id"], 3)
        self.assertTrue(resp.context["is_eiken"])

    def test_different_source_type_raise_404(self):
        """
        is_eiken=1（英検想定）で教科書用 passage にアクセスした場合、
        source_type が一致しないため 404
        """
        url = reverse("listening_trainer:student_solve", args=[self.passage.id])
        resp = self.client.get(url, data={"is_eiken": "1", "batch_id": "3"})

        self.assertEqual(resp.status_code, 404)

    def test_student_cannot_access_another_student_question(self):
        """
        他の生徒が作成した passage にアクセスすると 404
        （passage_access_check が expected_student_id 不一致で Http404 を raise）
        """
        url = reverse(
            "listening_trainer:student_solve", args=[self.another_passage.id]
        )
        resp = self.client.get(url, data={"is_eiken": "0", "batch_id": "1"})

        self.assertEqual(resp.status_code, 404)

    @patch("listening_trainer.views.student_views.process_listening_answers")
    def test_post_success_saves_session_and_redirects(self, mock_process):
        """
        正常系:
        - batch_id が正しい
        - 問題が存在する
        - process_listening_answers が正常終了
        → セッションに listening_quiz_result が保存され、student_result にリダイレクト
        → セッションの各フィールドが正しい値であること
        """
        mock_process.return_value = [
            {
                "question": self.question,
                "selected_option": "A",
                "is_correct": True,
            }
        ]

        url = reverse("listening_trainer:student_solve", args=[self.passage.id])
        resp = self.client.post(
            url,
            {
                "is_eiken": "0",
                "batch_id": "3",
                "audio_file_names": "test.mp3",
                f"question_{self.question.id}": "A",
            },
        )

        self.assertEqual(resp.status_code, 302)
        result_url = reverse("listening_trainer:student_result")
        self.assertIn(result_url, resp.url)
        self.assertIn("is_eiken=0", resp.url)

        session = self.client.session
        data = session.get("listening_quiz_result")
        self.assertIsNotNone(data)
        self.assertEqual(data["passage_id"], self.passage.id)
        self.assertEqual(data["student_id"], str(self.student.id))
        self.assertFalse(data["is_eiken"])
        self.assertEqual(data["batch_id"], 3)
        self.assertEqual(data["audio_file_names"], "test.mp3")
        self.assertEqual(len(data["result_data"]), 1)
        self.assertEqual(data["result_data"][0]["question_id"], self.question.id)
        self.assertEqual(data["result_data"][0]["selected_option"], "A")
        self.assertTrue(data["result_data"][0]["is_correct"])

    def test_post_invalid_batch_id_renders_scoring_failed(self):
        """
        batch_id が整数に変換できない場合、scoring_failed テンプレートが返される
        """
        url = reverse("listening_trainer:student_solve", args=[self.passage.id])
        resp = self.client.post(
            url,
            {"is_eiken": "0", "batch_id": "not-an-int"},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(
            resp, "listening_trainer/for_student/scoring_failed.html"
        )

    def test_anonymous_user_redirect_to_login(self):
        """
        未ログインユーザーは GET/POST ともにログイン画面へリダイレクト
        """
        self.client.logout()
        url = reverse("listening_trainer:student_solve", args=[self.passage.id])

        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("accounts_auth:login"))

        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("accounts_auth:login"))

    def test_teacher_and_admin_cannot_access(self):
        """
        生徒でないユーザーは GET/POST ともにアクセス不可（403）
        """
        teacher = Teacher.objects.create_user(
            email="teacher@example.com",
            password="pass123456",
            organization=self.org,
            is_first_login=False,
        )
        class_admin = ClassroomAdministrator.objects.create_user(
            email="class_admin@example.com",
            password="pass123456",
            organization=self.org,
            is_first_login=False,
        )
        org_admin = OrganizationAdministrator.objects.create_user(
            email="org_admin@example.com",
            password="pass123456",
        )
        org_admin.organizations.add(self.org)

        url = reverse("listening_trainer:student_solve", args=[self.passage.id])
        for email in [
            "teacher@example.com",
            "class_admin@example.com",
            "org_admin@example.com",
        ]:
            self.client.logout()
            with self.subTest(email=email):
                ok = self.client.login(email=email, password="pass123456")
                self.assertTrue(ok)
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 403)
                resp = self.client.post(url)
                self.assertEqual(resp.status_code, 403)

    def test_inactive_student_cannot_access(self):
        """
        非アクティブ生徒は ModelBackend により anonymous 扱いとなり、
        ログイン画面へリダイレクト（302）
        """
        self.client.logout()
        inactive_student = Student.objects.create_user(
            email="inactive_student@example.com",
            password="pass123456",
            line_user_id="inactive_student_line_user_id",
            organization=self.org,
            is_active=False,
        )
        inactive_passage = ListeningPassage.objects.create(
            title="非アクティブ生徒の長文",
            content="test content",
            created_by=inactive_student,
            source_type="textbook",
        )
        self.client.force_login(inactive_student)

        url = reverse("listening_trainer:student_solve", args=[inactive_passage.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)

    @patch("accounts.models.BaseUser.get_role_object")
    def test_user_without_role_object_cannot_access(self, mock_role_object):
        """
        ロールオブジェクトを持たない不正なユーザーはアクセス不可（403）
        """
        mock_role_object.return_value = None

        url = reverse("listening_trainer:student_solve", args=[self.passage.id])
        resp = self.client.get(url, data={"is_eiken": "0", "batch_id": "3"})
        self.assertEqual(resp.status_code, 403)


class StudentListeningQuizResultViewTests(BaseStudentListeningQuizTest):
    """
    student_result_view の挙動テスト
    """

    def setUp(self):
        super().setUp()

        self.passage = ListeningPassage.objects.create(
            title="結果用長文",
            content="Result passage.",
            created_by=self.student,
            source_type="textbook",
        )
        self.question = ListeningQuestion.objects.create(
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

        self.another_student = Student.objects.create_user(
            email="another_student@example.com",
            password="anotherpass",
            role="student",
            organization=self.org,
        )
        self.another_passage = ListeningPassage.objects.create(
            title="他生徒の結果用長文",
            content="Another result passage.",
            created_by=self.another_student,
            source_type="textbook",
        )

    def _make_session_data(self, **overrides):
        data = {
            "passage_id": self.passage.id,
            "student_id": str(self.student.id),
            "is_eiken": False,
            "audio_file_names": "",
            "batch_id": 5,
            "result_data": [
                {
                    "question_id": self.question.id,
                    "selected_option": "A",
                    "is_correct": True,
                }
            ],
        }
        data.update(overrides)
        return data

    def test_no_session_redirects_back_to_quiz_type_select(self):
        """
        セッションに listening_quiz_result が無い場合:
        - is_eiken=1 → 英検用クイズ選択画面へリダイレクト
        - is_eiken=0 → 通常クイズ選択画面へリダイレクト
        """
        url = reverse("listening_trainer:student_result")

        resp = self.client.get(url, {"is_eiken": "1"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn(
            reverse("listening_trainer:eiken_quiz_type_select_for_student"),
            resp.url,
        )

        resp = self.client.get(url, {"is_eiken": "0"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn(
            reverse("listening_trainer:quiz_type_select_for_student"),
            resp.url,
        )

    def test_result_view_renders_and_consumes_session(self):
        """
        セッションに listening_quiz_result がある場合:
        - 結果画面が表示される
        - セッションの listening_quiz_result は pop される（消費される）
        """
        session = self.client.session
        session["listening_quiz_result"] = self._make_session_data()
        session.save()

        resp = self.client.get(reverse("listening_trainer:student_result"))

        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "listening_trainer/for_student/result.html")
        self.assertIsNone(self.client.session.get("listening_quiz_result"))

    def test_student_can_access_and_see_correct_template(self):
        """
        正当な生徒のアクセスで結果画面が表示され、
        context に正しい passage / student が入ること
        """
        session = self.client.session
        session["listening_quiz_result"] = self._make_session_data()
        session.save()

        resp = self.client.get(reverse("listening_trainer:student_result"))

        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "listening_trainer/for_student/result.html")
        self.assertEqual(resp.context["passage"].id, self.passage.id)
        self.assertEqual(resp.context["student"].id, self.student.id)

    def test_student_cannot_access_with_different_id_from_session(self):
        """
        セッションの student_id が別生徒の ID になっている場合は 403
        （student_access_check が PermissionDenied を raise）
        """
        session = self.client.session
        session["listening_quiz_result"] = self._make_session_data(
            student_id=str(self.another_student.id)
        )
        session.save()

        resp = self.client.get(reverse("listening_trainer:student_result"))
        self.assertEqual(resp.status_code, 403)

    def test_student_cannot_access_another_student_passage(self):
        """
        セッションの student_id は自分自身だが、passage_id が別生徒のものになっている場合は 404
        （passage_access_check が expected_student_id 不一致で Http404 を raise）
        """
        another_question = ListeningQuestion.objects.create(
            passage=self.another_passage,
            question_text="Q2?",
            option_a="A1",
            option_b="B1",
            option_c="C1",
            option_d="D1",
            correct_option="A",
            explanation="説明",
            batch_id=5,
        )
        session = self.client.session
        session["listening_quiz_result"] = self._make_session_data(
            passage_id=self.another_passage.id,
            result_data=[
                {
                    "question_id": another_question.id,
                    "selected_option": "A",
                    "is_correct": True,
                }
            ],
        )
        session.save()

        resp = self.client.get(reverse("listening_trainer:student_result"))
        self.assertEqual(resp.status_code, 404)

    @patch("accounts.models.BaseUser.get_role_object")
    def test_user_without_role_object_cannot_access(self, mock_role_object):
        """
        ロールオブジェクトを持たない不正なユーザーはアクセス不可（403）
        """
        session = self.client.session
        session["listening_quiz_result"] = self._make_session_data()
        session.save()

        mock_role_object.return_value = None
        resp = self.client.get(reverse("listening_trainer:student_result"))
        self.assertEqual(resp.status_code, 403)

    def test_inactive_student_cannot_access(self):
        """
        非アクティブ生徒は force_login されても student_access_check により 404
        """
        self.client.logout()
        inactive_student = Student.objects.create_user(
            email="inactive_student@example.com",
            password="pass123456",
            line_user_id="inactive_student_line_user_id",
            organization=self.org,
            is_active=False,
        )
        passage = ListeningPassage.objects.create(
            title="inactive result passage",
            content="dummy",
            created_by=inactive_student,
            source_type="textbook",
        )
        question = ListeningQuestion.objects.create(
            passage=passage,
            question_text="Q?",
            option_a="A1",
            option_b="B1",
            option_c="C1",
            option_d="D1",
            correct_option="A",
            explanation="説明",
            batch_id=5,
        )

        self.client.force_login(inactive_student)

        session = self.client.session
        session["listening_quiz_result"] = {
            "passage_id": passage.id,
            "student_id": str(inactive_student.id),
            "is_eiken": False,
            "audio_file_names": "",
            "batch_id": 5,
            "result_data": [
                {
                    "question_id": question.id,
                    "selected_option": "A",
                    "is_correct": True,
                }
            ],
        }
        session.save()

        resp = self.client.get(reverse("listening_trainer:student_result"))
        self.assertEqual(resp.status_code, 302)

    def test_anonymous_redirect_to_login(self):
        """
        未ログインユーザーはログイン画面へリダイレクト
        """
        self.client.logout()
        resp = self.client.get(reverse("listening_trainer:student_result"))
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("accounts_auth:login"))

    def test_teacher_and_admin_cannot_access(self):
        """
        生徒でないユーザーはアクセス不可（403）
        """
        teacher = Teacher.objects.create_user(
            email="teacher@example.com",
            password="pass123456",
            organization=self.org,
            is_first_login=False,
        )
        class_admin = ClassroomAdministrator.objects.create_user(
            email="class_admin@example.com",
            password="pass123456",
            organization=self.org,
            is_first_login=False,
        )
        org_admin = OrganizationAdministrator.objects.create_user(
            email="org_admin@example.com",
            password="pass123456",
        )
        org_admin.organizations.add(self.org)

        url = reverse("listening_trainer:student_result")
        for email in [
            "teacher@example.com",
            "class_admin@example.com",
            "org_admin@example.com",
        ]:
            self.client.logout()
            with self.subTest(email=email):
                ok = self.client.login(email=email, password="pass123456")
                self.assertTrue(ok)
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 403)
