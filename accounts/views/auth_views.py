from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse

from accounts.services.first_login import requires_first_login_password_change


class CustomLoginView(LoginView):
    template_name = 'accounts/auth/login.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:  # ログイン状態だとこちらで処理
            return redirect(self.get_success_url())  
        return super().dispatch(request, *args, **kwargs)  # 未ログインとしてログイン画面に誘導

    def get_success_url(self):
        user = self.request.user

        if requires_first_login_password_change(user):
            return reverse('organization_admin:account_edit')

        redirect_to = self.get_redirect_url()
        if redirect_to:
            return redirect_to

        if user.is_superuser:
            return reverse('admin:index')
        elif user.role == 'organization_administrator':
            return reverse('organization_admin:classroom_list')
        elif user.role == 'classroom_administrator':
            return reverse('organization_admin:classroom_list')
        elif user.role == 'teacher':
            return reverse('organization_admin:teacher_dashboard')
        elif user.role == 'student':
            return reverse('student:home')
        else:
            raise PermissionDenied("このページにアクセスする権限がありません。")

class CustomLogoutView(LogoutView):
    def get(self, request, *args, **kwargs):
        return self.http_method_not_allowed(request, *args, **kwargs)

    def get_next_page(self):
        return reverse('accounts_auth:login')
