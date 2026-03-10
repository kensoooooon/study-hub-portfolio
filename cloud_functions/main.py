"""
11/14
マルチチャンネルに対応できるように構成を変更する.具体的にはアクセストークン

11/15
そのままではなく,line_channelsへ委譲
"""

import os
import logging
import functions_framework
import requests
import json

import base64

# ロギング設定
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

def send_line_notification(user_id, message, access_token=None):
    """
    LINE API を使用してメッセージを送信します。

    access_token が引数で渡されていればそれを優先し、
    渡されていなければ従来どおり環境変数を使う（後方互換用）。
    """
    token = access_token or LINE_CHANNEL_ACCESS_TOKEN

    if not token:
        logger.error("LINE channel access token is not set (neither attribute nor env).")
        return {"error": "LINE API credentials not found"}, 500

    if not user_id or user_id.strip() == "":
        logger.error("Invalid LINE user_id. Cannot send notification.")
        return {"error": "Invalid LINE user_id"}, 400

    logger.info(f"Sending notification to LINE user: {user_id}")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {"to": user_id, "messages": [{"type": "text", "text": message}]}

    response = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers=headers,
        json=payload
    )

    if response.status_code == 200:
        logger.info("Notification sent successfully.")
        return {"status": "success"}, 200
    else:
        logger.error(f"Failed to send notification: {response.text}")
        return {"error": response.text}, response.status_code


@functions_framework.cloud_event
def pubsub_listener(event):
    try:
        # CloudEvent から Pub/Sub メッセージを取得
        event_data = event.data

        # メッセージの構造に合わせて attributes を取得
        message_data = event_data.get("message", {})
        attributes = message_data.get("attributes", {})
        
        # logでの表示用
        safe_attributes = dict(attributes)

        token = safe_attributes.get("access_token")
        if token:
            masked = token[:8] + "..."   # 頭8文字だけ残す
            safe_attributes["access_token"] = masked

        logger.info("Received attributes (masked): %s", safe_attributes)
        # logger.info(f"Received attributes: {attributes}")

        if "data" in message_data:
            decoded_data = base64.b64decode(message_data["data"]).decode("utf-8")
            logger.info(f"Decoded data: {decoded_data}")

        line_user_id = attributes.get("line_user_id")
        custom_message = attributes.get("custom_message")
        access_token = attributes.get("access_token")  # ★ 追加

        if not line_user_id:
            logger.error(
                "No LINE user ID found in message attributes.",
                extra={"attributes": safe_attributes}
                )
            return {"error": "No LINE user ID provided"}, 400

        logger.info(f"Sending reminder to LINE user: {line_user_id}")
        send_line_notification(line_user_id, custom_message, access_token)

    except Exception as e:
        logger.exception(f"Error processing message: {e}")
        return {"error": str(e)}, 500
