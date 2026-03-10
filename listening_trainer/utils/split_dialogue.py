import re

def split_dialogue_by_speaker(text: str) -> list[tuple[str, str]]:
    """
    Args:
        text (str): 整理したい会話文
    
    Returns:
        (list[tuple[str, str]]): 話者ごとに分割されたセリフ
    
    'Speaker A: ...' や 'Speaker A (Female): ...' のような行を
    話者ごとに (speaker, text) に分割する
    """
    lines = text.strip().splitlines()
    parts = []
    current_speaker = None
    current_text = []

    for line in lines:
        stripped = line.strip()
        # Speaker A: / Speaker A(Female): / Speaker A (Female): を全部許容
        match = re.match(r"^(Speaker [A-Z])(?:\s*\([^)]*\))?:\s*(.*)", stripped)
        if match:
            # 直前の塊を確定
            if current_speaker and current_text:
                parts.append((current_speaker, " ".join(current_text).strip()))

            # Speaker A / Speaker B のような「ベース名」だけを使う
            current_speaker = match.group(1)
            first_text = match.group(2)
            current_text = [first_text] if first_text else []
        elif current_speaker:
            # 継続行はそのまま本文に追加
            if stripped:
                current_text.append(stripped)

    if current_speaker and current_text:
        parts.append((current_speaker, " ".join(current_text).strip()))

    return parts