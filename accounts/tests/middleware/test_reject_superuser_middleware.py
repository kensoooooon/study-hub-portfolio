"""
Issue #162: RejectSuperuserMiddleware の回帰テスト。

生成ガード + CheckConstraint により is_superuser=True の行は生成できないため、
request.user はメモリ上でフラグを立てたインスタンスで代用する。
"""
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.middleware import RejectSuperuserMiddleware
from accounts.models import BaseUser


def _dummy_response(request):
    return HttpResponse("ok")


class RejectSuperuserMiddlewareTests(TestCase):
    """RejectSuperuserMiddleware の単体テスト"""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = RejectSuperuserMiddleware(_dummy_response)

    def _make_user(self, role: str):
        return BaseUser.objects.create_user(
            email="user@example.com",
            password="pass12345",
            username="user",
            role=role,
        )

    def _make_superuser_like(self):
        user = self._make_user("organization_administrator")
        user.is_superuser = True  # DBへは保存しない（CheckConstraintにより不可）
        return user

    def _call(self, path, user):
        request = self.factory.get(path)
        request.user = user
        return self.middleware(request)

    def test_superuser_is_denied_on_protected_path(self):
        """
        is_superuserのユーザーは通常の保護ページで PermissionDenied となることを確認する。
        """
        user = self._make_superuser_like()
        with self.assertRaises(PermissionDenied):
            self._call(reverse("organization_admin:classroom_list"), user)

    def test_superuser_can_reach_logout(self):
        """
        is_superuserのユーザーでもログアウトURLは通過できることを確認する
        (ログアウトすら不可だと詰むため、許可パスから除外している)。
        """
        user = self._make_superuser_like()
        resp = self._call(reverse("accounts_auth:logout"), user)
        self.assertEqual(resp.status_code, 200)

    def test_superuser_can_reach_login(self):
        """
        is_superuserのユーザーでもログインURLは通過できることを確認する。
        """
        user = self._make_superuser_like()
        resp = self._call(reverse("accounts_auth:login"), user)
        self.assertEqual(resp.status_code, 200)

    def test_superuser_static_asset_is_allowed(self):
        """
        is_superuserのユーザーでも static プレフィックスは通過できることを確認する
        (ログイン画面のCSS等が読めるようにするため)。
        """
        user = self._make_superuser_like()
        resp = self._call("/static/example.css", user)
        self.assertEqual(resp.status_code, 200)

    def test_organization_admin_passes_through(self):
        """
        組織管理者は RejectSuperuserMiddleware を素通りすることを確認する。
        """
        user = self._make_user("organization_administrator")
        resp = self._call(reverse("organization_admin:classroom_list"), user)
        self.assertEqual(resp.status_code, 200)

    def test_classroom_admin_passes_through(self):
        """
        教室管理者は RejectSuperuserMiddleware を素通りすることを確認する。
        """
        user = self._make_user("classroom_administrator")
        resp = self._call(reverse("organization_admin:classroom_list"), user)
        self.assertEqual(resp.status_code, 200)

    def test_teacher_passes_through(self):
        """
        講師は RejectSuperuserMiddleware を素通りすることを確認する。
        """
        user = self._make_user("teacher")
        resp = self._call(reverse("organization_admin:classroom_list"), user)
        self.assertEqual(resp.status_code, 200)

    def test_student_passes_through(self):
        """
        生徒は RejectSuperuserMiddleware を素通りすることを確認する。
        """
        user = self._make_user("student")
        resp = self._call(reverse("organization_admin:classroom_list"), user)
        self.assertEqual(resp.status_code, 200)

    def test_anonymous_user_passes_through(self):
        """
        未認証ユーザーは RejectSuperuserMiddleware を素通りすることを確認する。
        """
        request = self.factory.get(reverse("organization_admin:classroom_list"))
        request.user = AnonymousUser()
        resp = self.middleware(request)
        self.assertEqual(resp.status_code, 200)

    def test_user_with_none_logs_warning_and_passes_through(self):
        """
        request.user が None の場合、ミドルウェア順序ミスを検知するための
        logger.warning が送出され、かつリクエスト自体は素通り(200)することを確認する。
        防御的分岐(本来到達しない)の挙動を固定する回帰テスト。
        """
        with self.assertLogs("accounts.middleware", level="WARNING") as cm:
            resp = self._call(reverse("organization_admin:classroom_list"), None)

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(any("ミドルウェア順序" in msg for msg in cm.output))


class RejectSuperuserMiddlewarePipelineTests(TestCase):
    """実際の動作により近い形で挙動を確認"""

    def test_superuser_session_is_403_in_real_pipeline(self):
        """
        制約導入前に発行された認証済み superuser セッションを模し、
        実パイプラインで任意の保護ページが 403 になることを確認する回帰テスト。

        is_superuser=True の行は生成できないため、force_login した通常ユーザーの
        request.user 解決を is_superuser=True のインスタンスへ差し替える。
        """
        user = BaseUser.objects.create_user(
            email="pipe@example.com",
            password="pass12345",
            username="pipe",
            role="organization_administrator",
        )
        self.client.force_login(user)

        from unittest.mock import patch

        real_user = BaseUser.objects.get(pk=user.pk)
        real_user.is_superuser = True  # メモリ上でのみスーパーユーザーに見せる(DB保存不可)

        with patch(
            "django.contrib.auth.middleware.get_user", return_value=real_user
        ):
            resp = self.client.get(reverse("organization_admin:classroom_list"))

        self.assertEqual(resp.status_code, 403)
