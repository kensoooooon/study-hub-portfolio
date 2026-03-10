import time
import requests
from datetime import datetime

def trigger_reminders():
    while True:
        try:
            # 修正後のURL
            response = requests.post("http://127.0.0.1:8000/study_reminder/process-reminders/")
            print(f"[{datetime.now()}] Triggered reminders: {response.status_code}")
        except Exception as e:
            print(f"[{datetime.now()}] Error triggering reminders: {e}")
        time.sleep(60)  # 1分待機

if __name__ == "__main__":
    trigger_reminders()
