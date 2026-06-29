from django.test import TestCase
from django.shortcuts import reverse
import uuid
from unittest.mock import patch
from django.contrib.messages import get_messages


from accounts.models import (
    Student,
    Teacher,
    ClassroomAdministrator,
    OrganizationAdministrator,
    Classroom,
    Organization
)


class StudentReactivateViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org1 = Organization.objects.create(name="org1")
        cls.org1_admin = OrganizationAdministrator.objects.create_user(
            username="org1_admin",
            email="org1_admin@example.com",
            password="pass123456",
        )
        cls.org1_admin.organizations.add(cls.org1)

        cls.class1_1 = Classroom.objects.create(name="class1_1", organization=cls.org1)
        cls.class1_1_admin = ClassroomAdministrator.objects.create_user(
            username="class1_1_admin",
            email="class1_1_admin@example.com",
            password="pass123456",
            organization=cls.org1,
            is_first_login=False,
        )
        cls.class1_1_admin.classrooms.add(cls.class1_1)
        cls.class1_1_teacher = Teacher.objects.create_user(
            username="class1_1_teacher",
            email="class1_1_teacher@example.com",
            password="pass123456",
            organization=cls.org1,
            is_first_login=False,
        )
        cls.class1_1_teacher.classrooms.add(cls.class1_1)

        cls.class1_1_active_student = Student.objects.create_user(
            username="class1_1_active_student",
            email="class1_1_active_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=True,
            line_user_id="line_id_class1_1_active_student",
            is_first_login=False,
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


    # dispatchのテスト
    def test_anonymous_get_redirect_to_login(self):
        """
        未ログインユーザーはgetでログイン画面へアクセスするとnext付きでリダイレクト
        """
        resp = self.client.get(self.url_to_class1_1)
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(
            resp,
            f'{reverse("accounts_auth:login")}?next={reverse("organization_admin:student_reactivate", kwargs={"classroom_id": self.class1_1.id})}'
        )

    def test_anonymous_post_redirect_to_login(self):
        """
        未ログインユーザーはpostでログイン画面へアクセスしてもnext付きでリダイレクト
        """
        resp = self.client.post(self.url_to_class1_1)
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(
            resp,
            f'{reverse("accounts_auth:login")}?next={reverse("organization_admin:student_reactivate", kwargs={"classroom_id": self.class1_1.id})}'
        )

    def test_student_cannot_access_by_get(self):
        """
        生徒はgetでアクセス不可
        """
        ok = self.client.login(email="class1_1_active_student@example.com", password="pass123456")
        self.assertTrue(ok)
        resp = self.client.get(self.url_to_class1_1)
        self.assertEqual(resp.status_code, 403)

    def test_student_cannot_access_by_post(self):
        """
        生徒はpostでアクセス不可
        """
        ok = self.client.login(email="class1_1_active_student@example.com", password="pass123456")
        self.assertTrue(ok)
        resp = self.client.post(self.url_to_class1_1)
        self.assertEqual(resp.status_code, 403)
    
    def test_teacher_cannot_access_by_get(self):
        """
        講師はgetでアクセス不可
        """
        ok = self.client.login(email="class1_1_teacher@example.com", password="pass123456")
        self.assertTrue(ok)
        resp = self.client.get(self.url_to_class1_1)
        self.assertEqual(resp.status_code, 403)

    def test_teacher_cannot_access_by_post(self):
        """
        講師はpostでアクセス不可
        """
        ok = self.client.login(email="class1_1_teacher@example.com", password="pass123456")
        self.assertTrue(ok)
        resp = self.client.post(self.url_to_class1_1)
        self.assertEqual(resp.status_code, 403)

    def test_class_admin_can_access_by_get(self):
        """
        教室管理者はgetでアクセス可能
        """
        self.login_as_classroom_admin()
        resp = self.client.get(self.url_to_class1_1)
        self.assertEqual(resp.status_code, 200)

    def test_org_admin_can_access_by_get(self):
        """
        組織管理者はgetでアクセス可能
        """
        self.login_as_org_admin()
        resp = self.client.get(self.url_to_class1_1)
        self.assertEqual(resp.status_code, 200)

    def test_class_admin_can_see_inactive_students(self):
        """
        教室管理者は教室に所属している非アクティブ生徒を閲覧可能
        """
        self.login_as_classroom_admin()
        resp = self.client.get(self.url_to_class1_1)
        students = resp.context["students"]
        self.assertNotIn(self.class1_1_active_student, students)
        self.assertIn(self.class1_1_inactive_student, students)
        self.assertIn(self.class1_1_inactive_student_without_teacher, students)
        self.assertNotIn(self.class1_2_active_student, students)
        self.assertNotIn(self.class1_2_inactive_student, students)
        self.assertNotIn(self.class1_not_active_student, students)
        self.assertNotIn(self.class1_not_inactive_student, students)
        self.assertNotIn(self.class2_active_student, students)
        self.assertNotIn(self.class2_inactive_student, students)
        self.assertEqual(students.count(), 2)

    def test_org_admin_can_see_inactive_students(self):
        """
        組織管理者は教室に所属している非アクティブの生徒を閲覧可能
        """
        self.login_as_org_admin()
        resp = self.client.get(self.url_to_class1_1)
        students = resp.context["students"]
        self.assertNotIn(self.class1_1_active_student, students)
        self.assertIn(self.class1_1_inactive_student, students)
        self.assertIn(self.class1_1_inactive_student_without_teacher, students)
        self.assertNotIn(self.class1_2_active_student, students)
        self.assertNotIn(self.class1_2_inactive_student, students)
        self.assertNotIn(self.class1_not_active_student, students)
        self.assertNotIn(self.class1_not_inactive_student, students)
        self.assertNotIn(self.class2_active_student, students)
        self.assertNotIn(self.class2_inactive_student, students)
        self.assertEqual(students.count(), 2)

    def test_classroom_admin_can_reactivate_inactive_students(self):
        """
        教室管理者は、指定された生徒をアクティブ化可能
        """
        self.login_as_classroom_admin()
        students_ids = [self.class1_1_inactive_student.id, self.class1_1_inactive_student_without_teacher.id]
        resp = self.client.post(self.url_to_class1_1, data={"student_id": students_ids})
        self.assertEqual(resp.status_code, 302)
        self.class1_1_inactive_student.refresh_from_db()
        self.class1_1_inactive_student_without_teacher.refresh_from_db()
        self.assertTrue(self.class1_1_inactive_student.is_active)
        self.assertTrue(self.class1_1_inactive_student_without_teacher.is_active)

    def test_org_admin_can_reactivate_inactive_students(self):
        """
        組織管理者は、指定された生徒をアクティブ化可能
        """
        self.login_as_org_admin()
        students_ids = [self.class1_1_inactive_student.id, self.class1_1_inactive_student_without_teacher.id]
        resp = self.client.post(self.url_to_class1_1, data={"student_id": students_ids})
        self.assertEqual(resp.status_code, 302)
        self.class1_1_inactive_student.refresh_from_db()
        self.class1_1_inactive_student_without_teacher.refresh_from_db()
        self.assertTrue(self.class1_1_inactive_student.is_active)
        self.assertTrue(self.class1_1_inactive_student_without_teacher.is_active)

    def test_classroom_admin_do_not_reactivate_inactive_students_in_another_classroom(self):
        """
        教室管理者は、対象となっていない教室の生徒が混じっても勝手にアクティブ化しない
        """
        self.login_as_classroom_admin()
        students_ids = [self.class1_2_inactive_student.id] 
        resp = self.client.post(self.url_to_class1_1, data={"student_id": students_ids})
        self.assertEqual(resp.status_code, 302)
        self.class1_2_inactive_student.refresh_from_db()
        self.assertFalse(self.class1_2_inactive_student.is_active)

    def test_org_admin_do_not_reactivate_inactive_students_in_another_classroom(self):
        """
        組織管理者は、対象となっていない教室の生徒が混じっても勝手にアクティブ化しない
        """
        self.login_as_org_admin()
        students_ids = [self.class1_2_inactive_student.id] 
        resp = self.client.post(self.url_to_class1_1, data={"student_id": students_ids})
        self.assertEqual(resp.status_code, 302)
        self.class1_2_inactive_student.refresh_from_db()
        self.assertFalse(self.class1_2_inactive_student.is_active)

    def test_classroom_admin_do_not_reactivate_inactive_students_in_another_organization(self):
        """
        教室管理者は、他組織の生徒が混じっても勝手にアクティブ化しない
        """
        self.login_as_classroom_admin()
        students_ids = [self.class2_inactive_student.id] 
        resp = self.client.post(self.url_to_class1_1, data={"student_id": students_ids})
        self.assertEqual(resp.status_code, 302)
        self.class2_inactive_student.refresh_from_db()
        self.assertFalse(self.class2_inactive_student.is_active)

    def test_org_admin_do_not_reactivate_inactive_students_in_another_organization(self):
        """
        組織管理者は、他組織の生徒が混じっても勝手にアクティブ化しない
        """
        self.login_as_org_admin()
        students_ids = [self.class2_inactive_student.id] 
        resp = self.client.post(self.url_to_class1_1, data={"student_id": students_ids})
        self.assertEqual(resp.status_code, 302)
        self.class2_inactive_student.refresh_from_db()
        self.assertFalse(self.class2_inactive_student.is_active)

    def test_classroom_admin_do_not_do_anything_for_wrong_student_id(self):
        """
        教室管理者は存在しないIDに対して特に何の処理もせず終了する
        """
        self.login_as_classroom_admin()
        dummy_student_id = uuid.uuid4()
        students_ids = [dummy_student_id] 
        resp = self.client.post(self.url_to_class1_1, data={"student_id": students_ids})
        self.assertEqual(resp.status_code, 302)

    def test_org_admin_do_not_do_anything_for_wrong_student_id(self):
        """
        組織管理者は存在しないIDに対して特に何の処理もせず終了する
        """
        self.login_as_org_admin()
        dummy_student_id = uuid.uuid4()
        students_ids = [dummy_student_id] 
        resp = self.client.post(self.url_to_class1_1, data={"student_id": students_ids})
        self.assertEqual(resp.status_code, 302)

    def test_classroom_admin_deals_only_with_correct_student_id(self):
        """
        教室管理者は正しいIDとそうでないIDが混じっても、正しいIDのみを処理対象とする
        """
        self.login_as_classroom_admin()
        students_ids = [
            self.class1_1_active_student.id,
            self.class1_1_inactive_student.id,
            self.class1_2_active_student.id,
            self.class1_2_inactive_student.id,
            self.class1_not_active_student.id,
            self.class1_not_inactive_student.id,
            self.class2_active_student.id,
            self.class2_inactive_student.id,
            ]
        resp = self.client.post(self.url_to_class1_1, data={"student_id": students_ids})
        self.assertEqual(resp.status_code, 302)
        self.class1_1_active_student.refresh_from_db()
        self.assertTrue(self.class1_1_active_student.is_active)
        self.class1_1_inactive_student.refresh_from_db()
        self.assertTrue(self.class1_1_inactive_student.is_active)
        self.class1_2_active_student.refresh_from_db()
        self.assertTrue(self.class1_2_active_student.is_active)
        self.class1_2_inactive_student.refresh_from_db()
        self.assertFalse(self.class1_2_inactive_student.is_active)
        self.class1_not_active_student.refresh_from_db()
        self.assertTrue(self.class1_not_active_student.is_active)
        self.class1_not_inactive_student.refresh_from_db()
        self.assertFalse(self.class1_not_inactive_student.is_active)
        self.class2_active_student.refresh_from_db()
        self.assertTrue(self.class2_active_student.is_active)
        self.class2_inactive_student.refresh_from_db()
        self.assertFalse(self.class2_inactive_student.is_active)

    def test_org_admin_deals_only_with_correct_student_id(self):
        """
        組織管理者は正しいIDとそうでないIDが混じっても、正しいIDのみを処理対象とする
        """
        self.login_as_org_admin()
        students_ids = [
            self.class1_1_active_student.id,
            self.class1_1_inactive_student.id,
            self.class1_2_active_student.id,
            self.class1_2_inactive_student.id,
            self.class1_not_active_student.id,
            self.class1_not_inactive_student.id,
            self.class2_active_student.id,
            self.class2_inactive_student.id,
            ]
        resp = self.client.post(self.url_to_class1_1, data={"student_id": students_ids})
        self.assertEqual(resp.status_code, 302)
        self.class1_1_active_student.refresh_from_db()
        self.assertTrue(self.class1_1_active_student.is_active)
        self.class1_1_inactive_student.refresh_from_db()
        self.assertTrue(self.class1_1_inactive_student.is_active)
        self.class1_2_active_student.refresh_from_db()
        self.assertTrue(self.class1_2_active_student.is_active)
        self.class1_2_inactive_student.refresh_from_db()
        self.assertFalse(self.class1_2_inactive_student.is_active)
        self.class1_not_active_student.refresh_from_db()
        self.assertTrue(self.class1_not_active_student.is_active)
        self.class1_not_inactive_student.refresh_from_db()
        self.assertFalse(self.class1_not_inactive_student.is_active)
        self.class2_active_student.refresh_from_db()
        self.assertTrue(self.class2_active_student.is_active)
        self.class2_inactive_student.refresh_from_db()
        self.assertFalse(self.class2_inactive_student.is_active)

    def test_classroom_admin_redirect_without_any_students(self):
        """
        教室管理者が非アクティブ生徒0人で復帰させる処理を行った場合、選択画面へリダイレクト
        """
        self.login_as_classroom_admin()
        students_ids = []
        resp = self.client.post(self.url_to_class1_1, data={"student_id": students_ids})
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, f'{reverse("organization_admin:student_reactivate", kwargs={"classroom_id": self.class1_1.id})}')

    def test_org_admin_redirect_without_any_students(self):
        """
        組織管理者が非アクティブ生徒0人で復帰させる処理を行った場合、選択画面へリダイレクト
        """
        self.login_as_org_admin()
        students_ids = []
        resp = self.client.post(self.url_to_class1_1, data={"student_id": students_ids})
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, f'{reverse("organization_admin:student_reactivate", kwargs={"classroom_id": self.class1_1.id})}')

    def test_class_admin_redirects_without_candidates(self):
        """
        教室管理者で復帰させる対象がそもそも存在しない場合、教室詳細へリダイレクト
        """
        self.login_as_classroom_admin()
        self.class1_1_inactive_student.is_active=True
        self.class1_1_inactive_student.save(update_fields=["is_active"])
        self.class1_1_inactive_student_without_teacher.is_active=True
        self.class1_1_inactive_student_without_teacher.save(update_fields=["is_active"])
        resp = self.client.get(self.url_to_class1_1)
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, f'{reverse("organization_admin:classroom_detail", kwargs={"pk":self.class1_1.id})}')

    def test_org_admin_redirects_without_candidates(self):
        """
        組織管理者で復帰させる対象がそもそも存在しない場合、教室詳細へリダイレクト
        """
        self.login_as_org_admin()
        self.class1_1_inactive_student.is_active=True
        self.class1_1_inactive_student.save(update_fields=["is_active"])
        self.class1_1_inactive_student_without_teacher.is_active=True
        self.class1_1_inactive_student_without_teacher.save(update_fields=["is_active"])
        resp = self.client.get(self.url_to_class1_1)
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, f'{reverse("organization_admin:classroom_detail", kwargs={"pk":self.class1_1.id})}')

    def test_non_existent_classroom_raise_404(self):
        """
        存在しない教室にアクセスすると404
        """
        non_existent_classroom_id = 9999

        url = reverse("organization_admin:student_reactivate", args=[non_existent_classroom_id])

        # 教室管理者
        self.login_as_classroom_admin()
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

        # 組織管理者
        self.client.logout()
        self.login_as_org_admin()
        resp = self.client.get(url)  # ←ここをちゃんと再取得
        self.assertEqual(resp.status_code, 404)

    def test_missing_role_object_raise_403(self):
        """
        ロールオブジェクトが取得できない場合は403を送出
        """
        ok = self.client.login(email="class1_1_admin@example.com", password="pass123456")
        self.assertTrue(ok)

        # with patch("accounts.models.ClassroomAdministrator.get_role_object", return_value=None):
        #     resp = self.client.get(self.url_to_class1_1)

        with patch("accounts.views.organization_admin_views.BaseUser.get_role_object", return_value=None):  # BaseUserとして解釈されているので、その対策
            resp = self.client.get(self.url_to_class1_1)
        # print(type(resp.wsgi_request.user))
        # print(resp.wsgi_request.user.__class__.__mro__)

        self.assertEqual(resp.status_code, 403)

    def test_org_admin_cannot_access_another_organization_classroom(self):
        """
        組織管理者は自分以外の組織の教室にアクセスすると403
        """
        self.login_as_org_admin()
        url_to_another_org_classroom = reverse(
            "organization_admin:student_reactivate",
            kwargs={"classroom_id": self.class2.id}
        )
        resp = self.client.get(url_to_another_org_classroom)
        self.assertEqual(resp.status_code, 403)
    
    def test_classroom_admin_cannot_access_another_organization_classroom(self):
        """
        教室管理者は自分以外の組織の教室にアクセスすると403
        """
        self.login_as_classroom_admin()
        url_to_another_org_classroom = reverse(
            "organization_admin:student_reactivate",
            kwargs={"classroom_id": self.class2.id}
        )
        resp = self.client.get(url_to_another_org_classroom)
        self.assertEqual(resp.status_code, 403)

    def test_post_with_only_invalid_targets_finishes_safely(self):
        """
        対象外のstudent_idだけ送られても落ちずに終了する
        """
        self.login_as_classroom_admin()

        resp = self.client.post(
            self.url_to_class1_1,
            data={
                "student_id": [
                    self.class1_1_active_student.id,      # アクティブ
                    self.class1_2_inactive_student.id,    # 他教室
                    self.class2_inactive_student.id,      # 他組織
                ]
            },
            follow=True,
        )

        self.assertEqual(resp.status_code, 200)

        self.class1_1_active_student.refresh_from_db()
        self.class1_2_inactive_student.refresh_from_db()
        self.class2_inactive_student.refresh_from_db()

        self.assertTrue(self.class1_1_active_student.is_active)
        self.assertFalse(self.class1_2_inactive_student.is_active)
        self.assertFalse(self.class2_inactive_student.is_active)

    def test_get_students_are_ordered_by_grade(self):
        """
        非アクティブ生徒は学年順で並ぶ
        """
        self.login_as_classroom_admin()

        self.class1_1_inactive_student.grade = 5
        self.class1_1_inactive_student.save(update_fields=["grade"])

        self.class1_1_inactive_student_without_teacher.grade = 8
        self.class1_1_inactive_student_without_teacher.save(update_fields=["grade"])

        another_student = Student.objects.create(
            username="order_test",
            is_active=False,
            organization=self.org1,
            grade=1,
        )
        another_student.classrooms.add(self.class1_1)

        resp = self.client.get(self.url_to_class1_1)
        self.assertEqual(resp.status_code, 200)

        students = list(resp.context["students"])

        self.assertEqual(
            students,
            [
                another_student,
                self.class1_1_inactive_student,
                self.class1_1_inactive_student_without_teacher,
            ]
        )

    def test_post_without_selection_shows_warning_message(self):
        """
        生徒未選択時に警告メッセージが出る
        """
        self.login_as_classroom_admin()

        resp = self.client.post(self.url_to_class1_1, data={}, follow=True)

        messages = list(get_messages(resp.wsgi_request))
        self.assertTrue(any("選択して下さい" in str(m) for m in messages))

    def test_get_no_inactive_students_shows_warning(self):
        """
        非アクティブ生徒がいない場合は警告メッセージ
        """
        self.login_as_classroom_admin()

        self.class1_1_inactive_student.is_active = True
        self.class1_1_inactive_student.save(update_fields=["is_active"])

        self.class1_1_inactive_student_without_teacher.is_active = True
        self.class1_1_inactive_student_without_teacher.save(update_fields=["is_active"])

        resp = self.client.get(self.url_to_class1_1, follow=True)

        messages = list(get_messages(resp.wsgi_request))
        self.assertTrue(any("存在しません" in str(m) for m in messages))

    def test_post_success_shows_success_message(self):
        """
        正常に再アクティブ化された場合、成功メッセージが出る
        """
        self.login_as_classroom_admin()

        resp = self.client.post(
            self.url_to_class1_1,
            data={"student_id": [self.class1_1_inactive_student.id]},
            follow=True,
        )

        messages = list(get_messages(resp.wsgi_request))
        self.assertTrue(any("完了しました" in str(m) for m in messages))