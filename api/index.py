import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app, init_files, ensure_pyrogram_session

# Initialize files on startup
try:
    init_files()
    ensure_pyrogram_session()
except Exception as e:
    print(f"Init error: {e}")

# WSGI app for Vercel
application = app

