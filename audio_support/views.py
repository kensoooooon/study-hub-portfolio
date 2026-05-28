# audio_support/views.py
import tempfile
from django.http import FileResponse
from google.cloud import texttospeech

from vocab_trainer.models import WordMeaningContext
from read_trainer.models import ReadingPassage


from django.shortcuts import render
from django.http import HttpResponseBadRequest, HttpResponse

import random
import os

import threading

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from listening_trainer.models import ListeningPassage
from listening_trainer.utils.split_dialogue import split_dialogue_by_speaker

# 音声ファイル
import uuid

from django.views.decorators.csrf import csrf_exempt

import re

# 削除用
# OIDC認証
from auth.oidc_verify import require_oidc_token
import time

from django.conf import settings

from google.api_core.exceptions import ServiceUnavailable

# URL経由での再生実現
from django.views.decorators.http import require_GET
from django.http import Http404

from django.contrib.auth.decorators import login_required

import sys

import logging
logger = logging.getLogger(__name__)


TEMP_AUDIO_DIR = os.path.join(settings.MEDIA_ROOT, "temp_audio")
os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)


_TTS_CLIENT = None

def get_tts_client():
    """
    TextToSpeechのクライアントをローカルでRESTモードにするためのヘルパ関数
    """
    global _TTS_CLIENT
    if _TTS_CLIENT is not None:
        return _TTS_CLIENT
    env = getattr(settings, "ENVIRONMENT", "").lower()
    is_windows = sys.platform.startswith("win")
    use_rest = is_windows or env in {"local", "dev", "development"}
    if use_rest:
        _TTS_CLIENT = texttospeech.TextToSpeechClient(transport="rest")
    else:
        _TTS_CLIENT = texttospeech.TextToSpeechClient()
    return _TTS_CLIENT


def generate_audio_to_tempfile(text: str, voice: str = "en-US-Wavenet-C", rate: float = 1.0) -> tempfile._TemporaryFileWrapper:
    """
    渡されたテキストと指定されたタイプ、および再生レートに応じて音声を一時ファイルとして生成
    """
    # client = texttospeech.TextToSpeechClient()
    client = get_tts_client()
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice_params = texttospeech.VoiceSelectionParams(language_code="en-US", name=voice)
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=rate
        )

    response = client.synthesize_speech(input=synthesis_input, voice=voice_params, audio_config=audio_config)

    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp_file.write(response.audio_content)
    tmp_file.flush()
    return tmp_file


def generate_audio_file(text: str, voice: str = "en-US-Wavenet-C", rate: float = 1.0, retries=5, delay=1.5) -> str:
    """
    音声を media/temp_audio に保存し、ファイル名を返す
    """
    # client = texttospeech.TextToSpeechClient()
    client = get_tts_client()
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice_params = texttospeech.VoiceSelectionParams(language_code="en-US", name=voice)
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3, speaking_rate=rate)

    for attempt in range(retries):
        try:
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice_params,
                audio_config=audio_config
            )
            filename = f"{uuid.uuid4()}.mp3"
            file_path = os.path.join(TEMP_AUDIO_DIR, filename)
            with open(file_path, "wb") as out:
                out.write(response.audio_content)

            logger.info("[audio_support] Generated audio file at: %s", file_path)
            if os.path.exists(file_path):
                logger.info("[audio_support] File exists ✅")
            else:
                logger.warning("[audio_support] ERROR: File NOT found ❌")

            return filename
        except ServiceUnavailable as e:
            logger.info("[Retry %s/%s] Service unavailable. Retrying in %s seconds...", attempt+1, retries, delay)
            time.sleep(delay)
        except Exception:
            logger.exception("Unexpected failure during TTS")
            break

    raise RuntimeError("音声生成に失敗しました（リトライ上限に達しました）")


