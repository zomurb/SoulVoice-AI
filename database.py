import sqlite3
import datetime
import logging

DB_NAME = "bot.db"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    """Initialize the database tables."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Users table
    # subscription_level: 0 = Free, 1 = Premium
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            language TEXT DEFAULT 'en',
            subscription_level INTEGER DEFAULT 0,
            messages_today INTEGER DEFAULT 0,
            last_message_date DATE,
            join_date DATE
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("Database initialized.")

def get_user(user_id):
    """Get user details."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def add_user(user_id, username, first_name):
    """Add a new user if not exists."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name, join_date, last_message_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, datetime.date.today(), datetime.date.today()))
        conn.commit()
    except Exception as e:
        logger.error(f"Error adding user: {e}")
    finally:
        conn.close()

def check_limit(user_id, limit=3):
    """Check if user has reached daily limit. Resets count if new day."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    today = datetime.date.today()
    cursor.execute('SELECT messages_today, last_message_date, subscription_level FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if not result:
        conn.close()
        return False # User should start flow to be added
        
    count, last_date_str, sub_level = result
    
    # Convert string date to object if needed (sqlite stores as string usually)
    # But python sqlite3 adapter often handles this if strictly typed, but here robust check:
    if str(today) != str(last_date_str):
        # New day, reset
        cursor.execute('UPDATE users SET messages_today = 0, last_message_date = ? WHERE user_id = ?', (today, user_id))
        conn.commit()
        conn.close()
        return True
    
    # Check limit (Premium = 1 is unlimited)
    if sub_level >= 1:
        conn.close()
        return True
        
    if count < limit:
        conn.close()
        return True
        
    conn.close()
    return False

def increment_usage(user_id):
    """Increment message count for today."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET messages_today = messages_today + 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def set_subscription(user_id, level):
    """Set subscription level (0=Free, 1=Premium)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET subscription_level = ? WHERE user_id = ?', (level, user_id))
    conn.commit()
    conn.close()

def get_stats():
    """Return basic stats."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM users WHERE subscription_level > 0')
    premium_users = cursor.fetchone()[0]
    conn.close()
    return total_users, premium_users
