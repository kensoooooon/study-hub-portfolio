import re
from django import forms


from line_channels.models import LineChannel
from accounts.models import Organization


SAFE_SECRET_RE = re.compile(r"^[A-Za-z0-9\-_]+$")  # アルファベット、数字、アンダースコア、ハイフンのみを許可
SAFE_ACCESS_TOKEN_RE = re.compile(r"^[^\s]+$")
SAFE_CHANNEL_ID_RE = re.compile(r"^\d+$")  # 数字のみ許可


class ChannelSecretRotateForm(forms.Form):
    new_channel_secret = forms.CharField(
        strip=False,
        required=True,
        max_length=80,
        widget=forms.PasswordInput(attrs={"autocomplete": "off"}),
    )
    new_channel_secret_confirm = forms.CharField(
        strip=False,
        required=True,
        max_length=80,
        widget=forms.PasswordInput(attrs={"autocomplete": "off"}),
    )

    def clean_new_channel_secret(self):
        s = self.cleaned_data["new_channel_secret"]

        # 空白・改行系を弾く（コピペ事故対策）
        if any(ch in s for ch in ["\n", "\r", "\t", " "]):
            raise forms.ValidationError("空白や改行を含まない値を入力してください。")

        # 文字種（必要に応じて緩めてもOK）
        if not SAFE_SECRET_RE.match(s):
            raise forms.ValidationError("使用できない文字が含まれています。")

        # 最低長（任意。短すぎる事故を防ぐ）
        if len(s) < 20:
            raise forms.ValidationError("短すぎます。入力内容を確認してください。")

        return s

    def clean(self):
        cleaned = super().clean()
        a = cleaned.get("new_channel_secret")
        b = cleaned.get("new_channel_secret_confirm")
        if a and b and a != b:
            self.add_error("new_channel_secret_confirm", "確認用の入力が一致しません。")
        return cleaned

class ChannelAccessTokenRotateForm(forms.Form):
    new_channel_access_token = forms.CharField(
        strip=False,
        required=True,
        max_length=300,
        widget=forms.PasswordInput(attrs={"autocomplete": "off"}),
    )
    new_channel_access_token_confirm = forms.CharField(
        strip=False,
        required=True,
        max_length=300,
        widget=forms.PasswordInput(attrs={"autocomplete": "off"}),
    )
    
    def clean_new_channel_access_token(self):
        s = self.cleaned_data["new_channel_access_token"]

        # 空白・改行系を弾く（コピペ事故対策）
        if any(ch in s for ch in ["\n", "\r", "\t", " "]):
            raise forms.ValidationError("空白や改行を含まない値を入力してください。")

        # 文字種（必要に応じて緩めてもOK）
        if not SAFE_ACCESS_TOKEN_RE.match(s):
            raise forms.ValidationError("使用できない文字が含まれています。")

        # 最低長（任意。短すぎる事故を防ぐ）
        if len(s) < 20:
            raise forms.ValidationError("短すぎます。入力内容を確認してください。")

        return s
    
    def clean(self):
        cleaned = super().clean()
        a = cleaned.get("new_channel_access_token")
        b = cleaned.get("new_channel_access_token_confirm")
        if a and b and a != b:
            self.add_error("new_channel_access_token_confirm", "確認用の入力が一致しません。")
        return cleaned


class LineChannelCreateForm(forms.ModelForm):
    channel_secret = forms.CharField(
        label="チャネルシークレット",
        required=True,
        max_length=80,
        strip=False,  # 重要：トークン系は勝手にstripしない
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="LINE Developers のチャネルシークレットを貼り付けてください。",
    )
    channel_secret_confirm = forms.CharField(
        label="チャネルシークレット（確認用）",
        required=True,
        max_length=80,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    channel_access_token = forms.CharField(
        label="チャンネルアクセストークン",
        required=True,
        max_length=300,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="LINE Developers の長期アクセストークンを貼り付けてください。",
    )
    channel_access_token_confirm = forms.CharField(
        label="チャンネルアクセストークン（確認用）",
        required=True,
        max_length=300,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = LineChannel
        fields = ["channel_id"]
        labels = {"channel_id": "チャネルID"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (css + " form-control")

    def clean_channel_id(self):
        s = (self.cleaned_data.get("channel_id") or "")
        if any(ch in s for ch in ["\n", "\r", "\t", " "]):
            raise forms.ValidationError("空白や改行を含まない値を入力してください。")
        s = s.strip()  # 前後だけ救済
        if not s:
            raise forms.ValidationError("チャネルIDを入力してください。")
        if not SAFE_CHANNEL_ID_RE.match(s):
            raise forms.ValidationError("チャネルIDは数字のみで入力してください。")
        return s

    def _reject_whitespace(self, s: str, label: str) -> str:
        # stripしない。含まれていたら「ミス」として弾く
        if any(ch in s for ch in ["\n", "\r", "\t", " "]):
            raise forms.ValidationError(f"{label}に空白や改行を含めないでください。")
        return s

    def clean_channel_secret(self):
        s = self.cleaned_data.get("channel_secret") or ""
        s = self._reject_whitespace(s, "チャネルシークレット")
        if not SAFE_SECRET_RE.match(s):
            raise forms.ValidationError("使用できない文字が含まれています。")
        if len(s) < 20:
            raise forms.ValidationError("短すぎます。入力内容を確認してください。")
        return s

    def clean_channel_access_token(self):
        s = self.cleaned_data.get("channel_access_token") or ""
        s = self._reject_whitespace(s, "チャンネルアクセストークン")
        if not SAFE_ACCESS_TOKEN_RE.match(s):
            raise forms.ValidationError("使用できない文字が含まれています。")
        if len(s) < 20:
            raise forms.ValidationError("短すぎます。入力内容を確認してください。")
        return s

    def clean(self):
        cleaned = super().clean()

        secret1 = cleaned.get("channel_secret")
        secret2 = cleaned.get("channel_secret_confirm")
        if secret1 and secret2 and secret1 != secret2:
            self.add_error("channel_secret_confirm", "チャネルシークレットの値が一致しません。")

        token1 = cleaned.get("channel_access_token")
        token2 = cleaned.get("channel_access_token_confirm")
        if token1 and token2 and token1 != token2:
            self.add_error("channel_access_token_confirm", "チャンネルアクセストークンの値が一致しません。")

        return cleaned