"""
実削除から論理削除(ソフトデリート)に切り替わったことを確認するためのテスト群
"""
from django.test import TestCase
from django.urls import reverse

from accounts.models import (
    Student,
    Teacher,
    ClassroomAdministrator,
    OrganizationAdministrator,
    Classroom,
    Organization
)


class StudentSoftDeleteTest(TestCase):
    """
    生徒の削除がきちんとソフトデリートになっていることを確認するためのテスト
    """
    
    @classmethod
    def setUpTestData(cls):
        # 自テナント
        cls.org1 = Organization.objects.create(name="Organization 1")
        cls.org_admin1 = OrganizationAdministrator.objects.create_user(
            username="Org Admin1",
            email="org_admin1@example.com",
            password="pass123456"
        )
        cls.org_admin1.organizations.add(cls.org1)

        cls.classroom1 = Classroom.objects.create(name="ClassRoom 1", organization=cls.org1)

        # 対象が所属する組織管理者
        cls.classroom_admin1 = ClassroomAdministrator.objects.create_user(
            username="Classroom Admin1",
            email="classroom_admin1@example.com",
            password="pass123456",
            organization=cls.org1
        )
        cls.classroom_admin1.classrooms.add(cls.classroom1)

        # 同じ組織だが、対象生徒が属さない教室とその管理者
        cls.classroom1_2 = Classroom.objects.create(name="ClassRoom 1_2", organization=cls.org1)
        cls.classroom_admin1_2 = ClassroomAdministrator.objects.create_user(
            username="Classroom Admin1_2",
            email="classroom_admin1_2@example.com",
            password="pass123456",
            organization=cls.org1
        )
        cls.classroom_admin1_2.classrooms.add(cls.classroom1_2)

        # 同じ組織で、対象を担当している講師
        cls.teacher1 = Teacher.objects.create_user(
            username="Teacher1",
            email="teacher1@example.com",
            password="pass123456",
            organization=cls.org1,
        )
        cls.teacher1.classrooms.add(cls.classroom1)

        # 対象生徒を担当していない講師
        cls.teacher1_2 = Teacher.objects.create_user(
            username="Teacher1_2",
            email="teacher1_2@example.com",
            password="pass123456",
            organization=cls.org1,
        )
        cls.teacher1_2.classrooms.add(cls.classroom1)

        # 対象生徒
        cls.student1 = Student.objects.create_user(
            username="Sample Student1",
            email="student1@example.com",
            password="pass123456",
            organization=cls.org1,
        )
        cls.student1.classrooms.add(cls.classroom1)
        cls.student1.teachers.add(cls.teacher1)

        # 別の生徒
        cls.student_actor1 = Student.objects.create_user(
            username="Student Actor1",
            email="student_actor1@example.com",
            password="pass123456",
            organization=cls.org1,
        )
        cls.student_actor1.classrooms.add(cls.classroom1)

        # 別テナント
        cls.org2 = Organization.objects.create(name="Organization 2")
        cls.org_admin2 = OrganizationAdministrator.objects.create_user(
            username="Org Admin2",
            email="org_admin2@example.com",
            password="pass123456"
        )
        cls.org_admin2.organizations.add(cls.org2)

        cls.classroom2 = Classroom.objects.create(name="ClassRoom 2", organization=cls.org2)

        cls.classroom_admin2 = ClassroomAdministrator.objects.create_user(
            username="Classroom Admin2",
            email="classroom_admin2@example.com",
            password="pass123456",
            organization=cls.org2
        )
        cls.classroom_admin2.classrooms.add(cls.classroom2)

        cls.teacher2 = Teacher.objects.create_user(
            username="Teacher2",
            email="teacher2@example.com",
            password="pass123456",
            organization=cls.org2,
        )
        cls.teacher2.classrooms.add(cls.classroom2)

        cls.student_actor2 = Student.objects.create_user(
            username="Student Actor2",
            email="student_actor2@example.com",
            password="pass123456",
            organization=cls.org2,
        )
        cls.student_actor2.classrooms.add(cls.classroom2)
    
    def login_org_admin1(self):
        ok = self.client.login(email="org_admin1@example.com", password="pass123456")
        self.assertTrue(ok)
    
    def login_org_admin2(self):
        ok = self.client.login(email="org_admin2@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_classroom_admin1(self):
        ok = self.client.login(email="classroom_admin1@example.com", password="pass123456")
        self.assertTrue(ok)
    
    def login_classroom_admin1_2(self):
        ok = self.client.login(email="classroom_admin1_2@example.com", password="pass123456")
        self.assertTrue(ok)
        
    def login_teacher1(self):
        ok = self.client.login(email="teacher1@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_teacher1_2(self):
        ok = self.client.login(email="teacher1_2@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_student1(self):
        ok = self.client.login(email="student1@example.com", password="pass123456")
        self.assertTrue(ok)
    
    def login_student_actor1(self):
        ok = self.client.login(email="student_actor1@example.com", password="pass123456")
        self.assertTrue(ok)
    
    def login_classroom_admin2(self):
        ok = self.client.login(email="classroom_admin2@example.com", password="pass123456")
        self.assertTrue(ok)
    
    def login_teacher2(self):
        ok = self.client.login(email="teacher2@example.com", password="pass123456")
        self.assertTrue(ok)
    
    def login_student_actor2(self):
        ok = self.client.login(email="student_actor2@example.com", password="pass123456")
        self.assertTrue(ok)

    def test_same_tenant_org_admin_can_delete_student_and_redirect_to_classroom_detail(self):
        """
        組織管理者により削除された生徒が、きちんと実データは残っているが、非アクティブにはなっている様子
        また、削除後に教室のIDがあるため、教室詳細に飛ばされている様子
        """
        self.login_org_admin1()
        url = reverse("organization_admin:student_delete", kwargs={"pk": self.student1.pk})  # 対象生徒の削除ページへログイン
        response = self.client.post(url, data={"classroom_id": self.classroom1.pk})  # POSTフォームで削除実行
        self.assertEqual(response.status_code, 302)  # コード確認
        self.student1.refresh_from_db()  # DBからのリロード
        self.assertTrue(Student.objects.filter(pk=self.student1.pk).exists())  # 存在はしているが
        self.assertFalse(self.student1.is_active)  # アクティブではない
        self.assertRedirects(
            response,
            reverse("organization_admin:classroom_detail", kwargs={"pk": self.classroom1.pk})
        )

    def test_same_tenant_org_admin_can_delete_student_and_redirect_to_classroom_list(self):
        """
        組織管理者により削除された生徒が、きちんと実データは残っているが、非アクティブにはなっている様子
        また、削除後に教室のIDがないので、教室一覧に飛ばされている様子
        """
        self.login_org_admin1()
        url = reverse("organization_admin:student_delete", kwargs={"pk": self.student1.pk})  # 対象生徒の削除ページへログイン
        response = self.client.post(url)  # POSTフォームで削除実行
        self.assertEqual(response.status_code, 302)  # コード確認
        self.student1.refresh_from_db()  # DBからのリロード
        self.assertTrue(Student.objects.filter(pk=self.student1.pk).exists())  # 存在はしているが
        self.assertFalse(self.student1.is_active)  # アクティブではない
        self.assertRedirects(
            response,
            reverse("organization_admin:classroom_list")
        )

    def test_same_tenant_same_classroom_admin_can_delete_student_and_redirect_to_classroom_detail(self):
        """
        同じ組織で同じ教室の教室管理者が削除できる様子
        また削除後に教室のIDがあるので、教室詳細に飛ばされている様子
        """
        self.login_classroom_admin1()
        url = reverse("organization_admin:student_delete", kwargs={"pk": self.student1.pk})  # 対象生徒の削除ページへログイン
        response = self.client.post(url, data={"classroom_id": self.classroom1.pk})  # POSTフォームで削除実行
        self.assertEqual(response.status_code, 302)  # コード確認
        self.student1.refresh_from_db()  # DBからのリロード
        self.assertTrue(Student.objects.filter(pk=self.student1.pk).exists())  # 存在はしているが
        self.assertFalse(self.student1.is_active)  # アクティブではない
        self.assertRedirects(
            response,
            reverse("organization_admin:classroom_detail", kwargs={"pk": self.classroom1.pk})
        )

    def test_same_tenant_same_classroom_admin_can_delete_student_and_redirect_to_classroom_list(self):
        """
        同じ組織で同じ教室の教室管理者が削除できる様子
        また削除後に教室のIDがないので、教室一覧に飛ばされている様子
        """
        self.login_classroom_admin1()
        url = reverse("organization_admin:student_delete", kwargs={"pk": self.student1.pk})  # 対象生徒の削除ページへログイン
        response = self.client.post(url)  # POSTフォームで削除実行
        self.assertEqual(response.status_code, 302)  # コード確認
        self.student1.refresh_from_db()  # DBからのリロード
        self.assertTrue(Student.objects.filter(pk=self.student1.pk).exists())  # 存在はしているが
        self.assertFalse(self.student1.is_active)  # アクティブではない
        self.assertRedirects(
            response,
            reverse("organization_admin:classroom_list")
        )

    def test_same_tenant_different_classroom_admin_cannot_delete_student(self):
        """
        同じ組織で異なる教室の教室管理者では削除できない様子
        """
        self.login_classroom_admin1_2()
        url = reverse("organization_admin:student_delete", kwargs={"pk": self.student1.pk})  # 対象生徒のログインページへログイン
        response = self.client.post(url, data={"classroom_id": self.classroom1.pk})  # POSTフォームで削除実行
        self.assertEqual(response.status_code, 404)  # get_querysetの中に含まれないため、get_objectで短絡
        self.student1.refresh_from_db()  # 念の為DBからのリロード
        self.assertTrue(self.student1.is_active)  # 当然ステータスに影響は受けない

    def test_different_tenant_org_admin_cannot_delete(self):
        """
        組織管理者でも、異なる組織の管理者は削除できない様子
        """
        self.login_org_admin2()
        url = reverse("organization_admin:student_delete", kwargs={"pk": self.student1.pk})
        response = self.client.post(url, data={"classroom_id": self.classroom1.pk})
        self.assertEqual(response.status_code, 404)  # get_querysetに生徒が存在しないため、get_objectで404に短絡
        self.student1.refresh_from_db()
        self.assertTrue(self.student1.is_active)

    def test_assigned_teacher_cannot_delete(self):
        """
        担当の講師であっても、削除はできない様子
        """
        self.login_teacher1()
        url = reverse("organization_admin:student_delete", kwargs={"pk": self.student1.pk})
        response = self.client.post(url, data={"classroom_id": self.classroom1.pk})
        self.assertEqual(response.status_code, 403)
        self.student1.refresh_from_db()
        self.assertTrue(self.student1.is_active)

    def test_not_assigned_teacher_cannot_delete(self):
        """
        担当外の講師は当然削除不可
        """
        self.login_teacher1_2()
        url = reverse("organization_admin:student_delete", kwargs={"pk": self.student1.pk})
        response = self.client.post(url, data={"classroom_id": self.classroom1.pk})
        self.assertEqual(response.status_code, 403)
        self.student1.refresh_from_db()
        self.assertTrue(self.student1.is_active)

    def test_student_self_cannot_delete(self):
        """
        自分自身を削除するのも不可能
        """
        self.login_student1()
        url = reverse("organization_admin:student_delete", kwargs={"pk": self.student1.pk})
        response = self.client.post(url, data={"classroom_id": self.classroom1.pk})
        self.assertEqual(response.status_code, 403)
        self.student1.refresh_from_db()
        self.assertTrue(self.student1.is_active)
    
    def test_student_actor_cannot_delete(self):
        """
        生徒から削除されるのも当然不可能
        """
        self.login_student_actor1()
        url = reverse("organization_admin:student_delete", kwargs={"pk": self.student1.pk})
        response = self.client.post(url, data={"classroom_id": self.classroom1.pk})
        self.assertEqual(response.status_code, 403)
        self.student1.refresh_from_db()
        self.assertTrue(self.student1.is_active)
    
    def test_different_tenant_classroom_admin_cannot_delete(self):
        """
        別の組織の教室管理者からは削除不可
        """
        self.login_classroom_admin2()
        url = reverse("organization_admin:student_delete", kwargs={"pk": self.student1.pk})
        response = self.client.post(url, data={"classroom_id": self.classroom1.pk})
        self.assertEqual(response.status_code, 404)  # get_querysetの中に対象が可視化されないため、get_objectで404に短絡する
        self.student1.refresh_from_db()
        self.assertTrue(self.student1.is_active)
    
    def test_different_tenant_teacher_cannot_delete(self):
        """
        別の組織の教師からも削除不可
        """
        self.login_teacher2()
        url = reverse("organization_admin:student_delete", kwargs={"pk": self.student1.pk})
        response = self.client.post(url, data={"classroom_id": self.classroom1.pk})
        self.assertEqual(response.status_code, 403)
        self.student1.refresh_from_db()
        self.assertTrue(self.student1.is_active)
    
    def test_different_tenant_student_cannot_delete(self):
        """
        別の組織の生徒からも当然削除不可
        """
        self.login_student_actor2()
        url = reverse("organization_admin:student_delete", kwargs={"pk": self.student1.pk})
        response = self.client.post(url, data={"classroom_id": self.classroom1.pk})
        self.assertEqual(response.status_code, 403)
        self.student1.refresh_from_db()
        self.assertTrue(self.student1.is_active)

    def test_same_tenant_org_admin_get_delete_url_returns_405(self):
        """
        同じ組織の組織管理者でも、削除URLへのGETアクセスでは確認画面は表示されず405になる
        """
        self.login_org_admin1()
        url = reverse("organization_admin:student_delete", kwargs={"pk": self.student1.pk})
        response = self.client.get(url, data={"classroom_id": self.classroom1.pk})

        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "POST")

    def test_different_tenant_org_admin_get_delete_url_returns_405(self):
        """
        他組織の組織管理者でも、削除URLへのGETアクセスでは確認画面は表示されず405になる
        """
        self.login_org_admin2()
        url = reverse("organization_admin:student_delete", kwargs={"pk": self.student1.pk})
        response = self.client.get(url, data={"classroom_id": self.classroom1.pk})

        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "POST")

    def test_same_tenant_same_classroom_admin_get_delete_url_returns_405(self):
        """
        同じ教室の教室管理者でも、削除URLへのGETアクセスでは確認画面は表示されず405になる
        """
        self.login_classroom_admin1()
        url = reverse("organization_admin:student_delete", kwargs={"pk": self.student1.pk})
        response = self.client.get(url, data={"classroom_id": self.classroom1.pk})

        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "POST")

    def test_same_tenant_different_classroom_admin_get_delete_url_returns_405(self):
        """
        同じ組織でも別教室の教室管理者は、削除URLへのGETアクセスで確認画面は表示されず405になる
        """
        self.login_classroom_admin1_2()
        url = reverse("organization_admin:student_delete", kwargs={"pk": self.student1.pk})
        response = self.client.get(url, data={"classroom_id": self.classroom1.pk})

        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "POST")

    def test_different_tenant_classroom_admin_get_delete_url_returns_405(self):
        """
        他組織の教室管理者でも、削除URLへのGETアクセスでは確認画面は表示されず405になる
        """
        self.login_classroom_admin2()
        url = reverse("organization_admin:student_delete", kwargs={"pk": self.student1.pk})
        response = self.client.get(url, data={"classroom_id": self.classroom1.pk})

        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "POST")

    def test_anonymous_user_get_delete_url_redirects_to_login_with_next(self):
        """
        未ログインユーザーが削除URLへGETした場合、ログイン画面へnext付きでリダイレクトされる
        """
        url = reverse("organization_admin:student_delete", kwargs={"pk": self.student1.pk})
        response = self.client.get(url, data={"classroom_id": self.classroom1.pk})

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            f'{reverse("accounts_auth:login")}?next='
            f'{reverse("organization_admin:student_delete", kwargs={"pk": self.student1.pk})}%3Fclassroom_id%3D{self.classroom1.pk}'
        )
        self.student1.refresh_from_db()
        self.assertTrue(self.student1.is_active)

    def test_anonymous_user_post_delete_url_redirects_to_login_with_next(self):
        """
        未ログインユーザーが削除URLへPOSTした場合、ログイン画面へnext付きでリダイレクトされる
        """
        url = reverse("organization_admin:student_delete", kwargs={"pk": self.student1.pk})
        response = self.client.post(url, data={"classroom_id": self.classroom1.pk})

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            f'{reverse("accounts_auth:login")}?next='
            f'{reverse("organization_admin:student_delete", kwargs={"pk": self.student1.pk})}'
        )
        self.student1.refresh_from_db()
        self.assertTrue(self.student1.is_active)
