import openai
from django.conf import settings

# ログ出力用
import logging

logger = logging.getLogger(__name__)

class ExampleSentenceProcessor:
    """
    ChatGPTを利用して例文を動的に生成するクラス
    """

    def __init__(self) -> None:
        """
        OpenAI APIの初期化
        """
        OPENAI_API_KEY = settings.OPENAI_API_KEY
        if not OPENAI_API_KEY:
            logger.error("OPENAI_API_KEYが設定されていません。(ExampleSentenceProcessor)")
            raise EnvironmentError("APIキーが取得できません")
        self.openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

    def generate_example_sentence(self, word: str, japanese_meaning: str, part_of_speech: str) -> str:
        """
        英単語と品詞をもとに、ChatGPTを利用してシンプルな例文を生成
        
        Args:
            word (str): 英単語
            part_of_speech (str): 品詞

        Returns:
            str: 生成された例文
        """
        try:
            # プロンプトの設定
            prompt = (
                f"次の英単語とそれに対応する日本語訳を使用して、中学生程度のシンプルな英文を作成してください。\n"
                f"英単語: {word}\n"
                f"対応する日本語: {japanese_meaning}\n"
                f"品詞: {part_of_speech}\n"
                f"解答には和訳の文章も併せてつけてください。\n"
                f"また、単語の覚え方や覚えておくべき知識もあれば、併せてつけてください。"
            )

            # ChatGPTにリクエスト
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "あなたは親切な学習アシスタントです。標準的な中学生を対象としたシンプルな解答を心がけてみてください。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.5
            )
            text = response.choices[0].message.content.strip()
            logger.debug(
                "Example sentence processor generated (name=%s, length=%d)",
                word, len(text)
            )
            return text
        except Exception:
            logger.exception("英単語解説生成中にエラー (name=%s)", word)
            return "例文を生成できませんでした。"
