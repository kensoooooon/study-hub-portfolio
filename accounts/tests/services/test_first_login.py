from django.test import TestCase

from accounts.models import (
    BaseUser,
    Student,
    Teacher,
    ClassroomAdministrator,
    OrganizationAdministrator,
    Organization,
)
from accounts.services.first_login import requires_first_login_password_change


class RequiresFirstLoginPasswordChangeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Test Org")

    def _make_user(
        self,
        role: str,
        is_first_login: bool = True,
    ):
        role_mapping = {
            "student": Student,
            "teacher": Teacher,
            "classroom_administrator": ClassroomAdministrator,
            "organization_administrator": OrganizationAdministrator,
        }
        user_model = role_mapping[role]

        kwargs = dict(
            email=f"{role}_{is_first_login}@example.com",
            password="testpass123",
            username=f"{role}_{is_first_login}",
            is_first_login=is_first_login,
        )
        if role in ("student", "teacher", "classroom_administrator", "organization_administrator"):
            kwargs["organization"] = self.org

        user = user_model.objects.create_user(**kwargs)
        return user

    def test_student_with_is_first_login_true(self):
        """
        is_first_loginがTrueの生徒をきちんと判定できる
        """
        user = self._make_user("student", is_first_login=True)
        self.assertTrue(requires_first_login_password_change(user))

    def test_teacher_with_is_first_login_true(self):
        """
        is_first_loginがTrueの講師をきちんと判定できる
        """
        user = self._make_user("teacher", is_first_login=True)
        self.assertTrue(requires_first_login_password_change(user))

    def test_classroom_admin_with_is_first_login_true(self):
        user = self._make_user("classroom_administrator", is_first_login=True)
        self.assertTrue(requires_first_login_password_change(user))

    def test_org_admin_excluded(self):
        """
        is_first_loginはTrueだったとしても組織管理者を含まない
        """
        user = self._make_user("organization_administrator", is_first_login=True)
        self.assertFalse(requires_first_login_password_change(user))

    def test_superuser_excluded(self):
        """
        is_superuserフラグの付いたユーザーは、is_first_login=Trueでも
        初回ログイン扱いにならないことを確認する回帰テスト。

        Issue #162でrequires_first_login_password_change()から明示的な
        is_superuser判定を撤去したため、除外はroleゲート
        (organization_administratorはTARGET_ROLESに含まれない)が担う。
        is_superuser=Trueの行はCheckConstraintにより生成不可のため、
        メモリ上のインスタンスにフラグを立てて検証する。
        """
        user = self._make_user(
            "organization_administrator", is_first_login=True
        )
        user.is_superuser = True  # DBへは保存しない（CheckConstraintにより不可）
        self.assertFalse(requires_first_login_password_change(user))

    def test_is_first_login_false_excluded_student(self):
        """
        生徒は、is_first_loginがFalseであれば、初回ログイン扱いにはならない
        """
        user = self._make_user("student", is_first_login=False)
        self.assertFalse(requires_first_login_password_change(user))

    def test_is_first_login_false_excluded_teacher(self):
        """
        生徒は、is_first_loginがFalseであれば、初回ログイン扱いにはならない
        """
        user = self._make_user("teacher", is_first_login=False)
        self.assertFalse(requires_first_login_password_change(user))

    def test_is_first_login_false_excluded_classroom_administrator(self):
        """
        生徒は、is_first_loginがFalseであれば、初回ログイン扱いにはならない
        """
        user = self._make_user("classroom_administrator", is_first_login=False)
        self.assertFalse(requires_first_login_password_change(user))

    def test_anonymous_excluded(self):
        """
        未ログインユーザーも判定外
        """
        from django.contrib.auth.models import AnonymousUser
        self.assertFalse(requires_first_login_password_change(AnonymousUser()))
