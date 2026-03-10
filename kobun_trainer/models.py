"""
古文単語の学習をサポートする構造

・各モデル
    ClassicalWord: 品詞ごとに区別された古文単語
    Meaning: 日本語の意味
    Inflection: 活用形
    Example Sentence: 特定の品詞で利用された単語の例文

@startuml
skinparam classAttributeIconSize 0

class ClassicalWord {
  +id : PK
  surface_form : str
  reading : str
  part_of_speech : str
  has_inflection : bool
}

class Meaning {
  +id : PK
  translation : str
  explanation : str
}

class Inflection {
  +id : PK
  form_name : str
  form_value : str
}

class ExampleSentence {
  +id : PK
  classical_text : str
  modern_translation : str
  source : str
}

' リレーション（関連名は任意で補助的）
ClassicalWord "1" -- "0..*" Meaning : defines
ClassicalWord "1" -- "0..*" Inflection : conjugates_to
Meaning "1" -- "0..*" ExampleSentence : exemplified_by

@enduml

"""

from django.db import models


class ClassicalWord(models.Model):
    surface_form = models.CharField(max_length=50)  # 表記：例「おとなし」
    reading = models.CharField(max_length=50)       # よみがな：例「おとなし」
    part_of_speech = models.CharField(max_length=20, choices=[
        ('noun', '名詞'),
        ('verb', '動詞'),
        ('adj', '形容詞'),
        ('adv', '副詞'),
        ('conj', '接続詞'),
        ('prt', '助詞'),
        ('aux', '助動詞'),
        # 必要に応じて追加
    ])
    has_inflection = models.BooleanField(default=False)

    def __str__(self):
        return self.surface_form


class Meaning(models.Model):
    word = models.ForeignKey(ClassicalWord, on_delete=models.CASCADE, related_name='meanings')
    translation = models.CharField(max_length=100)         # 現代語訳（例：大人びている）
    explanation = models.TextField(blank=True)             # 詳細説明

    def __str__(self):
        return f"{self.word.surface_form} - {self.translation}"


class Inflection(models.Model):
    word = models.ForeignKey(ClassicalWord, on_delete=models.CASCADE, related_name='inflections')
    form_name = models.CharField(max_length=20)   # 例：「未然形」「已然形」
    form_value = models.CharField(max_length=50)  # 例：「あら」「あれ」

    def __str__(self):
        return f"{self.word.surface_form}（{self.form_name}）→ {self.form_value}"


class ExampleSentence(models.Model):
    meaning = models.ForeignKey(Meaning, on_delete=models.CASCADE, related_name='examples')
    classical_text = models.TextField()           # 古文本文
    modern_translation = models.TextField()       # 現代語訳
    source = models.CharField(max_length=100, blank=True)  # 出典

    def __str__(self):
        return f"{self.classical_text[:20]}..."
