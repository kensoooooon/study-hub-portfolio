from unittest.mock import patch

from django.test import TestCase

from accounts.forms import AccountEditForm
from accounts.models import BaseUser


class AccountEditFormTests(TestCase):
    def _make_user(self, role: str, is_first_login: bool = True):
        user = BaseUser.objects.create_user(
            email=f"{role}@example.com",
            password="oldpassword",
            username=f"{role}_user",
            role=role,
        )
        user.is_first_login = is_first_login
        user.save(update_fields=["is_first_login"])
        return user

    def _form(self, user, data):
        return AccountEditForm(data=data, instance=user)

    # --- 初回ログイン時 ---

    def test_first_login_password_required(self):
        """
        初回ログイン時はパスワードは変更必須なので空欄を許さない
        """
        user = self._make_user("student")
        form = self._form(user, {"email": user.email, "password": "", "password_confirm": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("password", form.errors)

    def test_password_min_length(self):
        """
        パスワードは最低でも8文字以上
        """
        user = self._make_user("student")
        form = self._form(user, {"email": user.email, "password": "short1", "password_confirm": "short1"})
        self.assertFalse(form.is_valid())
        self.assertIn("password", form.errors)

    def test_password_confirm_mismatch(self):
        """
        確認用パスワードも一致する必要がある
        """
        user = self._make_user("student")
        form = self._form(user, {"email": user.email, "password": "newpass123", "password_confirm": "different1"})
        self.assertFalse(form.is_valid())
        self.assertIn("password_confirm", form.errors)

    def test_valid_first_login_password_change(self):
        """
        条件を満たしたパスワードはバリデーションを通過する
        """
        user = self._make_user("student")
        with patch("accounts.forms.settings") as mock_settings:
            mock_settings.STUDENT_DEFAULT_PASSWORD = "default_student"
            mock_settings.TEACHER_DEFAULT_PASSWORD = "default_teacher"
            form = self._form(user, {"email": user.email, "password": "newpass123", "password_confirm": "newpass123"})
            self.assertTrue(form.is_valid())

    # --- 通常時 ---

    def test_normal_empty_password_allowed(self):
        """
        初回ログイン以外では、空欄=変更しないが通る
        """
        user = self._make_user("student", is_first_login=False)
        form = self._form(user, {"email": user.email, "password": "", "password_confirm": ""})
        self.assertTrue(form.is_valid())

    def test_normal_valid_password_change(self):
        """
        初回ログインでなくても、新しいパスワードが条件を満たしていれば変更可能
        """
        user = self._make_user("student", is_first_login=False)
        with patch("accounts.forms.settings") as mock_settings:
            mock_settings.STUDENT_DEFAULT_PASSWORD = "default_student"
            mock_settings.TEACHER_DEFAULT_PASSWORD = "default_teacher"
            form = self._form(user, {"email": user.email, "password": "newpass123", "password_confirm": "newpass123"})
            self.assertTrue(form.is_valid())

    # --- 共用初期値チェック ---

    def test_student_default_password_rejected(self):
        """
        生徒は生徒用デフォルトパスワードを設定できない
        """
        user = self._make_user("student")
        with patch("accounts.forms.settings") as mock_settings:
            mock_settings.STUDENT_DEFAULT_PASSWORD = "student_default"
            mock_settings.TEACHER_DEFAULT_PASSWORD = "teacher_default"
            form = self._form(user, {"email": user.email, "password": "student_default", "password_confirm": "student_default"})
            self.assertFalse(form.is_valid())
            self.assertIn("password", form.errors)

    def test_normal_student_default_password_rejected(self):
        """
        初回ログイン完了後であっても、生徒は生徒用デフォルトパスワードへ戻せない
        """
        user = self._make_user("student", is_first_login=False)

        with patch("accounts.forms.settings") as mock_settings:
            mock_settings.STUDENT_DEFAULT_PASSWORD = "student_default"
            mock_settings.TEACHER_DEFAULT_PASSWORD = "teacher_default"

            form = self._form(
                user,
                {
                    "email": user.email,
                    "password": "student_default",
                    "password_confirm": "student_default",
                },
            )

            self.assertFalse(form.is_valid())
            self.assertIn("password", form.errors)

    def test_teacher_not_rejected_student_default_password(self):
        """
        講師は生徒用デフォルトパスワードを設定可能
        """
        user = self._make_user("teacher")
        with patch("accounts.forms.settings") as mock_settings:
            mock_settings.STUDENT_DEFAULT_PASSWORD = "student_default"
            mock_settings.TEACHER_DEFAULT_PASSWORD = "teacher_default"
            form = self._form(user, {"email": user.email, "password": "student_default", "password_confirm": "student_default"})
            self.assertTrue(form.is_valid())

    def test_teacher_default_password_rejected(self):
        """
        講師は講師用デフォルトパスワードを設定できない
        """
        user = self._make_user("teacher")
        with patch("accounts.forms.settings") as mock_settings:
            mock_settings.STUDENT_DEFAULT_PASSWORD = "student_default"
            mock_settings.TEACHER_DEFAULT_PASSWORD = "teacher_default"
            form = self._form(user, {"email": user.email, "password": "teacher_default", "password_confirm": "teacher_default"})
            self.assertFalse(form.is_valid())
            self.assertIn("password", form.errors)

    def test_normal_teacher_default_password_rejected(self):
        """
        初回ログイン完了後であっても、講師は講師用デフォルトパスワードへ戻せない
        """
        user = self._make_user("teacher", is_first_login=False)

        with patch("accounts.forms.settings") as mock_settings:
            mock_settings.STUDENT_DEFAULT_PASSWORD = "student_default"
            mock_settings.TEACHER_DEFAULT_PASSWORD = "teacher_default"

            form = self._form(
                user,
                {
                    "email": user.email,
                    "password": "teacher_default",
                    "password_confirm": "teacher_default",
                },
            )

            self.assertFalse(form.is_valid())
            self.assertIn("password", form.errors)

    def test_student_not_rejected_teacher_default_password(self):
        """
        生徒は講師用デフォルトパスワードを設定可能
        """
        user = self._make_user("student")
        with patch("accounts.forms.settings") as mock_settings:
            mock_settings.STUDENT_DEFAULT_PASSWORD = "student_default"
            mock_settings.TEACHER_DEFAULT_PASSWORD = "teacher_default"
            form = self._form(user, {"email": user.email, "password": "teacher_default", "password_confirm": "teacher_default"})
            self.assertTrue(form.is_valid())

    def test_classroom_admin_no_default_password_check(self):
        """
        教室管理者はデフォルトパスワードが設定されておらず、特にチェックなくパスワードを利用できる
        """
        user = self._make_user("classroom_administrator")
        with patch("accounts.forms.settings") as mock_settings:
            mock_settings.STUDENT_DEFAULT_PASSWORD = "student_default"
            mock_settings.TEACHER_DEFAULT_PASSWORD = "teacher_default"
            form = self._form(user, {"email": user.email, "password": "classroom_pass1", "password_confirm": "classroom_pass1"})
            self.assertTrue(form.is_valid())
    
    def test_classroom_admin_can_use_student_default_password(self):
        """
        教室管理者は生徒用デフォルトパスワードを設定可能
        """
        user = self._make_user("classroom_administrator")
        with patch("accounts.forms.settings") as mock_settings:
            mock_settings.STUDENT_DEFAULT_PASSWORD = "student_default"
            mock_settings.TEACHER_DEFAULT_PASSWORD = "teacher_default"
            form = self._form(user, {"email": user.email, "password": "student_default", "password_confirm": "student_default"})
            self.assertTrue(form.is_valid())

    def test_classroom_admin_can_use_teacher_default_password(self):
        """
        教室管理者は講師用デフォルトパスワードを設定可能
        """
        user = self._make_user("classroom_administrator")
        with patch("accounts.forms.settings") as mock_settings:
            mock_settings.STUDENT_DEFAULT_PASSWORD = "student_default"
            mock_settings.TEACHER_DEFAULT_PASSWORD = "teacher_default"
            form = self._form(user, {"email": user.email, "password": "teacher_default", "password_confirm": "teacher_default"})
            self.assertTrue(form.is_valid())

    def test_org_admin_can_use_student_default_password(self):
        """
        組織管理者は生徒用デフォルトパスワードを利用可能
        """
        user = self._make_user("organization_administrator", is_first_login=False)
        with patch("accounts.forms.settings") as mock_settings:
            mock_settings.STUDENT_DEFAULT_PASSWORD = "student_default"
            mock_settings.TEACHER_DEFAULT_PASSWORD = "teacher_default"
            # 他ロールの共用初期値を使っても org_admin には拒否されない
            form = self._form(user, {"email": user.email, "password": "student_default", "password_confirm": "student_default"})
            self.assertTrue(form.is_valid())

    def test_org_admin_can_use_teacher_default_password(self):
        """
        組織管理者は講師用デフォルトパスワードを利用可能
        """
        user = self._make_user("organization_administrator", is_first_login=False)
        with patch("accounts.forms.settings") as mock_settings:
            mock_settings.STUDENT_DEFAULT_PASSWORD = "student_default"
            mock_settings.TEACHER_DEFAULT_PASSWORD = "teacher_default"
            # 他ロールの共用初期値を使っても org_admin には拒否されない
            form = self._form(user, {"email": user.email, "password": "teacher_default", "password_confirm": "teacher_default"})
            self.assertTrue(form.is_valid())


    # --- メールアドレス disabled ---

    def test_first_login_email_disabled(self):
        """
        初回ログイン時はメールアドレスの変更は不可
        """
        user = self._make_user("student")
        form = AccountEditForm(instance=user)
        self.assertTrue(form.fields["email"].disabled)

    def test_normal_email_editable(self):
        """
        初回ログインでなければメールアドレスを変更可能
        """
        user = self._make_user("student", is_first_login=False)
        form = AccountEditForm(instance=user)
        self.assertFalse(form.fields["email"].disabled)

    def test_first_login_ignores_tampered_email_post(self):
        """
        初回ログイン時は、例え改ざんされたメールアドレスが入力されても、メールアドレスは変更されない
        """
        user = self._make_user("student")
        original_email = user.email
        with patch("accounts.forms.settings") as mock_settings:
            mock_settings.STUDENT_DEFAULT_PASSWORD = "student_default"
            mock_settings.TEACHER_DEFAULT_PASSWORD = "teacher_default"
            form = self._form(user, {
                "email": "tampered@evil.com",
                "password": "newpass123",
                "password_confirm": "newpass123",
            })
            self.assertTrue(form.is_valid())
            saved_user = form.save()
            self.assertEqual(saved_user.email, original_email)

    def test_save_updates_password_when_new_password_is_entered(self):
        """
        初回ログインがFalseでも新しいパスワードが入れられた際には、きちんと反映される
        """
        user = self._make_user("student", is_first_login=False)

        form = self._form(
            user,
            {
                "email": user.email,
                "password": "newpass123",
                "password_confirm": "newpass123",
            },
        )

        self.assertTrue(form.is_valid())
        saved_user = form.save()
        saved_user.refresh_from_db()

        self.assertTrue(saved_user.check_password("newpass123"))
        self.assertFalse(saved_user.check_password("oldpassword"))

    def test_save_clears_first_login_flag_when_password_is_changed(self):
        """
        初回ログイン時にパスワードを変更すると、
        初回ログイン状態が解除される
        """
        user = self._make_user("student", is_first_login=True)

        with patch("accounts.forms.settings") as mock_settings:
            mock_settings.STUDENT_DEFAULT_PASSWORD = "student_default"
            mock_settings.TEACHER_DEFAULT_PASSWORD = "teacher_default"

            form = self._form(
                user,
                {
                    "email": user.email,
                    "password": "newpass123",
                    "password_confirm": "newpass123",
                },
            )

            self.assertTrue(form.is_valid())

            saved_user = form.save()
            saved_user.refresh_from_db()

            self.assertFalse(saved_user.is_first_login)
            self.assertTrue(saved_user.check_password("newpass123"))
            self.assertFalse(saved_user.check_password("oldpassword"))

    def test_save_preserves_password_when_password_is_empty(self):
        """
        初回ログインがFalseだとパスワードが空欄のときは変更されない
        """
        user = self._make_user("student", is_first_login=False)

        form = self._form(
            user,
            {
                "email": user.email,
                "password": "",
                "password_confirm": "",
            },
        )

        self.assertTrue(form.is_valid())
        saved_user = form.save()
        saved_user.refresh_from_db()

        self.assertTrue(saved_user.check_password("oldpassword"))

