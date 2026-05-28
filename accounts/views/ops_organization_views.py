"""
組織内の教室や講師、生徒などを管理するorganization_admin_views.py
組織自体の作成などを管理するops_organization_views.py
"""
import logging
import hashlib


from django.views.generic import ListView, DetailView, CreateView, FormView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.http import Http404
from django.db import transaction
from django.conf import settings
from django.db.models import Q, Count

from accounts.models import Organization
from accounts.forms import OrganizationCreateForm, OrganizationAdminSelectForm
from accounts.access_policies import (
    require_can_view_organization,
    require_can_add_organization,
    require_can_assign_organization_administrator,
    require_can_invite_organization_administrator
    )
from accounts.selectors import visible_organizations_qs, visible_organization_administrators_qs
from accounts.services.invitations import invite_organization_administrator
from accounts.services.exceptions import (
    InvalidEmailError,
    InvitationAlreadyExistsError,
    InvitationOrganizationNotFoundError,
    InvalidTokenError,
    InvitationDoesNotExist,
    InactiveInvitationError,
    ExistingUserError,
    OrganizationAdministratorAlreadyAssignedError,
    OrganizationAdministratorExistsInAnotherOrganizationError,
    ExistingUserWrongRoleError,
    AnotherRoleExistsInAnotherOrganizationError
)
from accounts.forms import OrganizationAdminInvitationCreateForm, OrganizationAdminInvitationAcceptForm
from accounts.services.accept_invitations import build_accept_invitation_display_info, check_and_confirm_invitation

logger = logging.getLogger(__name__)


class OrganizationListView(LoginRequiredMixin, ListView):
    model = Organization
    template_name = "accounts/ops_organization/list.html"
    context_object_name = "organizations"
    
    def dispatch(self, request, *args, **kwargs):
        user = request.user
        user_id = user.id
        if hasattr(user, "role"):
            role = user.role
        else:
            role = None
        phase = "list dispatch"
        log_dict = {
            "phase": phase,
            "user_id": user_id,
            "role": role,
        }
        require_can_view_organization(user, log_dict=log_dict)
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return visible_organizations_qs(self.request.user).annotate(
            active_student_count=Count(
                "students",
                filter=Q(students__is_active=True),
            )
        )
    

class OrganizationDetailView(LoginRequiredMixin, DetailView):
    model = Organization
    template_name = "accounts/ops_organization/detail.html"
    context_object_name = "organization"
    
    def dispatch(self, request, *args, **kwargs):
        user = request.user
        user_id = user.id
        if hasattr(user, "role"):
            role = user.role
        else:
            role = None
        phase = "detail dispatch"
        org_id = kwargs.get("pk")
        log_dict = {
            "phase": phase,
            "user_id": user_id,
            "org_id": org_id,
            "role": role,
        }
        require_can_view_organization(user, log_dict=log_dict)
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        orgs = visible_organizations_qs(self.request.user).prefetch_related("administrators")
        return get_object_or_404(orgs, pk=self.kwargs["pk"])

    def get_queryset(self):
        return (
            visible_organizations_qs(self.request.user)
            .prefetch_related("administrators")
        )
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        org = self.get_object()
        has_line_channel = org.line_channels.exists()
        context["has_line_channel"] = has_line_channel
        return context


class OrganizationCreateView(LoginRequiredMixin, CreateView):
    model = Organization
    form_class = OrganizationCreateForm
    template_name = "accounts/ops_organization/create.html"

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        phase = "create dispatch"

        org_name = None
        if request.method == "POST":
            # フォーム未検証なので「そのまま」取得（strip だけしてもOK）
            org_name = (request.POST.get("name") or "").strip()
        org_name = org_name[:200] if org_name else None


        log_dict = {
            "phase": phase,
            "user_id": user.id,
            "role": getattr(user, "role", None),
            "org_name": org_name,   # ← 追加
        }

        require_can_add_organization(user, log_dict=log_dict)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        logger.info(
            "organization created",
            extra={
                "user_id": self.request.user.id,
                "organization_id": self.object.pk,
                "organization_name": self.object.name,
            },
        )
        return response
    
    def get_success_url(self):
        return reverse(
            "ops_organization:detail",
            kwargs={"pk": self.object.pk}
        )


