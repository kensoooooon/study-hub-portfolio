class MessageService:
    @staticmethod
    def generate_message(reminder, chat_processor):
        """
        リマインダーに基づいてメッセージを生成する。

        Args:
            reminder (StudyReminder): リマインダーオブジェクト
            chat_processor (ChatProcessor): メッセージ生成プロセッサ

        Returns:
            str: メッセージ文字列
        """
        return reminder.custom_message or chat_processor.make_message_of_encouragement()
