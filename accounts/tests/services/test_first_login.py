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
        is_superuser: bool = False,
    ):
        role_mapping = {
            "student": Student,
            "teacher": Teacher,
            "classroom_administrator": ClassroomAdministrator,
            "organization_administrator": OrganizationAdministrator,
        }
        user_model = role_mapping[role]

        kwargs = dict(
            email=f"{role}_{is_first_login}_{is_superuser}@example.com",
            password="testpass123",
            username=f"{role}_{is_first_login}_{is_superuser}",
            is_first_login=is_first_login,
            is_superuser=is_superuser,
        )
        if role in ("student", "teacher", "classroom_administrator"):
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
        スーパーユーザーもまたis_first_login=Trueだったとしても、初回ログイン扱いにはならない
        """
        user = self._make_user("organization_administrator", is_first_login=True, is_superuser=True)
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
