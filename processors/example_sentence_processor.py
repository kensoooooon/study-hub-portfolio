import openai
from django.conf import settings
from processors.openai_models import OpenAIModel

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
            system_prompt = (
                "あなたは英単語クイズの解答画面に表示する解説文を生成するシステムです。"
                "出力はそのまま画面に表示されます。"
                "ユーザーとの会話は行わず、呼びかけ・前置き・確認・追加提案を書いてはいけません。"
                "Markdownの見出し、箇条書き、区切り線、太字記法は使わないでください。"
                "指定された形式だけで、簡潔な日本語で出力してください。"
            )

            prompt = f"""
            次の英単語について、中学生向けの解説を作成してください。

            英単語: {word}
            対応する日本語: {japanese_meaning}
            品詞: {part_of_speech}

            必ず次の形式だけで出力してください。

            "<英単語を自然に使った中学生程度の英文を1文>"
            和訳: "<上の英文の自然な日本語訳>"

            覚え方:
            <単語の意味やつづりを覚えるための説明を1〜2文>

            覚えておくべき知識:
            <この単語の基本的な使い方、よく使う形、注意点を1〜3文>

            禁止事項:
            - 「もちろんです」などの前置きを書かない
            - 「必要なら」「どうしますか」などの呼びかけを書かない
            - 追加の例文を出さない
            - Markdown記法を使わない
            - 箇条書きを使わない
            - 指定形式以外の見出しを増やさない
            """

            # ChatGPTにリクエスト
            response = self.openai_client.chat.completions.create(
                model=OpenAIModel.SHORT_TASK,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=1000,
                temperature=0.3
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
