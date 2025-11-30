"""
Search Dashboard - Telegram Bot Admin + Flask API Backend
=========================================================
Deploy this file on any Telegram Bot Hosting platform (like Heroku, Railway, PythonAnywhere)
The bot handles all admin functions, Flask API handles frontend requests.

Environment Variables Required:
- BOT_TOKEN: Your Telegram Bot Token (get from @BotFather)
- ADMIN_ID: Your Telegram User ID (for admin authorization)
- ADMIN_PASSWORD: Password for API admin functions (optional fallback)

For Pyrogram (Search Accounts):
- NUMBER_API_ID, NUMBER_API_HASH, NUMBER_PHONE: For number search account
- USERNAME1_API_ID, USERNAME1_API_HASH, USERNAME1_PHONE: For username search account 1
- USERNAME2_API_ID, USERNAME2_API_HASH, USERNAME2_PHONE: For username search account 2
"""

import os
import json
import time
import asyncio
import threading
import string
from random import randint, choice

from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
from pyrogram.client import Client
from pyrogram.errors import FloodWait

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# ============================================
# CONFIGURATION
# ============================================

BOT_TOKEN = '8327107898:AAEdV1eHiX4ckuUncT9b4j90iYNnFIHEZyo'
ADMIN_ID = -8415818047
ADMIN_PASSWORD = 'admin123'

NUMBER_SEARCH_PYROGRAM = {
    "api_id": 39782165,
    "api_hash": "e0e665ae0de9e60ab4b1d77fcc71820c",
    "phone": "+919661948912",
    "session_name": "number_search_account"
}

USERNAME_SEARCH_PYROGRAMS = [
    {
        "api_id": 34654267,
        "api_hash": "357a43d409317339d74ef6ecf3869dcd",
        "phone": "+917479569462",
        "target_bot": "@Dfjyt_bot",
        "session_name": "username_search_account_1"
    },
    {
        "api_id": 35591923,
        "api_hash": "bfbcb925759e8b0e400c7e29caaf2724",
        "phone": "+919142484615",
        "target_bot": "@Dfjyt_bot",
        "session_name": "username_search_account_2"
    }
]

ACTIVE_USERNAME_PYROGRAM_INDEX = 0

# File paths
USERS_FILE = "web_users.json"
SEARCHED_NO_DATA_FILE = "searched_no_data.json"
DEPOSIT_REQUESTS_FILE = "deposit_requests.json"
PROMO_CODES_FILE = "promo_codes.json"

# Thread locks
users_lock = threading.RLock()
searched_no_data_lock = threading.RLock()

# ============================================
# FLASK APP SETUP
# ============================================

app = Flask(__name__)
app.secret_key = 'search-dashboard-secret-key-2024'

CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# ============================================
# PYROGRAM CLIENTS
# ============================================

number_search_client = None
username_search_clients = []

def init_pyrogram_clients():
    global number_search_client, username_search_clients
    
    if NUMBER_SEARCH_PYROGRAM["api_id"] != 0:
        try:
            number_search_client = Client(
                NUMBER_SEARCH_PYROGRAM["session_name"],
                api_id=NUMBER_SEARCH_PYROGRAM["api_id"],
                api_hash=NUMBER_SEARCH_PYROGRAM["api_hash"],
                phone_number=NUMBER_SEARCH_PYROGRAM["phone"],
                workdir=".",
                no_updates=True
            )
            print("✅ Number search client initialized")
        except Exception as e:
            print(f"❌ Number search client init failed: {e}")
    
    username_search_clients = []
    for idx, config in enumerate(USERNAME_SEARCH_PYROGRAMS):
        session_file = f"{config['session_name']}.session"
        if os.path.exists(session_file) or (config["api_id"] != 0 and config["api_hash"]):
            try:
                api_id = config["api_id"] if config["api_id"] != 0 else 1
                api_hash = config["api_hash"] if config["api_hash"] else "dummy"
                
                client = Client(
                    config["session_name"],
                    api_id=api_id,
                    api_hash=api_hash,
                    phone_number=config["phone"] if config["phone"] else None,
                    workdir=".",
                    no_updates=True
                )
                username_search_clients.append(client)
                print(f"✅ Username search client #{idx + 1} initialized")
            except Exception as e:
                print(f"❌ Username search client #{idx + 1} failed: {e}")

# ============================================
# FILE OPERATIONS
# ============================================

def init_files():
    for filepath, default_data in [
        (USERS_FILE, {}),
        (SEARCHED_NO_DATA_FILE, {}),
        (DEPOSIT_REQUESTS_FILE, []),
        (PROMO_CODES_FILE, {})
    ]:
        if not os.path.exists(filepath):
            with open(filepath, 'w') as f:
                json.dump(default_data, f)
            print(f"✅ Created {filepath}")

def load_json(filepath, default=None):
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except:
        return default if default is not None else {}

