#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

if os.name == "nt":
    os.environ.setdefault("GOOGLE_CLOUD_DISABLE_GRPC", "true")

# ★ 追加：.env を先読み（settings.py より前）
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(), override=False)  # 既にOS側に同名があれば尊重
except Exception:
    pass


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_study_hub.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
