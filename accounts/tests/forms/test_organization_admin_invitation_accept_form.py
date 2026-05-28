from __future__ import annotations

from django.test import SimpleTestCase

from accounts.forms import OrganizationAdminInvitationAcceptForm


class OrganizationAdminInvitationAcceptFormTests(SimpleTestCase):
    def _valid_data(self, **overrides):
        data = {
            "username": "new_admin",
            "password": "testpass123",
            "password_confirm": "testpass123",
        }
        data.update(overrides)
        return data

    def test_form_is_valid_with_normal_input(self):
        form = OrganizationAdminInvitationAcceptForm(data=self._valid_data())

        self.assertTrue(form.is_valid(), form.errors)

    def test_username_with_space_is_invalid(self):
        form = OrganizationAdminInvitationAcceptForm(
            data=self._valid_data(username="new admin")
        )

        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)
        self.assertIn("ユーザー名に空白や改行を含めないでください。", form.errors["username"])

    def test_username_with_newline_is_invalid(self):
        form = OrganizationAdminInvitationAcceptForm(
            data=self._valid_data(username="new\nadmin")
        )

        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)
        self.assertIn("ユーザー名に空白や改行を含めないでください。", form.errors["username"])

    def test_username_with_tab_is_invalid(self):
        form = OrganizationAdminInvitationAcceptForm(
            data=self._valid_data(username="new\tadmin")
        )

        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)
        self.assertIn("ユーザー名に空白や改行を含めないでください。", form.errors["username"])

    def test_password_with_space_is_invalid(self):
        form = OrganizationAdminInvitationAcceptForm(
            data=self._valid_data(password="test pass123", password_confirm="test pass123")
        )

        self.assertFalse(form.is_valid())
        self.assertIn("password", form.errors)
        self.assertIn("パスワードに空白や改行を含めないでください。", form.errors["password"])

    def test_password_with_newline_is_invalid(self):
        form = OrganizationAdminInvitationAcceptForm(
            data=self._valid_data(password="test\npass123", password_confirm="test\npass123")
        )

        self.assertFalse(form.is_valid())
        self.assertIn("password", form.errors)
        self.assertIn("パスワードに空白や改行を含めないでください。", form.errors["password"])

    def test_password_with_tab_is_invalid(self):
        form = OrganizationAdminInvitationAcceptForm(
            data=self._valid_data(password="test\tpass123", password_confirm="test\tpass123")
        )

        self.assertFalse(form.is_valid())
        self.assertIn("password", form.errors)
        self.assertIn("パスワードに空白や改行を含めないでください。", form.errors["password"])

    def test_password_shorter_than_8_chars_is_invalid(self):
        form = OrganizationAdminInvitationAcceptForm(
            data=self._valid_data(password="abc1234", password_confirm="abc1234")
        )

        self.assertFalse(form.is_valid())
        self.assertIn("password", form.errors)
        self.assertIn("短すぎます。8文字以上入力してください。", form.errors["password"])

    def test_password_confirm_mismatch_is_invalid(self):
        form = OrganizationAdminInvitationAcceptForm(
            data=self._valid_data(password_confirm="differentpass123")
        )

        self.assertFalse(form.is_valid())
        self.assertIn("password_confirm", form.errors)
        self.assertIn(
            "確認用パスワードの値が一致しません。",
            form.errors["password_confirm"],
        )
