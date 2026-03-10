"""単語学習に基づいた英語長文をChatGPTAPIを利用して作成する

ReadingPassageGenerator
    教科書準拠の比較的短めの長文を出力する

EikenPassageGenerator:
    英検の長文問題に対応するための、比較的眺めの長文を出力する

Note:
    出力はある程度プロンプトで制御できるが、ChatGPT依存であり、問題数や構造は必ずしも安定していない
    受取先でNoneやtry, exceptでの例外補足などを含めて利用すること
"""
import openai
import json
from django.conf import settings
from accounts.models import Student
from vocab_trainer.models import WordMeaningContext, StudentContextProgress
from read_trainer.models import ReadingPassage


# ログ出力用
import logging

logger = logging.getLogger(__name__)

# 級ごとの長文の語数指定
EIKEN_LEVEL_WORD_LIMITS = {
    "5": 170,
    "4": 190,
    "3": 250,
    "pre2": 310,
    "2": 350,
}


# 級ごとの利用英文法の指定
EIKEN_LEVEL_GRAMMAR = {
    "5": ["be動詞", "一般動詞（現在）", "代名詞", "疑問詞", "命令文"],
    "4": ["過去形", "未来表現", "助動詞", "前置詞", "比較級"],
    "3": ["現在完了", "受動態", "不定詞", "動名詞", "接続詞", "関係代名詞"],
    "pre2": ["仮定法過去", "分詞構文", "関係代名詞の省略", "間接疑問文"],
    "2": ["仮定法過去完了", "関係副詞", "複合関係詞", "倒置構文", "強調構文"],
}


def get_cumulative_grammar(level: str) -> list[str]:
    order = ["5", "4", "3", "pre2", "2"]
    result = []
    for lvl in order:
        result.extend(EIKEN_LEVEL_GRAMMAR.get(lvl, []))
        if lvl == level:
            break
    return result


