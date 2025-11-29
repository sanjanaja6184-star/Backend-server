# Backend Deployment on Zampto

## Files Required
Upload the entire `backend` folder:
- `main.py` - Flask application
- `requirements.txt` - Python dependencies
- `*.session` - Telegram session files (IMPORTANT!)
- `web_users.json` - User database
- `deposit_requests.json` - Deposit requests

## Deployment Steps

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables
Set these environment variables in Zampto:
- `ADMIN_PASSWORD`: Your admin panel password (default: admin123)
- `SECRET_KEY`: Flask session secret key

### 3. Run the Application
```bash
python main.py
```

The server will start on `0.0.0.0:5000`

## Important Notes

### Session Files
The `.session` files contain your Telegram login sessions. 
**DO NOT share these files publicly** - they contain sensitive authentication data.

### CORS Configuration
CORS is already enabled to accept requests from any origin.
For production, edit `main.py` and change:
```python
CORS(app, resources={r"/*": {"origins": "*"}})
```
to:
```python
CORS(app, resources={r"/*": {"origins": "https://your-netlify-site.netlify.app"}})
```

### Admin Panel
Access admin panel at: `https://your-zampto-url.com/admin`

### API Endpoints
All these endpoints will be available:
- POST `/login` - User login
- POST `/signup` - User signup
- POST `/search/number` - Phone number search
- POST `/search/username` - Username search
- POST `/search/userid` - UserID search
- GET `/get_balance` - Get user balance
- POST `/submit_deposit` - Submit deposit request
- POST `/apply_promo_code` - Apply promo code

## Troubleshooting

### CORS Errors
If you see CORS errors in browser console, check:
1. Backend is running and accessible
2. API_URL in frontend is correct
3. CORS is properly configured in main.py

### Session Errors
If Telegram sessions fail:
1. Delete the `.session` files
2. Re-authenticate by running the app locally first
3. Upload the new session files
