from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
import threading
from random import randint, choice
import string
import time
import asyncio
from pyrogram.client import Client
from pyrogram.errors import FloodWait

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

# Enable CORS for Netlify frontend with credentials
CORS(app, 
     resources={r"/*": {"origins": ["https://*.netlify.app", "https://back-ho33.onrender.com", "http://localhost:*"]}},
     supports_credentials=True,
     allow_headers=['Content-Type', 'Authorization'],
     methods=['GET', 'POST', 'OPTIONS'])

# Pyrogram for Number Search
NUMBER_SEARCH_PYROGRAM = {
    "api_id": 39782165,
    "api_hash": "e0e665ae0de9e60ab4b1d77fcc71820c",
    "phone": "+919661948912",
    "session_name": "number_search_account"
}

# Pyrogram for Username Search (Phone extraction from @Dfjyt_bot)
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
    },
    {
        "api_id": 0,
        "api_hash": "",
        "phone": "",
        "target_bot": "@Dfjyt_bot",
        "session_name": "username_search_account_3"
    },
    {
        "api_id": 0,
        "api_hash": "",
        "phone": "",
        "target_bot": "@Dfjyt_bot",
        "session_name": "username_search_account_4"
    },
    {
        "api_id": 0,
        "api_hash": "",
        "phone": "",
        "target_bot": "@Dfjyt_bot",
        "session_name": "username_search_account_5"
    },
    {
        "api_id": 0,
        "api_hash": "",
        "phone": "",
        "target_bot": "@Dfjyt_bot",
        "session_name": "username_search_account_6"
    },
    {
        "api_id": 0,
        "api_hash": "",
        "phone": "",
        "target_bot": "@Dfjyt_bot",
        "session_name": "username_search_account_7"
    },
    {
        "api_id": 0,
        "api_hash": "",
        "phone": "",
        "target_bot": "@Dfjyt_bot",
        "session_name": "username_search_account_8"
    },
    {
        "api_id": 0,
        "api_hash": "",
        "phone": "",
        "target_bot": "@Dfjyt_bot",
        "session_name": "username_search_account_9"
    },
]

ACTIVE_USERNAME_PYROGRAM_INDEX = 0

# File paths
USERS_FILE = "web_users.json"
SEARCHED_NO_DATA_FILE = "searched_no_data.json"
DEPOSIT_REQUESTS_FILE = "deposit_requests.json"

# Thread locks
users_lock = threading.RLock()
searched_no_data_lock = threading.RLock()

# Create Pyrogram clients
number_search_client = None
username_search_clients = []

if NUMBER_SEARCH_PYROGRAM["api_id"] != 0:
    number_search_client = Client(
        NUMBER_SEARCH_PYROGRAM["session_name"],
        api_id=NUMBER_SEARCH_PYROGRAM["api_id"],
        api_hash=NUMBER_SEARCH_PYROGRAM["api_hash"],
        phone_number=NUMBER_SEARCH_PYROGRAM["phone"],
        workdir=".",
        no_updates=True
    )

def init_username_search_clients():
    global username_search_clients
    username_search_clients = []
    for idx, config in enumerate(USERNAME_SEARCH_PYROGRAMS):
        session_file = f"{config['session_name']}.session"
        # Check if session file exists OR if credentials are provided
        if os.path.exists(session_file) or (config["api_id"] != 0 and config["api_hash"]):
            try:
                # Use provided credentials or defaults for existing sessions
                api_id = config["api_id"] if config["api_id"] != 0 else 1  # Dummy value for existing sessions
                api_hash = config["api_hash"] if config["api_hash"] else "dummy"  # Dummy value for existing sessions

                client = Client(
                    config["session_name"],
                    api_id=api_id,
                    api_hash=api_hash,
                    phone_number=config["phone"] if config["phone"] else None,
                    workdir=".",
                    no_updates=True
                )
                username_search_clients.append(client)
                print(f"✅ Loaded session for {config['session_name']}")
            except Exception as e:
                print(f"❌ Error initializing username search client {idx + 1} ({config['session_name']}): {e}")
        else:
            print(f"⚠️ Skipping {config['session_name']} - No session file and no credentials")

def init_files():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w') as f:
            json.dump({}, f)
    if not os.path.exists(SEARCHED_NO_DATA_FILE):
        with open(SEARCHED_NO_DATA_FILE, 'w') as f:
            json.dump({}, f)
    if not os.path.exists(DEPOSIT_REQUESTS_FILE):
        with open(DEPOSIT_REQUESTS_FILE, 'w') as f:
            json.dump([], f)
    init_username_search_clients()

