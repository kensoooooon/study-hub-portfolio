import requests
import logging
from requests import RequestException


from django.views.generic import ListView, DetailView, View, FormView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction, IntegrityError


from line_channels.models import LineChannel, KeyKind
from line_channels.access_policies import require_can_view_line_channel_secret_metadata_or_404, require_can_manage_line_channels_or_404, require_can_add_line_channels_or_404
from line_channels.selectors import visible_line_channels_qs, manageable_organizations_for_line_channels
from line_channels.services import store_secret
from line_channels.forms import ChannelSecretRotateForm, ChannelAccessTokenRotateForm, LineChannelCreateForm


logger = logging.getLogger(__name__)


class LineChannelListView(LoginRequiredMixin, ListView):
    model = LineChannel
    template_name = "line_channels/list.html"
    context_object_name = "channels"

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
        require_can_view_line_channel_secret_metadata_or_404(user, log_dict=log_dict)
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return visible_line_channels_qs(self.request.user).select_related("organization")

class LineChannelDetailView(LoginRequiredMixin, DetailView):
    model = LineChannel
    template_name = "line_channels/detail.html"
    context_object_name = "channel"

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        user_id = user.id
        if hasattr(user, "role"):
            role = user.role
        else:
            role = None
        phase = "detail dispatch"
        log_dict = {
            "phase": phase,
            "user_id": user_id,
            "role": role,
        }
        require_can_view_line_channel_secret_metadata_or_404(request.user, log_dict=log_dict)
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return visible_line_channels_qs(self.request.user).select_related("organization")

class LineChannelDeactivateConfirmView(LoginRequiredMixin, DetailView):
    model = LineChannel
    template_name = "line_channels/confirm_deactivate.html"
    context_object_name = "channel"

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        user_id = user.id
        if hasattr(user, "role"):
            role = user.role
        else:
            role = None
        phase = "deactivate confirm dispatch"
        log_dict = {
            "phase": phase,
            "user_id": user_id,
            "role": role,
        }
        require_can_manage_line_channels_or_404(request.user, log_dict=log_dict)
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return visible_line_channels_qs(self.request.user)


class LineChannelDeactivateView(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        user = request.user
        user_id = user.id
        if hasattr(user, "role"):
            role = user.role
        else:
            role = None
        phase = "deactivate dispatch"
        log_dict = {
            "phase": phase,
            "user_id": user_id,
            "role": role,
        }
        require_can_manage_line_channels_or_404(request.user, log_dict=log_dict)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, pk: int, *args, **kwargs):
        channel = get_object_or_404(visible_line_channels_qs(request.user), pk=pk)
        if channel.is_active:
            channel.is_active = False
            channel.save(update_fields=["is_active"])
        return redirect("line_channels:detail", pk=channel.pk)


class LineChannelActivateConfirmView(LoginRequiredMixin, DetailView):
    model = LineChannel
    template_name = "line_channels/confirm_activate.html"
    context_object_name = "channel"

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        user_id = user.id
        if hasattr(user, "role"):
            role = user.role
        else:
            role = None
        phase = "activate confirm dispatch"
        log_dict = {
            "phase": phase,
            "user_id": user_id,
            "role": role,
        }
        require_can_manage_line_channels_or_404(request.user, log_dict=log_dict)
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return visible_line_channels_qs(self.request.user)


class LineChannelActivateView(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        user = request.user
        user_id = user.id
        if hasattr(user, "role"):
            role = user.role
        else:
            role = None
        phase = "activate dispatch"
        log_dict = {
            "phase": phase,
            "user_id": user_id,
            "role": role,
        }
        require_can_manage_line_channels_or_404(request.user, log_dict=log_dict)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, pk: int, *args, **kwargs):
        channel = get_object_or_404(visible_line_channels_qs(request.user), pk=pk)
        if not channel.is_active:
            channel.is_active = True
            channel.save(update_fields=["is_active"])
        return redirect("line_channels:detail", pk=channel.pk)

