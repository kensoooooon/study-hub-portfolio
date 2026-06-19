from django.shortcuts import render
from django.urls import reverse
from django.views import View

from accounts.forms import StudentEmailRegistrationForm
from accounts.services.exceptions import (
    StudentEmailAlreadyRegisteredError,
    StudentEmailConflictError,
    StudentEmailRegistrationTokenInactiveError,
    StudentEmailRegistrationTokenInvalidError,
)
from accounts.services.student_email_registration import (
    confirm_email_registration,
    get_token_by_raw,
)

_INVALID_TEMPLATE = "accounts/user_register/invalid_email_registration.html"
_FORM_TEMPLATE = "accounts/user_register/register_email.html"
_SUCCESS_TEMPLATE = "accounts/user_register/email_registration_success.html"


class RegisterEmailView(View):
    """LINE経由のメールアドレス登録フォームを提供するView。

    GET: トークン検証後にメール入力フォームを表示する。
    POST: フォーム値を受け取り confirm_email_registration() で登録を確定する。
    """

    def get(self, request):
        raw_token = request.GET.get("t")
        if not raw_token:
            return self._invalid(request, "登録リンクが不正です。")

        try:
            token = get_token_by_raw(raw_token)
        except StudentEmailRegistrationTokenInvalidError:
            return self._invalid(request, "登録リンクが不正です。")

        if not token.is_active:
            return self._invalid(
                request,
                "この登録リンクはすでに無効です。LINEから再度「メール登録」と送信してください。",
            )

        student = token.student
        if not student.is_active:
            return self._invalid(request, "アカウントが無効化されています。")

        if student.email:
            login_url = request.build_absolute_uri(reverse("accounts_auth:login"))
            return render(request, _FORM_TEMPLATE, {"already_registered": True, "login_url": login_url})

        form = StudentEmailRegistrationForm()
        return render(request, _FORM_TEMPLATE, {"form": form, "token": raw_token})

    def post(self, request):
        raw_token = request.POST.get("t")
        if not raw_token:
            return self._invalid(request, "登録リンクが不正です。")

        form = StudentEmailRegistrationForm(request.POST)
        if not form.is_valid():
            return render(
                request, _FORM_TEMPLATE, {"form": form, "token": raw_token}
            )

        try:
            confirm_email_registration(
                raw_token=raw_token,
                email=form.cleaned_data["email"],
            )
        except StudentEmailRegistrationTokenInvalidError:
            return self._invalid(request, "登録リンクが不正です。")
        except StudentEmailRegistrationTokenInactiveError:
            return self._invalid(
                request,
                "この登録リンクはすでに無効です。LINEから再度「メール登録」と送信してください。",
            )
        except StudentEmailAlreadyRegisteredError:
            login_url = request.build_absolute_uri(reverse("accounts_auth:login"))
            return render(request, _FORM_TEMPLATE, {"already_registered": True, "login_url": login_url})
        except StudentEmailConflictError as e:
            form.add_error("email", e.user_message)
            return render(
                request, _FORM_TEMPLATE, {"form": form, "token": raw_token}
            )

        login_url = request.build_absolute_uri(reverse("accounts_auth:login"))
        return render(request, _SUCCESS_TEMPLATE, {"login_url": login_url})

    def _invalid(self, request, reason: str):
        return render(
            request,
            _INVALID_TEMPLATE,
            {"reason": reason},
            status=400,
        )