class OrganizationAdminSelectView(LoginRequiredMixin, FormView):
    """
        dispatch()
            ↓
        post()
            ↓
        get_form()
            ↓
        get_form_class()
            ↓
        get_form_kwargs(): kwargsが設定
            ↓
        form_class(**kwargs)  ← __init__ が呼ばれる
            ↓
        form.is_valid()
            ↓
        form.full_clean()
            ↓
        ・各フィールドの clean
        ・clean_<field>()
        ・clean()
            ↓
        if True:
            form_valid(form)   ← ★ここ
        else:
            form_invalid(form)

        dispatch()
        ↓
        get()
        ↓
        get_form()
        ↓
        get_form_kwargs()
        ↓
        form_class(**kwargs)
        ↓
        render_to_response(context)
    """
    form_class = OrganizationAdminSelectForm
    template_name = "accounts/ops_organization/admin_select.html"
    
    def dispatch(self, request, *args, **kwargs):
        user = request.user
        phase = "admin select dispatch"
        org_id = self.kwargs.get("pk")
        orgs = visible_organizations_qs(self.request.user)
        self._org = get_object_or_404(orgs, pk=org_id)
        log_dict = {
            "phase": phase,
            "user_id": user.id,
            "role": getattr(user, "role", None),
            "org_id": org_id,
        }
        require_can_assign_organization_administrator(user, log_dict=log_dict)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["org_id"] = self._org.id
        context["org_name"] = self._org.name
        candidate_qs = self.get_org_admin_candidates()
        context["has_candidates"] = candidate_qs.exists()
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        candidate_qs = self.get_org_admin_candidates()
        kwargs["candidate_qs"] = candidate_qs
        return kwargs

    def form_valid(self, form):
        org_id = self.kwargs["pk"]
        org = get_object_or_404(visible_organizations_qs(self.request.user), pk=org_id)

        selected_admins = form.cleaned_data["admins"]  # ← 既に候補QSで検証済み

        return render(self.request, "accounts/ops_organization/admin_confirm.html", {
            "org": org,
            "org_name": org.name,
            "selected_admins": selected_admins,
        })
    
    def get_org_admin_candidates(self):
        """
        組織管理者のうち、既に組織に登録されている人を除く人たちを返す
        """
        candidate_qs = visible_organization_administrators_qs(self.request.user)
        candidate_qs = candidate_qs.exclude(organizations=self._org)
        return candidate_qs


