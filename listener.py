# listener.yamlからの環境変数取得用
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_study_hub.settings")
django.setup()

from google.cloud import pubsub_v1
from study_reminder.models import StudyReminder
from study_reminder.services.message_service import MessageService
from processors.chat_processor import ChatProcessor
import requests
from django.conf import settings
from requests.exceptions import RequestException
from time import sleep
import logging

logger = logging.getLogger(__name__)


def send_line_notification(user_id, message, max_retries=5):
    """
    LINE APIを使用してメッセージを送信します。
    """
    logger.info(f"Attempting to send LINE notification to user ID: {user_id}")
    headers = {
        "Authorization": f"Bearer {settings.LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"to": user_id, "messages": [{"type": "text", "text": message}]}

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                "https://api.line.me/v2/bot/message/push",
                headers=headers,
                json=payload,
            )
            if response.status_code == 200:
                logger.info(f"LINE通知が送信されました: {response.status_code}")
                return response.json()
            elif response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                logger.warning(
                    f"Rate limit exceeded. Retrying after {retry_after} seconds..."
                )
                sleep(retry_after)
            else:
                logger.error(f"Unexpected error: {response.status_code}, {response.text}")
                response.raise_for_status()
        except RequestException as e:
            logger.error(
                f"Error during notification send attempt {attempt}/{max_retries}: {e}"
            )
            if attempt < max_retries:
                logger.warning(f"Retrying ({attempt}/{max_retries}) after failure: {e}")
                sleep(2 ** attempt)
            else:
                logger.error(f"Failed after {max_retries} attempts: {e}")
                raise


def callback(message):
    """
    Pub/Subからのメッセージを処理します。
    """
    logger.info(f"Attributes in message: {message.attributes}")
    logger.info(f"Data in message: {message.data.decode('utf-8')}")
    reminder_id = message.attributes.get("reminder_id")

    if not reminder_id:
        logger.warning("No reminder_id found in message attributes.")
        message.ack()
        return

    try:
        reminder = StudyReminder.objects.get(id=int(reminder_id))
        text_processor = ChatProcessor(reminder.student)
        message_content = MessageService.generate_message(reminder, text_processor)
        send_line_notification(reminder.student.line_user_id, message_content)
        message.ack()
    except StudyReminder.DoesNotExist:
        logger.warning(f"Reminder with ID {reminder_id} does not exist.")
        message.nack()


def listen_to_messages():
    """
    Pub/Subサブスクリプションを監視し、メッセージを処理します。
    """
    subscription_name = os.getenv(
        "PUBSUB_SUBSCRIPTION",
        getattr(settings, "PUBSUB_SUBSCRIPTION", "your-subscription-name"),
    )

    project_id = (
        os.getenv("GCP_PROJECT")
        or os.getenv("GOOGLE_CLOUD_PROJECT")
        or getattr(settings, "GCP_PROJECT_ID_FALLBACK", "your-gcp-project-id")
    )

    logger.info(
        f"Retrieved project_id: {project_id}, subscription_name: {subscription_name}"
    )

    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(project_id, subscription_name)
    logger.info(f"Generated subscription_path: {subscription_path}")

    streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
    logger.info(f"Listening for messages on {subscription_path}...")

    try:
        streaming_pull_future.result()
    except Exception as e:
        logger.error(f"Listener encountered an error: {e}")
        streaming_pull_future.cancel()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ],
    )
    logger.info("Starting listener service...")
    listen_to_messages()