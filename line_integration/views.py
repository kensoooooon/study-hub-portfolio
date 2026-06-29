"""
複数チャンネルに対応できるように整えられたview

→基本的な仕組みは同じだが、
    シークレットはsettings.pyからではなく、新しく作成されたline_channels/adapters.pyに委託
    名前の登録の際に多重クリック
"""
from django.views import View
from django.http import JsonResponse
from django.urls import reverse
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core import signing

import json
import requests

from processors.chat_processor import ChatProcessor
from processors.image_processor import ImageProcessor

from accounts.models import Student
from conversations.models import Conversation, MessageLog

from line_channels.adapters import resolve_channel_and_verify, SignatureError, ChannelNotFound
from line_channels.services import get_secret
from line_channels.models import KeyKind

from accounts.services.student_email_registration import maybe_build_email_registration_response

import logging
logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class LineWebhookView(View):
    """
    1) resolve_channel_and_verify() で destination→LineChannel 特定＋署名検証
    2) 返信/画像取得が必要な時だけ ACCESS_TOKEN を封筒復号（遅延復号）
    3) テキスト/画像などの種別はディスパッチ辞書で分岐
    """

    MESSAGE_HANDLERS = {
        "text":  lambda self, e, u, tok: self.handle_text_event(e, u),
        "image": lambda self, e, u, tok: self.handle_image_event(e, u, tok),
    }

    def post(self, request, *args, **kwargs):
        logger.info(
            "[webhook] POST received",
            extra={"path": request.path, "length": len(request.body or b"")}
        )
        try:
            ch = resolve_channel_and_verify(request)
            logger.info(
                "[webhook] channel resolved",
                extra={"channel_id": ch.id, "org_id": ch.organization_id}
            )
        except SignatureError as e:
            logger.warning("[webhook] SignatureError", extra={"error": str(e)})
            return JsonResponse({"error": "Bad Request"}, status=400)
        except ChannelNotFound as e:
            logger.warning("[webhook] ChannelNotFound", extra={"error": str(e)})
            return JsonResponse({"error": "Bad Request"}, status=400)
        except Exception as e:
            logger.exception("[webhook] resolve_channel_and_verify failed", extra={"error": str(e)})
            return JsonResponse({"error": "Bad Request"}, status=400)

        try:
            body_json = json.loads(request.body.decode("utf-8"))
            logger.info(
                "[webhook] JSON decoded",
                extra={"has_events": "events" in body_json,
                    "events_len": len(body_json.get("events", []))}
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            logger.warning("[webhook] JSON decode error", extra={"error": str(e)})
            return JsonResponse({"error": "Bad Request"}, status=400)

        events = body_json.get("events", [])
        access_token = None  # 遅延復号キャッシュ

        for event in events:
            needs_token = (
                (event.get("type") == "message" and event.get("message", {}).get("type") == "image")
                or bool(event.get("replyToken"))
            )
            if needs_token and access_token is None:
                try:
                    access_token = get_secret(ch, KeyKind.ACCESS_TOKEN).decode().strip()
                except Exception:
                    logger.exception(
                        "Access Token Unavailable",
                        extra={
                            "needs_token": needs_token,
                            "access_token": access_token
                            }
                        )
                    return JsonResponse({"error": "Bad Request"}, status=400)

            response_text = self.handle_event(request, event, access_token, ch)
            reply_token = event.get("replyToken")
            if reply_token and response_text:
                self.send_reply_message(reply_token, response_text, access_token)

        return JsonResponse({"message": "Webhook processed"}, status=200)

    def handle_event(self, request, event, access_token, ch):
        """イベントのルーティング（ガード強化版）"""
        if event.get("type") != "message":
            return "未対応のイベントです。"

        source = event.get("source") or {}
        if source.get("type") != "user" or not source.get("userId"):
            return "個人チャット以外からのメッセージは現在未対応です。"

        line_user_id = source["userId"]
        user, created = Student.objects.get_or_create_user(
            line_user_id=line_user_id,
            organization_id=ch.organization_id,
        )

        if user.organization_id != ch.organization_id:
            return (
                "現在、別の教室アカウントでご利用中です。"
                "ご所属のアカウントからご連絡いただくか、教室までお問い合わせください。"
            )

        if getattr(user, "is_active", True) is False:
            return "アカウントが無効化されています。お手数ですが教室までご連絡ください。"

        username = getattr(user, "username", None)
        needs_name = (username is None) or (isinstance(username, str) and username.strip() == "")
        if created or needs_name:
            # ← 署名トークン付きURL（dest=bot_user_id を安全に受け渡し）
            payload = {
                "line_user_id": line_user_id,
                "dest": ch.bot_user_id,
                "org_id": ch.organization_id
                }
            token = signing.dumps(payload, salt="register-name", compress=True)  # 有効期限は受け側で検証
            reg_url = request.build_absolute_uri(
                reverse("user_register:register_name", args=[line_user_id])
            ) + f"?t={token}"
            return f"お名前を登録してください！以下のリンクをクリックしてください。\n{reg_url}"

        # テキストメッセージかつメール登録コマンドなら ChatProcessor より先に処理する
        if (event.get("message") or {}).get("type") == "text":
            msg = (event.get("message") or {}).get("text", "")
            email_reg_response = maybe_build_email_registration_response(
                request=request, student=user, line_channel=ch, message_text=msg
            )
            if email_reg_response is not None:
                return email_reg_response

        mtype = (event.get("message") or {}).get("type")
        handler = self.MESSAGE_HANDLERS.get(mtype)
        if not handler:
            return "未対応のメッセージタイプです。"

        return handler(self, event, user, access_token)

    def handle_text_event(self, event, user):
        message_text = event["message"]["text"]
        conversation = Conversation.get_active_conversation(user)
        self.record_message(conversation, message_text, is_sent_by_user=True)
        response_text = ChatProcessor(user).generate_response_text(message_text)
        self.record_message(conversation, response_text, is_sent_by_user=False)
        return response_text

    def handle_image_event(self, event, user, access_token):
        if not access_token:
            return "画像を取得できませんでした。"
        message_id = event["message"]["id"]
        image_data = self.fetch_image_data(message_id, access_token)
        if not image_data:
            return "画像を取得できませんでした。"

        extracted_text = ImageProcessor().process_image(image_data)
        if not extracted_text:
            return "画像からテキストを抽出できませんでした。"

        conversation = Conversation.get_active_conversation(user)
        self.record_message(conversation, extracted_text, is_sent_by_user=True)
        prompt = f"{extracted_text}\nこの問題の答えを教えてください。"
        response_text = ChatProcessor(user).generate_response_text(prompt)
        self.record_message(conversation, response_text, is_sent_by_user=False)
        return response_text

    def fetch_image_data(self, message_id, access_token):
        url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            resp = requests.get(url, headers=headers, timeout=(3.05, 10))
            if resp.status_code == 200:
                return resp.content
            logger.error(
                "画像取得のレスポンスとして200が得られませんでした",
                extra={"status_code": resp.status_code}
                )
            return None
        except requests.RequestException as e:
            logger.exception(
                "リクエスト時に例外が発生しました"
            )
            return None

    def send_reply_message(self, reply_token, message_text, access_token):
        if not access_token:
            logger.error("アクセストークンが存在しません。")
            return

        url = "https://api.line.me/v2/bot/message/reply"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        body = {
            "replyToken": reply_token,
            "messages": [{"type": "text", "text": message_text}]
        }

        try:
            resp = requests.post(url, headers=headers, json=body, timeout=(3.05, 10))

            if resp.status_code != 200:
                # ここだけ error ログ
                logger.error(
                    "応答のステータスコードが200ではありませんでした。",
                    extra={
                        "status": resp.status_code,
                        "response_body": resp.text[:500],
                        "replyToken": reply_token,
                    }
                )
            else:
                # 成功時は info か debug にしておくと追跡しやすいです（不要なら省略でもOK）
                logger.info(
                    "LINE 応答送信に成功しました。",
                    extra={"status": resp.status_code}
                )

        except requests.RequestException:
            logger.exception("LINE reply API リクエスト時に例外が発生しました。")

    def record_message(self, conversation, message_text, is_sent_by_user=True):
        MessageLog.objects.create(
            conversation=conversation,
            message=message_text,
            is_sent_by_user=is_sent_by_user,
        )
        conversation.last_message_at = now()
        conversation.save()
