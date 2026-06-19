from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.middleware import FirstLoginMiddleware
from accounts.models import BaseUser, Organization


def _dummy_response(request):
    return HttpResponse("ok")


class FirstLoginMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = FirstLoginMiddleware(_dummy_response)

    def _make_user(self, role: str, is_first_login: bool = True, is_superuser: bool = False):
        user = BaseUser.objects.create_user(
            email=f"{role}_{is_first_login}_{is_superuser}@example.com",
            password="testpass123",
            username=f"{role}_{is_first_login}_{is_superuser}",
            role=role,
            is_superuser=is_superuser,
        )
        user.is_first_login = is_first_login
        user.save(update_fields=["is_first_login"])
        return user

    def _get(self, path, user):
        request = self.factory.get(path)
        request.user = user
        return self.middleware(request)

    def _account_edit_url(self):
        return reverse("organization_admin:account_edit")

    # --- 対象ロールはリダイレクトされる ---

    def test_teacher_first_login_redirected(self):
        """
        講師は初回ログイン状態だとアカウント編集ページへリダイレクトされる
        """
        user = self._make_user("teacher")
        resp = self._get(reverse("organization_admin:teacher_dashboard"), user)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], self._account_edit_url())

    def test_student_first_login_redirected(self):
        """
        生徒は初回ログイン状態だとアカウント編集ページへリダイレクトされる
        """
        user = self._make_user("student")
        resp = self._get(reverse("student:home"), user)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], self._account_edit_url())

    def test_classroom_admin_first_login_redirected(self):
        """
        教室管理者は初回ログイン状態だとアカウント編集ページへリダイレクトされる
        """
        user = self._make_user("classroom_administrator")
        resp = self._get(reverse("organization_admin:classroom_list"), user)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], self._account_edit_url())

    # --- 対象外はリダイレクトされない ---

    def test_org_admin_not_redirected(self):
        """
        組織管理者は初回ログイン状態であっても、リダイレクト対象外
        """
        user = self._make_user("organization_administrator")
        resp = self._get(reverse("organization_admin:classroom_list"), user)
        self.assertEqual(resp.status_code, 200)

    def test_superuser_not_redirected(self):
        """
        スーパーユーザーは初回ログイン状態であっても、リダイレクト対象外
        """
        user = self._make_user("organization_administrator", is_superuser=True)
        resp = self._get(reverse("organization_admin:classroom_list"), user)
        self.assertEqual(resp.status_code, 200)

    def test_anonymous_not_redirected(self):
        """
        未ログインユーザーはリダイレクト対象外
        """
        from django.contrib.auth.models import AnonymousUser
        request = self.factory.get(reverse("organization_admin:classroom_list"))
        request.user = AnonymousUser()
        resp = self.middleware(request)
        self.assertEqual(resp.status_code, 200)

    def test_student_without_first_login_do_not_redirected(self):
        """
        生徒は初回ログイン状態でなければリダイレクトされない
        """
        user = self._make_user("student", is_first_login=False)
        resp = self._get(reverse("student:home"), user)
        self.assertEqual(resp.status_code, 200)

    def test_teacher_without_first_login_do_not_redirected(self):
        """
        講師は初回ログイン状態でなければリダイレクトされない
        """
        user = self._make_user("teacher", is_first_login=False)
        resp = self._get(reverse("organization_admin:teacher_dashboard"), user)
        self.assertEqual(resp.status_code, 200)

    def test_classroom_admin_without_first_login_do_not_redirected(self):
        """
        教室管理者は初回ログイン状態でなければリダイレクトされない
        """
        user = self._make_user("classroom_administrator", is_first_login=False)
        resp = self._get(reverse("organization_admin:classroom_list"), user)
        self.assertEqual(resp.status_code, 200)

    # --- 許可 URL（middleware は通過させる）---
    def test_student_login_url_allowed(self):
        """
        生徒は初回ログイン状態であっても、ログイン画面は許可されているのでリダイレクトされない
        """
        user = self._make_user("student")
        resp = self._get(reverse("accounts_auth:login"), user)
        self.assertEqual(resp.status_code, 200)

    def test_student_logout_url_allowed(self):
        """
        生徒は初回ログイン状態であっても、ログアウト画面は許可されているのでリダイレクトされない
        """
        user = self._make_user("student")
        resp = self._get(reverse("accounts_auth:logout"), user)
        self.assertEqual(resp.status_code, 200)

    def test_student_account_edit_get_allowed(self):
        """
        生徒は初回ログイン状態であっても、アカウント編集画面へのGETは許可されているのでリダイレクトされない
        """
        user = self._make_user("student")
        resp = self._get(self._account_edit_url(), user)
        self.assertEqual(resp.status_code, 200)

    def test_student_account_edit_post_allowed(self):
        """
        生徒は初回ログイン状態であっても、アカウント編集画面へのPOSTは許可されているのでリダイレクトされない
        """
        user = self._make_user("student")
        request = self.factory.post(self._account_edit_url(), data={})
        request.user = user
        resp = self.middleware(request)
        self.assertEqual(resp.status_code, 200)

    def test_teacher_login_url_allowed(self):
        """
        講師は初回ログイン状態であっても、ログイン画面は許可されているのでリダイレクトされない
        """
        user = self._make_user("teacher")
        resp = self._get(reverse("accounts_auth:login"), user)
        self.assertEqual(resp.status_code, 200)

    def test_teacher_logout_url_allowed(self):
        """
        講師は初回ログイン状態であっても、ログアウト画面は許可されているのでリダイレクトされない
        """
        user = self._make_user("teacher")
        resp = self._get(reverse("accounts_auth:logout"), user)
        self.assertEqual(resp.status_code, 200)

    def test_teacher_account_edit_get_allowed(self):
        """
        講師は初回ログイン状態であっても、アカウント編集画面へのGETは許可されているのでリダイレクトされない
        """
        user = self._make_user("teacher")
        resp = self._get(self._account_edit_url(), user)
        self.assertEqual(resp.status_code, 200)

    def test_teacher_account_edit_post_allowed(self):
        """
        講師は初回ログイン状態であっても、アカウント編集画面へのPOSTは許可されているのでリダイレクトされない
        """
        user = self._make_user("teacher")
        request = self.factory.post(self._account_edit_url(), data={})
        request.user = user
        resp = self.middleware(request)
        self.assertEqual(resp.status_code, 200)

    def test_classroom_administrator_login_url_allowed(self):
        """
        教室管理者は初回ログイン状態であっても、ログイン画面は許可されているのでリダイレクトされない
        """
        user = self._make_user("classroom_administrator")
        resp = self._get(reverse("accounts_auth:login"), user)
        self.assertEqual(resp.status_code, 200)

    def test_classroom_administrator_logout_url_allowed(self):
        """
        教室管理者は初回ログイン状態であっても、ログアウト画面は許可されているのでリダイレクトされない
        """
        user = self._make_user("classroom_administrator")
        resp = self._get(reverse("accounts_auth:logout"), user)
        self.assertEqual(resp.status_code, 200)

    def test_classroom_administrator_account_edit_get_allowed(self):
        """
        教室管理者は初回ログイン状態であっても、アカウント編集画面へのGETは許可されているのでリダイレクトされない
        """
        user = self._make_user("classroom_administrator")
        resp = self._get(self._account_edit_url(), user)
        self.assertEqual(resp.status_code, 200)

    def test_classroom_administrator_account_edit_post_allowed(self):
        """
        教室管理者は初回ログイン状態であっても、アカウント編集画面へのPOSTは許可されているのでリダイレクトされない
        """
        user = self._make_user("classroom_administrator")
        request = self.factory.post(self._account_edit_url(), data={})
        request.user = user
        resp = self.middleware(request)
        self.assertEqual(resp.status_code, 200)

    # --- 許可 prefix ---
    def test_student_static_prefix_allowed(self):
        """
        生徒は/static/フォルダへアクセス可能
        """
        user = self._make_user("student")
        resp = self._get("/static/example.css", user)
        self.assertEqual(resp.status_code, 200)

    def test_student_media_temp_audio_allowed(self):
        """
        生徒は/media/temp_audio/フォルダへアクセス可能
        """
        user = self._make_user("student")
        resp = self._get("/media/temp_audio/example.mp3", user)
        self.assertEqual(resp.status_code, 200)


    def test_teacher_static_prefix_allowed(self):
        """
        講師は/static/フォルダへアクセス可能
        """
        user = self._make_user("teacher")
        resp = self._get("/static/example.css", user)
        self.assertEqual(resp.status_code, 200)

    def test_teacher_media_temp_audio_allowed(self):
        """
        講師は/media/temp_audio/フォルダへアクセス可能
        """
        user = self._make_user("teacher")
        resp = self._get("/media/temp_audio/example.mp3", user)
        self.assertEqual(resp.status_code, 200)

    def test_classroom_administrator_static_prefix_allowed(self):
        """
        教室管理者は/static/フォルダへアクセス可能
        """
        user = self._make_user("classroom_administrator")
        resp = self._get("/static/example.css", user)
        self.assertEqual(resp.status_code, 200)

    def test_classroom_administrator_media_temp_audio_allowed(self):
        """
        教室管理者は/media/temp_audio/フォルダへアクセス可能
        """
        user = self._make_user("classroom_administrator")
        resp = self._get("/media/temp_audio/example.mp3", user)
        self.assertEqual(resp.status_code, 200)

    # --- 許可 URL に偽装したパス ---

    def test_student_account_edit_evil_path_blocked(self):
        """
        account_edit に似せた別 URL は許可しない
        """
        user = self._make_user("student")

        resp = self._get(self._account_edit_url() + "-evil/", user)

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], self._account_edit_url())

    # --- 許可されない prefix ---
    def test_student_static_evil_blocked(self):
        """
        生徒はstaticに偽装されたリンクではリダイレクトが発生する
        """
        user = self._make_user("student")
        resp = self._get("/static-evil/example.css", user)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], self._account_edit_url())

    def test_student_media_temp_audio_evil_blocked(self):
        """
        生徒はmediaに偽装されたリンクではリダイレクトが発生する
        """
        user = self._make_user("student")
        resp = self._get("/media/temp_audio-evil/example.mp3", user)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], self._account_edit_url())

    def test_student_media_root_blocked(self):
        """
        生徒はmediaに偽装されたリンクではリダイレクトが発生する
        """
        user = self._make_user("student")
        resp = self._get("/media/example.mp3", user)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], self._account_edit_url())

    def test_teacher_static_evil_blocked(self):
        """
        講師はstaticに偽装されたリンクではリダイレクトが発生する
        """
        user = self._make_user("teacher")
        resp = self._get("/static-evil/example.css", user)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], self._account_edit_url())

    def test_teacher_media_temp_audio_evil_blocked(self):
        """
        講師はmediaに偽装されたリンクではリダイレクトが発生する
        """
        user = self._make_user("teacher")
        resp = self._get("/media/temp_audio-evil/example.mp3", user)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], self._account_edit_url())

    def test_teacher_media_root_blocked(self):
        """
        講師はmediaに偽装されたリンクではリダイレクトが発生する
        """
        user = self._make_user("teacher")
        resp = self._get("/media/example.mp3", user)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], self._account_edit_url())

    def test_classroom_administrator_static_evil_blocked(self):
        """
        教室管理者はstaticに偽装されたリンクではリダイレクトが発生する
        """
        user = self._make_user("classroom_administrator")
        resp = self._get("/static-evil/example.css", user)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], self._account_edit_url())

    def test_classroom_administrator_media_temp_audio_evil_blocked(self):
        """
        教室管理者はmediaに偽装されたリンクではリダイレクトが発生する
        """
        user = self._make_user("classroom_administrator")
        resp = self._get("/media/temp_audio-evil/example.mp3", user)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], self._account_edit_url())

    def test_classroom_administrator_media_root_blocked(self):
        """
        教室管理者はstaticに偽装されたリンクではリダイレクトが発生する
        """
        user = self._make_user("classroom_administrator")
        resp = self._get("/media/example.mp3", user)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], self._account_edit_url())

class FirstLoginMiddlewareIntegrationTests(TestCase):
    def test_first_login_middleware_is_applied_in_request_pipeline(self):
        """
        Django の実リクエストパイプラインでも、
        初回ログイン中の生徒は通常画面へ進めない
        """
        user = BaseUser.objects.create_user(
            email="pipeline_student@example.com",
            password="testpass123",
            username="pipeline_student",
            role="student",
        )
        user.is_first_login = True
        user.save(update_fields=["is_first_login"])

        self.client.force_login(user)

        resp = self.client.get(reverse("student:home"))

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            resp["Location"],
            reverse("organization_admin:account_edit"),
        )