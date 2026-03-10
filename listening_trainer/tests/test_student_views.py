from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from listening_trainer.models import ListeningPassage
from vocab_trainer.models import Student as VocabStudent


class BaseStudentListeningQuizTest(TestCase):
    """
    生徒用リスニングクイズビュー共通セットアップ
    - role='student' なユーザーを作成してログイン
    - user.get_role_object() が「生徒ロールオブジェクト」を返すようにモック
    """

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="student-listen@example.com",
            password="testpass",
            role="student",
        )

        # ログイン
        logged_in = self.client.login(
            email="student-listen@example.com",
            password="testpass",
        )
        assert logged_in, "ログインに失敗しました（テスト前提が崩れています）"

        # 生徒ロールオブジェクト（StudentContextProgress などで使う）
        self.student_role = SimpleNamespace(id=1)

        def fake_get_role_object(_self):
            # request.user.get_role_object() → 常に同じ生徒ロールオブジェクトを返す
            return self.student_role

        self.role_patcher = patch.object(
            User,
            "get_role_object",
            fake_get_role_object,
        )
        self.role_patcher.start()

    def tearDown(self):
        self.role_patcher.stop()


class StudentListeningQuizDispatcherViewTests(BaseStudentListeningQuizTest):
    """
    StudentListeningQuizDispatcherView.post の挙動テスト
    """

    @patch("listening_trainer.views.student_views.generate_eiken_passage_with_questions")
    @patch("listening_trainer.views.student_views.softmax_permute_contexts_from_progresses")
    @patch("listening_trainer.views.student_views.StudentContextProgress.objects.filter")
    def test_eiken_new_redirects_on_success(
        self,
        mock_scprogress_filter,
        mock_softmax,
        mock_generate_eiken,
    ):
        """
        quiz_type=eiken_new のとき:
        - 語彙が存在し、
        - 英検リスニング長文生成が成功する
        → student_solve への 302 リダイレクトになること
        """
        # StudentContextProgress.objects.filter(...).select_related("context")
        mock_scprogress_filter.return_value.select_related.return_value = ["dummy_progress"]
        # softmax_sort_progresses が空でないリストを返す
        mock_softmax.return_value = ["sorted_ctx1"]

        # 実際の ListeningPassage モデルを使ってダミーオブジェクトを生成してもよいが、
        # ここでは spec 付き MagicMock にしておく
        dummy_passage = MagicMock(spec=ListeningPassage)
        dummy_passage.id = 10
        dummy_passage.created_by = self.student_role

        # generate_eiken_passage_with_questions は (passage, batch_id) を返す
        mock_generate_eiken.return_value = (dummy_passage, 3)

        url = reverse("listening_trainer:quiz_student_dispatch")
        response = self.client.post(
            url,
            {
                "quiz_type": "eiken_new",
                "eiken_level": "pre2",
            },
        )

        self.assertEqual(response.status_code, 302)

        expected_solve_url = reverse(
            "listening_trainer:student_solve", args=[dummy_passage.id]
        )
        self.assertIn(expected_solve_url, response.url)
        self.assertIn("batch_id=3", response.url)
        self.assertIn("is_eiken=1", response.url)

    def test_missing_quiz_type_returns_generation_failed(self):
        """
        quiz_type が送信されなかった場合、
        generation_failed テンプレートが返されること
        """
        url = reverse("listening_trainer:quiz_student_dispatch")
        response = self.client.post(url, {})  # quiz_type を送らない

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "listening_trainer/for_student/generation_failed.html"
        )