class ChannelSecretRotateView(LoginRequiredMixin, FormView):
    """
    form入力が介在するため、確認と更新を同じビュー、テンプレートで統一
    """
    form_class = ChannelSecretRotateForm
    template_name = "line_channels/channel_secret_rotate.html"

    def dispatch(self, request, *args, **kwargs):
        require_can_manage_line_channels_or_404(request.user, log_dict={
            "phase": "rotate secret dispatch",
            "user_id": request.user.id,
            "role": getattr(request.user, "role", None),
        })
        return super().dispatch(request, *args, **kwargs)

    def get_channel(self):
        return get_object_or_404(
            visible_line_channels_qs(self.request.user),
            pk=self.kwargs["pk"],
        )

    def get_last_update(self, channel):
        bundle = channel.key_bundles.filter(
            kind=KeyKind.CHANNEL_SECRET,
            is_active=True,
        ).only("created_at").first()
        return bundle.created_at if bundle else None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        channel = self.get_channel()
        ctx["channel"] = channel
        ctx["last_update"] = self.get_last_update(channel)
        return ctx

    def form_valid(self, form):
        channel = self.get_channel()  # ここは例外を握らない（404は404で返す）

        log_ctx = {
            "user_id": self.request.user.id,
            "role": getattr(self.request.user, "role", None),
            "channel_id": channel.id,
            "org_id": channel.organization_id,
            "phase": "rotate channel secret",
        }

        new_secret = form.cleaned_data["new_channel_secret"].encode("utf-8")

        try:
            store_secret(channel, KeyKind.CHANNEL_SECRET, new_secret)
        except Exception:
            logger.exception("チャンネルシークレット登録時にエラーが発生しました。", extra={"ctx": log_ctx})
            form.add_error(None, "チャンネルシークレット登録に失敗しました。時間を置いて再度お試しください。")
            return self.form_invalid(form)

        messages.success(self.request, "新しいチャンネルシークレットを登録しました。")
        return redirect("line_channels:detail", pk=channel.id)


class ChannelAccessTokenRotateView(LoginRequiredMixin, FormView):
    """
    form入力が介在するため、確認と更新を同じビュー、テンプレートで統一
    """
    form_class = ChannelAccessTokenRotateForm
    template_name = "line_channels/channel_access_token_rotate.html"

    def dispatch(self, request, *args, **kwargs):
        require_can_manage_line_channels_or_404(request.user, log_dict={
            "phase": "rotate secret dispatch",
            "user_id": request.user.id,
            "role": getattr(request.user, "role", None),
        })
        return super().dispatch(request, *args, **kwargs)

    def get_channel(self):
        return get_object_or_404(
            visible_line_channels_qs(self.request.user),
            pk=self.kwargs["pk"],
        )

    def get_last_update(self, channel):
        bundle = channel.key_bundles.filter(
            kind=KeyKind.ACCESS_TOKEN,
            is_active=True,
        ).only("created_at").first()
        return bundle.created_at if bundle else None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        channel = self.get_channel()
        ctx["channel"] = channel
        ctx["last_update"] = self.get_last_update(channel)
        return ctx

    def form_valid(self, form):
        channel = self.get_channel()  # ここは例外を握らない（404は404で返す）

        log_ctx = {
            "user_id": self.request.user.id,
            "role": getattr(self.request.user, "role", None),
            "channel_id": channel.id,
            "org_id": channel.organization_id,
            "phase": "rotate access token",
        }

        new_secret = form.cleaned_data["new_channel_access_token"].encode("utf-8")

        try:
            store_secret(channel, KeyKind.ACCESS_TOKEN, new_secret)
        except Exception:
            logger.exception("チャンネルアクセストークン登録時にエラーが発生しました。", extra={"ctx": log_ctx})
            form.add_error(None, "チャンネルアクセストークン登録に失敗しました。時間を置いて再度お試しください。")
            return self.form_invalid(form)

        messages.success(self.request, "新しいチャンネルアクセストークンを登録しました。")
        return redirect("line_channels:detail", pk=channel.id)



