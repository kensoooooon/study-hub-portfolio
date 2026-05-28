import openai
from django.conf import settings
from processors.openai_models import OpenAIModel
from conversations.models import MessageLog
from accounts.models import Student

# ログ出力用
import logging

logger = logging.getLogger(__name__)


class SummaryProcessor:
    """生徒の質問履歴を要約するクラス"""

    def __init__(self, student: Student):
        """
        OpenAI APIを初期化
        """
        self.student = student
        OPENAI_API_KEY = settings.OPENAI_API_KEY
        if not OPENAI_API_KEY:
            logger.error("OPENAI_API_KEY が設定されていません (SummaryProcessor, student_id=%s)", student.id)
            raise EnvironmentError("APIキーが取得できません")
        self.openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

    def fetch_recent_questions(self, limit=10):
        """
        生徒の最近の質問ログを取得
        """
        logs = MessageLog.objects.filter(
            conversation__student=self.student,
            is_sent_by_user=True
        ).order_by('-timestamp')[:limit]
        logger.debug(
            "Fetched %d recent questions for summary (student_id=%s, limit=%d)",
            len(logs), self.student.id, limit
        )
        return [log.message for log in logs]

    def generate_summary(self):
        """
        質問履歴を要約し、簡潔なまとめを生成
        """
        questions = self.fetch_recent_questions()

        if not questions:
            logger.info("No recent questions to summarize (student_id=%s)", self.student.id)
            return "最近の質問履歴はありません。"

        prompt = (
            "以下は学生が過去にした質問のリストです。\n"
            "この学生が苦手としている分野や頻出の質問パターンを簡潔に要約してください。\n"
            "また、どのような補助学習が役立つかも提案してください。\n\n"
            + "\n".join(questions)
        )
        
        logger.info(
            "Start generating summary (student_id=%s, question_count=%d)",
            self.student.id, len(questions)
        )

        try:
            response = self.openai_client.chat.completions.create(
                model=OpenAIModel.SUMMARY,
                messages=[
                    {"role": "system", "content": "あなたは教育アシスタントです。"},
                    {"role": "user", "content": prompt}
                    ],
                max_completion_tokens=1000,
                temperature=0.5
            )
            summary = response.choices[0].message.content.strip()
            logger.debug(
                "Summary generated (student_id=%s, length=%d)",
                self.student.id, len(summary)
            )
            return summary
        except Exception as e:
            logger.exception("要約生成中にエラー (student_id=%s)", self.student.id)
            return "質問履歴の要約を生成できませんでした。"