class StudentListeningQuizSolveViewTests(BaseStudentListeningQuizTest):
    """
    StudentListeningQuizSolveView.get/post の挙動テスト
    """

    @patch("listening_trainer.views.student_views.process_listening_answers")
    @patch("listening_trainer.views.student_views.get_object_or_404")
    def test_post_success_saves_session_and_redirects(
        self,
        mock_get_object,
        mock_process,
    ):
        """
        正常系:
        - batch_id が正しい
        - 問題が存在する
        - process_listening_answers が正常終了
        → セッションに listening_quiz_result が保存され、student_result にリダイレクト
        """
        # 質問一覧 (questions) のモック
        dummy_qs = MagicMock()
        dummy_qs.exists.return_value = True

        # passage.questions.filter(...) が dummy_qs を返すような Passage
        dummy_passage = MagicMock(spec=ListeningPassage)
        dummy_passage.id = 10
        dummy_passage.created_by = self.student_role
        dummy_passage.questions.filter.return_value = dummy_qs

        # get_object_or_404(ListeningPassage, pk=...) → dummy_passage
        def _fake_get_object(model, *args, **kwargs):
            if model is ListeningPassage:
                return dummy_passage
            raise AssertionError(f"Unexpected model in get_object_or_404: {model}")

        mock_get_object.side_effect = _fake_get_object

        # process_listening_answers が返す結果
        dummy_question = MagicMock()
        dummy_question.id = 1
        mock_process.return_value = [
            {
                "question": dummy_question,
                "selected_option": "A",
                "is_correct": True,
            }
        ]

        url = reverse("listening_trainer:student_solve", args=[dummy_passage.id])
        response = self.client.post(
            url,
            {
                "is_eiken": "1",
                "batch_id": "3",
                "audio_file_names": "test.mp3",
                "question_1": "A",
            },
        )

        self.assertEqual(response.status_code, 302)
        result_url = reverse("listening_trainer:student_result")
        self.assertIn(result_url, response.url)
        self.assertIn("is_eiken=1", response.url)

        # セッションを確認
        session = self.client.session
        data = session.get("listening_quiz_result")
        self.assertIsNotNone(data)
        self.assertEqual(data["passage_id"], dummy_passage.id)
        self.assertEqual(data["student_id"], str(self.student_role.id))
        self.assertEqual(data["batch_id"], 3)
        self.assertEqual(data["audio_file_names"], "test.mp3")
        self.assertEqual(len(data["result_data"]), 1)
        self.assertEqual(data["result_data"][0]["question_id"], dummy_question.id)
        self.assertEqual(data["result_data"][0]["selected_option"], "A")

    @patch("listening_trainer.views.student_views.get_object_or_404")
    def test_post_invalid_batch_id_renders_scoring_failed(self, mock_get_object):
        """
        batch_id が整数に変換できない場合、
        scoring_failed テンプレートが返されること
        """
        dummy_passage = MagicMock(spec=ListeningPassage)
        dummy_passage.id = 10
        dummy_passage.created_by = self.student_role

        def _fake_get_object(model, *args, **kwargs):
            if model is ListeningPassage:
                return dummy_passage
            raise AssertionError("Unexpected model")

        mock_get_object.side_effect = _fake_get_object

        url = reverse("listening_trainer:student_solve", args=[dummy_passage.id])
        response = self.client.post(
            url,
            {
                "is_eiken": "0",
                "batch_id": "not-an-int",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "listening_trainer/for_student/scoring_failed.html"
        )


class StudentListeningQuizResultViewTests(BaseStudentListeningQuizTest):
    """
    student_result_view の挙動テスト
    """

    def test_no_session_redirects_back_to_quiz_type_select(self):
        """
        セッションに listening_quiz_result が無い場合:
        is_eiken パラメータに応じて
        クイズ選択画面にリダイレクトされること
        """
        url = reverse("listening_trainer:student_result")

        # is_eiken=1 → 英検用クイズ選択
        response = self.client.get(url, {"is_eiken": "1"})
        self.assertEqual(response.status_code, 302)
        expected = reverse("listening_trainer:eiken_quiz_type_select_for_student")
        self.assertIn(expected, response.url)

        # is_eiken=0 → 通常クイズ選択
        response = self.client.get(url, {"is_eiken": "0"})
        self.assertEqual(response.status_code, 302)
        expected = reverse("listening_trainer:quiz_type_select_for_student")
        self.assertIn(expected, response.url)

    @patch("listening_trainer.views.student_views.get_object_or_404")
    def test_result_view_renders_and_consumes_session(self, mock_get_object):
        """
        セッションに listening_quiz_result がある場合:
        - 結果画面が表示される
        - セッションの listening_quiz_result は pop される
        """
        # Student モデル用のダミー
        dummy_student = MagicMock(spec=VocabStudent)
        dummy_student.id = self.student_role.id

        # 質問オブジェクト
        dummy_question = MagicMock()
        dummy_question.id = 1
        dummy_question.correct_option = "A"
        dummy_question.option_a = "A1"
        dummy_question.option_b = "B1"
        dummy_question.option_c = "C1"
        dummy_question.option_d = "D1"

        # passage.questions.filter(batch_id=...) が [dummy_question] を返す Passage
        dummy_passage = MagicMock(spec=ListeningPassage)
        dummy_passage.id = 10
        dummy_passage.created_by = dummy_student
        dummy_passage.questions.filter.return_value = [dummy_question]

        def _fake_get_object(model, *args, **kwargs):
            if model is ListeningPassage:
                return dummy_passage
            if model is VocabStudent:
                return dummy_student
            raise AssertionError(f"Unexpected model in get_object_or_404: {model}")

        mock_get_object.side_effect = _fake_get_object

        # セッションに事前に結果データを保存
        session = self.client.session
        session["listening_quiz_result"] = {
            "passage_id": dummy_passage.id,
            "student_id": str(dummy_student.id),
            "is_eiken": True,
            "audio_file_names": "test.mp3",
            "batch_id": 3,
            "result_data": [
                {
                    "question_id": dummy_question.id,
                    "selected_option": "A",
                    "is_correct": True,
                }
            ],
        }
        session.save()

        url = reverse("listening_trainer:student_result")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "listening_trainer/for_student/result.html"
        )

        # セッションからは pop されているはず
        session = self.client.session
        self.assertIsNone(session.get("listening_quiz_result"))
