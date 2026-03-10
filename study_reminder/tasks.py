from google.cloud import pubsub_v1

def publish_message(topic_name, reminder_id, message):
    """
    Pub/Subトピックにメッセージを送信します。

    Args:
        topic_name (str): Pub/Subトピック名
        reminder_id (int): リマインダーのID
        message (str): 通知メッセージ
    """
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path("django-study-hub", topic_name)
    
    # メッセージにリマインダーIDを含める
    data = message.encode("utf-8")
    future = publisher.publish(topic_path, data, reminder_id=str(reminder_id))
    print(f"Published message ID: {future.result()}")