def load_users():
    with open(USERS_FILE, 'r') as f:
        return json.load(f)

def save_users(data):
    with open(USERS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_searched_no_data():
    with open(SEARCHED_NO_DATA_FILE, 'r') as f:
        return json.load(f)

def add_to_searched_no_data(query, search_type, has_result=False):
    with searched_no_data_lock:
        data = load_searched_no_data()
        key = f"{search_type}_{query.lower()}"
        data[key] = {
            "query": query,
            "search_type": search_type,
            "timestamp": time.time(),
            "has_result": has_result
        }
        with open(SEARCHED_NO_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)

def is_already_searched_no_data(query, search_type):
    with searched_no_data_lock:
        data = load_searched_no_data()
        normalized_query = query.lstrip('@').lower() if search_type == "username" else query.lower()
        key = f"{search_type}_{normalized_query}"
        return key in data

_pyrogram_loop = None
_pyrogram_thread = None

def get_pyrogram_loop():
    global _pyrogram_loop, _pyrogram_thread
    if _pyrogram_loop is None:
        def start_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()
        _pyrogram_loop = asyncio.new_event_loop()
        _pyrogram_thread = threading.Thread(target=start_loop, args=(_pyrogram_loop,), daemon=True)
        _pyrogram_thread.start()
    return _pyrogram_loop

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
    phone_pattern = r'[Тт]елефон\s*[:\s]+(\+?\d{10,15})'
    match = re.search(phone_pattern, raw_text)
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
                return None
            client = username_search_clients[ACTIVE_USERNAME_PYROGRAM_INDEX]
            target_bot = "@Dfjyt_bot"
        else:
            if not number_search_client:
                return None
            client = number_search_client
            target_bot = "@ZaverinBot"

        if not client.is_connected:
            await client.start()

        if is_username_search:
            if query.startswith('@'):
                formatted_query = f"t.me/{query[1:]}"
            else:
                formatted_query = f"t.me/{query}"
            print(f"[USERNAME SEARCH] Sending formatted query: {formatted_query} to {target_bot}")
        elif is_userid_search:
            formatted_query = f"/tg{query}"
            print(f"[USERID SEARCH] Sending formatted query: {formatted_query} to {target_bot}")
        else:
            formatted_query = query
            print(f"[NUMBER SEARCH] Sending query: {formatted_query} to {target_bot}")

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
                            print(f"[BOT RESPONSE] Raw message from {target_bot}: {msg_text[:500]}...")
                            if msg_text and ('+' in msg_text or 'ID:' in msg_text or 'id:' in msg_text.lower() or 'елефон' in msg_text or 'Phone' in msg_text):
                                response_text = msg_text
                                print(f"[MATCHED] Found valid response with phone/ID data")
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
                            print(f"[NUMBER SEARCH RESPONSE] Raw message: {msg_text[:500]}...")
                            if msg_text and len(msg_text) > 50:
                                response_text = msg_text
                                print(f"[NUMBER SEARCH] Found valid response")
                                break
                if response_text:
                    break
                await asyncio.sleep(1.5)
                attempts += 1

        if not response_text:
            print(f"[ERROR] No response received from {target_bot}")
            return None

        print(f"[FULL RESPONSE] Complete bot response:\n{response_text}")

        if is_username_search or is_userid_search:
            phone_number = extract_telegram_data(response_text)
            print(f"[EXTRACTED] Phone number: {phone_number}")
            if phone_number:
                return phone_number
            else:
                return None
        else:
            filtered_text = filter_response_data(response_text)
            print(f"[FILTERED] Number search result: {filtered_text}")
            return filtered_text

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
        loop = get_pyrogram_loop()
        future = asyncio.run_coroutine_threadsafe(
            generate_report_from_bot(query, query_id, is_username_search, is_userid_search),
            loop
        )
        return future.result(timeout=20)
    except Exception as e:
        print(f"[ERROR] generate_report wrapper: {e}")
        import traceback
        traceback.print_exc()
        return None

# Flask Routes
@app.route('/attached_assets/<path:filename>')
def serve_attached_assets(filename):
    return send_from_directory('attached_assets', filename)

# Frontend deployed separately on Netlify - not needed here

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if admin is authenticated
        if not session.get('is_admin'):
            return jsonify({'success': False, 'message': 'Admin authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

# Admin panel URL: https://your-backend.onrender.com/admin - served from separate frontend

@app.route('/admin/verify', methods=['POST'])
def admin_verify():
    data = request.get_json()
    password = data.get('password', '')
    
    if password == ADMIN_PASSWORD:
        session['is_admin'] = True
        session.permanent = True
        return jsonify({'success': True}), 200
    return jsonify({'success': False, 'message': 'Invalid password'}), 401

@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    session.pop('is_admin', None)
    return jsonify({'success': True}), 200

@app.route('/admin/add_balance', methods=['POST'])
@admin_required
def admin_add_balance():
    data = request.get_json()
    hash_code = data.get('user_name')  # This is actually hash_code from admin panel
    amount = data.get('amount')
    
    if not hash_code or not amount:
        return jsonify({'success': False, 'message': 'Missing fields'}), 400
    
    with users_lock:
        users = load_users()
        # Find user by hash_code
        found_user = None
        for name, user_data in users.items():
            if user_data.get('hash_code') == hash_code.upper():
                found_user = name
                break
        
        if not found_user:
            return jsonify({'success': False, 'message': 'User not found with this hash code'}), 404
        
        users[found_user]['balance'] = users[found_user].get('balance', 0) + amount
        save_users(users)
        new_balance = users[found_user]['balance']
    
    return jsonify({'success': True, 'message': f'Added ₹{amount} to {found_user} ({hash_code}). New balance: ₹{new_balance}'}), 200

@app.route('/admin/deduct_balance', methods=['POST'])
@admin_required
def admin_deduct_balance():
    data = request.get_json()
    hash_code = data.get('user_name')  # This is actually hash_code from admin panel
    amount = data.get('amount')
    
    if not hash_code or not amount:
        return jsonify({'success': False, 'message': 'Missing fields'}), 400
    
    with users_lock:
        users = load_users()
        # Find user by hash_code
        found_user = None
        for name, user_data in users.items():
            if user_data.get('hash_code') == hash_code.upper():
                found_user = name
                break
        
        if not found_user:
            return jsonify({'success': False, 'message': 'User not found with this hash code'}), 404
        
        users[found_user]['balance'] = users[found_user].get('balance', 0) - amount
        save_users(users)
        new_balance = users[found_user]['balance']
    
    return jsonify({'success': True, 'message': f'Deducted ₹{amount} from {found_user} ({hash_code}). New balance: ₹{new_balance}'}), 200

@app.route('/admin/switch_pyrogram', methods=['POST'])
@admin_required
def admin_switch_pyrogram():
    global ACTIVE_USERNAME_PYROGRAM_INDEX
    data = request.get_json()
    account_index = data.get('account_index')
    
    if account_index is None or account_index < 0 or account_index >= len(username_search_clients):
        return jsonify({'success': False, 'message': 'Invalid account index'}), 400
    
    ACTIVE_USERNAME_PYROGRAM_INDEX = account_index
    return jsonify({'success': True, 'message': f'Switched to Pyrogram Account #{account_index + 1}'}), 200

@app.route('/admin/get_all_users', methods=['GET'])
@admin_required
def admin_get_all_users():
    with users_lock:
        users = load_users()
    return jsonify({'success': True, 'users': users}), 200

@app.route('/admin/pyrogram_status', methods=['GET'])
@admin_required
def admin_pyrogram_status():
    number_search_status = number_search_client.is_connected if number_search_client else False
    username_search_status = [client.is_connected for client in username_search_clients]
    
    return jsonify({
        'success': True,
        'number_search': number_search_status,
        'username_search': username_search_status,
        'active_username_account': ACTIVE_USERNAME_PYROGRAM_INDEX
    }), 200

@app.route('/admin/get_deposits', methods=['GET'])
@admin_required
def admin_get_deposits():
    try:
        with open(DEPOSIT_REQUESTS_FILE, 'r') as f:
            deposits = json.load(f)
        return jsonify({'success': True, 'deposits': deposits}), 200
    except:
        return jsonify({'success': True, 'deposits': []}), 200

@app.route('/admin/approve_deposit', methods=['POST'])
@admin_required
def admin_approve_deposit():
    data = request.get_json()
    request_id = data.get('request_id')
    
    try:
        with open(DEPOSIT_REQUESTS_FILE, 'r') as f:
            deposits = json.load(f)
        
        deposit_found = None
        for dep in deposits:
            if dep['request_id'] == request_id and dep['status'] == 'pending':
                deposit_found = dep
                break
        
        if not deposit_found:
            return jsonify({'success': False, 'message': 'Deposit not found'}), 404
        
        # Add balance to user
        name = deposit_found['name']
        amount = deposit_found['amount']
        
        with users_lock:
            users = load_users()
            if name in users:
                users[name]['balance'] = users[name].get('balance', 0) + amount
                save_users(users)
                deposit_found['status'] = 'approved'
                
                with open(DEPOSIT_REQUESTS_FILE, 'w') as f:
                    json.dump(deposits, f, indent=2)
                
                return jsonify({'success': True, 'message': f'Approved! ₹{amount} added to {name}'}), 200
            else:
                return jsonify({'success': False, 'message': 'User not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/reject_deposit', methods=['POST'])
@admin_required
def admin_reject_deposit():
    data = request.get_json()
    request_id = data.get('request_id')
    
    try:
        with open(DEPOSIT_REQUESTS_FILE, 'r') as f:
            deposits = json.load(f)
        
        deposit_found = None
        for dep in deposits:
            if dep['request_id'] == request_id:
                deposit_found = dep
                break
        
        if not deposit_found:
            return jsonify({'success': False, 'message': 'Deposit not found'}), 404
        
        deposit_found['status'] = 'rejected'
        
        with open(DEPOSIT_REQUESTS_FILE, 'w') as f:
            json.dump(deposits, f, indent=2)
        
        return jsonify({'success': True, 'message': 'Deposit rejected'}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

def generate_hash_code():
    """Generate a 6-letter alphanumeric hash code in CAPITAL letters"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(choice(chars) for _ in range(6))

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    name = data.get('name', '').strip()

    if not name:
        return jsonify({'success': False, 'message': 'Name is required'}), 400

    with users_lock:
        users = load_users()
        if name in users:
            return jsonify({'success': False, 'message': 'Name already taken'}), 409

        # Generate unique hash code
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

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    hash_code = data.get('hash_code', '').strip()

    if not hash_code:
        return jsonify({'success': False, 'message': 'Hash Code is required'}), 400

    with users_lock:
        users = load_users()
        # Find user by hash code
        found_user = None
        for name, user_data in users.items():
            if user_data.get('hash_code') == hash_code:
                found_user = name
                break
        
        if not found_user:
            return jsonify({'success': False, 'message': 'Invalid hash code'}), 401

    session['user_name'] = found_user
    return jsonify({'success': True, 'message': 'Login successful!', 'user_name': found_user}), 200

@app.route('/logout')
def logout():
    session.pop('user_name', None)
    return redirect(url_for('index'))


@app.route('/get_balance', methods=['GET', 'POST'])
def get_balance():
    # Balance endpoint - client sends user_name
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
    data = request.get_json()
    number = data.get('number')

    print(f"\n{'='*50}")
    print(f"[NUMBER SEARCH REQUEST] Number: {number}")

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
    
    print(f"[NUMBER SEARCH] User: {name}, Formatted number: {number}")
    
    NUMBER_SEARCH_PRICE = 4
    with users_lock:
        users = load_users()
        user_data = users.get(name, {})
        current_balance = user_data.get('balance', 0)
        
        if current_balance < NUMBER_SEARCH_PRICE:
            return jsonify({'success': False, 'message': f'Insufficient balance. Need ₹{NUMBER_SEARCH_PRICE}, have ₹{current_balance}'}), 402

    query_id = randint(0, 9999999)
    
    print(f"[NUMBER SEARCH] Starting search for: {number}")
    start_time = time.time()
    
    result = generate_report(number, query_id, is_username_search=False, is_userid_search=False)
    
    elapsed_time = time.time() - start_time
    print(f"[NUMBER SEARCH] Completed in {elapsed_time:.2f} seconds")
    print(f"[NUMBER SEARCH] Raw result: {result}")

    if result and isinstance(result, dict) and 'status' in result:
        if result.get('status') == 'no_results':
            add_to_searched_no_data(number, "number")
            print(f"[NUMBER SEARCH] No results found")
            return jsonify({'success': False, 'message': result.get('message', 'No data found')}), 404
        else:
            print(f"[NUMBER SEARCH] Error occurred")
            return jsonify({'success': False, 'message': result.get('message', 'An error occurred')}), 500
    elif result and isinstance(result, list) and len(result) > 0:
        first_item = result[0]
        if isinstance(first_item, dict) and 'status' in first_item:
            add_to_searched_no_data(number, "number")
            print(f"[NUMBER SEARCH] Error in list response")
            return jsonify({'success': False, 'message': first_item.get('message', 'No data found')}), 404

        add_to_searched_no_data(number, "number")
        with users_lock:
            users = load_users()
            if name in users:
                users[name]['balance'] = users[name].get('balance', 0) - NUMBER_SEARCH_PRICE
                save_users(users)
                new_balance = users[name]['balance']

        print(f"[NUMBER SEARCH] Returning success with {len(result)} records")
        return jsonify({'success': True, 'data': result, 'new_balance': new_balance}), 200
    else:
        add_to_searched_no_data(number, "number")
        print(f"[NUMBER SEARCH] No data found or error")
        return jsonify({'success': False, 'message': 'No data found or an error occurred'}), 404


@app.route('/search/username', methods=['POST'])
def search_username():
    data = request.get_json()
    username = data.get('username')
    name = data.get('user_name')
    
    print(f"\n{'='*50}")
    print(f"[USERNAME SEARCH REQUEST] Username: {username}, User: {name}")
    
    if not name:
        return jsonify({'success': False, 'message': 'User name required'}), 400

    if not username:
        return jsonify({'success': False, 'message': 'Username is required'}), 400

    if username.startswith('@'):
        username = username[1:]

    if not username:
        return jsonify({'success': False, 'message': 'Invalid username'}), 400

    USERNAME_SEARCH_PRICE = 21
    with users_lock:
        users = load_users()
        user_data = users.get(name, {})
        current_balance = user_data.get('balance', 0)

        if current_balance < USERNAME_SEARCH_PRICE:
            return jsonify({'success': False, 'message': f'Insufficient balance. Need ₹{USERNAME_SEARCH_PRICE}, have ₹{current_balance}'}), 402

    query_id = randint(0, 9999999)
    
    print(f"[USERNAME SEARCH] Starting search for: {username}")
    start_time = time.time()
    
    phone_result = generate_report(username, query_id, True, False)
    
    elapsed_time = time.time() - start_time
    print(f"[USERNAME SEARCH] Completed in {elapsed_time:.2f} seconds")
    print(f"[USERNAME SEARCH] Phone result: {phone_result}")
    
    has_phone = phone_result and isinstance(phone_result, str) and phone_result.startswith('+')
    
    if has_phone:
        add_to_searched_no_data(username, "username", has_result=True)
        with users_lock:
            users = load_users()
            if name in users:
                users[name]['balance'] = users[name].get('balance', 0) - USERNAME_SEARCH_PRICE
                save_users(users)
                new_balance = users[name]['balance']

        print(f"[USERNAME SEARCH] Returning success with phone: {phone_result}")
        return jsonify({
            'success': True,
            'new_balance': new_balance,
            'phone_number': phone_result
        }), 200
    else:
        add_to_searched_no_data(username, "username", has_result=False)
        print(f"[USERNAME SEARCH] No data found")
        return jsonify({'success': False, 'message': 'No data found'}), 404

@app.route('/search/userid', methods=['POST'])
def search_userid():
    data = request.get_json()
    user_id_str = data.get('user_id')
    name = data.get('user_name')

    print(f"\n{'='*50}")
    print(f"[USERID SEARCH REQUEST] UserID: {user_id_str}, User: {name}")

    if not name:
        return jsonify({'success': False, 'message': 'User name required'}), 400

    if not user_id_str:
        return jsonify({'success': False, 'message': 'User ID is required'}), 400

    if not user_id_str.isdigit():
        return jsonify({'success': False, 'message': 'User ID must be numeric'}), 400

    USERID_SEARCH_PRICE = 21
    with users_lock:
        users = load_users()
        user_data = users.get(name, {})
        current_balance = user_data.get('balance', 0)

        if current_balance < USERID_SEARCH_PRICE:
            return jsonify({'success': False, 'message': f'Insufficient balance. Need ₹{USERID_SEARCH_PRICE}, have ₹{current_balance}'}), 402

    query_id = randint(0, 9999999)
    
    print(f"[USERID SEARCH] Starting search for UserID: {user_id_str}")
    start_time = time.time()
    
    result = generate_report(user_id_str, query_id, is_username_search=False, is_userid_search=True)
    
    elapsed_time = time.time() - start_time
    print(f"[USERID SEARCH] Completed in {elapsed_time:.2f} seconds")
    print(f"[USERID SEARCH] Result: {result}")

    if result and isinstance(result, str) and result.startswith('+'):
        add_to_searched_no_data(user_id_str, "user_id", has_result=True)
        with users_lock:
            users = load_users()
            if name in users:
                users[name]['balance'] = users[name].get('balance', 0) - USERID_SEARCH_PRICE
                save_users(users)
                new_balance = users[name]['balance']

        print(f"[USERID SEARCH] Returning success with phone: {result}")
        return jsonify({'success': True, 'phone_number': result, 'user_id': user_id_str, 'new_balance': new_balance}), 200
    else:
        add_to_searched_no_data(user_id_str, "user_id", has_result=False)
        print(f"[USERID SEARCH] No data found")
        return jsonify({'success': False, 'message': 'No data found or an error occurred'}), 404

@app.route('/get_my_history', methods=['GET'])
def get_my_history():
    if 'user_email' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    email = session['user_email']
    with users_lock:
        users = load_users()
        user_data = users.get(email, {})
        history = user_data.get('search_history', [])
        # Return last 50 searches
        history = history[-50:]
        history.reverse() # Most recent first

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

    # Load promo codes
    try:
        with open('promo_codes.json', 'r') as f:
            promo_codes = json.load(f)
    except:
        promo_codes = {}

    # Check if promo code exists
    if promo_code not in promo_codes:
        return jsonify({'success': False, 'message': 'Invalid promo code'}), 404

    promo_data = promo_codes[promo_code]

    # Check if already used by this user
    if user_name in promo_data.get('used_by', []):
        return jsonify({'success': False, 'message': 'You have already used this promo code'}), 400

    # Check if max uses reached
    if promo_data.get('used_count', 0) >= promo_data.get('max_uses', 0):
        return jsonify({'success': False, 'message': 'This promo code has reached its maximum usage limit'}), 400

    # Apply promo code
    amount = promo_data.get('amount', 0)
    
    with users_lock:
        users = load_users()
        if user_name not in users:
            return jsonify({'success': False, 'message': 'User not found'}), 404

        users[user_name]['balance'] = users[user_name].get('balance', 0) + amount
        save_users(users)
        new_balance = users[user_name]['balance']

    # Update promo code usage
    if 'used_by' not in promo_data:
        promo_data['used_by'] = []
    promo_data['used_by'].append(user_name)
    promo_data['used_count'] = promo_data.get('used_count', 0) + 1

    with open('promo_codes.json', 'w') as f:
        json.dump(promo_codes, f, indent=2)

    return jsonify({
        'success': True, 
        'message': f'Promo code applied! ₹{amount} added to your balance. New balance: ₹{new_balance}'
    }), 200

@app.route('/admin/create_promo_code', methods=['POST'])
@admin_required
def admin_create_promo_code():
    data = request.get_json()
    promo_code = data.get('promo_code', '').strip().upper()
    amount = data.get('amount')
    max_uses = data.get('max_uses')

    if not promo_code or not amount or not max_uses:
        return jsonify({'success': False, 'message': 'All fields required'}), 400

    # Load existing promo codes
    try:
        with open('promo_codes.json', 'r') as f:
            promo_codes = json.load(f)
    except:
        promo_codes = {}

    # Check if promo code already exists
    if promo_code in promo_codes:
        return jsonify({'success': False, 'message': 'Promo code already exists'}), 409

    # Create new promo code
    promo_codes[promo_code] = {
        'amount': float(amount),
        'max_uses': int(max_uses),
        'used_count': 0,
        'used_by': []
    }

    # Save promo codes
    with open('promo_codes.json', 'w') as f:
        json.dump(promo_codes, f, indent=2)

    return jsonify({'success': True, 'message': f'Promo code "{promo_code}" created successfully!'}), 200

@app.route('/admin/get_promo_codes', methods=['GET'])
@admin_required
def admin_get_promo_codes():
    try:
        with open('promo_codes.json', 'r') as f:
            promo_codes = json.load(f)
        return jsonify({'success': True, 'promo_codes': promo_codes}), 200
    except:
        return jsonify({'success': True, 'promo_codes': {}}), 200

@app.route('/admin/delete_promo_code', methods=['POST'])
@admin_required
def admin_delete_promo_code():
    data = request.get_json()
    promo_code = data.get('promo_code', '').strip().upper()

    if not promo_code:
        return jsonify({'success': False, 'message': 'Promo code required'}), 400

    try:
        with open('promo_codes.json', 'r') as f:
            promo_codes = json.load(f)

        if promo_code not in promo_codes:
            return jsonify({'success': False, 'message': 'Promo code not found'}), 404

        del promo_codes[promo_code]

        with open('promo_codes.json', 'w') as f:
            json.dump(promo_codes, f, indent=2)

        return jsonify({'success': True, 'message': f'Promo code "{promo_code}" deleted'}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/submit_deposit', methods=['POST'])
def submit_deposit():
    data = request.get_json()
    amount = data.get('amount')
    utr = data.get('utr')
    # Accept both 'name' and 'user_name' for compatibility
    name = data.get('name') or data.get('user_name')

    if not name:
        return jsonify({'success': False, 'message': 'User name required'}), 400

    if not amount or float(amount) < 25:
        return jsonify({'success': False, 'message': 'Minimum amount is ₹25'}), 400

    if not utr or len(utr) != 12 or not utr.isdigit():
        return jsonify({'success': False, 'message': 'Invalid UTR (must be 12 digits)'}), 400

    # Verify user exists in web_users
    with users_lock:
        users = load_users()
        if name not in users:
            return jsonify({'success': False, 'message': 'User not found'}), 404

    # Load deposit requests
    try:
        with open(DEPOSIT_REQUESTS_FILE, 'r') as f:
            deposit_requests = json.load(f)
    except:
        deposit_requests = []

    # Add new request
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

    # Save requests
    with open(DEPOSIT_REQUESTS_FILE, 'w') as f:
        json.dump(deposit_requests, f, indent=2)

    return jsonify({'success': True, 'message': 'Deposit request submitted'}), 200


async def start_pyrogram_client(client, client_name):
    """Start a single Pyrogram client"""
    try:
        await client.start()
        print(f"✅ {client_name} connected.")
        return True
    except Exception as e:
        print(f"❌ {client_name} connection error: {e}")
        import traceback
        traceback.print_exc()
        return False

def ensure_pyrogram_session():
    """Ensure Pyrogram accounts are authenticated"""
    try:
        loop = get_pyrogram_loop()
        if number_search_client:
            print("\n📞 Authenticating Number Search Pyrogram...")
            future = asyncio.run_coroutine_threadsafe(
                start_pyrogram_client(number_search_client, "Number Search Pyrogram"),
                loop
            )
            future.result()

        for idx, client in enumerate(username_search_clients):
            config = USERNAME_SEARCH_PYROGRAMS[idx]
            if config.get('api_id', 0) == 0 or not config.get('api_hash'):
                continue # Skip unconfigured accounts
            print(f"\n👤 Authenticating Username Search Pyrogram #{idx + 1}...")
            future = asyncio.run_coroutine_threadsafe(
                start_pyrogram_client(client, f"Username Search Pyrogram #{idx + 1}"),
                loop
            )
            future.result()

        print("\n✅ All configured Pyrogram sessions authenticated.")
        return True
    except Exception as e:
        print(f"\n❌ Pyrogram connection error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    init_files()
    print("✅ Files initialized")

    if not ensure_pyrogram_session():
        print("⚠️ Warning: Pyrogram authentication failed. Some search features might not work.")

    print("\n🚀 Starting Flask web application...")
    print("\n" + "="*70)
    print("📋 BACKEND API CONFIGURATION")
    print("="*70)
    print("\n✅ Backend is running on: http://0.0.0.0:5000")
    print("\n🔗 FOR FRONTEND DEPLOYMENT:")
    print("   Copy your Wispbyte/deployment URL and paste in frontend/index.html")
    print("   Example: const API_URL = 'https://your-backend-url.com';")
    print("\n📡 API ENDPOINTS AVAILABLE:")
    print("   • POST /login - User login")
    print("   • POST /signup - User signup")
    print("   • POST /search/number - Phone number search")
    print("   • POST /search/username - Username search")
    print("   • POST /search/userid - UserID search")
    print("   • GET /get_balance - Get user balance")
    print("   • GET /admin - Admin panel")
    print("\n" + "="*70 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=False)

if __name__ == "__main__":
    main()