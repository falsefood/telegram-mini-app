import sqlite3
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_file="bot_database.db"):
        self.db_file = db_file
        self.init_db()

    def init_db(self):
        """Initialize database and create tables if they don't exist."""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Create subscriptions table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS subscriptions (
                        user_id INTEGER PRIMARY KEY,
                        plan_id TEXT NOT NULL,
                        purchase_time REAL NOT NULL,
                        expiration_time REAL NOT NULL,
                        notified INTEGER DEFAULT 0
                    )
                ''')
                
                # Create payments history table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS payments (
                        payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        plan_id TEXT NOT NULL,
                        amount REAL NOT NULL,
                        currency TEXT NOT NULL,
                        payment_time REAL NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES subscriptions (user_id)
                    )
                ''')
                
                # Add notified column if it doesn't exist
                cursor.execute("PRAGMA table_info(subscriptions)")
                columns = [column[1] for column in cursor.fetchall()]
                if "notified" not in columns:
                    cursor.execute("ALTER TABLE subscriptions ADD COLUMN notified INTEGER DEFAULT 0")
                
                conn.commit()
                logger.info("Database initialized successfully")
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")
            raise

    def add_subscription(self, user_id, plan_id, duration_days):
        """Add or update user subscription."""
        try:
            current_time = datetime.now().timestamp()
            
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Check if user already has a subscription
                cursor.execute(
                    "SELECT expiration_time FROM subscriptions WHERE user_id = ?",
                    (user_id,)
                )
                existing = cursor.fetchone()
                
                if existing and existing[0] > current_time:
                    # Extend existing subscription
                    new_expiration = existing[0] + (duration_days * 24 * 3600)
                else:
                    # Create new subscription
                    new_expiration = current_time + (duration_days * 24 * 3600)
                
                # Insert or update subscription
                cursor.execute('''
                    INSERT OR REPLACE INTO subscriptions 
                    (user_id, plan_id, purchase_time, expiration_time, notified)
                    VALUES (?, ?, ?, ?, 0)
                ''', (user_id, plan_id, current_time, new_expiration))
                
                conn.commit()
                logger.info(f"Subscription added/updated for user {user_id}")
                return True
        except sqlite3.Error as e:
            logger.error(f"Error adding subscription: {e}")
            return False

    def add_payment(self, user_id, plan_id, amount, currency):
        """Record a payment."""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO payments 
                    (user_id, plan_id, amount, currency, payment_time)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, plan_id, amount, currency, datetime.now().timestamp()))
                conn.commit()
                logger.info(f"Payment recorded for user {user_id}")
                return True
        except sqlite3.Error as e:
            logger.error(f"Error recording payment: {e}")
            return False

    def get_subscription(self, user_id):
        """Get user's subscription details."""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM subscriptions WHERE user_id = ?",
                    (user_id,)
                )
                result = cursor.fetchone()
                
                if result:
                    return {
                        "user_id": result[0],
                        "plan_id": result[1],
                        "purchase_time": result[2],
                        "expiration_time": result[3]
                    }
                return None
        except sqlite3.Error as e:
            logger.error(f"Error getting subscription: {e}")
            return None

    def is_subscription_active(self, user_id):
        """Check if user's subscription is active."""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                current_time = datetime.now().timestamp()
                
                cursor.execute(
                    "SELECT expiration_time FROM subscriptions WHERE user_id = ?",
                    (user_id,)
                )
                result = cursor.fetchone()
                
                if result:
                    return result[0] > current_time
                return False
        except sqlite3.Error as e:
            logger.error(f"Error checking subscription: {e}")
            return False

    def get_remaining_time(self, user_id):
        """Get remaining subscription time in days."""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                current_time = datetime.now().timestamp()
                
                cursor.execute(
                    "SELECT expiration_time FROM subscriptions WHERE user_id = ?",
                    (user_id,)
                )
                result = cursor.fetchone()
                
                if result:
                    remaining_seconds = result[0] - current_time
                    return max(0, int(remaining_seconds / (24 * 3600)))  # Convert to days
                return 0
        except sqlite3.Error as e:
            logger.error(f"Error getting remaining time: {e}")
            return 0

    def get_payment_history(self, user_id):
        """Get user's payment history."""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM payments WHERE user_id = ? ORDER BY payment_time DESC",
                    (user_id,)
                )
                results = cursor.fetchall()
                
                return [{
                    "payment_id": row[0],
                    "user_id": row[1],
                    "plan_id": row[2],
                    "amount": row[3],
                    "currency": row[4],
                    "payment_time": row[5]
                } for row in results]
        except sqlite3.Error as e:
            logger.error(f"Error getting payment history: {e}")
            return [] 