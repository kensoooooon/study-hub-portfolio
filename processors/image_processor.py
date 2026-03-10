"""
画像をGoogle Cloud Vision APIで処理
"""
# 環境変数用
from django.conf import settings

# 画像処理用
from google.cloud import vision
from google.auth.exceptions import GoogleAuthError

# ログ出力用
import logging

logger = logging.getLogger(__name__)

class ImageProcessor:
    def __init__(self):
        try:
            # Google Cloud Vision APIクライアントの初期化
            self.client = vision.ImageAnnotatorClient()
            logger.info("Vision ImageAnnotatorClient initialized")
        except GoogleAuthError as e:
            logger.exception("Google Cloud Vision APIクライアントの初期化に失敗しました")
            self.client = None
            
    def process_image(self, image_data):
        """
        Google Cloud Vision APIを使用して画像を解析
        """
        logger.info("Start processing image (bytes_length=%d)", len(image_data))
        if not self.client:
            logger.warning("Vision クライアント未初期化のため処理不能")
            return "Google Cloud Vision APIクライアントが初期化されていません。"
        try:
            # 画像データをエンコードしてリクエストを送信
            image = vision.Image(content=image_data)
            response = self.client.text_detection(image=image)
            
            if response.error.message:
                logger.error("Google Vision API error: %s", response.error.message)
                return "画像処理中にエラーが発生しました。"
            
            texts = response.text_annotations
            return texts[0].description.strip() if texts else "画像からテキストを抽出できませんでした。"
        
        except Exception as e:
            logger.exception("画像処理中にエラーが発生しました")
            return "画像処理中にエラーが発生しました。"
