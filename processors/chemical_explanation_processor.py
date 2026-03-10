import openai
from django.conf import settings

# ログ出力用
import logging

logger = logging.getLogger(__name__)


class ChemicalExplanationProcessor:
    """
    ChatGPTを利用して化学物質の解説を動的に生成するクラス
    """

    def __init__(self) -> None:
        """
        OpenAI APIの初期化
        """
        OPENAI_API_KEY = settings.OPENAI_API_KEY
        if not OPENAI_API_KEY:
            logger.error("OPENAI_API_KEYが設定されていません。(ChemicalExplanationProcessor)")
            raise EnvironmentError("APIキーが取得できません")
        self.openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

    def generate_explanation(self, chemical_name: str) -> str:
        """
        化学物質の名前をもとに、ChatGPTを利用して用途や性質に関する解説を生成
        
        Args:
            chemical_name (str): 化学物質名

        Returns:
            str: 生成された解説
        """
        try:
            # プロンプトの設定
            prompt = (
                f"次の化学物質について、簡潔に説明してください。\n"
                f"化学物質: {chemical_name}\n"
                f"・主な用途\n"
                f"・化学的性質\n"
                f"・取り扱い時の注意点\n"
                f"簡潔に200文字以内でお願いします。"
            )

            # ChatGPTにリクエスト
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "あなたは化学に詳しい教育アシスタントです。簡潔でわかりやすい説明を心がけてください。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.5
            )
            text = response.choices[0].message.content.strip()
            logger.debug(
                "Chemical explanation generated (name=%s, length=%d)",
                chemical_name, len(text)
            )
            return text
        except Exception:
            logger.exception("化学物質解説生成中にエラー (name=%s)", chemical_name)
            return "解説を生成できませんでした。"
