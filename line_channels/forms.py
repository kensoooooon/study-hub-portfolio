import re
from django import forms


SAFE_SECRET_RE = re.compile(r"^[A-Za-z0-9\-_]+$")  # アルファベット、数字、アンダースコア、ハイフンのみを許可

SAFE_ACCESS_TOKEN_RE = re.compile(r"^[^\s]+$")

class ChannelSecretRotateForm(forms.Form):
    new_channel_secret = forms.CharField(
        required=True,
        max_length=80,
        widget=forms.PasswordInput(attrs={"autocomplete": "off"}),
    )
    new_channel_secret_confirm = forms.CharField(
        required=True,
        max_length=80,
        widget=forms.PasswordInput(attrs={"autocomplete": "off"}),
    )

    def clean_new_channel_secret(self):
        s = self.cleaned_data["new_channel_secret"].strip()

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
        required=True,
        max_length=300,
        widget=forms.PasswordInput(attrs={"autocomplete": "off"}),
    )
    new_channel_access_token_confirm = forms.CharField(
        required=True,
        max_length=300,
        widget=forms.PasswordInput(attrs={"autocomplete": "off"}),
    )
    
    def clean_new_channel_access_token(self):
        s = self.cleaned_data["new_channel_access_token"].strip()

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
