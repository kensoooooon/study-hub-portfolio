from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch
from uuid import uuid4
from django.contrib.auth.models import AnonymousUser

from accounts.models import Student, OrganizationAdministrator, ClassroomAdministrator, Teacher
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
    def test_post_success_redirects(
        self,
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
            organization=self.organization
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

    @patch("listening_trainer.views.admin_views.process_listening_answers")
    def test_cannot_access_unassigned_student(
        self,
        mock_process,
    ):
        """
        たとえばデータが完全に揃っていたとしても、作成者たる生徒が管理組織に所属していない場合アクセス不可
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

        self.assertEqual(res.status_code, 404)  # ListeningPassageのvisible_toで、組織がないため弾かれる

    def test_cannot_access_inactive_student_solve_get(self):
        """
        非アクティブ生徒へはアクセス不可
        """
        inactive_student = Student.objects.create_user(
            username="inactive_student",
            email="inactive-student@example.com",
            password="pass123456",
            organization=self.organization,
            is_active=False,
            line_user_id="inactive-student-line-user-id",
        )
        inactive_student.classrooms.add(self.classroom)

        passage = ListeningPassage.objects.create(
            title="Listening Test Passage",
            content="content",
            created_by=inactive_student,
            source_type="textbook",
        )

        url = reverse("listening_trainer:admin_solve", args=[passage.id])
        res = self.client.get(url, {"batch_id": "3", "is_eiken": "0"})
        
        self.assertEqual(res.status_code, 404)  # student_access_check

    # by chatgpt
    def test_post_raises_404_when_student_id_does_not_match_passage_creator(self):
        """
        POSTされた student_id と passage.created_by が一致しない場合は 404。

        Why:
            - hidden input の student_id を改ざんされても、
                別生徒の passage をその生徒の解答として処理してはいけない
            - 管理者が両方の生徒を管理できる場合でも、
                passage と student_id の整合性は必ず守る
        """
        passage_owner = Student.objects.create_user(
            username="Passage Owner",
            email="passage-owner@example.com",
            password="pass123456",
            organization=self.organization,
            is_active=True,
            line_user_id="passage-owner-line-id",
        )
        passage_owner.classrooms.add(self.classroom)

        posted_student = Student.objects.create_user(
            username="Posted Student",
            email="posted-student@example.com",
            password="pass123456",
            organization=self.organization,
            is_active=True,
            line_user_id="posted-student-line-id",
        )
        posted_student.classrooms.add(self.classroom)

        passage = ListeningPassage.objects.create(
            title="Owner Passage",
            content="content",
            created_by=passage_owner,
            source_type="textbook",
        )

        question = ListeningQuestion.objects.create(
            passage=passage,
            batch_id=3,
            question_text="Q?",
            option_a="A1",
            option_b="B1",
            option_c="C1",
            option_d="D1",
            correct_option="A",
        )

        url = reverse("listening_trainer:admin_solve", args=[passage.id])
        res = self.client.post(url, {
            "batch_id": "3",
            "is_eiken": "0",
            "student_id": str(posted_student.id),  # passage.created_by とは別
            "classroom_id": str(self.classroom.id),
            "audio_file_names": "",
            f"question_{question.id}": "A",
        })

        self.assertEqual(res.status_code, 404)

    def test_post_raises_404_when_textbook_passage_is_posted_as_eiken(self):
        """
        textbook passage に is_eiken=1 で POST した場合は 404。

        Why:
            - hidden input の is_eiken を改ざんされても、
                source_type が一致しない passage は処理しない
        """
        student = Student.objects.create_user(
            username="Textbook Student",
            email="textbook-student@example.com",
            password="pass123456",
            organization=self.organization,
            is_active=True,
            line_user_id="textbook-student-line-id",
        )
        student.classrooms.add(self.classroom)

        passage = ListeningPassage.objects.create(
            title="Textbook Passage",
            content="content",
            created_by=student,
            source_type="textbook",
        )

        question = ListeningQuestion.objects.create(
            passage=passage,
            batch_id=3,
            question_text="Q?",
            option_a="A1",
            option_b="B1",
            option_c="C1",
            option_d="D1",
            correct_option="A",
        )

        url = reverse("listening_trainer:admin_solve", args=[passage.id])
        res = self.client.post(url, {
            "batch_id": "3",
            "is_eiken": "1",  # textbook passage なのに eiken として送る
            "student_id": str(student.id),
            "classroom_id": str(self.classroom.id),
            "audio_file_names": "",
            f"question_{question.id}": "A",
        })

        self.assertEqual(res.status_code, 404)

    def test_post_raises_404_when_eiken_passage_is_posted_as_textbook(self):
        """
        eiken passage に is_eiken=0 で POST した場合は 404。

        Why:
            - hidden input の is_eiken を改ざんされても、
                source_type が一致しない passage は処理しない
        """
        student = Student.objects.create_user(
            username="Eiken Student",
            email="eiken-student@example.com",
            password="pass123456",
            organization=self.organization,
            is_active=True,
            line_user_id="eiken-student-line-id",
        )
        student.classrooms.add(self.classroom)

        passage = ListeningPassage.objects.create(
            title="Eiken Passage",
            content="content",
            created_by=student,
            source_type="eiken",
            eiken_level="pre2",
        )

        question = ListeningQuestion.objects.create(
            passage=passage,
            batch_id=3,
            question_text="Q?",
            option_a="A1",
            option_b="B1",
            option_c="C1",
            option_d="D1",
            correct_option="A",
        )

        url = reverse("listening_trainer:admin_solve", args=[passage.id])
        res = self.client.post(url, {
            "batch_id": "3",
            "is_eiken": "0",  # eiken passage なのに textbook として送る
            "student_id": str(student.id),
            "classroom_id": str(self.classroom.id),
            "audio_file_names": "",
            f"question_{question.id}": "A",
        })

        self.assertEqual(res.status_code, 404)


# ---------------------------------------------------------
# 結果画面のテスト
# ---------------------------------------------------------
class AdminListeningQuizResultViewTests(BaseAdminListeningQuizTest):

    def test_result_view_renders_and_consumes_session(self):
        """
        結果のビューは、セッションのデータを消費する
        """
        student = Student.objects.create_user(
            username="Result Test",
            email="result-test@example.com",
            password="testpass",
            organization=self.organization,
            is_active=True,
        )
        student.classrooms.add(self.classroom)

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

    def test_result_view_cannot_accept_inactive_student(self):
        """
        セッションに含まれる生徒が非アクティブの場合、アクセス不可
        """
        active_student = Student.objects.create_user(
            username="Result Test",
            email="result-test-active@example.com",
            password="testpass",
            organization=self.organization,
            is_active=True,
        )
        active_student.classrooms.add(self.classroom)


        inactive_student = Student.objects.create_user(
            username="Result Test",
            email="result-test-inactive@example.com",
            password="testpass",
            organization=self.organization,
            is_active=False,
        )
        inactive_student.classrooms.add(self.classroom)

        passage = ListeningPassage.objects.create(
            title="ResultPassage",
            content="dummy",
            created_by=active_student,
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


        # セッションへ書き込み
        session = self.client.session
        session["listening_quiz_result"] = {
            "passage_id": passage.id,
            "classroom_id": str(self.classroom.id),
            "audio_file_names": "",
            "student_id": str(inactive_student.id),
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

        self.assertEqual(res.status_code, 404)


# ---------------------------------------------------------
# アクティブ生徒だけを取得するようになったことに伴う変更
# ---------------------------------------------------------

class QuizTypeSelectWithAdminTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org1 = Organization.objects.create(name="org1")
        cls.org1_admin = OrganizationAdministrator.objects.create_user(
            username="org1_admin",
            email="org1_admin@example.com",
            password="pass123456"
        )
        cls.org1_admin.organizations.add(cls.org1)

        cls.class1_1 = Classroom.objects.create(name="class1_1", organization=cls.org1)
        cls.class1_1_admin = ClassroomAdministrator.objects.create_user(
            username="class1_1_admin",
            email="class1_1_admin@example.com",
            password="pass123456",
            organization=cls.org1
        )
        cls.class1_1_admin.classrooms.add(cls.class1_1)
        cls.class1_1_teacher = Teacher.objects.create_user(
            username="class1_1_teacher",
            email="class1_1_teacher@example.com",
            password="pass123456",
            organization=cls.org1,
        )
        cls.class1_1_teacher.classrooms.add(cls.class1_1)

        cls.class1_1_active_student = Student.objects.create_user(
            username="class1_1_active_student",
            email="class1_1_active_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=True,
            line_user_id="line_id_class1_1_active_student"
        )
        cls.class1_1_active_student.classrooms.add(cls.class1_1)
        cls.class1_1_active_student.teachers.add(cls.class1_1_teacher)

        cls.class1_1_inactive_student = Student.objects.create_user(
            username="class1_1_inactive_student",
            email="class1_1_inactive_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=False,
            line_user_id="line_id_class1_1_inactive_student"
        )
        cls.class1_1_inactive_student.classrooms.add(cls.class1_1)
        cls.class1_1_inactive_student.teachers.add(cls.class1_1_teacher)

        cls.class1_1_inactive_student_without_teacher = Student.objects.create_user(
            username="class1_1_inactive_student_without_teacher",
            email="class1_1_inactive_student_without_teacher@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=False,
            line_user_id="line_id_class1_1_inactive_student_without_teacher"
        )
        cls.class1_1_inactive_student_without_teacher.classrooms.add(cls.class1_1)

        cls.class1_2 = Classroom.objects.create(name="class1_2", organization=cls.org1)
        cls.class1_2_admin = ClassroomAdministrator.objects.create_user(
            username="class1_2_admin",
            email="class1_2_admin@example.com",
            password="pass123456"
        )
        cls.class1_2_admin.classrooms.add(cls.class1_2)
        cls.class1_2_active_student = Student.objects.create_user(
            username="class1_2_active_student",
            email="class1_2_active_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=True,
            line_user_id="line_id_class1_2_active_student"
        )
        cls.class1_2_active_student.classrooms.add(cls.class1_2)
        cls.class1_2_inactive_student = Student.objects.create_user(
            username="class1_2_inactive_student",
            email="class1_2_inactive_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=False,
            line_user_id="line_id_class1_2_inactive_student"
        )
        cls.class1_2_inactive_student.classrooms.add(cls.class1_2)

        cls.class1_not_active_student = Student.objects.create_user(
            username="class1_not_active_student",
            email="class1_not_active_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=True,
            line_user_id="line_id_class1_not_active_student"
        )
        cls.class1_not_inactive_student = Student.objects.create_user(
            username="class1_not_inactive_student",
            email="class1_not_inactive_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=False,
            line_user_id="line_id_class1_not_inactive_student"
        )


        cls.org2 = Organization.objects.create(name="org2")
        cls.class2 = Classroom.objects.create(name="class2", organization=cls.org2)
        cls.class2_active_student = Student.objects.create_user(
            username="class2_active_student",
            email="class2_active_student@example.com",
            password="pass123456",
            organization=cls.org2,
            is_active=True,
            line_user_id="line_id_class2_active_student"
        )
        cls.class2_active_student.classrooms.add(cls.class2)

        cls.class2_inactive_student = Student.objects.create_user(
            username="class2_inactive_student",
            email="class2_inactive_student@example.com",
            password="pass123456",
            organization=cls.org2,
            is_active=False,
            line_user_id="line_id_class2_inactive_student"
        )
        cls.class2_inactive_student.classrooms.add(cls.class2)
    
        cls.url_to_class1_1 = reverse(
            "organization_admin:student_reactivate",
            kwargs={"classroom_id": cls.class1_1.id},
        )
    
    def login_as_classroom_admin(self):
        ok = self.client.login(email="class1_1_admin@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_as_org_admin(self):
        ok = self.client.login(email="org1_admin@example.com", password="pass123456")
        self.assertTrue(ok)
    
    def login_as_teacher(self):
        ok = self.client.login(email="class1_1_teacher@example.com", password="pass123456")
        self.assertTrue(ok)
    
    def login_as_student(self):
        ok = self.client.login(email="class1_1_active_student@example.com", password="pass123456")
        self.assertTrue(ok)
    
    def test_anonymous_redirect_to_login(self):
        """
        未ログインユーザーはログイン画面へリダイレクト
        """
        classroom = self.class1_1
        student = self.class1_1_active_student
        resp = self.client.get(
            reverse("listening_trainer:quiz_type_select_with_admin"),
            data={"classroom_id": classroom.id, "target_student_id": student.id}
            )
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("accounts_auth:login"))
        
    def test_org_admin_can_access(self):
        """
        組織管理者は自身の管理組織に所属する生徒を対象にアクセス可能
        """
        self.login_as_org_admin()
        classroom = self.class1_1
        student = self.class1_1_active_student
        resp = self.client.get(
            reverse("listening_trainer:quiz_type_select_with_admin"),
            data={"classroom_id": classroom.id, "target_student_id": student.id}
            )
        self.assertEqual(resp.status_code, 200)

    def test_class_admin_can_access(self):
        """
        教室管理者は自身の管理した教室に所属する生徒を対象にアクセス可能
        """
        self.login_as_classroom_admin()
        classroom = self.class1_1
        student = self.class1_1_active_student
        resp = self.client.get(
            reverse("listening_trainer:quiz_type_select_with_admin"),
            data={"classroom_id": classroom.id, "target_student_id": student.id}
            )
        self.assertEqual(resp.status_code, 200)

    def test_teacher_can_access(self):
        """
        講師は自身の担当である生徒を対象にアクセス可能
        """
        self.login_as_teacher()
        classroom = self.class1_1
        student = self.class1_1_active_student
        resp = self.client.get(
            reverse("listening_trainer:quiz_type_select_with_admin"),
            data={"classroom_id": classroom.id, "target_student_id": student.id}
            )
        self.assertEqual(resp.status_code, 200)
    
    def test_student_cannot_access(self):
        """
        生徒はたとえ自分自身が対象だったとしても、管理者用関数にアクセスできない
        """
        self.login_as_student()
        classroom = self.class1_1
        student = self.class1_1_active_student
        resp = self.client.get(
            reverse("listening_trainer:quiz_type_select_with_admin"),
            data={"classroom_id": classroom.id, "target_student_id": student.id}
            )
        self.assertEqual(resp.status_code, 403)
    
    def test_org_admin_cannot_access_inactive_student(self):
        """
        組織管理者は非アクティブ生徒へアクセスはできない
        """
        self.login_as_org_admin()
        classroom = self.class1_1
        student = self.class1_1_inactive_student
        resp = self.client.get(
            reverse("listening_trainer:quiz_type_select_with_admin"),
            data={"classroom_id": classroom.id, "target_student_id": student.id}
            )
        self.assertEqual(resp.status_code, 404)

    def test_class_admin_cannot_access_inactive_student(self):
        """
        教室管理者は非アクティブ生徒にアクセスできない
        """
        self.login_as_classroom_admin()
        classroom = self.class1_1
        student = self.class1_1_inactive_student
        resp = self.client.get(
            reverse("listening_trainer:quiz_type_select_with_admin"),
            data={"classroom_id": classroom.id, "target_student_id": student.id}
            )
        self.assertEqual(resp.status_code, 404)
    
    def test_teacher_cannot_access_inactive_student(self):
        """
        講師は非アクティブ生徒にアクセスできない
        """
        self.login_as_teacher()
        classroom = self.class1_1
        student = self.class1_1_inactive_student
        resp = self.client.get(
            reverse("listening_trainer:quiz_type_select_with_admin"),
            data={"classroom_id": classroom.id, "target_student_id": student.id}
            )
        self.assertEqual(resp.status_code, 404)

    def test_org_admin_cannot_another_org_student(self):
        """
        組織管理者は異なる組織の生徒にアクセス不可
        """
        self.login_as_org_admin()
        classroom = self.class1_1
        student = self.class2_active_student
        resp = self.client.get(
            reverse("listening_trainer:quiz_type_select_with_admin"),
            data={"classroom_id": classroom.id, "target_student_id": student.id}
            )
        self.assertEqual(resp.status_code, 403)

    def test_class_admin_cannot_access_another_org_student(self):
        """
        教室管理者は異なる組織の生徒にアクセス不可
        """
        self.login_as_classroom_admin()
        classroom = self.class1_1
        student = self.class2_active_student
        resp = self.client.get(
            reverse("listening_trainer:quiz_type_select_with_admin"),
            data={"classroom_id": classroom.id, "target_student_id": student.id}
            )
        self.assertEqual(resp.status_code, 403)

    def test_teacher_cannot_access_another_org_student(self):
        """
        講師は異なる組織の生徒にアクセス不可
        """
        self.login_as_teacher()
        classroom = self.class1_1
        student = self.class2_active_student
        resp = self.client.get(
            reverse("listening_trainer:quiz_type_select_with_admin"),
            data={"classroom_id": classroom.id, "target_student_id": student.id}
            )
        self.assertEqual(resp.status_code, 403)

    @patch("accounts.models.BaseUser.get_role_object")
    def test_user_without_role_object_cannot_access(self, mock_role_object):
        """
        ロールオブジェクトがNoneのユーザーはアクセス不可
        """
        self.login_as_org_admin()
        mock_role_object.return_value = None
        classroom = self.class1_1
        student = self.class1_1_active_student
        resp = self.client.get(
            reverse("listening_trainer:quiz_type_select_with_admin"),
            data={"classroom_id": classroom.id, "target_student_id": student.id}
            )
        self.assertEqual(resp.status_code, 403)

class EikenQuizTypeSelectWithAdminTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org1 = Organization.objects.create(name="org1")
        cls.org1_admin = OrganizationAdministrator.objects.create_user(
            username="org1_admin",
            email="org1_admin@example.com",
            password="pass123456"
        )
        cls.org1_admin.organizations.add(cls.org1)

        cls.class1_1 = Classroom.objects.create(name="class1_1", organization=cls.org1)
        cls.class1_1_admin = ClassroomAdministrator.objects.create_user(
            username="class1_1_admin",
            email="class1_1_admin@example.com",
            password="pass123456",
            organization=cls.org1
        )
        cls.class1_1_admin.classrooms.add(cls.class1_1)
        cls.class1_1_teacher = Teacher.objects.create_user(
            username="class1_1_teacher",
            email="class1_1_teacher@example.com",
            password="pass123456",
            organization=cls.org1,
        )
        cls.class1_1_teacher.classrooms.add(cls.class1_1)

        cls.class1_1_active_student = Student.objects.create_user(
            username="class1_1_active_student",
            email="class1_1_active_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=True,
            line_user_id="line_id_class1_1_active_student"
        )
        cls.class1_1_active_student.classrooms.add(cls.class1_1)
        cls.class1_1_active_student.teachers.add(cls.class1_1_teacher)

        cls.class1_1_inactive_student = Student.objects.create_user(
            username="class1_1_inactive_student",
            email="class1_1_inactive_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=False,
            line_user_id="line_id_class1_1_inactive_student"
        )
        cls.class1_1_inactive_student.classrooms.add(cls.class1_1)
        cls.class1_1_inactive_student.teachers.add(cls.class1_1_teacher)

        cls.class1_1_inactive_student_without_teacher = Student.objects.create_user(
            username="class1_1_inactive_student_without_teacher",
            email="class1_1_inactive_student_without_teacher@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=False,
            line_user_id="line_id_class1_1_inactive_student_without_teacher"
        )
        cls.class1_1_inactive_student_without_teacher.classrooms.add(cls.class1_1)

        cls.class1_2 = Classroom.objects.create(name="class1_2", organization=cls.org1)
        cls.class1_2_admin = ClassroomAdministrator.objects.create_user(
            username="class1_2_admin",
            email="class1_2_admin@example.com",
            password="pass123456"
        )
        cls.class1_2_admin.classrooms.add(cls.class1_2)
        cls.class1_2_active_student = Student.objects.create_user(
            username="class1_2_active_student",
            email="class1_2_active_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=True,
            line_user_id="line_id_class1_2_active_student"
        )
        cls.class1_2_active_student.classrooms.add(cls.class1_2)
        cls.class1_2_inactive_student = Student.objects.create_user(
            username="class1_2_inactive_student",
            email="class1_2_inactive_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=False,
            line_user_id="line_id_class1_2_inactive_student"
        )
        cls.class1_2_inactive_student.classrooms.add(cls.class1_2)

        cls.class1_not_active_student = Student.objects.create_user(
            username="class1_not_active_student",
            email="class1_not_active_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=True,
            line_user_id="line_id_class1_not_active_student"
        )
        cls.class1_not_inactive_student = Student.objects.create_user(
            username="class1_not_inactive_student",
            email="class1_not_inactive_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=False,
            line_user_id="line_id_class1_not_inactive_student"
        )


        cls.org2 = Organization.objects.create(name="org2")
        cls.class2 = Classroom.objects.create(name="class2", organization=cls.org2)
        cls.class2_active_student = Student.objects.create_user(
            username="class2_active_student",
            email="class2_active_student@example.com",
            password="pass123456",
            organization=cls.org2,
            is_active=True,
            line_user_id="line_id_class2_active_student"
        )
        cls.class2_active_student.classrooms.add(cls.class2)

        cls.class2_inactive_student = Student.objects.create_user(
            username="class2_inactive_student",
            email="class2_inactive_student@example.com",
            password="pass123456",
            organization=cls.org2,
            is_active=False,
            line_user_id="line_id_class2_inactive_student"
        )
        cls.class2_inactive_student.classrooms.add(cls.class2)
    
        cls.url_to_class1_1 = reverse(
            "organization_admin:student_reactivate",
            kwargs={"classroom_id": cls.class1_1.id},
        )
    
    def login_as_classroom_admin(self):
        ok = self.client.login(email="class1_1_admin@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_as_org_admin(self):
        ok = self.client.login(email="org1_admin@example.com", password="pass123456")
        self.assertTrue(ok)
    
    def login_as_teacher(self):
        ok = self.client.login(email="class1_1_teacher@example.com", password="pass123456")
        self.assertTrue(ok)
    
    def login_as_student(self):
        ok = self.client.login(email="class1_1_active_student@example.com", password="pass123456")
        self.assertTrue(ok)

    def test_anonymous_redirect_to_login(self):
        """
        未ログインユーザーはログイン画面へリダイレクト
        """
        classroom = self.class1_1
        student = self.class1_1_active_student
        resp = self.client.get(
            reverse("listening_trainer:eiken_quiz_type_select_with_admin"),
            data={"classroom_id": classroom.id, "target_student_id": student.id}
            )
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("accounts_auth:login"))
        
    def test_org_admin_can_access(self):
        """
        組織管理者は自身の管理組織に所属する生徒を対象にアクセス可能
        """
        self.login_as_org_admin()
        classroom = self.class1_1
        student = self.class1_1_active_student
        resp = self.client.get(
            reverse("listening_trainer:eiken_quiz_type_select_with_admin"),
            data={"classroom_id": classroom.id, "target_student_id": student.id}
            )
        self.assertEqual(resp.status_code, 200)

    def test_class_admin_can_access(self):
        """
        教室管理者は自身の管理した教室に所属する生徒を対象にアクセス可能
        """
        self.login_as_classroom_admin()
        classroom = self.class1_1
        student = self.class1_1_active_student
        resp = self.client.get(
            reverse("listening_trainer:eiken_quiz_type_select_with_admin"),
            data={"classroom_id": classroom.id, "target_student_id": student.id}
            )
        self.assertEqual(resp.status_code, 200)

    def test_teacher_can_access(self):
        """
        講師は自身の担当である生徒を対象にアクセス可能
        """
        self.login_as_teacher()
        classroom = self.class1_1
        student = self.class1_1_active_student
        resp = self.client.get(
            reverse("listening_trainer:eiken_quiz_type_select_with_admin"),
            data={"classroom_id": classroom.id, "target_student_id": student.id}
            )
        self.assertEqual(resp.status_code, 200)
    
    def test_student_cannot_access(self):
        """
        生徒はたとえ自分自身が対象だったとしても、管理者用関数にアクセスできない
        """
        self.login_as_student()
        classroom = self.class1_1
        student = self.class1_1_active_student
        resp = self.client.get(
            reverse("listening_trainer:eiken_quiz_type_select_with_admin"),
            data={"classroom_id": classroom.id, "target_student_id": student.id}
            )
        self.assertEqual(resp.status_code, 403)

    def test_org_admin_cannot_access_inactive_student(self):
        """
        組織管理者は非アクティブ生徒へアクセスはできない
        """
        self.login_as_org_admin()
        classroom = self.class1_1
        student = self.class1_1_inactive_student
        resp = self.client.get(
            reverse("listening_trainer:eiken_quiz_type_select_with_admin"),
            data={"classroom_id": classroom.id, "target_student_id": student.id}
            )
        self.assertEqual(resp.status_code, 404)

    def test_class_admin_cannot_access_inactive_student(self):
        """
        教室管理者は非アクティブ生徒にアクセスできない
        """
        self.login_as_classroom_admin()
        classroom = self.class1_1
        student = self.class1_1_inactive_student
        resp = self.client.get(
            reverse("listening_trainer:eiken_quiz_type_select_with_admin"),
            data={"classroom_id": classroom.id, "target_student_id": student.id}
            )
        self.assertEqual(resp.status_code, 404)
    
    def test_teacher_cannot_access_inactive_student(self):
        """
        講師は非アクティブ生徒にアクセスできない
        """
        self.login_as_teacher()
        classroom = self.class1_1
        student = self.class1_1_inactive_student
        resp = self.client.get(
            reverse("listening_trainer:eiken_quiz_type_select_with_admin"),
            data={"classroom_id": classroom.id, "target_student_id": student.id}
            )
        self.assertEqual(resp.status_code, 404)

    def test_org_admin_cannot_another_org_student(self):
        """
        組織管理者は異なる組織の生徒にアクセス不可
        """
        self.login_as_org_admin()
        classroom = self.class1_1
        student = self.class2_active_student
        resp = self.client.get(
            reverse("listening_trainer:eiken_quiz_type_select_with_admin"),
            data={"classroom_id": classroom.id, "target_student_id": student.id}
            )
        self.assertEqual(resp.status_code, 403)

    def test_class_admin_cannot_access_another_org_student(self):
        """
        教室管理者は異なる組織の生徒にアクセス不可
        """
        self.login_as_classroom_admin()
        classroom = self.class1_1
        student = self.class2_active_student
        resp = self.client.get(
            reverse("listening_trainer:eiken_quiz_type_select_with_admin"),
            data={"classroom_id": classroom.id, "target_student_id": student.id}
            )
        self.assertEqual(resp.status_code, 403)

    def test_teacher_cannot_access_another_org_student(self):
        """
        講師は異なる組織の生徒にアクセス不可
        """
        self.login_as_teacher()
        classroom = self.class1_1
        student = self.class2_active_student
        resp = self.client.get(
            reverse("listening_trainer:eiken_quiz_type_select_with_admin"),
            data={"classroom_id": classroom.id, "target_student_id": student.id}
            )
        self.assertEqual(resp.status_code, 403)

    @patch("accounts.models.BaseUser.get_role_object")
    def test_user_without_role_object_cannot_access(self, mock_role_object):
        """
        ロールオブジェクトがNoneのユーザーはアクセス不可
        """
        self.login_as_org_admin()
        mock_role_object.return_value = None
        classroom = self.class1_1
        student = self.class1_1_active_student
        resp = self.client.get(
            reverse("listening_trainer:quiz_type_select_with_admin"),
            data={"classroom_id": classroom.id, "target_student_id": student.id}
            )
        self.assertEqual(resp.status_code, 403)


class AdminListeningQuizDispatcherViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org1 = Organization.objects.create(name="org1")
        cls.org1_admin = OrganizationAdministrator.objects.create_user(
            username="org1_admin",
            email="org1_admin@example.com",
            password="pass123456"
        )
        cls.org1_admin.organizations.add(cls.org1)

        cls.class1_1 = Classroom.objects.create(name="class1_1", organization=cls.org1)
        cls.class1_1_admin = ClassroomAdministrator.objects.create_user(
            username="class1_1_admin",
            email="class1_1_admin@example.com",
            password="pass123456",
            organization=cls.org1
        )
        cls.class1_1_admin.classrooms.add(cls.class1_1)
        cls.class1_1_teacher = Teacher.objects.create_user(
            username="class1_1_teacher",
            email="class1_1_teacher@example.com",
            password="pass123456",
            organization=cls.org1,
        )
        cls.class1_1_teacher.classrooms.add(cls.class1_1)

        cls.class1_1_active_student = Student.objects.create_user(
            username="class1_1_active_student",
            email="class1_1_active_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=True,
            line_user_id="line_id_class1_1_active_student"
        )
        cls.class1_1_active_student.classrooms.add(cls.class1_1)
        cls.class1_1_active_student.teachers.add(cls.class1_1_teacher)

        cls.class1_1_inactive_student = Student.objects.create_user(
            username="class1_1_inactive_student",
            email="class1_1_inactive_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=False,
            line_user_id="line_id_class1_1_inactive_student"
        )
        cls.class1_1_inactive_student.classrooms.add(cls.class1_1)
        cls.class1_1_inactive_student.teachers.add(cls.class1_1_teacher)

        cls.class1_1_inactive_student_without_teacher = Student.objects.create_user(
            username="class1_1_inactive_student_without_teacher",
            email="class1_1_inactive_student_without_teacher@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=False,
            line_user_id="line_id_class1_1_inactive_student_without_teacher"
        )
        cls.class1_1_inactive_student_without_teacher.classrooms.add(cls.class1_1)

        cls.class1_2 = Classroom.objects.create(name="class1_2", organization=cls.org1)
        cls.class1_2_admin = ClassroomAdministrator.objects.create_user(
            username="class1_2_admin",
            email="class1_2_admin@example.com",
            password="pass123456"
        )
        cls.class1_2_admin.classrooms.add(cls.class1_2)
        cls.class1_2_active_student = Student.objects.create_user(
            username="class1_2_active_student",
            email="class1_2_active_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=True,
            line_user_id="line_id_class1_2_active_student"
        )
        cls.class1_2_active_student.classrooms.add(cls.class1_2)
        cls.class1_2_inactive_student = Student.objects.create_user(
            username="class1_2_inactive_student",
            email="class1_2_inactive_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=False,
            line_user_id="line_id_class1_2_inactive_student"
        )
        cls.class1_2_inactive_student.classrooms.add(cls.class1_2)

        cls.class1_not_active_student = Student.objects.create_user(
            username="class1_not_active_student",
            email="class1_not_active_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=True,
            line_user_id="line_id_class1_not_active_student"
        )
        cls.class1_not_inactive_student = Student.objects.create_user(
            username="class1_not_inactive_student",
            email="class1_not_inactive_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=False,
            line_user_id="line_id_class1_not_inactive_student"
        )


        cls.org2 = Organization.objects.create(name="org2")
        cls.class2 = Classroom.objects.create(name="class2", organization=cls.org2)
        cls.class2_active_student = Student.objects.create_user(
            username="class2_active_student",
            email="class2_active_student@example.com",
            password="pass123456",
            organization=cls.org2,
            is_active=True,
            line_user_id="line_id_class2_active_student"
        )
        cls.class2_active_student.classrooms.add(cls.class2)

        cls.class2_inactive_student = Student.objects.create_user(
            username="class2_inactive_student",
            email="class2_inactive_student@example.com",
            password="pass123456",
            organization=cls.org2,
            is_active=False,
            line_user_id="line_id_class2_inactive_student"
        )
        cls.class2_inactive_student.classrooms.add(cls.class2)

        cls.url = reverse("listening_trainer:quiz_admin_dispatch")

        
    """
    正常系
    正常な設定なら admin_solve へ必要なクエリ付きでリダイレクト
    異常系
    未ログインユーザー: 302
    生徒ロール: 403
    非アクティブ生徒: 404
    権限外の生徒: 403
    quiz_type 未指定: 200 + generation_failed.html
    """
    def login_as_org_admin(self):
        ok = self.client.login(email="org1_admin@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_as_class_admin(self):
        ok = self.client.login(email="class1_1_admin@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_as_teacher(self):
        ok = self.client.login(email="class1_1_teacher@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_as_student(self):
        ok = self.client.login(email="class1_1_active_student@example.com", password="pass123456")
        self.assertTrue(ok)

    def make_listening_passage(self):
        passage = ListeningPassage.objects.create(
            content="this is sample content",
            source_type="textbook",
        )
        return passage

    @patch("listening_trainer.views.admin_views.generate_and_save_passage_with_questions")
    @patch("listening_trainer.views.admin_views.softmax_permute_contexts_from_progresses")
    @patch("listening_trainer.views.admin_views.StudentContextProgress.objects.filter")
    def test_right_access_redirect_to_admin_solve_with_required_information(
        self,
        mock_scprogress_filter,
        mock_softmax,
        mock_generate,
    ):
        """
        正しいアクセスを受けた場合は、必要な情報を伴ってadmin_solveへリダイレクトが起きる

        Learning:
        @patchと引数の対応関係
            一番下の @patch → 1番目の引数 mock_scprogress_filter
            真ん中の @patch → 2番目の引数 mock_softmax
            一番上の @patch → 3番目の引数 mock_generate

            引数で置き換えた後は、return_valueをこちらで指定。

            今回の、たとえばフィルターは
            progresses = StudentContextProgress.objects.filter(
                student=student,
                total_count__gt=0
            ).select_related("context")

            sorted_contexts = softmax_permute_contexts_from_progresses(list(progresses))
            if not sorted_contexts:
                ...
            でしか処理していないので、まずfilterの方の返し方は最低限リストになれるものでOKだし、またsortedも空値でさえなければ
            支障なしだからOK
        """
        self.login_as_org_admin()

        student = self.class1_1_active_student
        classroom = self.class1_1

        # mock
        mock_scprogress_filter.return_value.select_related.return_value = ["ctx"]
        mock_softmax.return_value = ["sorted_ctx"]

        passage = ListeningPassage.objects.create(
            title="test",
            content="dummy",
            created_by=student,
            source_type="textbook"
        )
        mock_generate.return_value = (passage, 5)

        resp = self.client.post(
            reverse("listening_trainer:quiz_admin_dispatch"),
            data={
                "target_student_id": student.id,
                "classroom_id": classroom.id,
                "quiz_type": "new",
            }
        )

        self.assertEqual(resp.status_code, 302)

        expected_base = reverse("listening_trainer:admin_solve", args=[passage.id])
        self.assertTrue(resp.url.startswith(expected_base))

        self.assertIn(f"classroom_id={classroom.id}", resp.url)
        self.assertIn("batch_id=5", resp.url)
        self.assertIn("is_eiken=0", resp.url)


    @patch("listening_trainer.views.admin_views.generate_and_save_passage_with_questions")
    @patch("listening_trainer.views.admin_views.softmax_permute_contexts_from_progresses")
    @patch("listening_trainer.views.admin_views.StudentContextProgress.objects.filter")
    def test_anonymous_user_redirect_to_login_page(
        self,
        mock_scprogress_filter,
        mock_softmax,
        mock_generate,
        ):
        """
        未ログインユーザーはログインページへリダイレクトされる
        """
        student = self.class1_1_active_student
        classroom = self.class1_1

        # mock
        mock_scprogress_filter.return_value.select_related.return_value = ["ctx"]
        mock_softmax.return_value = ["sorted_ctx"]

        passage = ListeningPassage.objects.create(
            title="test",
            content="dummy",
            created_by=student,
            source_type="textbook"
        )
        mock_generate.return_value = (passage, 5)

        resp = self.client.post(
            reverse("listening_trainer:quiz_admin_dispatch"),
            data={
                "target_student_id": student.id,
                "classroom_id": classroom.id,
                "quiz_type": "new",
            }
        )

        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("accounts_auth:login"))  # ログインページへパラメータなしで遷移

    @patch("listening_trainer.views.admin_views.generate_and_save_passage_with_questions")
    @patch("listening_trainer.views.admin_views.softmax_permute_contexts_from_progresses")
    @patch("listening_trainer.views.admin_views.StudentContextProgress.objects.filter")
    def test_student_cannot_access(
        self,
        mock_scprogress_filter,
        mock_softmax,
        mock_generate,
        ):
        """
        生徒のアクセスは403
        """
        self.login_as_student()
        student = self.class1_1_active_student
        classroom = self.class1_1

        # mock
        mock_scprogress_filter.return_value.select_related.return_value = ["ctx"]
        mock_softmax.return_value = ["sorted_ctx"]

        passage = ListeningPassage.objects.create(
            title="test",
            content="dummy",
            created_by=student,
            source_type="textbook"
        )
        mock_generate.return_value = (passage, 5)

        resp = self.client.post(
            reverse("listening_trainer:quiz_admin_dispatch"),
            data={
                "target_student_id": student.id,
                "classroom_id": classroom.id,
                "quiz_type": "new",
            }
        )

        self.assertEqual(resp.status_code, 403)

    @patch("listening_trainer.views.admin_views.generate_and_save_passage_with_questions")
    @patch("listening_trainer.views.admin_views.softmax_permute_contexts_from_progresses")
    @patch("listening_trainer.views.admin_views.StudentContextProgress.objects.filter")
    def test_access_to_inactive_student_cause_404(
        self,
        mock_scprogress_filter,
        mock_softmax,
        mock_generate,
        ):
        """
        非アクティブ生徒へのアクセスは404
        """
        self.login_as_org_admin()
        student = self.class1_1_inactive_student
        classroom = self.class1_1

        # mock
        mock_scprogress_filter.return_value.select_related.return_value = ["ctx"]
        mock_softmax.return_value = ["sorted_ctx"]

        passage = ListeningPassage.objects.create(
            title="test",
            content="dummy",
            created_by=student,
            source_type="textbook"
        )
        mock_generate.return_value = (passage, 5)

        resp = self.client.post(
            reverse("listening_trainer:quiz_admin_dispatch"),
            data={
                "target_student_id": student.id,
                "classroom_id": classroom.id,
                "quiz_type": "new",
            }
        )

        self.assertEqual(resp.status_code, 404)

    @patch("listening_trainer.views.admin_views.generate_and_save_passage_with_questions")
    @patch("listening_trainer.views.admin_views.softmax_permute_contexts_from_progresses")
    @patch("listening_trainer.views.admin_views.StudentContextProgress.objects.filter")
    def test_access_to_unaccessible_student_cause_403(
        self,
        mock_scprogress_filter,
        mock_softmax,
        mock_generate,
        ):
        """
        管理外の生徒へのアクセスは403
        """
        self.login_as_org_admin()
        student = self.class2_active_student
        classroom = self.class1_1

        # mock
        mock_scprogress_filter.return_value.select_related.return_value = ["ctx"]
        mock_softmax.return_value = ["sorted_ctx"]

        passage = ListeningPassage.objects.create(
            title="test",
            content="dummy",
            created_by=student,
            source_type="textbook"
        )
        mock_generate.return_value = (passage, 5)

        resp = self.client.post(
            reverse("listening_trainer:quiz_admin_dispatch"),
            data={
                "target_student_id": student.id,
                "classroom_id": classroom.id,
                "quiz_type": "new",
            }
        )

        self.assertEqual(resp.status_code, 403)
    
    @patch("listening_trainer.views.admin_views.generate_and_save_passage_with_questions")
    @patch("listening_trainer.views.admin_views.softmax_permute_contexts_from_progresses")
    @patch("listening_trainer.views.admin_views.StudentContextProgress.objects.filter")
    def test_non_existent_quiz_type_returns_generation_failed(
        self,
        mock_scprogress_filter,
        mock_softmax,
        mock_generate,
        ):
        """
        クイズタイプなしのアクセスは生成失敗をレンダリング
        """
        self.login_as_org_admin()
        student = self.class1_1_active_student
        classroom = self.class1_1

        # mock
        mock_scprogress_filter.return_value.select_related.return_value = ["ctx"]
        mock_softmax.return_value = ["sorted_ctx"]

        passage = ListeningPassage.objects.create(
            title="test",
            content="dummy",
            created_by=student,
            source_type="textbook"
        )
        mock_generate.return_value = (passage, 5)

        resp = self.client.post(
            reverse("listening_trainer:quiz_admin_dispatch"),
            data={
                "target_student_id": student.id,
                "classroom_id": classroom.id,
                "quiz_type": "non-existent_quiz_type",
            }
        )

        # generation_failed.htmlへどうつなぐ？→表示されるはずのテンプレートの中身を見る
        self.assertIn("不明な出題タイプです。", resp.context["error_message"])

    @patch("accounts.models.BaseUser.get_role_object")
    @patch("listening_trainer.views.admin_views.generate_and_save_passage_with_questions")
    @patch("listening_trainer.views.admin_views.softmax_permute_contexts_from_progresses")
    @patch("listening_trainer.views.admin_views.StudentContextProgress.objects.filter")
    def test_user_without_role_object_cannot_access(
        self,
        mock_scprogress_filter,
        mock_softmax,
        mock_generate,
        mock_role_object,
        ):
        """
        ロールオブジェクトがNoneのユーザーはアクセス不可
        """
        self.login_as_org_admin()
        student = self.class1_1_active_student
        classroom = self.class1_1

        # mock
        mock_scprogress_filter.return_value.select_related.return_value = ["ctx"]
        mock_softmax.return_value = ["sorted_ctx"]

        passage = ListeningPassage.objects.create(
            title="test",
            content="dummy",
            created_by=student,
            source_type="textbook"
        )
        mock_generate.return_value = (passage, 5)
        mock_role_object.return_value = None
        resp = self.client.post(
            reverse("listening_trainer:quiz_admin_dispatch"),
            data={
                "target_student_id": student.id,
                "classroom_id": classroom.id,
                "quiz_type": "non-existent_quiz_type",
            }
        )
        self.assertEqual(resp.status_code, 403)
