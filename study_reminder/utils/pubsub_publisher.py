# study_reminder/utils/pubsub_publisher.py 等

import os
import logging
from typing import Optional, Dict, Any

from google.cloud import pubsub_v1

logger = logging.getLogger(__name__)

# モジュール内で使い回すクライアント（シングルトン）
_publisher_client: Optional[pubsub_v1.PublisherClient] = None


def _get_publisher() -> pubsub_v1.PublisherClient:
    """
    PublisherClient をシングルトンで返す。
    Windows + ENV=local のときは REST transport を使い、
    それ以外は従来どおり gRPC を使う。
    """
    global _publisher_client
    if _publisher_client is not None:
        return _publisher_client

    env = os.getenv("ENV", "local")

    if os.name == "nt" and env == "local":
        # ✅ ローカル Windows 環境は gRPC でクラッシュするので REST を使う
        logger.info("Using Pub/Sub REST transport (Windows local env)")
        _publisher_client = pubsub_v1.PublisherClient(transport="rest")
    else:
        # 本番や Linux ではデフォルト(gRPC)のままでOK
        _publisher_client = pubsub_v1.PublisherClient()

    return _publisher_client


class PubSubPublisher:
    @staticmethod
    def publish(topic_name: str, data: str, attributes: Optional[Dict[str, Any]] = None) -> str:
        """
        Pub/Subトピックにメッセージを送信します。

        Args:
            topic_name (str): Pub/Subトピック名
            data (str): メッセージデータ
            attributes (dict): メッセージ属性

        Returns:
            str: メッセージID
        """
        attributes = attributes or {}

        # TODO: 必要に応じて Project ID を env から切り替え
        project_id = os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT") or "django-study-hub"

        publisher = _get_publisher()
        topic_path = publisher.topic_path(project_id, topic_name)

        # データを bytes に変換
        data_bytes = data.encode("utf-8") if isinstance(data, str) else data

        future = publisher.publish(topic_path, data_bytes, **attributes)
        message_id = future.result(timeout=10)

        # access_token はログでは一部だけにしておく
        safe_attributes = dict(attributes)
        token = safe_attributes.get("access_token")
        if token:
            safe_attributes["access_token"] = token[:8] + "..."

        logger.info(
            "Published message to topic %s: message_id=%s, attributes=%s",
            topic_name,
            message_id,
            safe_attributes,
        )
        return message_id