class OrganizationAssignAdminConfirmView(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        user = request.user
        phase = "admin select confirm dispatch"
        org_id = self.kwargs.get("pk")
        orgs = visible_organizations_qs(self.request.user)
        self._org = get_object_or_404(orgs, pk=org_id)
        log_dict = {
            "phase": phase,
            "user_id": user.id,
            "role": getattr(user, "role", None),
            "org_id": org_id,
        }
        require_can_assign_organization_administrator(user, log_dict=log_dict)
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        raw_admin_ids = request.POST.getlist("admin_ids")
        if not raw_admin_ids:
            messages.error(request, "割り当てたい組織管理者が選択されていません。")
            return redirect("ops_organization:list")

        # 重複検知（ログだけ）
        deduped_ids = list(dict.fromkeys(raw_admin_ids))  # 順序維持で重複除去（任意）
        if len(raw_admin_ids) != len(deduped_ids):
            logger.warning(
                "入力された管理者IDに重複が存在します。",
                extra={
                    "user_id": request.user.id,
                    "org_id": self._org.id,
                    "raw_count": len(raw_admin_ids),
                    "deduped_count": len(deduped_ids),
                },
            )

        admin_ids = set(deduped_ids)

        candidate_qs = (
            visible_organization_administrators_qs(request.user)
            .exclude(organizations=self._org)
        )
        admins = list(candidate_qs.filter(pk__in=admin_ids))

        # 差分チェック（改ざん耐性）
        actual_ids = {str(a.pk) for a in admins}
        expected_ids = {str(x) for x in admin_ids}

        missing_ids = sorted(expected_ids - actual_ids)  # 候補外/存在しない
        if missing_ids:
            logger.warning(
                "存在しない/候補外の組織管理者IDが指定されています。",
                extra={
                    "user_id": request.user.id,
                    "org_id": self._org.id,
                    "missing_ids": missing_ids[:20],  # ログ肥大化防止
                    "missing_count": len(missing_ids),
                },
            )
            raise Http404

        with transaction.atomic():
            self._org.administrators.add(*admins)

        messages.success(request, "組織管理者の割当が完了しました。")
        return redirect(reverse("ops_organization:detail", kwargs={"pk": self._org.pk}))

    
class OrganizationAdminInvitationCreateView(LoginRequiredMixin, FormView):
    """
    組織管理者招待作成画面の表示、および招待を担当する
    
    Note:
        formの使い所は？FormViewはいる？
    """
    template_name = "accounts/ops_organization/invite.html"
    form_class = OrganizationAdminInvitationCreateForm
    
    def dispatch(self, request, *args, **kwargs):  # 境界線チェック
        user = request.user
        phase = "admin invite create dispatch"
        org_id = self.kwargs.get("organization_id")
        orgs = visible_organizations_qs(self.request.user)
        self._org = get_object_or_404(orgs, pk=org_id)
        log_dict = {
            "phase": phase,
            "user_id": user.id,
            "role": getattr(user, "role", None),
            "org_id": org_id,
        }
        require_can_invite_organization_administrator(user, log_dict=log_dict)
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["organization"] = self._org
        return context
    
    def form_valid(self, form):
        email_address = form.cleaned_data["email"]
        accept_path = reverse("ops_organization:accept_org_admin_invitation")
        accept_base_url = f"{settings.APP_PUBLIC_BASE_URL}{accept_path}"

        try:
            invite_organization_administrator(
                accept_base_url=accept_base_url,
                user=self.request.user,
                organization_id=self._org.id,
                email_address=email_address,
            )
        except InvalidEmailError as e:  # 正規化したメールアドレスが取得できない
            form.add_error("email", e.user_message)
            return self.form_invalid(form)
        except InvitationAlreadyExistsError as e:  # すでに対象に対して有効な招待が存在している
            form.add_error("email", e.user_message)
            return self.form_invalid(form)
        except ExistingUserWrongRoleError as e:  # 該当組織に別ロールとして所属している
            form.add_error("email", e.user_message)
            return self.form_invalid(form)
        except AnotherRoleExistsInAnotherOrganizationError as e:  # 別組織に異なる役職として登録されている
            form.add_error("email", e.user_message)
            return self.form_invalid(form)
        except OrganizationAdministratorAlreadyAssignedError as e:  # 該当組織にすでに組織管理者として登録されている
            messages.info(self.request, e.user_message)
            return redirect("ops_organization:detail", pk=self._org.pk)
        except OrganizationAdministratorExistsInAnotherOrganizationError:  # 別組織に組織管理者として登録されている
            messages.error(
                self.request,
                "すでに他の組織で組織管理者として登録されています。新規招待ではなく、割り当てをご利用ください。"
            )
            return redirect("ops_organization:detail", pk=self._org.pk)
        except InvitationOrganizationNotFoundError:  # 対象となる組織が既に存在していない
            logger.warning(
                "招待対象組織が見つからないため、招待処理を中断しました。",
                extra={
                    "user_id": self.request.user.id,
                    "org_id": self._org.id,
                    "email_address": email_address,
                },
            )
            messages.error(
                self.request,
                "対象の組織が見つからないため、招待を完了できませんでした。組織一覧から状態をご確認ください。"
            )
            return redirect("ops_organization:list")
        except Exception:  # 想定外のエラー群
            logger.exception(
                "招待発行中に想定外の例外が発生しました。",
                extra={
                    "user_id": self.request.user.id,
                    "org_id": self._org.id,
                    "email_address": email_address,
                },
            )
            messages.error(self.request, "招待の送信に失敗しました。")
            return redirect("ops_organization:detail", pk=self._org.pk)

        messages.success(self.request, "招待メールを作成し、送信処理を実行しました。")
        return redirect("ops_organization:detail", pk=self._org.pk)

class OrganizationAdminInvitationAcceptView(FormView):
    form_class = OrganizationAdminInvitationAcceptForm
    template_name = "accounts/ops_organization/input.html"
    invalid_template_name = "accounts/ops_organization/invalid_invitation.html"

    def _get_token(self) -> str | None:
        return self.request.POST.get("t") or self.request.GET.get("t")

    def _render_invalid_invitation(self, message: str, status: int = 400):
        return render(
            self.request,
            self.invalid_template_name,
            {"error_message": message},
            status=status,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["token"] = self._get_token()
        context["info"] = kwargs.get("info")
        return context

    def get(self, request, *args, **kwargs):
        token = self._get_token()
        if not token:
            return self._render_invalid_invitation("無効な招待リンクです。")

        try:
            info = build_accept_invitation_display_info(token=token)
        except (InvalidTokenError, InvitationDoesNotExist, InactiveInvitationError) as e:
            logger.warning(
                "招待リンクの表示時に無効な招待が検出されました。",
                extra={"token_present": bool(token)},
            )
            return self._render_invalid_invitation(str(e))

        return self.render_to_response(
            self.get_context_data(
                form=self.get_form(),
                info=info,
            )
        )

    def form_valid(self, form):
        username = form.cleaned_data["username"]
        password = form.cleaned_data["password"]
        token = self._get_token()

        if not token:
            return self._render_invalid_invitation("無効な招待リンクです。")

        try:
            check_and_confirm_invitation(
                token=token,
                username=username,
                password=password,
            )
        except ExistingUserError as e:
            logger.warning(
                "既存ユーザーのため招待受理を拒否しました。",
                extra={
                    "username": username,
                    "token_present": True,
                },
            )
            form.add_error(None, str(e))

            try:
                info = build_accept_invitation_display_info(token=token)
            except (InvalidTokenError, InvitationDoesNotExist, InactiveInvitationError):
                return self._render_invalid_invitation("無効な招待リンクです。")

            return self.render_to_response(
                self.get_context_data(
                    form=form,
                    info=info,
                )
            )

        except InvalidTokenError as e:
            logger.warning(
                "無効なトークンが拒否されました。",
                extra={"token_present": True},
            )
            return self._render_invalid_invitation(str(e))

        except InvitationDoesNotExist as e:
            logger.warning(
                "該当する招待が存在しません。",
                extra={"token_present": True},
            )
            return self._render_invalid_invitation(str(e))

        except InactiveInvitationError as e:
            logger.warning(
                "無効な招待が選択されました。",
                extra={"token_present": True},
            )
            return self._render_invalid_invitation(str(e))

        messages.success(self.request, "新規組織管理者を作成しました。")
        return redirect("accounts_auth:login")

    def form_invalid(self, form):
        token = self._get_token()
        if not token:
            return self._render_invalid_invitation("無効な招待リンクです。")

        common_ctx = {
            "token_present": bool(token),
            "token_hash": hashlib.sha256(token.encode()).hexdigest()[:10] if token else None,
            "username": (form.data.get("username") or "").strip() or None,
            "form_errors": form.errors.get_json_data(),
            "ip": self.request.META.get("REMOTE_ADDR"),
            "user_agent": self.request.META.get("HTTP_USER_AGENT"),
        }

        try:
            info = build_accept_invitation_display_info(token=token)
        except (InvalidTokenError, InvitationDoesNotExist, InactiveInvitationError):
            logger.warning(
                "招待受理画面のコンテキスト構築中にエラーが発生しました。",
                extra=common_ctx,
                exc_info=True,
            )
            return self._render_invalid_invitation("無効な招待リンクです。")

        logger.info(
            "招待受理フォームのバリデーション失敗",
            extra=common_ctx,
        )

        return self.render_to_response(
            self.get_context_data(
                form=form,
                info=info,
            )
        )
