"""
作成日:
    2026/5/11

改定日:

    2026/5/24
        管理者用 quiz_type_select への has_vocab_progress ガード追加に伴う修正
        - AdminBothQuizTypeSelectTest カテゴリ2（通常画面到達テスト）4本: has_vocab_progress=True でpatch追加
        - AdminBothQuizTypeSelectTest カテゴリ3（vocab進捗なし防御テスト）4本: 新規追加


作成経緯:
    - Claudeによるコード精査において、管理者,生徒と通常,英検のいずれのクイズ選択にもテストがないことが指摘
    - 問題選択の入口という既存のテストに必ずしも一致しない枠組みであるため新設

Making:
    - 未認証ユーザー → ログインへのリダイレクト
    - ロール違反（admin が student 用にアクセス、またはその逆）→ 403
    - ソフトデリートされた生徒が自分のページにアクセス → 404
"""

from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from accounts.models import (
    OrganizationAdministrator,
    Organization,
    ClassroomAdministrator,
    Classroom,
    Teacher,
    Student
)
from vocab_trainer.models import (
    EnglishWord,
    JapaneseMeaning,
    WordMeaningRelation,
    Textbook,
    Chapter,
    WordMeaningContext,
    StudentContextProgress,
)


class AdminBothQuizTypeSelectTest(TestCase):
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

        cls.class1_2 = Classroom.objects.create(name="class1_2", organization=cls.org1)
        cls.class1_2_admin = ClassroomAdministrator.objects.create_user(
            username="class1_2_admin",
            email="class1_2_admin@example.com",
            password="pass123456",
            organization=cls.org1,
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

        cls.org2_admin = OrganizationAdministrator.objects.create_user(
            username="org2_admin",
            email="org2_admin@example.com",
            password="pass123456",
        )
        cls.org2_admin.organizations.add(cls.org2)

        cls.class2_teacher = Teacher.objects.create_user(
            username="class2_teacher",
            email="class2_teacher@example.com",
            password="pass123456",
            organization=cls.org2,
        )
        cls.class2_teacher.classrooms.add(cls.class2)

        # 講師は、同一組織内であれば「別教室の生徒」でも担当していればアクセスできる
        cls.class1_2_active_student.teachers.add(cls.class1_1_teacher)

        # データ上は担当関係があっても、異なる組織の生徒はアクセス不可であることを確認するため
        cls.class2_active_student.teachers.add(cls.class1_1_teacher)

        cls.url_to_quiz_type_select = reverse("read_trainer:quiz_type_select_with_admin")
        cls.url_to_eiken_quiz_type_select = reverse("read_trainer:eiken_quiz_type_select_with_admin")
        cls.url_to_login = reverse("accounts_auth:login")

    def login_as_org_admin(self):
        ok = self.client.login(email="org1_admin@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_as_classroom_admin(self):
        ok = self.client.login(email="class1_1_admin@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_as_teacher(self):
        ok = self.client.login(email="class1_1_teacher@example.com", password="pass123456")
        self.assertTrue(ok)
    
    def login_as_student(self):
        ok = self.client.login(email="class1_1_active_student@example.com", password="pass123456")
        self.assertTrue(ok)
    
    def check_normal_and_eiken_with_students(self, students: list[Student], *, expected_code: int) -> None:
        """与えられた生徒群に通常、英検の両方にアクセスし、所定のレスポンスが返ってくるかをチェック

        Args:
            students (list[Student]): チェックしたい生徒群
            expected_code (int): 期待しているレスポンスコード
        """
        for student in students:
            with self.subTest(student.username):
                resp = self.client.get(self.url_to_quiz_type_select, data={"target_student_id": student.id})
                self.assertEqual(resp.status_code, expected_code)
        for student in students:
            with self.subTest(student.username):
                resp = self.client.get(self.url_to_eiken_quiz_type_select, data={"target_student_id": student.id})
                self.assertEqual(resp.status_code, expected_code)

    def test_anonymous_redirect_to_login(self):
        """
        未ログインユーザーはログイン画面へリダイレクト
        """
        resp = self.client.get(self.url_to_quiz_type_select)
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, self.url_to_login)

        resp = self.client.get(self.url_to_eiken_quiz_type_select)
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, self.url_to_login)
    
    def test_student_cannot_access(self):
        """
        管理者用ビューであるため、生徒はログインできない
        """
        self.login_as_student()
        resp = self.client.get(self.url_to_quiz_type_select)
        self.assertEqual(resp.status_code, 403)

        resp = self.client.get(self.url_to_eiken_quiz_type_select)
        self.assertEqual(resp.status_code, 403)
    
    def test_all_users_cannot_access_inactive_student(self):
        """
        あらゆるユーザーは非アクティブ生徒にアクセスできない
        """
        def login_as_inactive_student():
            ok = self.client.login(email="class1_1_inactive_student@example.com", password="pass123456")
            self.assertFalse(ok)

        cases = [
            ("org_admin", self.login_as_org_admin, 404),  # student_access_checkの中のget_object_or_404
            ("classroom_admin", self.login_as_classroom_admin, 404),  # 同上
            ("teacher", self.login_as_teacher, 404),  # 同上
            ("student", self.login_as_student, 403),  # PermissionDenied想定
            ("inactive_student", login_as_inactive_student, 302)  # ログイン失敗→未ログイン扱いになる想定
        ]

        for url in [self.url_to_quiz_type_select, self.url_to_eiken_quiz_type_select]:
            for role_name, login_func, expected_status in cases:
                with self.subTest(role=role_name):
                    self.client.logout()
                    login_func()
                    response = self.client.get(url, data={"target_student_id": self.class1_1_inactive_student.id})
                    self.assertEqual(response.status_code, expected_status)

    def test_org_admin_can_access_student_in_their_org(self):
        """
        組織管理者は自身の管理組織に所属している生徒にアクセス可能
        """
        self.login_as_org_admin()
        students= [
            self.class1_1_active_student,
            self.class1_2_active_student,
        ]
        self.check_normal_and_eiken_with_students(students, expected_code=200)
    
    def test_org_admin_cannot_access_student_in_another_org(self):
        """
        組織管理者は他の組織の生徒にアクセス不可
        """
        self.login_as_org_admin()
        non_organization_student = Student.objects.create(
            username="non_organization_student",
            line_user_id="non_organization_student_line_user_id",
        )
        students = [
            self.class2_active_student,
            non_organization_student
            ]
        self.check_normal_and_eiken_with_students(students, expected_code=403)
    
    def test_classroom_admin_can_access_student_in_their_classroom(self):
        """
        教室管理者は自身の管理教室の生徒にアクセス可能
        """
        self.login_as_classroom_admin()
        students = [self.class1_1_active_student]
        self.check_normal_and_eiken_with_students(students, expected_code=200)

    def test_classroom_admin_cannot_access_student_in_another_org_and_classroom(self):
        """
        教室管理者は他の組織の生徒、および自組織他教室の生徒にアクセス不可
        """
        self.login_as_classroom_admin()
        students = [
            self.class2_active_student,
            self.class1_2_active_student
        ]
        self.check_normal_and_eiken_with_students(students, expected_code=403)

    
    def test_teacher_can_access_assigned_student(self):
        """
        講師は担当している生徒にアクセス可能
        """
        self.login_as_teacher()
        students = [
            self.class1_1_active_student,
            self.class1_2_active_student,
        ]
        self.check_normal_and_eiken_with_students(students, expected_code=200)

    def test_teacher_cannot_access_non_assigned_students(self):
        """
        講師は担当していない生徒、および担当しているが他組織に所属している生徒にはアクセス不可
        """
        self.login_as_teacher()
        unassigned_student = Student.objects.create_user(
            username="unassigned_student@example.com",
            line_user_id="unassigned_student_line_user_id",
            organization=self.org1
        )
        students = [
            unassigned_student,
            self.class2_active_student,
        ]
        self.check_normal_and_eiken_with_students(students, expected_code=403)
    
    # chatgpt
    def test_admin_quiz_type_select_requires_target_student_id(self):
        """
        対象生徒のIDがなければアクセス拒否
        """
        self.login_as_org_admin()

        for url in [self.url_to_quiz_type_select, self.url_to_eiken_quiz_type_select]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 403)
    
    def test_admin_quiz_type_select_rejects_invalid_target_student_id(self):
        """
        不正なIDを指定した場合アクセス拒否
        """
        self.login_as_org_admin()

        for url in [self.url_to_quiz_type_select, self.url_to_eiken_quiz_type_select]:
            with self.subTest(url=url):
                response = self.client.get(url, data={"target_student_id": "not-a-uuid"})
                self.assertEqual(response.status_code, 403)

    @patch("read_trainer.views.admin_views.has_vocab_progress", return_value=True)
    @patch("read_trainer.views.admin_views.select_passages_for_student")
    def test_admin_textbook_select_uses_textbook_source_type(self, mock_select, _):
        """
        教科書タイプの問題へのアクセスでは、きちんと教科書タイプを引数としてselect_passage_for_studentが呼び出されている
        """
        mock_select.return_value = ([], False)
        self.login_as_org_admin()

        response = self.client.get(
            self.url_to_quiz_type_select,
            data={"target_student_id": str(self.class1_1_active_student.id)},
        )

        self.assertEqual(response.status_code, 200)
        mock_select.assert_called_once()
        self.assertEqual(mock_select.call_args.args[0], self.class1_1_active_student)
        self.assertEqual(mock_select.call_args.args[1], "textbook")


    @patch("read_trainer.views.admin_views.has_vocab_progress", return_value=True)
    @patch("read_trainer.views.admin_views.select_passages_for_student")
    def test_admin_eiken_select_uses_eiken_source_type(self, mock_select, _):
        """
        英検タイプの問題では、きちんと英検タイプを引数としてselect_passage_for_studentが呼び出されている
        """
        mock_select.return_value = ([], False)
        self.login_as_org_admin()

        response = self.client.get(
            self.url_to_eiken_quiz_type_select,
            data={"target_student_id": str(self.class1_1_active_student.id)},
        )

        self.assertEqual(response.status_code, 200)
        mock_select.assert_called_once()
        self.assertEqual(mock_select.call_args.args[0], self.class1_1_active_student)
        self.assertEqual(mock_select.call_args.args[1], "eiken")

    @patch("read_trainer.views.admin_views.has_vocab_progress", return_value=True)
    def test_admin_access_for_quiz_type_uses_right_templates_and_contexts(self, _):
        """
        vocab進捗あり生徒に対して管理者が通常のクイズ選択にアクセスした際に
            - 想定したテンプレートが利用
            - コンテキストとして想定した生徒が設定されている
            - 遷移などに利用される教室IDもコンテキストとして渡されている
        ことを確認
        """
        self.login_as_org_admin()
        resp = self.client.get(
            self.url_to_quiz_type_select,
            data={
                "target_student_id": self.class1_1_active_student.id,
                "classroom_id": self.class1_1.id}
            )
        self.assertTemplateUsed(resp, "read_trainer/for_admin/quiz_type_select.html")
        self.assertEqual(resp.context["student"], self.class1_1_active_student)
        self.assertEqual(resp.context["classroom_id"], str(self.class1_1.id))

    @patch("read_trainer.views.admin_views.has_vocab_progress", return_value=True)
    def test_admin_access_for_eiken_quiz_type_uses_right_templates_and_contexts(self, _):
        """
        vocab進捗あり生徒に対して管理者が英検クイズ選択にアクセスした際に
            - 想定したテンプレートが利用
            - コンテキストとして想定した生徒が設定されている
            - 遷移などに利用される教室IDもコンテキストとして渡されている
        ことを確認
        """
        self.login_as_org_admin()
        resp = self.client.get(
            self.url_to_eiken_quiz_type_select,
            data={
                "target_student_id": self.class1_1_active_student.id,
                "classroom_id": self.class1_1.id}
            )
        self.assertTemplateUsed(resp, "read_trainer/for_admin/eiken_quiz_type_select.html")
        self.assertEqual(resp.context["student"], self.class1_1_active_student)
        self.assertEqual(resp.context["classroom_id"], str(self.class1_1.id))

    def test_admin_quiz_type_select_returns_no_vocab_when_no_progress(self):
        """vocab進捗なし生徒に対して管理者が通常の quiz_type_select にアクセスすると no_vocab_available.html が表示される"""
        self.login_as_org_admin()
        resp = self.client.get(
            self.url_to_quiz_type_select,
            data={"target_student_id": self.class1_1_active_student.id},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "read_trainer/for_admin/no_vocab_available.html")

    def test_admin_eiken_quiz_type_select_returns_no_vocab_when_no_progress(self):
        """vocab進捗なし生徒に対して管理者が英検 quiz_type_select にアクセスすると no_vocab_available.html が表示される"""
        self.login_as_org_admin()
        resp = self.client.get(
            self.url_to_eiken_quiz_type_select,
            data={"target_student_id": self.class1_1_active_student.id},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "read_trainer/for_admin/no_vocab_available.html")

    @patch("read_trainer.views.admin_views.select_passages_for_student")
    def test_admin_quiz_type_select_does_not_select_passages_without_vocab_progress(self, mock_select):
        """vocab進捗なし生徒に対して管理者がアクセスした場合、select_passages_for_student は一切呼ばれない"""
        self.login_as_org_admin()
        resp = self.client.get(
            self.url_to_quiz_type_select,
            data={"target_student_id": self.class1_1_active_student.id},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "read_trainer/for_admin/no_vocab_available.html")
        mock_select.assert_not_called()

    @patch("read_trainer.views.admin_views.select_passages_for_student")
    def test_admin_eiken_quiz_type_select_does_not_select_passages_without_vocab_progress(self, mock_select):
        """vocab進捗なし生徒に対して管理者が英検でアクセスした場合、select_passages_for_student は一切呼ばれない"""
        self.login_as_org_admin()
        resp = self.client.get(
            self.url_to_eiken_quiz_type_select,
            data={"target_student_id": self.class1_1_active_student.id},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "read_trainer/for_admin/no_vocab_available.html")
        mock_select.assert_not_called()

    @patch("read_trainer.views.admin_views.select_passages_for_student")
    def test_admin_quiz_type_select_reaches_normal_page_when_target_student_has_vocab_progress(self, mock_select):
        """
        管理者用 quiz_type_select では、
        target_student_id の生徒に vocab 進捗があれば通常画面に到達する
        """
        english_word = EnglishWord.objects.create(word="apple_admin")
        japanese_meaning = JapaneseMeaning.objects.create(meaning="りんご_admin")
        relation = WordMeaningRelation.objects.create(
            english_word=english_word,
            japanese_meaning=japanese_meaning,
        )

        textbook = Textbook.objects.create(
            name="Test Textbook Admin",
            publisher="Test Publisher",
            grade=1,
            publication_year=2026,
        )
        chapter = Chapter.objects.create(
            textbook=textbook,
            title="Unit 1",
            order=1,
        )
        context = WordMeaningContext.objects.create(
            relation=relation,
            chapter=chapter,
            grade=1,
        )

        StudentContextProgress.objects.create(
            student=self.class1_1_active_student,
            context=context,
            correct_count=1,
            total_count=1,
            accuracy_rate=1.0,
        )

        mock_select.return_value = ([], False)

        self.login_as_org_admin()
        resp = self.client.get(
            self.url_to_quiz_type_select,
            data={"target_student_id": str(self.class1_1_active_student.id)},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "read_trainer/for_admin/quiz_type_select.html")
        mock_select.assert_called_once()
        self.assertEqual(mock_select.call_args.args[0], self.class1_1_active_student)
        self.assertEqual(mock_select.call_args.args[1], "textbook")