class OrganizationLineChannelCreateView(LoginRequiredMixin, CreateView):
    model = LineChannel
    form_class = LineChannelCreateForm
    template_name = "line_channels/create.html"

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        require_can_add_line_channels_or_404(
            user,
            log_dict={"phase": "line_channel create dispatch", "user_id": user.id, "role": getattr(user, "role", None)},
        )
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["org_pk"] = self.kwargs["org_pk"]
        return context

    def form_valid(self, form):
        
        def _constraint_name(e: IntegrityError) -> str | None:
            """エラー情報から、どの規約違反を踏んだのかの詳細な情を取得するためのヘルパー

            Args:
                e (IntegrityError): 発生したエラー

            Returns:
                str | None: 規約違反の種類を示す
            """
            cause = getattr(e, "__cause__", None)
            diag = getattr(cause, "diag", None)
            if diag is not None:
                name = getattr(diag, "constraint_name", None)
                if name:
                    return name
            # fallback
            msg = str(e)
            if "uq_org_bot_user_id" in msg:
                return "uq_org_bot_user_id"
            if "uq_org_channel_id" in msg:
                return "uq_org_channel_id"
            return None

        org_pk = self.kwargs["org_pk"]
        org = get_object_or_404(
            manageable_organizations_for_line_channels(self.request.user),
            pk=org_pk,
        )

        channel_id = form.cleaned_data["channel_id"]
        secret = form.cleaned_data["channel_secret"]
        token = form.cleaned_data["channel_access_token"]

        # 1) まず access token の妥当性をLINE APIで確認しつつ bot_user_id を取得
        resp = None
        try:
            resp = requests.get(
                "https://api.line.me/v2/bot/info",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,  # ← 必須（無限待ち防止）
            )
            resp.raise_for_status()  # ← 4xx/5xx を例外にする
            info = resp.json()
            bot_user_id = info["userId"]
        except requests.HTTPError as e:
            # 401/403/500 など（機密はログに出さない）
            status = getattr(getattr(e, "response", None), "status_code", None)
            logger.warning("LINE bot info request failed (non-2xx).", extra={"org_id": org_pk, "status": status})
            form.add_error("channel_access_token", "アクセストークンが無効、またはLINE APIから情報取得できませんでした。")
            return self.form_invalid(form)
        except (KeyError, ValueError):
            # JSON形式が想定外 / userIdが無い
            logger.warning("LINE bot info response format unexpected.", extra={"org_id": org_pk})
            form.add_error(None, "LINE APIの応答が想定外でした。時間をおいて再試行してください。")
            return self.form_invalid(form)
        except RequestException:
            # タイムアウト、DNS、接続エラーなど
            logger.exception("LINE bot info request exception.", extra={"org_id": org_pk})
            form.add_error(None, "LINE APIへの接続でエラーが発生しました。時間をおいて再試行してください。")
            return self.form_invalid(form)

        try:
            with transaction.atomic():
                ch, created = LineChannel.objects.get_or_create(
                    organization=org,
                    channel_id=channel_id,  # 検索フィールドにbot_user_idを含めない
                    defaults={"bot_user_id": bot_user_id, "is_active": True},
                )

                if not created:
                    messages.warning(self.request, "このチャンネルはすでに登録されています。")
                    return redirect("ops_organization:detail", pk=org.id)

                store_secret(ch, KeyKind.CHANNEL_SECRET, secret.encode("utf-8"))
                store_secret(ch, KeyKind.ACCESS_TOKEN, token.encode("utf-8"))
        except IntegrityError as e:
            c = _constraint_name(e)
            if c == "uq_org_channel_id":
                form.add_error("channel_id", "このチャネルIDはすでに登録されています。")
                return self.form_invalid(form)
            if c == "uq_org_bot_user_id":
                form.add_error(None, "このアクセストークンは、すでに別のチャネルIDで登録されています。チャネルIDの貼り間違いがないか確認してください。")
                return self.form_invalid(form)

            # 想定外の制約違反
            form.add_error(None, "保存に失敗しました。入力内容を確認してください。")
            return self.form_invalid(form)
        
        except Exception:
            messages.error(self.request, "保存に失敗しました。もう一度お試しください。")
            logger.exception("作成保存処理失敗。ロールバック済み")
            return redirect("ops_organization:detail", pk=org.id)

        messages.success(self.request, "LINEチャンネルを登録しました。")
        return redirect("ops_organization:detail", pk=org.id)
