import logging

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import (
Organization,
Classroom,
OrganizationAdministrator,
ClassroomAdministrator,
Teacher,
Student,
)


class StudentEditViewTest(TestCase):
    """
    生徒詳細ビューのテスト

    Developing:
        anonymous は 302
        student ロールは 403
        teacher: 担当生徒 200
        teacher: 担当外生徒 404
        classroom admin: 自教室生徒 200
        classroom admin: 教室外生徒 404
        organization admin: 同一組織の複数生徒を 200 で取得できる
        inactive student は 404
        あれば十分
        organization admin: 同一組織の別教室生徒も 200
    """

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Org")
        cls.classroom1 = Classroom.objects.create(name="Class1", organization=cls.org)
        cls.classroom2 = Classroom.objects.create(name="Class2", organization=cls.org)
        cls.other_org = Organization.objects.create(name="OtherOrg")

        # --- ログイン用ユーザー ---
        cls.org_admin = OrganizationAdministrator.objects.create_user(
            email="org_admin@example.com",
            username="org_admin",
            password="pass123456",
            role="organization_administrator",
            organization=cls.org,
        )

        cls.class_admin = ClassroomAdministrator.objects.create_user(
            email="class_admin@example.com",
            username="class_admin",
            password="pass123456",
            role="classroom_administrator",
            organization=cls.org,
            is_first_login=False,
        )
        cls.class_admin.classrooms.add(cls.classroom1)

        cls.teacher = Teacher.objects.create_user(
            email="teacher@example.com",
            password="pass123456",
            organization=cls.org,
            is_first_login=False,
        )

        cls.student_user = Student.objects.create_user(
            email="student_user@example.com",
            password="pass123456",
            line_user_id="student_user_line_id",
            organization=cls.org,
            is_first_login=False,
        )

        # チェック対象生徒
        cls.target_student1 = Student.objects.create_user(
            email="target_student1@example.com",
            password="pass123456",
            line_user_id="target_student1_line_id",
            organization=cls.org,
        )
        cls.target_student1.classrooms.add(cls.classroom1)
        cls.target_student1.teachers.add(cls.teacher)

        # チェック対象生徒(教室外+組織内)
        cls.target_student2 = Student.objects.create_user(
            email="target_student2@example.com",
            password="pass123456",
            line_user_id="target_student2_line_id",
            organization=cls.org,
        )
        cls.target_student2.classrooms.add(cls.classroom2)

        # チェック対象生徒(教室所属+組織外)
        cls.target_student3 = Student.objects.create_user(
            email="target_student3@example.com",
            password="pass123456",
            line_user_id="target_student3_line_id",
            organization=cls.other_org,
        )

        cls.target_student4 = Student.objects.create_user(
            email="target_student4@example.com",
            password="pass123456",
            line_user_id="target_student4_line_id",
            organization=cls.org,
            is_active=False
        )

        # アクセスURL
        cls.url_to_target_student1_edit = reverse(
            "organization_admin:student_edit",
            kwargs={"pk": cls.target_student1.id}
        )
        cls.url_to_target_student2_edit = reverse(
            "organization_admin:student_edit",
            kwargs={"pk": cls.target_student2.id}
        )
        cls.url_to_target_student3_edit = reverse(
            "organization_admin:student_edit",
            kwargs={"pk": cls.target_student3.id}
        )
        cls.url_to_target_student4_edit = reverse(
            "organization_admin:student_edit",
            kwargs={"pk": cls.target_student4.id}
        )


    def login_as_org_admin(self):
        ok = self.client.login(email="org_admin@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_as_class_admin(self):
        ok = self.client.login(email="class_admin@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_as_teacher(self):
        ok = self.client.login(email="teacher@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_as_student_user(self):
        ok = self.client.login(email="student_user@example.com", password="pass123456")
        self.assertTrue(ok)
    
    def logout_correctly(self):
        self.client.logout()

    def test_org_admin_can_access_all_students(self):
        """
        組織管理者は教室を問わず、自身の組織に所属している全ての生徒へアクセス可能
        """
        self.login_as_org_admin()
        urls = [self.url_to_target_student1_edit, self.url_to_target_student2_edit]
        for url in urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200)
    
    def test_org_admin_cannot_access_other_org_students(self):
        """
        自身の組織に所属しない生徒へはアクセス不可
        """
        self.login_as_org_admin()
        resp = self.client.get(self.url_to_target_student3_edit)
        self.assertEqual(resp.status_code, 404)

    def test_class_admin_can_access_only_belonged_students(self):
        """
        教室管理者は自身の教室に所属している生徒のみアクセス可能
        """
        self.login_as_class_admin()
        resp = self.client.get(self.url_to_target_student1_edit)
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(self.url_to_target_student2_edit)
        self.assertEqual(resp.status_code, 404)
        resp = self.client.get(self.url_to_target_student3_edit)
        self.assertEqual(resp.status_code, 404)

    def test_teacher_cannot_access_any_students(self):
        """
        教師はいずれへも権限なしとして拒否
        """
        self.login_as_teacher()
        urls = [self.url_to_target_student1_edit, self.url_to_target_student2_edit, self.url_to_target_student3_edit, self.url_to_target_student4_edit]
        for url in urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 403)

    def test_student_cannot_access_any_students(self):
        """
        生徒はいずれへも権限なしとして拒否
        """
        self.login_as_student_user()
        urls = [self.url_to_target_student1_edit, self.url_to_target_student2_edit, self.url_to_target_student3_edit, self.url_to_target_student4_edit]
        for url in urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 403)
    
    def test_inactive_student_cannot_be_accessed(self):
        """
        非アクティブになった生徒はいずれのユーザーからもアクセスされない
        """
        self.login_as_org_admin()
        resp = self.client.get(self.url_to_target_student4_edit)
        self.assertEqual(resp.status_code, 404)
        self.logout_correctly()
        self.login_as_class_admin()
        resp = self.client.get(self.url_to_target_student4_edit)
        self.assertEqual(resp.status_code, 404)
        self.logout_correctly()
        self.login_as_teacher()
        resp = self.client.get(self.url_to_target_student4_edit)
        self.assertEqual(resp.status_code, 403)
        self.logout_correctly()

    def test_anonymous_user_is_redirected_to_login(self):
        """
        未ログインユーザーはログインページにリダイレクトされる
        """
        resp = self.client.get(self.url_to_target_student1_edit)
        self.assertEqual(resp.status_code, 302)
        expected_url = f'{reverse("accounts_auth:login")}?next={self.url_to_target_student1_edit}'
        self.assertRedirects(resp, expected_url)


