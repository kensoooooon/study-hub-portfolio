"""単語学習に基づいた英語長文をChatGPTAPIを利用して作成する

ListeningPassageGenerator
    教科書準拠の比較的短めの長文を出力する

EikenListeningPassageGenerator:
    英検の長文問題に対応するための、比較的眺めの長文を出力する

Note:
    出力はある程度プロンプトで制御できるが、ChatGPT依存であり、問題数や構造は必ずしも安定していない
    受取先でNoneやtry, exceptでの例外補足などを含めて利用すること
"""
import openai
import json
from django.conf import settings
from processors.openai_models import OpenAIModel
from accounts.models import Student
from vocab_trainer.models import WordMeaningContext, StudentContextProgress
from listening_trainer.models import ListeningPassage

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


class ListeningPassageGenerator:
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

    def generate_passage_with_questions(self, vocab_contexts: list[WordMeaningContext]) -> dict:
        """指定された英単語群から長文と問題を生成する
        
        Args:
            vocab_contexts (list[WordMeaningContext]): 対象となる語彙群
        
        Returns:
            (dict): 英語長文と和訳,問題

        Note:
            - ChatGPTのエラー、JSONのエラーが想定されるが、それぞれraiseと{}で処理
            これはutils/quiz_generation.pyで受け取ることを想定
            
            返り値はdictである点に注意
        """
        word_pairs = [
            (str(ctx.relation.english_word.word), str(ctx.relation.japanese_meaning.meaning))
            for ctx in vocab_contexts
        ]
        vocab_count = self.get_student_vocab_count()
        word_limit = self._estimate_word_limit_from_vocab_count(vocab_count)
        prompt = self._build_prompt(word_pairs, word_limit)
        level_prompt = self._get_student_level_prompt()
        logger.info(
            "Start listening passage and problem generation (student_id=%s, len(vocab_contexts)=%d, vocab_count=%d, word_limit=%d)",
            self.student.id, len(vocab_contexts), vocab_count, word_limit,
        )

        try:
            response = self.openai_client.chat.completions.create(
                model=OpenAIModel.PASSAGE_GENERATION,
                messages=[
                    {"role": "system", "content": f"あなたは英語教育用の教材作成アシスタントです。{level_prompt}"},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=4096,
                temperature=0.5
            )
        except Exception as e:
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
                "Parsed response is None while generating listening questions (student_id=%s)",
                self.student.id,
            )
            return {}

        return parsed

    def generate_questions_for_existing_passage(self, passage: ListeningPassage, vocab_contexts: list[WordMeaningContext]) -> list[dict]:
        """
        指定された長文と英単語群から問題のみを新規作成する
        
        Args:
            passage (ListeningPassage): 対象となる既存の長文
            vocab_contexts (list[WordMeaningContext]): 問題作成に利用する可能性がある語彙群
        
        Returns:
            list[dict]: 3問分のquestionsが格納されたリスト
        
        Note:
            - ChatGPTのエラー、JSONのエラーが想定されるが、それぞれraiseと{}で処理
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
            "Start listening problem generation (student_id=%s, len(vocab_contexts)=%d, passage_id=%s)",
            self.student.id, len(vocab_contexts), passage.id,
        )

        try:
            response = self.openai_client.chat.completions.create(
                model=OpenAIModel.PASSAGE_GENERATION,
                messages=[
                    {"role": "system", "content": f"あなたは英語教材を作成するアシスタントです。{level_prompt}"},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=4096,
                temperature=0.7
            )
        except Exception:
            logger.exception(
                "ChatGPT生成エラー (student_id=%s, vocab_contexts=%d)",
                self.student.id, len(vocab_contexts)
            )
            raise

        content = response.choices[0].message.content.strip()
        logger.debug("Raw response received (length=%d)", len(content))
        parsed = self._parse_response(content)
        if not parsed:
            logger.warning(
                "Parsed response is None while generating listening questions (student_id=%s)",
                self.student.id,
            )
            return []

        questions = parsed.get("questions", [])
        logger.debug(
            "listening questions generated (student_id=%s, question_count=%d)",
            self.student.id,
            len(questions),
        )
        return questions


    def _build_prompt(self, word_pairs: list[tuple[str, str]], word_limit: int) -> str:
        """
        長文と問題を同時に作成する際に必要なプロンプトの作成
        """
        words_and_meanings = ', '.join([f"{eng}（意味: {jpn}）" for eng, jpn in word_pairs])
        return (
            f"あなたは英語教材作成の専門家です。次の英単語をすべて自然に含むように、リスニング教材として使える英会話文を作成してください。\n\n"
            f"【目的】\n"
            f"この教材は、学習者が音声を聞いて内容理解を確認するために使用します。\n"
            f"そのため、会話は自然なテンポで行われるように意識し、口語的で理解しやすい表現を使ってください。\n"
            f"【条件】\n"
            f"・音声は男性・女性のいずれかがランダムに割り当てられます。\n"
            f"・対話相手を指す呼称として、**JamesやSarahのような性別を特定する人名の使用は禁止**します。\n"
            f"・ただし、会話中に登場する第三者（例: Emily, Mr. Smith）については、文脈上自然であれば名前を使用しても構いません。\n"
            f"・解説は必ず日本語で行うようにしてください。\n"
            f"【形式】\n"
            f"・約{word_limit}語の会話文\n"
            f"・話者は2〜3名（必ず行頭に「Speaker A:」のように明示）\n"
            f"・各段落は3〜5文、複数段落構成で改行（\\n）を明示\n"
            f"\n"
            f"【出力内容】\n"
            f"- title（英語タイトル）\n"
            f"- passage（本文）\n"
            f"- translation（本文の日本語訳）\n"
            f"- questions（4択問題3問）\n"
            f"    - question（質問文）\n"
            f"    - options（'A) ...' 形式で4つ）\n"
            f"    - answer（正解の記号: A/B/C/D）\n"
            f"    - explanation（日本語の簡単な解説）\n"
            f"\n"
            f"【語彙】以下の語彙をすべて使用すること：\n{words_and_meanings}\n"
            f"\n"
            f"【フォーマット】出力は以下の JSON 構造に**厳密に**従い、それ以外は出力しないこと。\n"
            f"```json\n"
            f"{{\n"
            f"  \"title\": \"...\",\n"
            f"  \"passage\": \"...\",\n"
            f"  \"translation\": \"...\",\n"
            f"  \"questions\": [\n"
            f"    {{\n"
            f"      \"question\": \"...\",\n"
            f"      \"options\": [\"A) ...\", \"B) ...\", \"C) ...\", \"D) ...\"],\n"
            f"      \"answer\": \"A\",\n"
            f"      \"explanation\": \"...\"\n"
            f"    }}, ...\n"
            f"  ]\n"
            f"}}\n"
            f"```"
        )


    def _build_prompt_only_questions(self, passage_text: str, word_pairs: list[tuple[str, str]]) -> str:
        """
        問題のみを作成する際に必要なプロンプトの作成
        """
        words_and_meanings = ', '.join([f"{eng}（意味: {jpn}）" for eng, jpn in word_pairs])
        return (
            "あなたは英語のリスニング教材を作成する専門家です。\n"
            "以下に示す会話文は、英語学習者が「音声を聞いて理解する」ためのリスニング教材の原文です。\n"
            "この本文の内容をもとに、音声を聞いて理解したことを確認できる4択問題を3問作成してください。\n"
            "\n"
            "【前提】\n"
            "・本文は複数の話者による会話形式で構成されています。\n"
            "・質問は「話の流れ」「話者の意図」「内容の聞き取り」に関するものであること。\n"
            "・単なる語句の穴埋めや語彙確認ではなく、**音声理解**を前提とした設問にしてください。\n"
            "・解説は必ず日本語で行うようにしてください。\n"
            "\n"
            f"【本文】\n{passage_text}\n"
            "\n"
            f"できるだけ次の語彙も問題文や選択肢に反映してください：{words_and_meanings}\n"
            "【出力形式】\n"
            "以下の形式で、問題文を3問出力してください。\n"
            "**JSON構造のみ**を返してください。コードブロック（```）や前後の文は不要です。\n"
            "\n"
            "{\n"
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

    def _estimate_word_limit_from_vocab_count(self, vocab_count: int) -> int:
        """
        生徒の学力と学習済み語彙量の比例を前提として、長文の単語数を返すヘルパー関数
        """
        if vocab_count < 50:
            return 60  # 初学者：文法・構文を減らして短く
        elif vocab_count < 200:
            return 90  # 語彙が増え始めた頃：短い会話文
        elif vocab_count < 800:
            return 120  # 中学英語終了レベル相当
        elif vocab_count < 1500:
            return 160
        else:
            return 200

    def get_student_vocab_count(self) -> int:
        """
        対象生徒の学習済み語彙をカウントするヘルパー関数
        """
        return StudentContextProgress.objects.filter(
            student=self.student,
            total_count__gt=0
        ).count()

    def normalize_answer(self, raw: str) -> str:
        """
        解答の正規化を行う
        """
        import re
        match = re.match(r'^\"?([A-Da-d])[)．. ]', raw)
        return match.group(1).upper() if match else raw[:1]


class EikenListeningPassageGenerator:
    """
    英検練習用の長文を作成する
    
    Attributes:
        level: 英検の級(5, 4, 3, 2, pre2, 2)
        vocab_contexts: 設問に含められる可能性がある学習済みの英単語
        client (openai.OpenAI): APIへのアクセスポイント
    """
    def __init__(self, student: Student, level: str, vocab_contexts: list[WordMeaningContext] | None =None):
        self.student = student
        self.level = level
        self.vocab_contexts = vocab_contexts or []
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            logger.error("Open AI APIキーが設定されていません。")
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
        vocab_count = self.get_student_vocab_count()
        word_limit = EIKEN_LEVEL_WORD_LIMITS[self.level]
        if vocab_count < 100:
            word_limit = int(word_limit * 0.8)  # 最低限の配慮
        elif vocab_count > 1500:
            word_limit = int(word_limit * 1.1)  # やや長めに挑戦
        # 級数に応じた英文法の設定
        grammar_list = get_cumulative_grammar(self.level)
        grammar_section = "\n".join([f"- {item}" for item in grammar_list])

        if passage_text:
            return (
                "以下の英語会話文（リスニングスクリプト）を元に、"
                f"{level_str}レベルにふさわしいリスニング理解を確認するための4択問題を3問作成してください。\n"
                "\n"
                f"【本文】\n{passage_text}\n"
                "\n"
                "【条件】\n"
                "・問題は会話の流れや登場人物の意図、やり取りの意味内容に基づいたものにしてください。\n"
                "・音声から理解できる内容を前提にした設問とし、文法や単語の知識確認だけに偏らないようにしてください。\n"
                "・解説は必ず日本語で行うようにしてください。\n"
                "・音声は男性・女性のいずれかがランダムに割り当てられます。\n"
                "・対話相手を指す呼称として、**JamesやSarahのような性別を特定する人名の使用は禁止**します。\n"
                "・ただし、会話中に登場する第三者（例: Emily, Mr. Smith）については、文脈上自然であれば名前を使用して構いません。\n"
                "\n"
                "【出力形式】以下のJSON構造の形式で、**前置き・後書きやコードブロックを含めず**に出力してください：\n"
                "{\n"
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
        else:
            return (
                f"あなたは英検リスニング問題の作成者です。\n"
                f"{level_str}レベルの英語学習者向けに、約{word_limit}語の英会話文とその日本語訳、さらに内容理解を確認する4択問題を3問作成してください。\n"
                f"\n"
                f"【本文の条件】\n"
                f"・登場人物は2～3人とし、各段落の行頭に「Speaker A:」のように話者を明示すること。\n"
                f"・段落ごとに\\nで改行。1段落あたり3～5文とし、自然な口語英語で構成すること。\n"
                f"・解説は必ず日本語で行うようにしてください。\n"
                f"・音声は男性・女性のいずれかがランダムに割り当てられます。\n"
                f"・対話相手を指す呼称として、**JamesやSarahのような性別を特定する人名の使用は禁止**します。\n"
                "・ただし、会話中に登場する第三者（例: Emily, Mr. Smith）については、文脈上自然であれば名前を使用して構いません。"
                f"・以下の英文法と語彙をなるべくすべて本文中に盛り込むこと。\n"
                f"（文法はリスト後方のものを優先的に使用）\n\n"
                f"{grammar_section}\n\n"
                f"{vocab_section}\n"
                f"\n"
                f"【出力形式】JSON形式で出力してください。**マークダウン、前後の解説、コードブロックは禁止です。**\n"
                f"\n"
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
            "Start eiken listening passage and problem generation (student_id=%s)",
            self.student.id,
        )

        try:
            res = self.client.chat.completions.create(
                model=OpenAIModel.PASSAGE_GENERATION, messages=messages, max_completion_tokens=4096
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
                "Parsed response is None while generating eiken listening questions (student_id=%s)",
                self.student.id,
            )
            return {}

        return parsed

    def generate_questions_for_existing_passage(self, passage: ListeningPassage) -> list[dict]:
        """
        既存の英検長文に対して、追加の読解問題（questions）のみを生成する。

        Args:
            passage (ListeningPassage): 既存の長文。

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
            "Start eiken listening problem generation (student_id=%s)",
            self.student.id,
        )
        try:
            response = self.client.chat.completions.create(
                model=OpenAIModel.PASSAGE_GENERATION, messages=messages, max_completion_tokens=2048
            )
        except Exception:
            logger.exception(
                "ChatGPT生成エラー (student_id=%s)",
                self.student.id
            )
            raise
            
        content = response.choices[0].message.content.strip()
        logger.debug("Raw response received (length=%d)", len(content))
        parsed = self._parse_response(content)
        if not parsed:
            logger.warning(
                "Parsed response is None while generating eiken listening questions (student_id=%s)",
                self.student.id,
            )
            return []

        questions = parsed.get("questions", [])
        logger.debug(
            "eiken listening questions generated (student_id=%s, question_count=%d)",
            self.student.id,
            len(questions),
        )
        return questions

    def get_student_vocab_count(self) -> int:
        return StudentContextProgress.objects.filter(
            student=self.student,
            total_count__gt=0
        ).count()

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
