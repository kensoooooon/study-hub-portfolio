from django.views import View
from django.http import HttpResponse
from django.shortcuts import render
from django.core import signing

import requests

from line_channels.models import LineChannel, KeyKind
from line_channels.services import get_secret
from accounts.models import Student


# CSRF有効のまま（テンプレに {% csrf_token %} あり）
class RegisterNameView(View):
    def _get_student_or_403(self, line_user_id: str, org_id: int):
        """取得可能な生徒を取得する

        Args:
            line_user_id (str): 対象生徒のLINEユーザーID
            org_id (int): チャネルの組織ID（新規作成時に初回設定する）

        Returns:
            tuple(Optional[Student], Optional[HttpResponse]): 生徒とエラー発生時はエラーレスポンス
        
        Notes:
            - get_or_create_userの仕様により、既に生徒の組織が決まっている時は上書きされない挙動
        """
        student, _ = Student.objects.get_or_create_user(
            line_user_id=line_user_id,
            organization_id=org_id
        )

        if not student.is_active:
            return None, HttpResponse("アカウントが無効化されています。", status=403)

        return student, None

    def _load_token(self, request, line_user_id):
        token = request.GET.get("t") or request.POST.get("t")
        if not token:
            return None, None, "リンクが不正です（トークン欠如）"
        try:
            data = signing.loads(token, salt="register-name", max_age=3600)
        except signing.SignatureExpired:
            return None, None, "リンクの有効期限が切れています"
        except signing.BadSignature:
            return None, None, "リンクが不正です（署名検証失敗）"

        if data.get("line_user_id") != line_user_id:
            return None, None, "リンクが不正です（ユーザー不一致）"

        # ★ dest と org_id を返す
        return data.get("dest"), data.get("org_id"), None

    def _resolve_channel_and_org(self, dest, org_id):
        # ★ dest からチャネル・組織を確定し、トークンのorg_idと一致を検証
        ch = LineChannel.objects.get(bot_user_id=dest, is_active=True)
        org = ch.organization
        try:
            org_id_int = int(org_id)
        except (TypeError, ValueError):
            raise ValueError("リンクが不正です（組織ID不正）")
        if org.id != org_id_int:
            raise ValueError("リンクが不正です（組織不一致）")
        return ch, org

    def get(self, request, line_user_id, *args, **kwargs):
        if not line_user_id:
            return HttpResponse("セッションが無効です。", status=400)

        dest, org_id, err = self._load_token(request, line_user_id)
        if err:
            return HttpResponse(err, status=400)

        try:
            ch, org = self._resolve_channel_and_org(dest, org_id)
        except Exception as e:
            return HttpResponse(str(e), status=400)

        student, error_response = self._get_student_or_403(line_user_id, org_id=org.id)
        if error_response:
            return error_response
        if student.organization_id != org.id:
            return HttpResponse("現在、別の教室アカウントでご利用中です。", status=400)

        if (student.username or "").strip():
            return HttpResponse("すでにお名前は登録済みです。LINEに戻って質問を続けてください。")

        return render(request, "accounts/user_register/register_name.html",{"student": student, "token": request.GET.get("t")})

    def post(self, request, line_user_id, *args, **kwargs):
        if not line_user_id:
            return HttpResponse("セッションが無効です。", status=400)

        dest, org_id, err = self._load_token(request, line_user_id)
        if err:
            return HttpResponse(err, status=400)

        try:
            ch, org = self._resolve_channel_and_org(dest, org_id)
        except Exception as e:
            return HttpResponse(str(e), status=400)

        student, error_response = self._get_student_or_403(line_user_id, org_id=org.id)
        if error_response:
            return error_response
        if student.organization_id != org.id:
            return HttpResponse("現在、別の教室アカウントでご利用中です。", status=400)

        last_name = (request.POST.get("last_name") or "").strip()
        first_name = (request.POST.get("first_name") or "").strip()
        if not last_name or not first_name:
            return HttpResponse("姓と名を入力してください。", status=400)

        if (student.username or "").strip():
            return HttpResponse("すでにお名前は登録済みです。LINEに戻って質問を続けてください。")

        student.username = f"{last_name} {first_name}"
        student.save(update_fields=["username"])
        if not student.password:
            student.set_default_password()

        try:
            access_token = get_secret(ch, KeyKind.ACCESS_TOKEN).decode().strip()
        except Exception:
            return HttpResponse("名前は登録されましたが、メッセージ送信に失敗しました。", status=500)

        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"}
        data = {"to": line_user_id, "messages": [{"type": "text", "text": f"{student.username}さん、お名前の登録が完了しました！"}]}
        try:
            resp = requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=data, timeout=(3.05, 10))
            if resp.status_code != 200:
                return HttpResponse("名前は登録されましたが、メッセージ送信に失敗しました。", status=500)
        except requests.RequestException:
            return HttpResponse("名前は登録されましたが、メッセージ送信に失敗しました。", status=500)

        return HttpResponse("名前が登録されました! LINEに戻って質問を続けて下さい!")
