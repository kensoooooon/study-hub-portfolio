import openai
import re
from pylatexenc.latex2text import LatexNodes2Text

# 環境変数用
from django.conf import settings
from processors.openai_models import OpenAIModel

# ユーザーログ読み取り用
from conversations.models import MessageLog

# アカウントのモデル
from accounts.models import Student

# ログ出力用
import logging


logger = logging.getLogger(__name__)


class ChatProcessor:
    """APIを利用して返答用のテキストを生成
    
    Attributes:
        message_text (str): LineAPI経由で受信した文章
        openai_client: API利用のためのクライアント
    
    Notes:
        APIキーは.envファイルに格納
    """
    def __init__(self, student: Student) -> None:
        """APIキーを用いて、chatGPTのAPIにアクセスする前準備を行う
        
        Args:
            user (Student): 会話生成の対象となるユーザー
        
        Note:
            OpenAIのAPIキーは直接格納せず、.env, app.yamlに格納すること
        """
        self.student = student
        OPENAI_API_KEY = settings.OPENAI_API_KEY
        if not OPENAI_API_KEY:
            logger.error("OPENAI_API_KEY が設定されていません (student_id=%s)", student.id)
            raise EnvironmentError("APIキーが取得できません")
        self.openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
        logger.info("ChatProcessor initialized (student_id=%s)", student.id)

    def fetch_logs_as_messages(self, max_logs: int = 10) -> list[dict]:
        """
        ChatGPT用の`messages`形式でアクティブな会話ログを取得

        Args:
            max_logs (int): 最大取得件数。デフォルトは10

        Returns:
            list[dict]: 過去の会話ログをChatGPT API用に整形したリスト
        """
        try:
            logs = MessageLog.objects.filter(
                conversation__student=self.student,
                conversation__ended_at__isnull=True  # アクティブな会話に限定
            ).order_by('timestamp')[:max_logs]
            logger.debug(
                "Fetched %d logs for student_id=%s (max_logs=%d)",
                len(logs), self.student.id, max_logs
            )
            messages = [
                {"role": "user" if log.is_sent_by_user else "assistant", "content": log.message}
                for log in logs
            ]
            return messages
        except Exception as e:
            logger.exception("ログ取得中にエラーが発生しました (student_id=%s)", self.student.id)
            return []

    def generate_response_text(self, message_text: str) -> str:
        """
        chatGPTに会話ログと新規メッセージを送信して応答を生成

        Args:
            message_text (str): ユーザーからの新しいメッセージ

        Returns:
            response (str): LaTeXの除去を済ませたレスポンス
        """
        logger.info(
            "Start generating chat response (student_id=%s, message_length=%d)",
            self.student.id, len(message_text)
        )
        try:
            conversation_context = self.fetch_logs_as_messages()

            # 振る舞いの指定
            conversation_context.insert(0, {"role": "system", "content": "あなたは親切な学習アシスタントです。会話の流れを踏まえつつ、シンプルな日本語で回答してください。"})

            # 新しい質問を含むプロンプトを追加
            prompt = (
                f"以下の質問に、シンプルでわかりやすい日本語で解答してください。"
                f"可能であれば解説もお願いします。:\n\n{message_text}"
            )
            conversation_context.append({"role": "user", "content": prompt})
            api_response = self.openai_client.chat.completions.create(
                model=OpenAIModel.CHAT,
                messages=conversation_context,
                max_completion_tokens=2000,
                temperature=0.2
            )
            raw_text = api_response.choices[0].message.content.strip()
            # return response.choices[0].message.content.strip()
            if self.contains_latex(raw_text):
                response = self.process_latex_format(raw_text)
            else:
                response = raw_text
            logger.info(
                "Chat response generated successfully (student_id=%s, response_length=%d)",
                self.student.id, len(response)
            )
            return response
        except Exception:
            logger.exception("Chat 応答生成中にエラー (student_id=%s)", self.student.id)
            return "応答を生成できませんでした。しばらくしてから再度お試しください。"
        
    def contains_latex(self, text: str) -> bool:
        """LaTeX形式が含まれるか判定する
        
        LaTeX表現のさまざまな形式をチェックします。
        """
        latex_patterns = [
            r'\\\(', r'\\\[',      # 数式モードの開始記号
            r'\\\)', r'\\\]',      # 数式モードの終了記号
            r'\\begin{.*?}',       # LaTeXのbegin環境
            r'\\end{.*?}',         # LaTeXのend環境
            r'\\frac', r'\\sqrt',  # よく使われるコマンド
            r'\\text', r'\\math'   # LaTeXのテキスト/数式コマンド
        ]
        combined_pattern = '|'.join(latex_patterns)
        return bool(re.search(combined_pattern, text))


    def process_latex_format(self, text: str) -> str:
        """LaTeX形式を取り除き、平文に変換する
        
        Args:
            text (str): 処理対象のテキスト
        
        Returns:
            str: LaTeX形式が平文に変換されたテキスト
        """
        try:
            # LaTeX形式を平文に変換
            converter = LatexNodes2Text()
            converted_text = converter.latex_to_text(text)
            
            # 追加の後処理: 不要な記号を削除
            # 例: $$, \[, \], \(...\) の削除
            clean_text = re.sub(r'(\$\$|\\\[|\\\]|\\\(|\\\))', '', converted_text)
            
            return clean_text.strip()
        except Exception:
            logger.exception(
                "LaTeX変換中にエラーが発生しました (student_id=%s, text_length=%d)",
                self.student.id,
                len(text),
            )
            # もとのテキストをそのまま返す
            return text

    def make_message_of_encouragement(self) -> str:
        """
        学習の継続を褒める励ましのメッセージを生成する

        Returns:
            str: 励ましメッセージ
        """
        logger.info("Start encouragement message generation (student_id=%s)", self.student.id)

        try:
            # 過去ログの取得
            conversation_context = self.fetch_logs_as_messages()

            # 振る舞いの指定
            conversation_context.insert(0, {"role": "system", "content": "あなたは親切な学習アシスタントです。これまでの会話を踏まえ、学生を応援する励ましのメッセージを作成してください。"})

            # プロンプトを追加
            prompt = f"{self.student.username}さんの学習継続を褒めるメッセージを作成してください。"
            conversation_context.append({"role": "user", "content": prompt})

            # ChatGPTにリクエスト
            response = self.openai_client.chat.completions.create(
                model=OpenAIModel.CHAT,
                messages=conversation_context,
                max_completion_tokens=150,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.exception(
                "励ましメッセージの生成中にエラーが発生しました (student_id=%s)",
                self.student.id,
            )
            return "今日も勉強を頑張りましょう!"
