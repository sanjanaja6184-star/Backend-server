#!/usr/bin/env python3
"""
Standalone Telegram Bot Runner
Run this locally or on a separate server to handle admin commands
Usage: python run_bot.py
"""

import os
import sys
import asyncio
import threading
import signal
import time

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Import functions from main.py
from main import (
    BOT_TOKEN, ADMIN_ID, init_files, init_pyrogram_clients,
    ensure_pyrogram_session, cmd_start, handle_button_text
)

def run_bot():
    """Run Telegram bot with proper error handling"""
    
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not set! Cannot start bot.")
        print("Set BOT_TOKEN environment variable and try again.")
        return
    
    print("\n" + "="*60)
    print("🤖 STANDALONE TELEGRAM ADMIN BOT")
    print("="*60 + "\n")
    
    # Initialize files
    try:
        init_files()
        print("✅ Files initialized")
    except Exception as e:
        print(f"❌ File init failed: {e}")
        return
    
    # Initialize Pyrogram clients
    try:
        init_pyrogram_clients()
        if not ensure_pyrogram_session():
            print("⚠️ Warning: Some Pyrogram sessions may not be connected")
    except Exception as e:
        print(f"⚠️ Pyrogram init warning: {e}")
    
    # Create and run bot
    try:
        print("\n" + "="*60)
        print("🤖 TELEGRAM ADMIN BOT")
        print("="*60)
        print("Commands:")
        print("/start - Open Admin Panel with Buttons")
        print(f"Admin ID: {ADMIN_ID}")
        print("="*60 + "\n")
        
        telegram_app = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        telegram_app.add_handler(CommandHandler("start", cmd_start))
        telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button_text))
        
        print("✅ Bot handlers registered")
        print("🚀 Bot polling started! (Press Ctrl+C to stop)\n")
        
        # Run polling
        telegram_app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            stop_signals=(signal.SIGINT, signal.SIGTERM)
        )
        
    except Exception as e:
        print(f"\n❌ Bot Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = run_bot()
    sys.exit(exit_code if exit_code else 0)
