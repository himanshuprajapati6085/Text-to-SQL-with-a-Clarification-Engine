import uvicorn
import webbrowser
import threading
import time
from init_db import seed_database
from app.config import settings

def open_browser():
    time.sleep(1.5)
    url = f"http://{settings.HOST}:{settings.PORT}"
    print(f"\n[+] Opening browser at: {url}")
    webbrowser.open(url)

if __name__ == "__main__":
    print("[*] Initializing Database...")
    seed_database()
    threading.Thread(target=open_browser, daemon=True).start()
    print(f"[*] Starting QueryMind AI Server on http://{settings.HOST}:{settings.PORT} ...")
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=False)
