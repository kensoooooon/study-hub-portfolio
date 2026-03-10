"""
選択肢取得のために利用される関数群置き場
"""
import logging
import random

from vocab_trainer.models import EnglishWord, JapaneseMeaning, WordMeaningRelation

logger = logging.getLogger(__name__)


def _random_pick_english_words_excluding(correct_word: str, k: int) -> list[str]:
    """日本語から英語を答える問題において、正解の日本語に対応する英単語を除いた任意のk個の英単語を返す

    Args:
        correct_word (str): 除外対象となる英単語のスペル
        k (int): 選出数

    Returns:
        wrongs(list[str]): ランダムに選出された誤りのスペル群
    """
    if k<= 0:
        return []
    
    qs = EnglishWord.objects.exclude(word=correct_word).values_list("word", flat=True)
    words = list(qs)  # リスト化で過剰なクエリ発行を防止
    if not words:
        return []
    n = len(words)
    k = min(k, n)
    wrongs = random.sample(words, k)
    return wrongs


def _random_pick_japanese_meanings_excluding(correct_meaning: str, k: int) -> list[str]:
    """英語から日本語を答える問題において、正解の英語に対応する日本語を除いた任意のk個の日本語を返す

    Args:
        correct_meaning (str): 除外対象となる日本語の意味
        k (int): 選出数

    Returns:
        wrongs(list[str]): ランダムに選出された誤りの日本語群
    """
    if k<= 0:
        return []
    qs = JapaneseMeaning.objects.exclude(meaning=correct_meaning).values_list("meaning", flat=True)
    words = list(qs)  # リスト化でクエリ発行を1回にする
    if not words:
        return []
    n = len(words)
    k = min(k, n)
    wrongs = random.sample(words, k)
    return wrongs


def get_choices(relation: WordMeaningRelation, quiz_type: str) -> list[str]:
    """正解1つと誤答3つを含む選択肢群を返す

    Args:
        relation (WordMeaningRelation): 正解の英語・日本語対応関係
        quiz_type (str): jp_to_en(日本語から英語)か、en_to_jp(英語から日本語)のいずれか

    Returns:
        list[str]: 正解1誤答3の選択肢群
    """
    if quiz_type == "jp_to_en":
        correct = relation.english_word.word
        wrongs = _random_pick_english_words_excluding(correct, k=3)
    else:
        correct = relation.japanese_meaning.meaning
        wrongs = _random_pick_japanese_meanings_excluding(correct, k=3)

    choices = [correct] + wrongs
    random.shuffle(choices)
    return choices
