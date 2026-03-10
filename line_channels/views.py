from django.views.generic import ListView, DetailView, View, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages


from line_channels.models import LineChannel, KeyKind
from line_channels.access_policies import require_can_view_line_channel_secret_metadata_or_404, require_can_manage_line_channels_or_404
from line_channels.selectors import visible_line_channels_qs
from line_channels.services import store_secret
from line_channels.forms import ChannelSecretRotateForm, ChannelAccessTokenRotateForm


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
        channel = self.get_channel()
        new_secret = form.cleaned_data["new_channel_secret"].encode("utf-8")
        store_secret(channel, KeyKind.CHANNEL_SECRET, new_secret)
        messages.success(self.request, f"[{channel}]のチャンネルシークレットを更新しました。")
        return redirect("line_channels:detail", pk=channel.pk)


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
        channel = self.get_channel()
        new_secret = form.cleaned_data["new_channel_access_token"].encode("utf-8")
        store_secret(channel, KeyKind.ACCESS_TOKEN, new_secret)
        messages.success(self.request, f"[{channel}]のチャンネルアクセストークンを更新しました。")
        return redirect("line_channels:detail", pk=channel.pk)