class StudentBothQuizTypeSelectTest(TestCase):
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

        cls.class1_2 = Classroom.objects.create(name="class1_2", organization=cls.org1)
        cls.class1_2_admin = ClassroomAdministrator.objects.create_user(
            username="class1_2_admin",
            email="class1_2_admin@example.com",
            password="pass123456",
            organization=cls.org1,
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

        cls.org2_admin = OrganizationAdministrator.objects.create_user(
            username="org2_admin",
            email="org2_admin@example.com",
            password="pass123456",
        )
        cls.org2_admin.organizations.add(cls.org2)

        cls.class2_teacher = Teacher.objects.create_user(
            username="class2_teacher",
            email="class2_teacher@example.com",
            password="pass123456",
            organization=cls.org2,
        )
        cls.class2_teacher.classrooms.add(cls.class2)

        cls.class1_2_active_student.teachers.add(cls.class1_1_teacher)

        cls.class2_active_student.teachers.add(cls.class1_1_teacher)

        cls.url_to_quiz_type_select = reverse("read_trainer:quiz_type_select_for_student")
        cls.url_to_eiken_quiz_type_select = reverse("read_trainer:eiken_quiz_type_select_for_student")
        cls.url_to_login = reverse("accounts_auth:login")

    def login_as_org_admin(self):
        ok = self.client.login(email="org1_admin@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_as_classroom_admin(self):
        ok = self.client.login(email="class1_1_admin@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_as_teacher(self):
        ok = self.client.login(email="class1_1_teacher@example.com", password="pass123456")
        self.assertTrue(ok)
    
    def login_as_student(self):
        ok = self.client.login(email="class1_1_active_student@example.com", password="pass123456")
        self.assertTrue(ok)
    
    def assert_student_can_access_both_quiz_type_selects(self, expected_code: int) -> None:
        """通常、英検の両方にアクセスし、所定のレスポンスが返ってくるかをチェック

        Args:
            expected_code (int): 期待しているレスポンスコード
        """
        resp = self.client.get(self.url_to_quiz_type_select)
        self.assertEqual(resp.status_code, expected_code)
        resp = self.client.get(self.url_to_eiken_quiz_type_select)
        self.assertEqual(resp.status_code, expected_code)

    def test_anonymous_redirect_to_login(self):
        """
        未ログインユーザーはログイン画面へリダイレクト
        """
        resp = self.client.get(self.url_to_quiz_type_select)
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, self.url_to_login)

        resp = self.client.get(self.url_to_eiken_quiz_type_select)
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, self.url_to_login)
    
    def test_admin_and_teacher_cannot_access(self):
        """
        生徒用ビューなので、管理者や講師はアクセス不可
        """
        admin_and_teachers = [
            ("org_admin", self.login_as_org_admin, 403),
            ("classroom_admin", self.login_as_classroom_admin, 403),
            ("teacher", self.login_as_teacher, 403), 
        ]
        for url in [self.url_to_quiz_type_select, self.url_to_eiken_quiz_type_select]:
            for role_name, login_func, expected_status in admin_and_teachers:
                with self.subTest(role=role_name):
                    self.client.logout()
                    login_func()
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, expected_status)
    
    def test_student_can_access_self(self):
        """
        生徒は自分自身にアクセス可能
        """
        self.login_as_student()
        self.assert_student_can_access_both_quiz_type_selects(expected_code=200)
    
    # chatgpt
    
    @patch("read_trainer.views.student_views.has_vocab_progress", return_value=True)
    def test_student_target_student_id_is_ignored(self, _):
        """
        生徒用ビューでは target_student_id を信用せず、
        常にログイン中の生徒本人を使う
        """
        self.login_as_student()

        other_students = [
            self.class1_2_active_student,
            self.class2_active_student,
            self.class1_1_inactive_student,
        ]

        urls = [
            ("textbook", self.url_to_quiz_type_select),
            ("eiken", self.url_to_eiken_quiz_type_select),
        ]

        for url_name, url in urls:
            for other_student in other_students:
                with self.subTest(url=url_name, target_student=other_student.username):
                    response = self.client.get(
                        url,
                        data={"target_student_id": str(other_student.id)},
                    )

                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.context["student"].id, self.class1_1_active_student.id)



    @patch("read_trainer.views.student_views.has_vocab_progress", return_value=True)
    def test_student_access_for_quiz_type_uses_right_templates_and_contexts(self, _):
        """
        vocab進捗あり生徒が通常のクイズ選択にアクセスした際に
            - 想定したテンプレートが利用
            - コンテキストとして想定した生徒が設定されている
        ことを確認
        """
        self.login_as_student()
        resp = self.client.get(self.url_to_quiz_type_select, data={"target_student_id": self.class1_1_active_student.id})
        self.assertTemplateUsed(resp, "read_trainer/for_student/quiz_type_select.html")
        self.assertEqual(resp.context["student"], self.class1_1_active_student)

    @patch("read_trainer.views.student_views.has_vocab_progress", return_value=True)
    def test_student_access_for_eiken_quiz_type_uses_right_templates_and_contexts(self, _):
        """
        vocab進捗あり生徒が英検クイズ選択にアクセスした際に
            - 想定したテンプレートが利用
            - コンテキストとして想定した生徒が設定されている
        ことを確認
        """
        self.login_as_student()
        resp = self.client.get(self.url_to_eiken_quiz_type_select, data={"target_student_id": self.class1_1_active_student.id})
        self.assertTemplateUsed(resp, "read_trainer/for_student/eiken_quiz_type_select.html")
        self.assertEqual(resp.context["student"], self.class1_1_active_student)

    @patch("read_trainer.views.student_views.has_vocab_progress", return_value=True)
    @patch("read_trainer.views.student_views.select_passages_for_student")
    def test_student_textbook_select_uses_textbook_source_type(self, mock_select, _):
        """
        vocab進捗あり生徒の通常アクセスでは textbook を引数に select_passages_for_student が呼ばれる
        """
        mock_select.return_value = ([], False)
        self.login_as_student()

        response = self.client.get(self.url_to_quiz_type_select)

        self.assertEqual(response.status_code, 200)
        mock_select.assert_called_once()
        self.assertEqual(mock_select.call_args.args[0], self.class1_1_active_student)
        self.assertEqual(mock_select.call_args.args[1], "textbook")

    @patch("read_trainer.views.student_views.has_vocab_progress", return_value=True)
    @patch("read_trainer.views.student_views.select_passages_for_student")
    def test_student_eiken_select_uses_eiken_source_type(self, mock_select, _):
        """
        vocab進捗あり生徒の英検アクセスでは eiken を引数に select_passages_for_student が呼ばれる
        """
        mock_select.return_value = ([], False)
        self.login_as_student()

        response = self.client.get(self.url_to_eiken_quiz_type_select)

        self.assertEqual(response.status_code, 200)
        mock_select.assert_called_once()
        self.assertEqual(mock_select.call_args.args[0], self.class1_1_active_student)
        self.assertEqual(mock_select.call_args.args[1], "eiken")

    def test_student_quiz_type_select_returns_no_vocab_when_no_progress(self):
        """vocab進捗なし生徒が通常の quiz_type_select にアクセスすると no_vocab_available が表示される"""
        self.login_as_student()
        resp = self.client.get(self.url_to_quiz_type_select)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "read_trainer/for_student/no_vocab_available.html")

    def test_student_eiken_quiz_type_select_returns_no_vocab_when_no_progress(self):
        """vocab進捗なし生徒が英検 quiz_type_select にアクセスすると no_vocab_available が表示される"""
        self.login_as_student()
        resp = self.client.get(self.url_to_eiken_quiz_type_select)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "read_trainer/for_student/no_vocab_available.html")

    @patch("read_trainer.views.student_views.select_passages_for_student")
    def test_student_quiz_type_select_does_not_select_passages_without_vocab_progress(self, mock_select):
        """
        進捗がない場合、select_passageは何も返さない
        """
        self.login_as_student()

        resp = self.client.get(self.url_to_quiz_type_select)

        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "read_trainer/for_student/no_vocab_available.html")
        mock_select.assert_not_called()

    @patch("read_trainer.views.student_views.select_passages_for_student")
    def test_student_eiken_quiz_type_select_does_not_select_passages_without_vocab_progress(self, mock_select):
        """
        進捗がない場合、select_passageは何も返さない
        """
        self.login_as_student()

        resp = self.client.get(self.url_to_eiken_quiz_type_select)

        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "read_trainer/for_student/no_vocab_available.html")
        mock_select.assert_not_called()

    @patch("read_trainer.views.student_views.select_passages_for_student")
    def test_student_quiz_type_select_reaches_normal_page_when_vocab_progress_exists(self, mock_select):
        """
        実DB上に vocab 進捗がある生徒は、
        has_vocab_progress を mock しなくても通常の quiz_type_select に到達する
        """
        english_word = EnglishWord.objects.create(word="apple")
        japanese_meaning = JapaneseMeaning.objects.create(meaning="りんご")
        relation = WordMeaningRelation.objects.create(
            english_word=english_word,
            japanese_meaning=japanese_meaning,
        )

        textbook = Textbook.objects.create(
            name="Test Textbook",
            publisher="Test Publisher",
            grade=1,
            publication_year=2026,
        )
        chapter = Chapter.objects.create(
            textbook=textbook,
            title="Unit 1",
            order=1,
        )
        context = WordMeaningContext.objects.create(
            relation=relation,
            chapter=chapter,
            grade=1,
        )

        StudentContextProgress.objects.create(
            student=self.class1_1_active_student,
            context=context,
            correct_count=1,
            total_count=1,
            accuracy_rate=1.0,
        )

        mock_select.return_value = ([], False)

        self.login_as_student()
        resp = self.client.get(self.url_to_quiz_type_select)

        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "read_trainer/for_student/quiz_type_select.html")
        mock_select.assert_called_once()
        self.assertEqual(mock_select.call_args.args[0], self.class1_1_active_student)
        self.assertEqual(mock_select.call_args.args[1], "textbook")