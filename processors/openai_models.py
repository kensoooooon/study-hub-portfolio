from django.conf import settings


class OpenAIModel:
    CHAT: str = getattr(settings, "OPENAI_MODEL_CHAT", "gpt-4o")
    SHORT_TASK: str = getattr(settings, "OPENAI_MODEL_SHORT_TASK", "gpt-4")
    SUMMARY: str = getattr(settings, "OPENAI_MODEL_SUMMARY", "gpt-4o")
    PASSAGE_GENERATION: str = getattr(settings, "OPENAI_MODEL_PASSAGE_GENERATION", "gpt-4o")