def generate_audio(text):
    """
    generate_audio_to_tempfileを使って使って音声を合成し、
    一時的なMP3ファイルとして保存。そのファイルを FileResponse で返す。
    レスポンス送信後に自動でファイルを削除する。
    """
    available_voices = ["en-US-Wavenet-A", "en-US-Wavenet-B", "en-US-Wavenet-C", "en-US-Wavenet-D"]
    random_voice = random.choice(available_voices)
    random_rate = random.uniform(0.85, 1.2)
    tmp_file = generate_audio_to_tempfile(text, random_voice, random_rate)

    file = open(tmp_file.name, "rb")
    response = FileResponse(file, content_type="audio/mpeg")
    response["Content-Disposition"] = 'inline; filename="word.mp3"'

    def cleanup():
        try:
            os.remove(tmp_file.name)
        except Exception:
            logger.exception("Error removing temp file")

    threading.Timer(5.0, cleanup).start()
    return response

@login_required
def speak_word(request):
    """
    クエリパラメータから context_id 経由で英単語を取得し、音声を生成。
    ファイル名をJSON形式で返す。
    """
    context_id = request.GET.get("context_id")
    try:
        context = WordMeaningContext.objects.select_related(
            "relation__english_word"
        ).get(id=context_id)
    except WordMeaningContext.DoesNotExist:
        logger.warning("context not found")
        return JsonResponse({"error": "context not found"}, status=404)

    available_voices = ["en-US-Wavenet-A", "en-US-Wavenet-B", "en-US-Wavenet-C", "en-US-Wavenet-D"]
    random_voice = random.choice(available_voices)
    random_rate = random.uniform(0.85, 1.2)
    english_word = context.relation.english_word.word
    try:
        filename = generate_audio_file(english_word, voice=random_voice, rate=random_rate)
    except Exception:
        logger.exception(
            "Unexpected failure during TTS (user_id=%s, context_id=%s)",
            request.user.id,
            context_id
        )
        return JsonResponse({"error": "unexpected"}, status=404)
    return JsonResponse({"filename": filename})


@login_required
def speak_passage(request):
    """
    クエリパラメータから取得したpassage_idをもとに、文章を取得。
    文章用の音声を作成し、ファイル名を返す
    """
    passage_id = request.GET.get("passage_id")
    try:
        passage = ReadingPassage.objects.get(id=passage_id)
    except ReadingPassage.DoesNotExist:
        return JsonResponse({"error": "passage not found"}, status=404)
    content = passage.content
    available_voices = ["en-US-Wavenet-A", "en-US-Wavenet-B", "en-US-Wavenet-C", "en-US-Wavenet-D"]
    random_voice = random.choice(available_voices)
    random_rate = random.uniform(0.85, 1.2)
    try:
        filename = generate_audio_file(content, voice=random_voice, rate=random_rate)
    except Exception:
        logger.exception(
            "Unexpected failure during TTS (user_id=%s, passage_id=%s)",
            request.user.id,
            passage_id
        )
        return JsonResponse({"error": "unexpected"}, status=404)
    return JsonResponse({"filename": filename})    


@login_required
def speak_dialogue(request):
    """
    Speaker A: ~.
    Speaker B: ~.
    のような形式のテキストに対し、この後連続再生するための音声ファイルを作成し、URLとして渡す
    """

    passage_id = request.GET.get("passage_id")
    if not passage_id:
        return HttpResponseBadRequest("passage_idが指定されていません")

    passage = get_object_or_404(ListeningPassage, id=passage_id)
    lines = split_dialogue_by_speaker(passage.content)

    voice_variants = {
        "Speaker A": ["en-US-Wavenet-B", "en-US-Wavenet-C"],
        "Speaker B": ["en-US-Wavenet-A", "en-US-Wavenet-D"],
    }

    speaker_voice_map = {}

    results = []
    for speaker, text in lines:
        # ① 「Speaker A(Female)」 → 「Speaker A」に正規化
        normalized_speaker = re.sub(r"\s*\([^)]*\)", "", speaker).strip()

        # ② 正規化したスピーカー名で声の候補を取得
        if normalized_speaker not in speaker_voice_map:
            candidate_voices = voice_variants.get(
                normalized_speaker,
                ["en-US-Wavenet-C"]  # 想定外の話者名でも最低限しゃべる
            )
            speaker_voice_map[normalized_speaker] = random.choice(candidate_voices)

        voice = speaker_voice_map[normalized_speaker]

        # ③ テキスト自体はそのまま読み上げ（"(Female)" などが含まれていたら、
        #    別途 text 側からも除去したかったらここでやる）
        filename = generate_audio_file(text, voice=voice)
        audio_url = request.build_absolute_uri(settings.MEDIA_URL + f"temp_audio/{filename}")
        results.append({
            "speaker": speaker,  # 画面表示用には元の文字列を返す
            "text": text,
            "url": audio_url,
            "filename": filename,
        })

    return JsonResponse(results, safe=False)

