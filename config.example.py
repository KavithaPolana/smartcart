import os

SECRET_KEY = os.environ.get("SECRET_KEY", "your-secret-key-change-in-production")

# Base Directory & SQLite Database Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "smartcart.db")

# Email Configuration
MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True").lower() == "true"
MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "your-email@gmail.com")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "your-email-app-password")

# Razorpay Configuration
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "your_razorpay_key_id")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "your_razorpay_key_secret")
