from django.test import TestCase
from django.urls import reverse

from accounts.models import BaseUser


class AccountEditViewFirstLoginTests(TestCase):
    def _make_user(self):
        user = BaseUser.objects.create_user(
            email="student@example.com",
            password="oldpassword",
            username="student_user",
            role="student",
        )
        user.is_first_login = True
        user.save(update_fields=["is_first_login"])
        return user

    def test_first_login_password_change_clears_flag(self):
        """
        初回ログインでパスワードを変更したらそれが保存されて、古いパスワードでは入れなくなる
        """
        user = self._make_user()
        self.client.force_login(user)

        resp = self.client.post(
            reverse("organization_admin:account_edit"),
            data={
                "email": user.email,
                "password": "newpass123",
                "password_confirm": "newpass123",
            },
        )

        self.assertEqual(resp.status_code, 302)

        user.refresh_from_db()

        self.assertFalse(user.is_first_login)
        self.assertTrue(user.check_password("newpass123"))
        self.assertFalse(user.check_password("oldpassword"))