@login_required
@csrf_exempt
def delete_temp_audio_post_batch(request):
    """
    クライアントサイドからの一時音声ファイル削除用
    リスニングの解答結果(result.html)から呼び出す
    """
    if request.method != "POST":
        logger.error("POSTメソッド以外は利用できません (user_id=%s)", request.user.id)
        return JsonResponse({"error": "POST only"}, status=405)

    filenames_str = request.POST.get("filenames")
    if not filenames_str:
        logger.error("ファイル名が存在しません (user_id=%s)", request.user.id)
        return JsonResponse({"error": "no filenames"}, status=400)

    filenames = filenames_str.split(",")

    logger.info(
        "delete_temp_audio_post_batchが呼び出されました。処理を開始します。(user_id=%s, filenames=%s)",
        request.user.id,
        filenames,
    )

    results = []
    for filename in filenames:
        filename = filename.strip()
        if not re.match(r"^[a-f0-9\-]{36}\.mp3$", filename):
            logger.error("UUID形式と一致しませんでした (filename=%s, user_id=%s)", filename, request.user.id)
            continue

        path = os.path.join(TEMP_AUDIO_DIR, filename)
        logger.info("path: %s", path)
        if not os.path.abspath(path).startswith(os.path.abspath(f"{settings.MEDIA_ROOT}/temp_audio")):
            logger.error("ファイルパスが正確ではありません (path=%s, user_id=%s)", path, request.user.id)
            continue

        try:
            os.remove(path)
            logger.info("ファイルを削除しました (path=%s, user_id=%s)", path, request.user.id)
            results.append({"filename": filename, "status": "deleted"})
        except Exception as e:
            logger.exception("削除失敗しました (filename=%s, user_id=%s)", filename, request.user.id)
            results.append({"filename": filename, "error": str(e)})

    return JsonResponse(results, safe=False)


@csrf_exempt
@require_oidc_token(audience="https://django-study-hub.an.r.appspot.com")
def clean_old_temp_audio(request):
    """
    Google Cloud Schedulerを用いて、定期的に一時音声ファイルを削除
    現在は毎日朝4時の設定
    """
    if request.headers.get("X-Appengine-Cron") != "true":
        return JsonResponse({"error": "unauthorized"}, status=403)

    threshold = time.time() - 60 * 60 * 24  # 24時間前
    deleted = 0
    skipped = 0
    failed = 0

    folder = TEMP_AUDIO_DIR
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        try:
            if os.path.isfile(path) and os.path.getmtime(path) < threshold:
                os.remove(path)
                deleted += 1
            else:
                skipped += 1
        except Exception as e:
            failed += 1
            continue

    logger.info(
        "clean_old_temp_audio executed: deleted=%s skipped=%s failed=%s",
        deleted, skipped, failed
    )

    return JsonResponse({
        "status": "ok",
        "deleted": deleted,
        "skipped": skipped,
        "failed": failed
    })


@login_required
@require_GET
def serve_temp_audio(request, filename):
    if not re.match(r"^[a-f0-9\-]{36}\.mp3$", filename):
        logger.warning("Invalid filename requested: %s, user: %s", filename, request.user)
        raise Http404("Invalid filename")

    file_path = os.path.join(TEMP_AUDIO_DIR, filename)
    if not os.path.exists(file_path):
        raise Http404("Audio file not found")

    return FileResponse(open(file_path, 'rb'), content_type='audio/mpeg')