class ReadingPassageGenerator:
    """
    英語長文と、それに付随する4択読解問題をChatGPT経由で生成するクラス。

    Attributes:
        student (Student): 生成対象の生徒（語彙レベル等に活用）
        openai_client: 認証済みのAPIアクセスポイント
    """

    def __init__(self, student: Student):
        self.student = student
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            logger.error("Open AI APIキーが設定されていません。")
            raise EnvironmentError("OpenAI APIキーが設定されていません。")
        self.openai_client = openai.OpenAI(api_key=api_key)

    def generate_passage_with_questions(self, vocab_contexts: list[WordMeaningContext], word_limit: int = 120) -> dict:
        """与えられた語彙群から長文と問題を同時に生成
        
        Args:
            vocab_contexts(list[WordMeaningContext]): 対象となる語彙群のリスト
            word_limit (int): 上限となる長文の英単語数
        
        Returns:
            (dict): 英語長文と和訳,および問題
        
        Exception:
            ChatGPT関連のエラーで送出
        
        Note:
            - ChatGPTのエラー、JSONのエラーが想定されるが、それぞれraiseと{}で処理
            これはutils/quiz_generation.pyで受け取ることを想定
            
            返り値はdictである点に注意
        """
        word_pairs = [
            (str(ctx.relation.english_word.word), str(ctx.relation.japanese_meaning.meaning))
            for ctx in vocab_contexts
        ]
        prompt = self._build_prompt(word_pairs, word_limit)
        level_prompt = self._get_student_level_prompt()
        logger.info(
            "Start reading passage and problem generation  (student_id=%s, len(vocab_contexts)=%d, word_limit=%d)",
            self.student.id, len(vocab_contexts), word_limit
        )

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": f"あなたは英語教育用の教材作成アシスタントです。{level_prompt}"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4096,
                temperature=0.5
            )
        except Exception:
            logger.exception(
                "ChatGPT生成エラー (student_id=%s, len(vocab_contexts)=%d)",
                self.student.id, len(vocab_contexts)
            )
            raise
        
        content = response.choices[0].message.content.strip()
        logger.debug("Raw response received (length=%d)", len(content))
        parsed = self._parse_response(content)
        if not parsed:
            logger.warning(
                "Parsed response is None while generating reading questions (student_id=%s)",
                self.student.id,
            )
            return {}

        return parsed

    def generate_questions_for_existing_passage(self, passage: ReadingPassage, vocab_contexts: list[WordMeaningContext]) -> list[dict]:
        """
        指定された長文と英単語群から問題のみを新規作成する
        
        Args:
            passage (ReadingPassage): 対象となる既存の長文
            vocab_contexts (list[WordMeaningContext]): 問題作成に利用する可能性がある語彙群
        
        Returns:
            list[dict]: 3問分のquestionsが格納されたリスト
        
        Note:
            - ChatGPTのエラー、JSONのエラーが想定されるが、それぞれraiseと[]で処理
            これはutils/quiz_generation.pyで受け取ることを想定
            
            返り値はlist[dict]である点に注意
        """
        word_pairs = [
            (str(ctx.relation.english_word.word), str(ctx.relation.japanese_meaning.meaning))
            for ctx in vocab_contexts
        ]
        prompt = self._build_prompt_only_questions(passage.content, word_pairs)
        level_prompt = self._get_student_level_prompt()
        logger.info(
            "Start reading problem generation (student_id=%s, len(vocab_contexts)=%d, passage_id=%s)",
            self.student.id, len(vocab_contexts), passage.id,
        )

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": f"あなたは英語教材を作成するアシスタントです。{level_prompt}"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4096,
                temperature=0.7
            )
        except Exception:
            logger.exception(
                "ChatGPT生成エラー (student_id=%s, vocab_contexts=%d)",
                self.student.id, len(vocab_contexts)
            )
            raise

        content = response.choices[0].message.content.strip()
        parsed = self._parse_response(content)
        if not parsed:
            logger.warning(
                "Parsed response is None while generating reading questions (student_id=%s)",
                self.student.id,
            )
            return []

        questions = parsed.get("questions", [])
        logger.debug(
            "Reading questions generated (student_id=%s, question_count=%d)",
            self.student.id,
            len(questions),
        )
        return questions

    def _build_prompt(self, word_pairs: list[tuple[str, str]], word_limit: int) -> str:
        """
        長文と問題を同時に作成する際に必要なプロンプトの作成
        
        Args:
            word_paris (list[tuple[str, str]]): 長文および問題に作成する語彙群
            word_limit (int): ざっくりとしていする長文の語数
            
        Returns:
            (str): プロンプト本体
        """
        words_and_meanings = ', '.join([f"{eng}（意味: {jpn}）" for eng, jpn in word_pairs])
        return (
            f"次の英単語をすべて自然に含むように、約{word_limit}語の英語長文を作成してください。\n"
            f"まずその内容にふさわしい、短い英語のタイトル（最大10語程度）を1つ考えてください。\n"
            f"その後、本文（passage）を書き、日本語訳（translation）をつけ、最後に内容に関する4択読解問題を3問作成してください。\n"
            f"本文中では段落ごとに適切に改行（改行コード \\n）を入れてください。1段落あたり3〜5文を目安とし、複数段落構成としてください。\n"
            f"\n"
            f"各問題には以下の項目を含めてください：\n"
            f"- question（質問文）\n"
            f"- options（選択肢4つ。リスト形式で、'A) ...' の形式で記載）\n"
            f"- answer（正解の選択肢を A/B/C/D の1文字で返す）\n"
            f"- explanation（英語ではなく、日本語による簡単な解説）\n"
            f"\n出力は以下の JSON 形式に厳密に従ってください（説明文など他の文は含めないでください）：\n"
            f"{{\n"
            f"  \"title\": \"...\",\n"
            f"  \"passage\": \"...\",\n"
            f"  \"translation\": \"...\",\n"
            f"  \"questions\": [ ... ]\n"
            f"}}\n"
            f"\n使用語彙（英語と意味）: {words_and_meanings}"
        )


    def _build_prompt_only_questions(self, passage_text: str, word_pairs: list[tuple[str, str]]) -> str:
        """
        問題のみを作成する際に必要なプロンプトの作成
        
        Args:
            passage_text (str): 対象となる長文
            word_pairs (list(tuple[str, str])): 選択肢や問題文に反映させたい語彙群
        
        Returns:
            (str): プロンプト本体
        """
        words_and_meanings = ', '.join([f"{eng}（意味: {jpn}）" for eng, jpn in word_pairs])
        return (
            f"以下の英文を読んでください：\n\n{passage_text}\n\n"
            f"この内容に関する4択問題を3問作成してください。\n"
            f"各問題には以下の項目を含めてください：\n"
            f"- question（質問文）\n"
            f"- options（選択肢4つ。リスト形式で、'A) ...' の形式で記載）\n"
            f"- answer（正解の選択肢を A/B/C/D の1文字で返す）\n"
            f"- explanation（英語ではなく、日本語による簡単な解説）\n"
            f"できるだけ次の語彙も問題文や選択肢に反映してください：{words_and_meanings}\n"
            "解説は必ず日本語で行うようにしてください。\n"
            f"\n出力は必ず以下の JSON 形式で返してください（他の説明文を含めないでください）：\n"
            f"{{\n"
            f"  \"questions\": [\n"
            f"    {{\n"
            f"      \"question\": \"...\",\n"
            f"      \"options\": [\"A) ...\", \"B) ...\", \"C) ...\", \"D) ...\"],\n"
            f"      \"answer\": \"A\",\n"
            f"      \"explanation\": \"...\"\n"
            f"    }},\n"
            f"    ...\n"
            f"  ]\n"
            f"}}"
        )

    def _parse_response(self, content: str) -> dict:
        """
        レスポンスの形式ブレをある程度解消しつつ、jsonをデコードする
        
        Args:
            content (str): デコード対象であるjson形式の文字列
            
        Returns:
            (dict): jsonをデコードして出てきた辞書型のデータ
        """
        try:
            if content.startswith('```'):
                content = content.strip('`').strip()
                if content.startswith('json'):
                    content = content[4:].strip()
            if content.startswith('"questions"') or content.startswith('{"questions"'):
                if not content.strip().startswith('{'):
                    content = '{' + content + '}'
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error("JSONデコード失敗: %s", e)
            logger.debug("応答内容の先頭100文字: %s", content[:100])
            return None

    def _get_student_level_prompt(self) -> str:
        """
        生徒の学習済み英単語数に応じ難易度の変更を行うプロンプトの作成
        
        Returns:
            (str): 英単語数から作成したプロンプトの一部
        """
        vocab_count = StudentContextProgress.objects.filter(
            student=self.student,
            total_count__gt=0
        ).count()

        if vocab_count < 500:
            return "学習者は中学英語の初期段階です。簡単な構文と語彙を使い、文の長さも短めにしてください。"
        elif vocab_count < 1500:
            return "学習者は中学2〜3年程度の語彙と構文に慣れてきています。内容を少し発展させてください。"
        else:
            return "学習者は英語力が高く、高校初級レベルまで理解可能です。構文や語彙に多様性を持たせてください。"


