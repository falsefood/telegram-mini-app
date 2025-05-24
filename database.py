import sqlite3
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.db_file = "bot_database.db"
        self._init_db()

    def _init_db(self):
        """Initialize database with proper schema."""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Create subscriptions table with consistent column names
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS subscriptions (
                        user_id INTEGER PRIMARY KEY,
                        plan_id TEXT NOT NULL,
                        start_date INTEGER NOT NULL,
                        expiry_date INTEGER NOT NULL,
                        notified INTEGER DEFAULT 0
                    )
                """)
                
                # Create payments table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS payments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        plan_id TEXT NOT NULL,
                        amount REAL NOT NULL,
                        currency TEXT NOT NULL,
                        payment_time INTEGER NOT NULL
                    )
                """)
                
                conn.commit()
                logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise

    def add_subscription(self, user_id: int, plan_id: str, duration_days: float):
        """Add or update a subscription."""
        try:
            current_time = datetime.now().timestamp()
            expiry = (datetime.now() + timedelta(days=duration_days)).timestamp()
            
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO subscriptions 
                    (user_id, plan_id, start_date, expiry_date, notified) 
                    VALUES (?, ?, ?, ?, 0)
                """, (user_id, plan_id, current_time, expiry))
                conn.commit()
                logger.info(f"Added/updated subscription for user {user_id}")
        except Exception as e:
            logger.error(f"Error adding subscription: {e}")
            raise

    def get_subscription(self, user_id: int):
        """Get subscription details for a user."""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT user_id, plan_id, start_date, expiry_date 
                    FROM subscriptions 
                    WHERE user_id = ?
                """, (user_id,))
                result = cursor.fetchone()
                
                if result:
                    return {
                        "user_id": result[0],
                        "plan_id": result[1],
                        "start_date": result[2],
                        "expiry_date": result[3]
                    }
                return None
        except Exception as e:
            logger.error(f"Error getting subscription: {e}")
            raise

    def is_subscription_active(self, user_id: int) -> bool:
        """Check if a user's subscription is active."""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT expiry_date 
                    FROM subscriptions 
                    WHERE user_id = ?
                """, (user_id,))
                result = cursor.fetchone()
                
                if result:
                    expiry_date = result[0]
                    return expiry_date > datetime.now().timestamp()
                return False
        except Exception as e:
            logger.error(f"Error checking subscription status: {e}")
            return False

    def add_payment(self, user_id: int, plan_id: str, amount: float, currency: str):
        """Record a payment."""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO payments 
                    (user_id, plan_id, amount, currency, payment_time) 
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, plan_id, amount, currency, datetime.now().timestamp()))
                conn.commit()
                logger.info(f"Added payment record for user {user_id}")
        except Exception as e:
            logger.error(f"Error adding payment: {e}")
            raise

    def get_payment_history(self, user_id: int):
        """Get payment history for a user."""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, user_id, plan_id, amount, currency, payment_time 
                    FROM payments 
                    WHERE user_id = ? 
                    ORDER BY payment_time DESC
                """, (user_id,))
                results = cursor.fetchall()
                
                return [{
                    "id": row[0],
                    "user_id": row[1],
                    "plan_id": row[2],
                    "amount": row[3],
                    "currency": row[4],
                    "payment_time": row[5]
                } for row in results]
        except Exception as e:
            logger.error(f"Error getting payment history: {e}")
            raise

    def get_remaining_time(self, user_id: int) -> float:
        """Get remaining subscription time in days."""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT expiry_date 
                    FROM subscriptions 
                    WHERE user_id = ?
                """, (user_id,))
                result = cursor.fetchone()
                
                if result:
                    expiry_date = result[0]
                    remaining = expiry_date - datetime.now().timestamp()
                    return max(0, remaining / (24 * 3600))  # Convert to days
                return 0
        except Exception as e:
            logger.error(f"Error getting remaining time: {e}")
            return 0 