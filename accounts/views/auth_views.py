from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.urls import reverse

class CustomLoginView(LoginView):
    template_name = 'accounts/auth/login.html'  # ここでテンプレート名を指定    

    def get_success_url(self):
        user = self.request.user
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