class StudentEditViewFormValidOrganizationMismatchLogTest(TestCase):
    """
    StudentEditView.form_valid 周辺の組織整合性と、
    講師の所属教室自動追加処理を検証する。

    issue #126 では、form_valid 内に存在していた講師・教室の
    組織不整合チェックを到達不能な重複処理として削除した。

    不整合は以下の既存ガードで防止される。
    - 既存の講師不整合: Student.clean()
    - POSTで新たに指定する講師不整合: teachersフィールドのqueryset検証
    - 教室M2M追加時の不整合: validate_student_classroomsシグナル
    - 講師M2M追加時の不整合: validate_student_teachersシグナル（issue #140で追加）

    削除後も維持する teacher.classrooms の自動追加処理については、
    正常系のregression testで直接保証する。
    """

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="MismatchOrg")
        cls.other_org = Organization.objects.create(name="MismatchOtherOrg")
        cls.classroom = Classroom.objects.create(name="MismatchClass", organization=cls.org)
        cls.other_classroom = Classroom.objects.create(name="MismatchOtherClass", organization=cls.other_org)

        cls.org_admin = OrganizationAdministrator.objects.create_user(
            email="mismatch_org_admin@example.com",
            username="mismatch_org_admin",
            password="pass123456",
            role="organization_administrator",
            organization=cls.org,
        )

        cls.teacher_same_org = Teacher.objects.create_user(
            email="mismatch_teacher_same@example.com",
            username="mismatch_teacher_same",
            password="pass123456",
            organization=cls.org,
            is_first_login=False,
        )
        cls.teacher_other_org = Teacher.objects.create_user(
            email="mismatch_teacher_other@example.com",
            username="mismatch_teacher_other",
            password="pass123456",
            organization=cls.other_org,
            is_first_login=False,
        )

    def login_as_org_admin(self):
        ok = self.client.login(email="mismatch_org_admin@example.com", password="pass123456")
        self.assertTrue(ok)

    def _edit_url(self, student):
        return reverse("organization_admin:student_edit", kwargs={"pk": student.id})

    def _post_data(self, teacher_ids):
        return {
            "username": "mismatch_target_student",
            "grade": 7,
            "email": "mismatch_target_student@example.com",
            "teachers": teacher_ids,
        }

    def test_teacher_mismatch_log_is_unreachable_because_model_clean_rejects_first(self):
        """
        既存DB上で別組織の講師が割り当てられている場合、
        Student.clean() がフォームを無効にすることを確認する。

        issue #126で削除したform_valid内の不整合チェックより前に働く
        モデル側ガードのregression test。

        issue #140でvalidate_student_teachersシグナルを追加したことにより、
        student.teachers.add(組織が異なる講師) はM2M書き込み時点でValidationErrorに
        なるようになった。そのため「既存データとして既に不整合が存在する」状態を、
        StudentCleanMethodTests（test_org_classroom_constraints.py）と同様の手法
        （追加時点ではteacher_other_orgと同じorganizationにしてシグナルのpre_addガードを
        通過させ、事後的にorganizationだけを書き換えて不整合を再現する）で作為的に構築する。
        """
        student = Student.objects.create_user(
            email="mismatch_target_student@example.com",
            username="mismatch_target_student",
            password="pass123456",
            line_user_id="mismatch_target_student_line_id",
            organization=self.other_org,
        )
        # 追加時点ではteacher_other_orgと同じorganizationにしておき、
        # validate_student_teachersシグナル(issue #140)のpre_addガードを通過させる
        student.teachers.add(self.teacher_other_org)

        # 事後的にorganizationだけを書き換えて「既存データの不整合」を再現する
        # （シグナルはpre_add時のみ発火するため、この直接代入では検出されない）
        student.organization = self.org
        student.save(update_fields=["organization"])

        self.login_as_org_admin()
        logger = logging.getLogger("accounts.views.organization_admin_views")
        with self.assertNoLogs(logger, level="ERROR"):
            resp = self.client.post(
                self._edit_url(student),
                data=self._post_data([self.teacher_same_org.id]),
            )

        self.assertEqual(resp.status_code, 200)
        self.assertIn("teachers", resp.context["form"].errors)
        self.assertIn(
            "生徒の所属組織と異なる組織の講師が含まれています。",
            resp.context["form"].errors["teachers"],
        )
        # フォームが無効なので保存されず、不整合データはそのまま残っている
        self.assertEqual(list(student.teachers.all()), [self.teacher_other_org])

    def test_classroom_mismatch_cannot_even_be_written_due_to_m2m_changed_signal(self):
        """
        生徒と異なる組織の教室をstudent.classroomsに追加しようとすると、
        accounts/signals.pyのvalidate_student_classroomsシグナル(m2m_changed)が
        ValidationErrorを送出し、書き込みを拒否することを確認する。

        issue #126で削除したform_valid内の不整合チェックより前に働く
        M2M書き込み時ガードのregression test。
        """
        student = Student.objects.create_user(
            email="mismatch_target_student@example.com",
            username="mismatch_target_student",
            password="pass123456",
            line_user_id="mismatch_target_student_line_id2",
            organization=self.org,
        )
        student.teachers.add(self.teacher_same_org)

        with self.assertRaises(ValidationError):
            student.classrooms.add(self.other_classroom)

    def test_teacher_classrooms_are_auto_synced_with_student_classrooms(self):
        """
        生徒編集フォームを送信すると、担当講師の所属教室に
        生徒の所属教室が自動追加されることを確認する。

        issue #126で削除しなかったteacher.classrooms.add(classroom)の
        自動追加処理を直接保証するregression test。
        """
        student = Student.objects.create_user(
            email="mismatch_target_student@example.com",
            username="mismatch_target_student",
            password="pass123456",
            line_user_id="mismatch_target_student_line_id3",
            organization=self.org,
        )
        student.teachers.add(self.teacher_same_org)
        student.classrooms.add(self.classroom)

        # 前提: この時点では教師はまだ自教室として持っていない
        self.assertFalse(
            self.teacher_same_org.classrooms.filter(id=self.classroom.id).exists()
        )

        self.login_as_org_admin()
        resp = self.client.post(
            self._edit_url(student),
            data=self._post_data([self.teacher_same_org.id]),
        )

        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            self.teacher_same_org.classrooms.filter(id=self.classroom.id).exists()
        )

    def test_teacher_mismatch_id_outside_queryset_is_rejected_by_field_validation(self):
        """
        別組織の講師IDを、StudentEditFormのteachersフィールドの
        queryset外から直接POSTしても保存されないことを確認する。

        issue #126で不整合チェックを削除しても安全である根拠のひとつ
        （teachersフィールドのqueryset絞り込みによる拒否）を保証する
        regression test。
        """
        student = Student.objects.create_user(
            email="mismatch_target_student@example.com",
            username="mismatch_target_student",
            password="pass123456",
            line_user_id="mismatch_target_student_line_id5",
            organization=self.org,
        )

        self.login_as_org_admin()
        resp = self.client.post(
            self._edit_url(student),
            data=self._post_data([self.teacher_other_org.id]),
        )

        self.assertEqual(resp.status_code, 200)
        form = resp.context["form"]
        self.assertNotIn(self.teacher_other_org, form.fields["teachers"].queryset)
        self.assertIn("teachers", form.errors)
        # フォームが無効なのでDBは変化しない
        self.assertEqual(list(student.teachers.all()), [])
