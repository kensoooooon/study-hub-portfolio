import re

import os
import csv
from pathlib import Path
from collections import defaultdict


POS_DICT = {
    "動詞": "verb",
    "名詞": "noun",
    "形容詞": "adjective",
    "副詞": "adverb",
    "前置詞": "preposition",
    "接続詞": "conjunction",
    "間投詞": "interjection",
    "代名詞": "pronoun",
    "熟語": "phrase",
}

# 例外的なチャプター名の変換を定義するマッピング辞書（初期は空）
# 必要に応じて `"旧名称": "正規化名称"` を追加する
CHAPTER_TITLE_MAP: dict[str, str] = {}


def rule_based_normalize(title: str) -> str:
    """
    表記揺れの多いチャプター名に対して、ルールベースで正規化処理を行う関数。

    例：
        Unit3 → Unit 3
        Let'sTalk2 → Let's Talk 2
        Unit 1-2 → Unit 1 - 2

    Args:
        title (str): 元のチャプター名

    Returns:
        str: 規則に基づいて整形されたチャプター名
    """
    title = title.strip()

    # 英字と数字の間にスペース（例: "Unit3" → "Unit 3"）
    title = re.sub(r"([a-zA-Z])(\d)", r"\1 \2", title)

    # 数字と英字の間にもスペース（例: "3Part" → "3 Part"）
    title = re.sub(r"(\d)([a-zA-Z])", r"\1 \2", title)

    # 数字のハイフン結合にスペース（例: "1-2" → "1 - 2"）
    title = re.sub(r"(\d)-(\d)", r"\1 - \2", title)

    # 過剰なスペースを単一スペースに
    title = re.sub(r"\s{2,}", " ", title)

    return title

def normalize_chapter_title(title: str) -> str:
    """
    チャプター名をルールベース + 辞書ベースで正規化する関数。
    まずルールベースの補正を行い、その後例外辞書を参照して最終調整を行う。

    Args:
        title (str): 元のチャプター名

    Returns:
        str: 正規化されたチャプター名
    """
    title = rule_based_normalize(title)
    return CHAPTER_TITLE_MAP.get(title, title)


def load_chapter_orders(base_dir: Path) -> dict:
    chapter_orders = defaultdict(lambda: defaultdict(dict))
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file == "チャプターリスト.tsv":
                path = Path(root) / file
                textbook_name = Path(root).parents[1].name
                edition_str = Path(root).parents[0].name
                grade_str = Path(root).name
                try:
                    publication_year = int(edition_str.replace("年度", ""))
                    grade = int(grade_str[0])
                except ValueError:
                    continue
                with open(path, encoding="utf-8-sig") as f:
                    reader = csv.reader(f, delimiter="\t")
                    order_map = {}
                    for idx, row in enumerate(reader):
                        if row and row[0].strip():
                            order_map[row[0].strip()] = idx + 1
                    chapter_orders[textbook_name][publication_year][grade] = order_map
    return chapter_orders

def get_file_information(file_path: Path) -> tuple[str, str, str, str]:
    """
    ファイルパスを情報源として登録・更新に必要な情報を取得する
    
    Args:
        file_path (Path): TSVファイルが存在するファイルパス
            (eg. C:....data\vocab_trainer\Sunshine\2025年度\1年\前置詞.tsv)
    
    Returns:
        textbook_name (str): 教科書名
        edition_str (str): 版の情報
        grade_str (str): 学年の情報
        part_of_speech_jp (str): 品詞の情報
    """
    try:
        textbook_name = file_path.parents[2].name
        edition_str = file_path.parents[1].name
        grade_str = file_path.parents[0].name
    except Exception as e:
        print(f"❌ パス構造が不正です: {file_path} → {e}")
        raise

    part_of_speech_jp = file_path.stem
    if part_of_speech_jp not in POS_DICT:
        raise ValueError(f"無効な品詞: {part_of_speech_jp}")

    return textbook_name, edition_str, grade_str, part_of_speech_jp