class EikenPassageGenerator:
    """
    英検練習用の長文を作成する
    
    Attributes:
        level: 英検の級(5, 4, 3, 2, pre2, 2)
        vocab_contexts: 設問に含められる可能性がある学習済みの英単語
        client (openai.OpenAI): APIへのアクセスポイント
    """
    def __init__(self, student: Student, level: str, vocab_contexts: list[WordMeaningContext] = None):
        self.student = student
        self.level = level
        self.vocab_contexts = vocab_contexts or []
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            logger.error("Open AI APIキーが設定されていません。(EikenPassageGenerator)")
            raise EnvironmentError("OpenAI APIキーが設定されていません。")
        self.client = openai.OpenAI(api_key=api_key)

    def build_prompt(self, passage_text: str | None = None) -> str:
        """
        級数と学習済みの英単語を取り入れつつ、生成に必要なプロンプトの作成
        
        Args:
            passage_text (str | None): 対象となる長文
        
        Returns:
            (str): 問題のシチュエーションに応じたプロンプト
        
        Note:
            passage_textが存在する場合は「既存の問題への追加」であり、ない場合は「新規作成」
        """
        level_str = f"英検{self.level}級"
        vocab_list = "\n".join(f"- {vc.relation.english_word.word}" for vc in self.vocab_contexts)
        vocab_section = (
            f"次の英単語をできるだけ自然に本文または設問に含めてください：\n{vocab_list}\n"
            if self.vocab_contexts else ""
        )
        # 級数に応じた単語数の指定
        word_limit = EIKEN_LEVEL_WORD_LIMITS[self.level]
        # 級数に応じた英文法の設定
        grammar_list = get_cumulative_grammar(self.level)
        grammar_section = "\n".join([f"- {item}" for item in grammar_list])

        if passage_text:
            return (
                f"{level_str}にふさわしい英語長文を「本文」として以下に示します。\n"
                f"本文:\n{passage_text}"
                f"この本文に基づく4択読解問題を3問、指定した条件と形式で出力してください。\n\n"
                f"まず、利用する英文法については、以下のものをなるべく利用する形で英文を作成してください。\n"
                f"リストについては、後半に来るものを優先して利用してください。\n"
                f"{grammar_section}\n"
                f"また、以下の英単語も、同様に優先して利用してください。\n"
                f"{vocab_section}\n"
                f"出力は、**以下に示すJSON形式そのものだけを正確に出力してください。**\n"
                f"**マークダウン、コードブロック（```）などは絶対に含めず、前置き・後書きも出力しないでください。**\n"
                f"各問題には以下の項目を含めてください：\n"
                f"- question（質問文）\n"
                f"- options（選択肢4つ。リスト形式で、'A) ...' の形式で記載）\n"
                f"- answer（正解の選択肢を A/B/C/D の1文字で返す）\n"
                f"- explanation（英語ではなく、日本語による簡単な解説）\n"
                f"**JSON構造のみ**を返してください。形式は以下のとおりです：\n\n"
                "{\n"
                "  \"questions\": [\n"
                "    {\n"
                "      \"question\": \"...\",\n"
                "      \"options\": [\"A) ...\", \"B) ...\", \"C) ...\", \"D) ...\"],\n"
                "      \"answer\": \"A\",\n"
                "      \"explanation\": \"...\"\n"
                "    }, ...\n"
                "  ]\n"
                "}\n"
            )
        else:
            return (
                f"あなたは英語教材作成の専門家です。\n"
                f"{level_str}にふさわしい約{word_limit}語の英語長文を1つ作成してください。\n"
                f"その後、日本語訳をつけ、その内容と指定した条件に基づいた4択の読解問題を3問出力してください。\n\n"
                f"本文中では段落ごとに適切に改行（改行コード \\n）を入れてください。1段落あたり3〜5文を目安とし、複数段落構成としてください。\n"
                f"まず、利用する英文法については、以下のものをなるべく利用する形で英文を作成してください。\n"
                f"リストについては、後半に来るものを優先して利用してください。\n"
                f"{grammar_section}\n"
                f"また、以下の英単語も、同様に優先して利用してください。\n"
                f"{vocab_section}\n"
                f"出力は、**以下に示すJSON形式そのものだけを正確に出力してください。**\n"
                f"**マークダウン、コードブロック（```）などは絶対に含めず、前置き・後書きも出力しないでください。**\n"
                f"各問題には以下の項目を含めてください：\n"
                f"- question（質問文）\n"
                f"- options（選択肢4つ。リスト形式で、'A) ...' の形式で記載）\n"
                f"- answer（正解の選択肢を A/B/C/D の1文字で返す）\n"
                f"- explanation（英語ではなく、日本語による簡単な解説）\n"
                f"**JSON構造のみ**を返してください。形式は以下のとおりです：\n\n"
                "{\n"
                "  \"title\": \"...\",\n"
                "  \"passage\": \"...\",\n"
                "  \"translation\": \"...\",\n"
                "  \"questions\": [\n"
                "    {\n"
                "      \"question\": \"...\",\n"
                "      \"options\": [\"A) ...\", \"B) ...\", \"C) ...\", \"D) ...\"],\n"
                "      \"answer\": \"A\",\n"
                "      \"explanation\": \"...\"\n"
                "    }, ...\n"
                "  ]\n"
                "}"
            )

    def generate_passage_with_questions(self) -> dict:
        """
        長文とそれに対応する問題・解答を生成
        
        Returns:
            (dict): 長文と問題、選択肢などを含む問題データ
        """
        prompt = self.build_prompt()
        messages = [
            {"role": "system", "content": "あなたは英検対策用教材を正確なJSON形式で出力するAIです。"},
            {"role": "user", "content": prompt},
        ]
        logger.info(
            "Start eiken reading passage and problem generation (student_id=%s)",
            self.student.id,
        )
        
        try:
            res = self.client.chat.completions.create(
                model="gpt-4o", messages=messages, max_tokens=4096
            )
        except Exception as e:
            logger.exception(
                "ChatGPT生成エラー (student_id=%s)",
                self.student.id
            )
            raise

        content = res.choices[0].message.content.strip()
        logger.debug("Raw response received (length=%d)", len(content))

        parsed = self._parse_response(content)
        if not parsed:
            logger.warning(
                "Parsed response is None while generating eiken reading questions (student_id=%s)",
                self.student.id,
            )
            return {}

        return parsed

    def generate_questions_for_existing_passage(self, passage: ReadingPassage) -> list[dict]:
        """
        既存の英検長文に対して、追加の読解問題（questions）のみを生成する。

        Args:
            passage (ReadingPassage): 既存の長文。

        Returns:
            list[dict]: 生成された設問（question / options / answer / explanation）の
                辞書オブジェクトを含むリスト。
                JSON 形式の乱れやパースエラーなどの異常時は空リストを返す。

        Raises:
            Exception: OpenAI API 呼び出し時の通信エラー・APIエラーなど、
                ChatGPT 応答そのものが取得できなかった場合に発生する。
                （JSON パース失敗などの形式エラーは raise せず空リストを返す）
        """
        prompt = self.build_prompt(passage.content)
        messages = [
            {"role": "system", "content": "あなたは英検対策用問題作成AIです。出力はJSONのみで、説明文は禁止です。"},
            {"role": "user", "content": prompt},
        ]
        logger.info(
            "Start eiken reading problem generation (student_id=%s)",
            self.student.id,
        )
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o", messages=messages, max_tokens=2048
            )
            content = response.choices[0].message.content
        except Exception:
            logger.exception("ChatGPT生成エラー (student_id=%s)", self.student.id)
            raise

        content = response.choices[0].message.content.strip()
        logger.debug("Raw response received (length=%d)", len(content))
        parsed = self._parse_response(content)
        if not parsed:
            logger.warning(
                "Parsed response is None while generating eiken reading questions (student_id=%s)",
                self.student.id,
            )
            return []

        questions = parsed.get("questions", [])
        logger.debug(
            "Reading questions generated (student_id=%s, question_count=%d)",
            self.student.id,
            len(questions),
        )
        return questions

    def _parse_response(self, content: str) -> dict:
        """
        レスポンスの形式ブレをある程度解消しつつ、jsonをデコードする
        
        Args:
            content (str): デコード対象であるjson形式の文字列
            
        Returns:
            (dict): jsonをデコードして出てきた辞書型のデータ
        """
        try:
            if content.startswith('```'):
                content = content.strip('`').strip()
                if content.startswith('json'):
                    content = content[4:].strip()
            if content.startswith('"questions"') or content.startswith('{"questions"'):
                if not content.strip().startswith('{'):
                    content = '{' + content + '}'
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error("JSONデコード失敗: %s", e)
            logger.debug("応答内容の先頭100文字: %s", content[:100])
            return None