def save_json(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

def load_users():
    return load_json(USERS_FILE, {})

def save_users(data):
    save_json(USERS_FILE, data)

def load_searched_no_data():
    return load_json(SEARCHED_NO_DATA_FILE, {})

def add_to_searched_no_data(query, search_type, has_result=False):
    with searched_no_data_lock:
        data = load_searched_no_data()
        # Normalize the query for consistent key generation (same as is_already_searched_no_data)
        if search_type == "username":
            normalized_query = query.lstrip('@').lower()
        elif search_type == "userid":
            normalized_query = query.strip().lower()
        else:
            normalized_query = query.lower()
        
        key = f"{search_type}_{normalized_query}"
        data[key] = {
            "query": query,
            "search_type": search_type,
            "timestamp": time.time(),
            "has_result": has_result
        }
        save_json(SEARCHED_NO_DATA_FILE, data)

def is_already_searched_no_data(query, search_type):
    with searched_no_data_lock:
        data = load_searched_no_data()
        # Normalize the query for consistent key generation
        if search_type == "username":
            normalized_query = query.lstrip('@').lower()
        elif search_type == "userid":
            normalized_query = query.strip().lower()
        else:
            normalized_query = query.lower()
        
        key = f"{search_type}_{normalized_query}"
        if key in data:
            # Block if previously searched and no result was found
            return data[key].get('has_result', False) == False
        return False

def add_search_to_user_history(user_name, search_type, query, has_result):
    with users_lock:
        users = load_users()
        if user_name in users:
            if 'search_history' not in users[user_name]:
                users[user_name]['search_history'] = []
            users[user_name]['search_history'].append({
                "search_type": search_type,
                "query": query,
                "timestamp": time.time(),
                "has_result": has_result
            })
            save_users(users)

def generate_hash_code():
    chars = string.ascii_uppercase + string.digits
    return ''.join(choice(chars) for _ in range(6))

# ============================================
# PYROGRAM SEARCH FUNCTIONS
# ============================================

def get_event_loop():
    """Get or create event loop safely for use within Flask requests."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("Event loop is closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop

def filter_response_data(raw_text):
    import re
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F1E0-\U0001F1FF"
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE)
    clean_text = emoji_pattern.sub('', raw_text)
    
    # Check for "The name of the father" field to verify complete data
    if "The name of the father" not in raw_text:
        return {"status": "no_results", "message": "Incomplete data - missing father's name"}
    
    paragraphs = clean_text.split('\n\n')
    all_records = []
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph or ":" not in paragraph:
            continue
        lines = paragraph.split('\n')
        record_fields = []
        has_data = False
        for line in lines:
            line = line.strip()
            if not line or ":" not in line:
                continue
            parts = line.split(":", 1)
            if len(parts) != 2:
                continue
            key = parts[0].strip()
            value = parts[1].strip()
            if not key or not value:
                continue
            record_fields.append({key: value})
            has_data = True
        if has_data and record_fields:
            all_records.append(record_fields)
    if not all_records:
        return {"status": "no_results", "message": "No data available"}
    return all_records

def extract_telegram_data(raw_text):
    import re
    # Check for "Phone": "+91..." pattern (English format)
    phone_pattern_en = r'[Pp]hone["\']?\s*:\s*["\']?\+?(\d{10,15})["\']?'
    # Check for Russian format (Телефон)
    phone_pattern_ru = r'[Тт]елефон\s*[:\s]+(\+?\d{10,15})'
    
    match = re.search(phone_pattern_en, raw_text)
    if not match:
        match = re.search(phone_pattern_ru, raw_text)
    
    if match:
        phone_number = match.group(1).replace('+', '')
        if len(phone_number) == 12 and phone_number.startswith('91'):
            return '+' + phone_number
        elif len(phone_number) == 10:
            return '+91' + phone_number
        else:
            return '+' + phone_number
    return None

async def generate_report_from_bot(query, query_id, is_username_search=False, is_userid_search=False):
    global ACTIVE_USERNAME_PYROGRAM_INDEX
    try:
        if is_username_search or is_userid_search:
            if not username_search_clients or ACTIVE_USERNAME_PYROGRAM_INDEX >= len(username_search_clients):
                print("[ERROR] No username search clients available")
                return None
            client = username_search_clients[ACTIVE_USERNAME_PYROGRAM_INDEX]
            target_bot = "@Dfjyt_bot"
        else:
            if not number_search_client:
                print("[ERROR] Number search client not initialized")
                return None
            client = number_search_client
            target_bot = "@ZaverinBot"

        max_retries = 3
        for attempt in range(max_retries):
            try:
                if not client.is_connected:
                    print(f"[CONNECTION] Attempting to connect (attempt {attempt + 1}/{max_retries})...")
                    await client.start()
                    print("[CONNECTION] Successfully connected!")
                break
            except Exception as e:
                print(f"[CONNECTION ERROR] Attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    return None
                await asyncio.sleep(2)

        if is_username_search:
            formatted_query = f"t.me/{query[1:]}" if query.startswith('@') else f"t.me/{query}"
            print(f"[USERNAME SEARCH] Sending: {formatted_query} to {target_bot}")
        elif is_userid_search:
            # Add /tg prefix to userid
            formatted_query = f"/tg{query}"
            print(f"[USERID SEARCH] Sending: {formatted_query} to {target_bot}")
        else:
            formatted_query = query
            print(f"[NUMBER SEARCH] Sending: {formatted_query} to {target_bot}")

        await client.send_message(target_bot, formatted_query, parse_mode=None)
        response_text = ""
        start_time = time.time()
        max_wait = 15

        if is_username_search or is_userid_search:
            await asyncio.sleep(2)
            attempts = 0
            max_attempts = 6
            while attempts < max_attempts and (time.time() - start_time) < max_wait:
                async for msg in client.get_chat_history(target_bot, limit=10):
                    if msg.from_user and msg.from_user.username == target_bot.replace("@", ""):
                        if msg.date.timestamp() > start_time:
                            msg_text = msg.text or msg.caption or ""
                            if msg_text and ('+' in msg_text or 'ID:' in msg_text or 'id:' in msg_text.lower() or 'елефон' in msg_text or 'Phone' in msg_text):
                                response_text = msg_text
                                break
                if response_text:
                    break
                await asyncio.sleep(1.5)
                attempts += 1
        else:
            await asyncio.sleep(3)
            attempts = 0
            max_attempts = 8
            while attempts < max_attempts and (time.time() - start_time) < max_wait:
                async for message in client.get_chat_history(target_bot, limit=10):
                    if message.from_user and message.from_user.username == target_bot.replace("@", ""):
                        if message.date.timestamp() > (start_time - 2):
                            msg_text = message.text or message.caption or ""
                            if msg_text and len(msg_text) > 50:
                                response_text = msg_text
                                break
                if response_text:
                    break
                await asyncio.sleep(1.5)
                attempts += 1

        if not response_text:
            return None

        if is_username_search or is_userid_search:
            return extract_telegram_data(response_text)
        else:
            return filter_response_data(response_text)

    except FloodWait as e:
        wait_time = e.value if isinstance(e.value, (int, float)) else 60
        print(f"[FLOOD WAIT] Waiting {wait_time} seconds...")
        await asyncio.sleep(wait_time)
        return await generate_report_from_bot(query, query_id, is_username_search, is_userid_search)
    except Exception as e:
        print(f"[PYROGRAM ERROR] {e}")
        import traceback
        traceback.print_exc()
        return None

def generate_report(query, query_id, is_username_search=False, is_userid_search=False):
    try:
        loop = get_event_loop()
        # Use run_until_complete instead of run_coroutine_threadsafe to avoid loop issues
        result = loop.run_until_complete(
            asyncio.wait_for(
                generate_report_from_bot(query, query_id, is_username_search, is_userid_search),
                timeout=25
            )
        )
        return result
    except asyncio.TimeoutError:
        print(f"[ERROR] generate_report timeout after 25 seconds")
        return None
    except Exception as e:
        print(f"[ERROR] generate_report: {e}")
        import traceback
        traceback.print_exc()
        return None

async def start_pyrogram_client(client, client_name):
    try:
        await client.start()
        print(f"✅ {client_name} connected.")
        return True
    except Exception as e:
        print(f"❌ {client_name} connection error: {e}")
        return False

def ensure_pyrogram_session():
    try:
        time.sleep(2)
        
        if number_search_client:
            print("📞 Authenticating Number Search Pyrogram...")
            try:
                loop = get_event_loop()
                loop.run_until_complete(
                    asyncio.wait_for(
                        start_pyrogram_client(number_search_client, "Number Search"),
                        timeout=30
                    )
                )
            except Exception as e:
                print(f"❌ Number Search error: {e}")

        for idx, client in enumerate(username_search_clients):
            print(f"👤 Authenticating Username Search Pyrogram #{idx + 1}...")
            try:
                loop = get_event_loop()
                loop.run_until_complete(
                    asyncio.wait_for(
                        start_pyrogram_client(client, f"Username Search #{idx + 1}"),
                        timeout=30
                    )
                )
            except Exception as e:
                print(f"❌ Username Search #{idx + 1} error: {e}")

        return True
    except Exception as e:
        print(f"❌ Pyrogram connection error: {e}")
        return False

# ============================================
# TELEGRAM BOT - ADMIN COMMANDS (NO PROTECTION)
# ============================================

user_states = {}

def get_main_keyboard():
    keyboard = [
        [KeyboardButton("👥 Users"), KeyboardButton("💰 Deposits")],
        [KeyboardButton("➕ Add Balance"), KeyboardButton("➖ Deduct Balance")],
        [KeyboardButton("🎁 Promos"), KeyboardButton("➕ Create Promo")],
        [KeyboardButton("📜 User History"), KeyboardButton("📊 Status")],
        [KeyboardButton("🔄 Switch Account")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔐 *Admin Panel*\n\n"
        "Select an option below:",
        parse_mode='Markdown',
        reply_markup=get_main_keyboard()
    )

async def show_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with users_lock:
        users = load_users()
    
    if not users:
        msg = "📭 No users found."
    else:
        msg = "👥 *All Users:*\n\n"
        for name, data in list(users.items())[:50]:
            hash_code = data.get('hash_code', 'N/A')
            balance = data.get('balance', 0)
            msg += f"• *{name}*\n  Hash: `{hash_code}`\n  Balance: ₹{balance}\n\n"
        
        if len(users) > 50:
            msg += f"\n_...and {len(users) - 50} more users_"
    
    await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=get_main_keyboard())

async def cmd_addbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ Usage: /addbalance <hash_code> <amount>")
        return
    
    hash_code = context.args[0].upper()
    try:
        amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid amount!")
        return
    
    with users_lock:
        users = load_users()
        found_user = None
        for name, user_data in users.items():
            if user_data.get('hash_code') == hash_code:
                found_user = name
                break
        
        if not found_user:
            await update.message.reply_text(f"❌ User with hash `{hash_code}` not found!")
            return
        
        users[found_user]['balance'] = users[found_user].get('balance', 0) + amount
        save_users(users)
        new_balance = users[found_user]['balance']
    
    await update.message.reply_text(
        f"✅ Added ₹{amount} to *{found_user}* (`{hash_code}`)\n"
        f"💰 New Balance: ₹{new_balance}",
        parse_mode='Markdown'
    )

async def cmd_deductbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ Usage: /deductbalance <hash_code> <amount>")
        return
    
    hash_code = context.args[0].upper()
    try:
        amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid amount!")
        return
    
    with users_lock:
        users = load_users()
        found_user = None
        for name, user_data in users.items():
            if user_data.get('hash_code') == hash_code:
                found_user = name
                break
        
        if not found_user:
            await update.message.reply_text(f"❌ User with hash `{hash_code}` not found!")
            return
        
        users[found_user]['balance'] = users[found_user].get('balance', 0) - amount
        save_users(users)
        new_balance = users[found_user]['balance']
    
    await update.message.reply_text(
        f"✅ Deducted ₹{amount} from *{found_user}* (`{hash_code}`)\n"
        f"💰 New Balance: ₹{new_balance}",
        parse_mode='Markdown'
    )

async def show_deposits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    deposits = load_json(DEPOSIT_REQUESTS_FILE, [])
    pending = [d for d in deposits if d.get('status') == 'pending']
    
    if not pending:
        msg = "📭 No pending deposits."
    else:
        msg = "💰 *Pending Deposits:*\n\n"
        for dep in pending[-10:]:
            name = dep.get('name', dep.get('user_name', 'Unknown'))
            amount = dep.get('amount', 0)
            utr = dep.get('utr', 'N/A')
            req_id = dep.get('request_id', dep.get('id', 'N/A'))
            timestamp = time.strftime('%Y-%m-%d %H:%M', time.localtime(dep.get('timestamp', 0)))
            
            msg += f"🆔 ID: `{req_id}`\n"
            msg += f"👤 User: *{name}*\n"
            msg += f"💵 Amount: ₹{amount}\n"
            msg += f"🔢 UTR: `{utr}`\n"
            msg += f"📅 Time: {timestamp}\n\n"
        
        msg += "\n💡 Use /approve <ID> or /reject <ID> to process deposits"
    
    await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=get_main_keyboard())

async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("❌ Usage: /approve <request_id>")
        return
    
    request_id = context.args[0]
    deposits = load_json(DEPOSIT_REQUESTS_FILE, [])
    
    deposit_found = None
    for dep in deposits:
        dep_id = str(dep.get('request_id') or dep.get('id'))
        if dep_id == str(request_id) and dep['status'] == 'pending':
            deposit_found = dep
            break
    
    if not deposit_found:
        await update.message.reply_text("❌ Deposit not found or already processed!")
        return
    
    name = deposit_found.get('name') or deposit_found.get('user_name')
    amount = deposit_found['amount']
    
    with users_lock:
        users = load_users()
        if name in users:
            users[name]['balance'] = users[name].get('balance', 0) + amount
            save_users(users)
            deposit_found['status'] = 'approved'
            save_json(DEPOSIT_REQUESTS_FILE, deposits)
            
            await update.message.reply_text(
                f"✅ Deposit Approved!\n"
                f"👤 User: *{name}*\n"
                f"💵 Amount: ₹{amount}",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(f"❌ User '{name}' not found!")

async def cmd_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("❌ Usage: /reject <request_id>")
        return
    
    request_id = context.args[0]
    deposits = load_json(DEPOSIT_REQUESTS_FILE, [])
    
    deposit_found = None
    for dep in deposits:
        dep_id = str(dep.get('request_id') or dep.get('id'))
        if dep_id == str(request_id) and dep['status'] == 'pending':
            deposit_found = dep
            break
    
    if not deposit_found:
        await update.message.reply_text("❌ Deposit not found or already processed!")
        return
    
    deposit_found['status'] = 'rejected'
    save_json(DEPOSIT_REQUESTS_FILE, deposits)
    
    await update.message.reply_text(f"✅ Deposit `{request_id}` rejected!", parse_mode='Markdown')


async def show_promos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    promo_codes = load_json(PROMO_CODES_FILE, {})
    
    if not promo_codes:
        msg = "📭 No promo codes found."
    else:
        msg = "🎁 *Promo Codes:*\n\n"
        for code, data in promo_codes.items():
            amount = data.get('amount', 0)
            max_uses = data.get('max_uses', 0)
            used = data.get('used_count', 0)
            msg += f"• `{code}`: ₹{amount} (Used: {used}/{max_uses})\n"
        
        msg += "\n💡 Use /deletepromo <CODE> to delete a promo code"
    
    await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=get_main_keyboard())


async def cmd_createpromo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("❌ Usage: /createpromo <code> <amount> <max_uses>")
        return
    
    code = context.args[0].upper()
    try:
        amount = float(context.args[1])
        max_uses = int(context.args[2])
        if amount <= 0:
            await update.message.reply_text("❌ Amount must be greater than 0!")
            return
        if max_uses <= 0:
            await update.message.reply_text("❌ Max uses must be greater than 0!")
            return
    except ValueError:
        await update.message.reply_text("❌ Invalid amount or max_uses!")
        return
    
    promo_codes = load_json(PROMO_CODES_FILE, {})
    
    if code in promo_codes:
        await update.message.reply_text(f"❌ Promo code `{code}` already exists!")
        return
    
    promo_codes[code] = {
        'amount': amount,
        'max_uses': max_uses,
        'used_count': 0,
        'used_by': []
    }
    save_json(PROMO_CODES_FILE, promo_codes)
    
    await update.message.reply_text(
        f"✅ Promo code created!\n"
        f"📝 Code: `{code}`\n"
        f"💵 Amount: ₹{amount}\n"
        f"🔢 Max Uses: {max_uses}",
        parse_mode='Markdown'
    )


async def cmd_deletepromo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("❌ Usage: /deletepromo <code>")
        return
    
    code = context.args[0].upper()
    promo_codes = load_json(PROMO_CODES_FILE, {})
    
    if code not in promo_codes:
        await update.message.reply_text(f"❌ Promo code `{code}` not found!")
        return
    
    del promo_codes[code]
    save_json(PROMO_CODES_FILE, promo_codes)
    
    await update.message.reply_text(f"✅ Promo code `{code}` deleted!", parse_mode='Markdown')


async def cmd_userhistory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("❌ Usage: /userhistory <hash_code>")
        return
    
    hash_code = context.args[0].upper()
    
    with users_lock:
        users = load_users()
        found_user = None
        for name, user_data in users.items():
            if user_data.get('hash_code') == hash_code:
                found_user = name
                break
        
        if not found_user:
            await update.message.reply_text(f"❌ User with hash `{hash_code}` not found!")
            return
        
        history = users[found_user].get('search_history', [])
    
    if not history:
        await update.message.reply_text(f"📭 No search history for *{found_user}*", parse_mode='Markdown')
        return
    
    msg = f"📜 *Search History: {found_user}*\n\n"
    for entry in history[-20:]:
        search_type = entry.get('search_type', 'unknown')
        query = entry.get('query', 'N/A')
        has_result = "✅" if entry.get('has_result') else "❌"
        timestamp = time.strftime('%Y-%m-%d %H:%M', time.localtime(entry.get('timestamp', 0)))
        msg += f"• {search_type}: `{query}` {has_result}\n  📅 {timestamp}\n\n"
    
    await update.message.reply_text(msg, parse_mode='Markdown')


async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_users()
    deposits = load_json(DEPOSIT_REQUESTS_FILE, [])
    pending_deposits = len([d for d in deposits if d.get('status') == 'pending'])
    
    number_status = "🟢" if number_search_client and number_search_client.is_connected else "🔴"
    username_status = []
    for idx, client in enumerate(username_search_clients):
        status = "🟢" if client.is_connected else "🔴"
        active = " (ACTIVE)" if idx == ACTIVE_USERNAME_PYROGRAM_INDEX else ""
        username_status.append(f"  #{idx + 1}: {status}{active}")
    
    msg = (
        "📊 *System Status*\n\n"
        f"👥 Total Users: {len(users)}\n"
        f"💰 Pending Deposits: {pending_deposits}\n\n"
        f"📞 Number Search: {number_status}\n"
        f"👤 Username Search:\n" + "\n".join(username_status)
    )
    
    await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=get_main_keyboard())


async def handle_button_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ACTIVE_USERNAME_PYROGRAM_INDEX
    text = update.message.text
    user_id = update.effective_user.id
    
    # Check if user is in a state
    if user_id in user_states:
        await handle_message(update, context)
        return
    
    if text == "👥 Users":
        await show_users(update, context)
    
    elif text == "💰 Deposits":
        await show_deposits(update, context)
    
    elif text == "🎁 Promos":
        await show_promos(update, context)
    
    elif text == "📊 Status":
        await show_status(update, context)
    
    elif text == "➕ Add Balance":
        user_states[user_id] = "awaiting_addbalance"
        await update.message.reply_text(
            "➕ *Add Balance*\n\nSend message in format:\n`HASHCODE AMOUNT`\n\nExample: `ABC123 500`",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard()
        )
    
    elif text == "➖ Deduct Balance":
        user_states[user_id] = "awaiting_deductbalance"
        await update.message.reply_text(
            "➖ *Deduct Balance*\n\nSend message in format:\n`HASHCODE AMOUNT`\n\nExample: `ABC123 500`",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard()
        )
    
    elif text == "➕ Create Promo":
        user_states[user_id] = "awaiting_createpromo"
        await update.message.reply_text(
            "🎁 *Create Promo Code*\n\nSend message in format:\n`CODE AMOUNT MAX_USES`\n\nExample: `WELCOME50 50 100`",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard()
        )
    
    elif text == "📜 User History":
        user_states[user_id] = "awaiting_userhistory"
        await update.message.reply_text(
            "📜 *User History*\n\nSend the user's hash code:\n\nExample: `ABC123`",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard()
        )
    
    elif text == "🔄 Switch Account":
        msg = "🔄 *Switch Pyrogram Account*\n\n"
        for idx, client in enumerate(username_search_clients):
            status = "🟢" if client.is_connected else "🔴"
            active = " ✓ ACTIVE" if idx == ACTIVE_USERNAME_PYROGRAM_INDEX else ""
            msg += f"{status} Account #{idx + 1}{active}\n"
        msg += "\n💡 Send account number to switch (e.g., send `1` or `2`)"
        
        user_states[user_id] = "awaiting_switch"
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    else:
        await handle_message(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ACTIVE_USERNAME_PYROGRAM_INDEX
    user_id = update.effective_user.id
    text = update.message.text.strip()
    state = user_states.get(user_id)
    
    if not state:
        return
    
    if state == "awaiting_addbalance":
        parts = text.split()
        if len(parts) < 2:
            await update.message.reply_text("❌ Format: HASHCODE AMOUNT", reply_markup=get_main_keyboard())
            return
        
        hash_code = parts[0].upper()
        try:
            amount = float(parts[1])
        except ValueError:
            await update.message.reply_text("❌ Invalid amount!", reply_markup=get_main_keyboard())
            return
        
        with users_lock:
            users = load_users()
            found_user = None
            for name, user_data in users.items():
                if user_data.get('hash_code') == hash_code:
                    found_user = name
                    break
            
            if not found_user:
                await update.message.reply_text(f"❌ User with hash `{hash_code}` not found!", parse_mode='Markdown', reply_markup=get_main_keyboard())
                user_states.pop(user_id, None)
                return
            
            users[found_user]['balance'] = users[found_user].get('balance', 0) + amount
            save_users(users)
            new_balance = users[found_user]['balance']
        
        await update.message.reply_text(
            f"✅ Added ₹{amount} to *{found_user}*\n💰 New Balance: ₹{new_balance}",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard()
        )
        user_states.pop(user_id, None)
    
    elif state == "awaiting_deductbalance":
        parts = text.split()
        if len(parts) < 2:
            await update.message.reply_text("❌ Format: HASHCODE AMOUNT", reply_markup=get_main_keyboard())
            return
        
        hash_code = parts[0].upper()
        try:
            amount = float(parts[1])
        except ValueError:
            await update.message.reply_text("❌ Invalid amount!", reply_markup=get_main_keyboard())
            return
        
        with users_lock:
            users = load_users()
            found_user = None
            for name, user_data in users.items():
                if user_data.get('hash_code') == hash_code:
                    found_user = name
                    break
            
            if not found_user:
                await update.message.reply_text(f"❌ User with hash `{hash_code}` not found!", parse_mode='Markdown', reply_markup=get_main_keyboard())
                user_states.pop(user_id, None)
                return
            
            users[found_user]['balance'] = users[found_user].get('balance', 0) - amount
            save_users(users)
            new_balance = users[found_user]['balance']
        
        await update.message.reply_text(
            f"✅ Deducted ₹{amount} from *{found_user}*\n💰 New Balance: ₹{new_balance}",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard()
        )
        user_states.pop(user_id, None)
    
    elif state == "awaiting_createpromo":
        parts = text.split()
        if len(parts) < 3:
            await update.message.reply_text("❌ Format: CODE AMOUNT MAX_USES", reply_markup=get_main_keyboard())
            return
        
        code = parts[0].upper()
        try:
            amount = float(parts[1])
            max_uses = int(parts[2])
            if amount <= 0 or max_uses <= 0:
                await update.message.reply_text("❌ Amount and max uses must be > 0!", reply_markup=get_main_keyboard())
                return
        except ValueError:
            await update.message.reply_text("❌ Invalid amount or max uses!", reply_markup=get_main_keyboard())
            return
        
        promo_codes = load_json(PROMO_CODES_FILE, {})
        
        if code in promo_codes:
            await update.message.reply_text(f"❌ Promo code `{code}` already exists!", parse_mode='Markdown', reply_markup=get_main_keyboard())
            return
        
        promo_codes[code] = {
            'amount': amount,
            'max_uses': max_uses,
            'used_count': 0,
            'used_by': []
        }
        save_json(PROMO_CODES_FILE, promo_codes)
        
        await update.message.reply_text(
            f"✅ Promo Created!\n📝 Code: `{code}`\n💵 Amount: ₹{amount}\n🔢 Max Uses: {max_uses}",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard()
        )
        user_states.pop(user_id, None)
    
    elif state == "awaiting_userhistory":
        hash_code = text.upper()
        
        with users_lock:
            users = load_users()
            found_user = None
            for name, user_data in users.items():
                if user_data.get('hash_code') == hash_code:
                    found_user = name
                    break
            
            if not found_user:
                await update.message.reply_text(f"❌ User with hash `{hash_code}` not found!", parse_mode='Markdown', reply_markup=get_main_keyboard())
                user_states.pop(user_id, None)
                return
            
            history = users[found_user].get('search_history', [])
        
        if not history:
            await update.message.reply_text(f"📭 No search history for *{found_user}*", parse_mode='Markdown', reply_markup=get_main_keyboard())
        else:
            msg = f"📜 *Search History: {found_user}*\n\n"
            for entry in history[-20:]:
                search_type = entry.get('search_type', 'unknown')
                query_text = entry.get('query', 'N/A')
                has_result = "✅" if entry.get('has_result') else "❌"
                timestamp = time.strftime('%Y-%m-%d %H:%M', time.localtime(entry.get('timestamp', 0)))
                msg += f"• {search_type}: `{query_text}` {has_result}\n  📅 {timestamp}\n\n"
            
            await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=get_main_keyboard())
        
        user_states.pop(user_id, None)
    
    elif state == "awaiting_switch":
        try:
            index = int(text) - 1
            if 0 <= index < len(username_search_clients):
                ACTIVE_USERNAME_PYROGRAM_INDEX = index
                await update.message.reply_text(
                    f"✅ Switched to Account #{index + 1}",
                    parse_mode='Markdown',
                    reply_markup=get_main_keyboard()
                )
            else:
                await update.message.reply_text("❌ Invalid account number!", reply_markup=get_main_keyboard())
        except ValueError:
            await update.message.reply_text("❌ Please send a valid account number!", reply_markup=get_main_keyboard())
        
        user_states.pop(user_id, None)

# ============================================
# FLASK API - USER ENDPOINTS
# ============================================

from flask import send_from_directory

@app.route('/')
def serve_index():
    try:
        with open('forentend/index.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return jsonify({'status': 'Backend API is running!'}), 200

@app.route('/forentend/<path:filename>')
def serve_static(filename):
    return send_from_directory('forentend', filename)

@app.route('/api/status')
def health_check():
    return jsonify({'status': 'Backend API is running!'}), 200

@app.route('/signup', methods=['POST'])
def signup():
    try:
        data = request.get_json()
        name = data.get('name', '').strip()

        if not name:
            return jsonify({'success': False, 'message': 'Name is required'}), 400

        with users_lock:
            init_files()
            users = load_users()
            if name in users:
                return jsonify({'success': False, 'message': 'Name already taken'}), 409

            hash_code = generate_hash_code()
            while hash_code in [u.get('hash_code') for u in users.values()]:
                hash_code = generate_hash_code()

            users[name] = {
                'hash_code': hash_code,
                'created_at': time.time(),
                'balance': 0
            }
            save_users(users)

        return jsonify({'success': True, 'message': f'Account created! Your Hash Code: {hash_code}', 'hash_code': hash_code}), 201
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    hash_code = data.get('hash_code', '').strip().upper()

    if not hash_code:
        return jsonify({'success': False, 'message': 'Hash Code is required'}), 400

    with users_lock:
        users = load_users()
        found_user = None
        for name, user_data in users.items():
            if user_data.get('hash_code') == hash_code:
                found_user = name
                break
        
        if not found_user:
            return jsonify({'success': False, 'message': 'Invalid hash code'}), 401

    session['user_name'] = found_user
    return jsonify({'success': True, 'message': 'Login successful!', 'user_name': found_user}), 200

@app.route('/get_balance', methods=['GET', 'POST'])
def get_balance():
    if request.method == 'GET':
        name = request.args.get('user_name')
    else:
        data = request.get_json() or {}
        name = data.get('user_name')
    
    if not name:
        return jsonify({'success': False, 'message': 'User name required'}), 400
    
    with users_lock:
        users = load_users()
        user_data = users.get(name, {})
        balance = user_data.get('balance', 0)

    return jsonify({'success': True, 'balance': balance}), 200

@app.route('/search/number', methods=['POST'])
def search_number():
    try:
        data = request.get_json()
        number = data.get('number')

        if not number:
            return jsonify({'success': False, 'message': 'Phone number is required'}), 400

        if not (number.startswith('+91') and len(number) == 13 and number[1:].isdigit()):
            if len(number) == 10 and number.isdigit():
                number = '+91' + number
            else:
                return jsonify({'success': False, 'message': 'Invalid phone number format. Use +91XXXXXXXXXX'}), 400

        name = data.get('user_name')
        if not name:
            return jsonify({'success': False, 'message': 'User name required'}), 400

        init_files()
        NUMBER_SEARCH_PRICE = 4
        
        with users_lock:
            users = load_users()
            user_data = users.get(name, {})
            current_balance = user_data.get('balance', 0)
            
            if current_balance < NUMBER_SEARCH_PRICE:
                return jsonify({'success': False, 'message': f'Insufficient balance. Need ₹{NUMBER_SEARCH_PRICE}, have ₹{current_balance}'}), 402

        # Check if already searched with no result
        if is_already_searched_no_data(number, "number"):
            return jsonify({'success': False, 'message': 'This number has been searched before and no result was found'}), 404

        query_id = randint(0, 9999999)
        result = generate_report(number, query_id)

        if result and not (isinstance(result, dict) and result.get('status') == 'no_results'):
            # Complete data found - deduct balance
            with users_lock:
                users = load_users()
                if name in users:
                    users[name]['balance'] = users[name].get('balance', 0) - NUMBER_SEARCH_PRICE
                    save_users(users)
            add_search_to_user_history(name, "number", number, True)
            add_to_searched_no_data(number, "number", has_result=True)
            return jsonify({'success': True, 'data': result}), 200
        else:
            # Incomplete data or no result - don't deduct balance, block future searches
            add_search_to_user_history(name, "number", number, False)
            add_to_searched_no_data(number, "number", has_result=False)
            return jsonify({'success': False, 'message': 'No result found for this number'}), 404

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/search/username', methods=['POST'])
def search_username():
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        name = data.get('user_name')

        if not username:
            return jsonify({'success': False, 'message': 'Username is required'}), 400
        if not name:
            return jsonify({'success': False, 'message': 'User name required'}), 400

        if not username.startswith('@'):
            username = '@' + username

        init_files()
        USERNAME_SEARCH_PRICE = 21
        
        with users_lock:
            users = load_users()
            user_data = users.get(name, {})
            current_balance = user_data.get('balance', 0)
            
            if current_balance < USERNAME_SEARCH_PRICE:
                return jsonify({'success': False, 'message': f'Insufficient balance. Need ₹{USERNAME_SEARCH_PRICE}, have ₹{current_balance}'}), 402

        # Check if already searched with no result
        if is_already_searched_no_data(username, "username"):
            return jsonify({'success': False, 'message': 'This username has been searched before and no result was found'}), 404

        query_id = randint(0, 9999999)
        phone_number = generate_report(username, query_id, is_username_search=True)

        if phone_number:
            # Complete data found - deduct balance
            with users_lock:
                users = load_users()
                if name in users:
                    users[name]['balance'] = users[name].get('balance', 0) - USERNAME_SEARCH_PRICE
                    save_users(users)
            add_search_to_user_history(name, "username", username, True)
            add_to_searched_no_data(username, "username", has_result=True)
            return jsonify({
                'success': True,
                'phone_number': phone_number,
                'profile': {'username': username.lstrip('@')}
            }), 200
        else:
            # Incomplete data or no result - don't deduct balance, block future searches
            add_search_to_user_history(name, "username", username, False)
            add_to_searched_no_data(username, "username", has_result=False)
            return jsonify({'success': False, 'message': 'No phone number found for this username'}), 404

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/search/userid', methods=['POST'])
def search_userid():
    try:
        data = request.get_json()
        user_id = data.get('user_id', '').strip()
        name = data.get('user_name')

        if not user_id:
            return jsonify({'success': False, 'message': 'User ID is required'}), 400
        if not name:
            return jsonify({'success': False, 'message': 'User name required'}), 400

        init_files()
        USERID_SEARCH_PRICE = 21
        
        with users_lock:
            users = load_users()
            user_data = users.get(name, {})
            current_balance = user_data.get('balance', 0)
            
            if current_balance < USERID_SEARCH_PRICE:
                return jsonify({'success': False, 'message': f'Insufficient balance. Need ₹{USERID_SEARCH_PRICE}, have ₹{current_balance}'}), 402

        # Check if already searched with no result
        if is_already_searched_no_data(user_id, "userid"):
            return jsonify({'success': False, 'message': 'This user ID has been searched before and no result was found'}), 404

        query_id = randint(0, 9999999)
        phone_number = generate_report(user_id, query_id, is_userid_search=True)

        if phone_number:
            # Complete data found - deduct balance
            with users_lock:
                users = load_users()
                if name in users:
                    users[name]['balance'] = users[name].get('balance', 0) - USERID_SEARCH_PRICE
                    save_users(users)
            add_search_to_user_history(name, "userid", user_id, True)
            add_to_searched_no_data(user_id, "userid", has_result=True)
            return jsonify({'success': True, 'phone_number': phone_number}), 200
        else:
            # Incomplete data or no result - don't deduct balance, block future searches
            add_search_to_user_history(name, "userid", user_id, False)
            add_to_searched_no_data(user_id, "userid", has_result=False)
            return jsonify({'success': False, 'message': 'No phone number found for this user ID'}), 404

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/get_my_history', methods=['GET', 'POST'])
def get_my_history():
    if request.method == 'GET':
        user_name = request.args.get('user_name')
    else:
        data = request.get_json() or {}
        user_name = data.get('user_name')
    
    if not user_name:
        return jsonify({'success': False, 'message': 'User name required'}), 400

    with users_lock:
        users = load_users()
        user_data = users.get(user_name, {})
        history = user_data.get('search_history', [])
        history = history[-50:]
        history.reverse()

    return jsonify({'success': True, 'history': history}), 200

@app.route('/apply_promo_code', methods=['POST'])
def apply_promo_code():
    data = request.get_json()
    promo_code = data.get('promo_code', '').strip().upper()
    user_name = data.get('user_name')

    if not user_name:
        return jsonify({'success': False, 'message': 'User name required'}), 400
    if not promo_code:
        return jsonify({'success': False, 'message': 'Promo code required'}), 400

    promo_codes = load_json(PROMO_CODES_FILE, {})

    if promo_code not in promo_codes:
        return jsonify({'success': False, 'message': 'Invalid promo code'}), 404

    promo_data = promo_codes[promo_code]

    if user_name in promo_data.get('used_by', []):
        return jsonify({'success': False, 'message': 'You have already used this promo code'}), 400

    if promo_data.get('used_count', 0) >= promo_data.get('max_uses', 0):
        return jsonify({'success': False, 'message': 'This promo code has reached its maximum usage limit'}), 400

    amount = promo_data.get('amount', 0)
    
    with users_lock:
        users = load_users()
        if user_name not in users:
            return jsonify({'success': False, 'message': 'User not found'}), 404

        users[user_name]['balance'] = users[user_name].get('balance', 0) + amount
        save_users(users)
        new_balance = users[user_name]['balance']

    if 'used_by' not in promo_data:
        promo_data['used_by'] = []
    promo_data['used_by'].append(user_name)
    promo_data['used_count'] = promo_data.get('used_count', 0) + 1
    save_json(PROMO_CODES_FILE, promo_codes)

    return jsonify({
        'success': True, 
        'message': f'Promo code applied! ₹{amount} added to your balance. New balance: ₹{new_balance}'
    }), 200

@app.route('/submit_deposit', methods=['POST'])
def submit_deposit():
    data = request.get_json()
    amount = data.get('amount')
    utr = data.get('utr')
    name = data.get('name') or data.get('user_name')

    if not name:
        return jsonify({'success': False, 'message': 'User name required'}), 400
    if not amount or float(amount) < 25:
        return jsonify({'success': False, 'message': 'Minimum amount is ₹25'}), 400
    if not utr or len(utr) != 12 or not utr.isdigit():
        return jsonify({'success': False, 'message': 'Invalid UTR (must be 12 digits)'}), 400

    with users_lock:
        users = load_users()
        if name not in users:
            return jsonify({'success': False, 'message': 'User not found'}), 404

    deposit_requests = load_json(DEPOSIT_REQUESTS_FILE, [])

    request_id = randint(100000, 999999)
    new_request = {
        'request_id': request_id,
        'name': name,
        'amount': float(amount),
        'utr': utr,
        'timestamp': time.time(),
        'status': 'pending'
    }
    deposit_requests.append(new_request)
    save_json(DEPOSIT_REQUESTS_FILE, deposit_requests)

    return jsonify({'success': True, 'message': 'Deposit request submitted'}), 200

# ============================================
# MAIN - RUN BOTH BOT AND FLASK
# ============================================

import os
import signal
import sys

bot_running = False
telegram_app = None

def run_telegram_bot_blocking():
    """Run Telegram bot - blocking call"""
    global telegram_app, bot_running
    
    try:
        print("\n" + "="*60)
        print("🤖 STARTING TELEGRAM ADMIN BOT...")
        print("="*60)
        
        telegram_app = Application.builder().token(BOT_TOKEN).build()
        telegram_app.add_handler(CommandHandler("start", cmd_start))
        telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button_text))
        
        print("📋 Telegram Bot Commands:")
        print("/start - Open Admin Panel with Buttons")
        print(f"Admin ID: {ADMIN_ID}")
        print("="*60 + "\n")
        
        bot_running = True
        print("✅ Bot polling started!")
        telegram_app.run_polling(allowed_updates=Update.ALL_TYPES, stop_signals=(signal.SIGINT, signal.SIGTERM))
        
    except Exception as e:
        print(f"❌ Bot Error: {e}")
        import traceback
        traceback.print_exc()

def run_telegram_bot_thread():
    """Run bot in separate thread"""
    bot_thread = threading.Thread(target=run_telegram_bot_blocking, daemon=False)
    bot_thread.start()
    return bot_thread

def run_flask():
    """Run Flask on port 5000"""
    port = int(os.environ.get("PORT", 5000))
    print(f"🌐 Starting Flask API on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)

def initialize_app():
    """Initialize when app is imported (for gunicorn) - FLASK ONLY on production"""
    import sys
    is_gunicorn = "gunicorn" in sys.argv[0] if sys.argv else False
    
    print("\n" + "="*60)
    print("🚀 Search Dashboard - Backend Starting...")
    print(f"📍 Mode: {'PRODUCTION (gunicorn)' if is_gunicorn else 'DEVELOPMENT'}")
    print("="*60 + "\n")
    
    init_files()
    print("✅ Files initialized")
    
    # Only initialize Pyrogram on development (not gunicorn)
    if not is_gunicorn:
        try:
            init_pyrogram_clients()
            if number_search_client or username_search_clients:
                if not ensure_pyrogram_session():
                    print("⚠️ Warning: Some Pyrogram sessions may not be connected")
        except Exception as e:
            print(f"⚠️ Pyrogram init skipped: {e}")
    else:
        print("⏭️  Skipping Pyrogram init on production (gunicorn)")
        print("📌 Run bot separately on local machine")

initialize_app()

def main():
    """Main entry point for direct execution"""
    print("\n" + "="*60)
    print("🚀 Search Dashboard - Backend Starting...")
    print("="*60 + "\n")
    
    init_files()
    print("✅ Files initialized")
    
    init_pyrogram_clients()
    
    if number_search_client or username_search_clients:
        if not ensure_pyrogram_session():
            print("⚠️ Warning: Some Pyrogram sessions may not be connected")
    
    if not BOT_TOKEN:
        print("\n⚠️ BOT_TOKEN not set! Starting Flask API only...")
        port = int(os.environ.get("PORT", 5000))
        app.run(host='0.0.0.0', port=port, debug=False)
        return
    
    print("\n🤖 Starting Telegram Bot + Flask API...\n")
    
    # Start bot in separate thread
    bot_thread = run_telegram_bot_thread()
    
    # Give bot time to initialize
    import time
    time.sleep(2)
    
    # Run Flask on main thread
    run_flask()

if __name__ == "__main__":
    main()
