# app.py
# ---------------------------------------------------------
# SMARTCART
# Admin + User + Products + Cart + Address + Razorpay
# ---------------------------------------------------------

from flask import Flask, render_template, request, redirect, session, flash
from flask_mail import Mail, Message
import traceback
from flask import make_response
from utils.pdf_generator import generate_pdf
import sqlite3
import bcrypt
import random
import os
import razorpay
from werkzeug.utils import secure_filename

try:
    import config
except ImportError:
    class ConfigFallback:
        SECRET_KEY = "abcdefg"
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        DB_PATH = os.path.join(BASE_DIR, "smartcart.db")
        MAIL_SERVER = 'smtp.gmail.com'
        MAIL_PORT = 587
        MAIL_USE_TLS = True
        MAIL_USERNAME = 'kavithapolana19@gmail.com'
        MAIL_PASSWORD = ''
        RAZORPAY_KEY_ID = 'rzp_test_Tbw0XTMtbWT5rb'
        RAZORPAY_KEY_SECRET = ''
    config = ConfigFallback()

app = Flask(__name__)
app.secret_key = getattr(config, 'SECRET_KEY', 'abcdefg')


# =========================================================
# EMAIL CONFIGURATION
# =========================================================

app.config['MAIL_SERVER'] = getattr(config, 'MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(getattr(config, 'MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = bool(getattr(config, 'MAIL_USE_TLS', True))
app.config['MAIL_USERNAME'] = getattr(config, 'MAIL_USERNAME', 'kavithapolana19@gmail.com')
app.config['MAIL_PASSWORD'] = getattr(config, 'MAIL_PASSWORD', '')

mail = Mail(app)


# =========================================================
# RAZORPAY CONFIGURATION
# =========================================================

razorpay_client = razorpay.Client(
    auth=(
        getattr(config, 'RAZORPAY_KEY_ID', 'rzp_test_Tbw0XTMtbWT5rb'),
        getattr(config, 'RAZORPAY_KEY_SECRET', '')
    )
)


# =========================================================
# DATABASE CONNECTION (SQLite for Universal Deployment)
# =========================================================

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


class SQLiteConnectionWrapper:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self, *args, **kwargs):
        return self._conn.cursor()

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    def executescript(self, sql):
        return self._conn.executescript(sql)

    def __getattr__(self, name):
        return getattr(self._conn, name)


def get_db_connection():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = dict_factory
    return SQLiteConnectionWrapper(conn)


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS admin (
        admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        profile_image TEXT
    );

    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS products (
        product_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        image TEXT
    );

    CREATE TABLE IF NOT EXISTS cart_items (
        cart_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS user_addresses (
        address_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        full_name TEXT NOT NULL,
        mobile TEXT NOT NULL,
        house_number TEXT NOT NULL,
        area TEXT NOT NULL,
        landmark TEXT,
        city TEXT NOT NULL,
        state TEXT NOT NULL,
        pincode TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_default INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS orders (
        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        address_id INTEGER,
        razorpay_order_id TEXT,
        razorpay_payment_id TEXT,
        amount REAL NOT NULL,
        payment_status TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL
    );
    """)
    conn.commit()
    cursor.close()
    conn.close()

init_db()


# =========================================================
# LOAD USER CART FROM DATABASE
# =========================================================

def load_user_cart(user_id):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            c.product_id,
            c.quantity,
            p.name,
            p.price,
            p.image
        FROM cart_items c
        JOIN products p
            ON c.product_id = p.product_id
        WHERE c.user_id = ?
    """, (user_id,))

    items = cursor.fetchall()

    cursor.close()
    conn.close()

    cart = {}

    for item in items:

        pid = str(item['product_id'])

        cart[pid] = {
            'name': item['name'],
            'price': float(item['price']),
            'image': item['image'],
            'quantity': item['quantity']
        }

    return cart


# =========================================================
# SAVE USER CART TO DATABASE
# =========================================================

def save_user_cart(user_id, cart):

    conn = get_db_connection()
    cursor = conn.cursor()

    # Remove old cart records for this user
    cursor.execute(
        "DELETE FROM cart_items WHERE user_id=?",
        (user_id,)
    )

    # Insert current cart
    for pid, item in cart.items():

        cursor.execute("""
            INSERT INTO cart_items
            (
                user_id,
                product_id,
                quantity
            )
            VALUES (?, ?, ?)
        """, (
            user_id,
            int(pid),
            item['quantity']
        ))

    conn.commit()

    cursor.close()
    conn.close()


# =========================================================
# HOME
# =========================================================

@app.route('/')
def home():

    return redirect('/admin-signup')


# =========================================================
# ADMIN SIGNUP
# =========================================================

@app.route('/admin-signup', methods=['GET', 'POST'])
def admin_signup():

    if request.method == "GET":
        return render_template(
            "admin/admin_signup.html"
        )

    name = request.form['name']
    email = request.form['email']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT admin_id FROM admin WHERE email=?",
        (email,)
    )

    existing_admin = cursor.fetchone()

    cursor.close()
    conn.close()

    if existing_admin:

        flash(
            "This email is already registered. "
            "Please login instead.",
            "danger"
        )

        return redirect('/admin-login')

    session['signup_name'] = name
    session['signup_email'] = email

    otp = random.randint(
        100000,
        999999
    )

    session['otp'] = otp

    try:
        message = Message(
            subject="SmartCart Admin OTP",
            sender=getattr(config, 'MAIL_USERNAME', 'kavithapolana19@gmail.com'),
            recipients=[email]
        )
        message.body = f"Your OTP for SmartCart Admin Registration is: {otp}"
        mail.send(message)
        flash("OTP sent to your email!", "success")
    except Exception as e:
        app.logger.warning("SMTP Error: %s", str(e))
        flash(f"OTP generated: {otp} (Use this OTP to complete registration)", "info")

    return redirect('/verify-otp')


# =========================================================
# ADMIN OTP PAGE
# =========================================================

@app.route('/verify-otp', methods=['GET'])
def verify_otp_get():

    return render_template(
        "admin/verify_otp.html"
    )


# =========================================================
# ADMIN VERIFY OTP
# =========================================================

@app.route('/verify-otp', methods=['POST'])
def verify_otp_post():

    user_otp = request.form['otp']
    password = request.form['password']

    if str(session.get('otp')) != str(user_otp):

        flash(
            "Invalid OTP. Try again!",
            "danger"
        )

        return redirect('/verify-otp')

    hashed_password = bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    )

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO admin
        (name, email, password)
        VALUES (?, ?, ?)
        """,
        (
            session['signup_name'],
            session['signup_email'],
            hashed_password
        )
    )

    conn.commit()

    cursor.close()
    conn.close()

    session.pop('otp', None)
    session.pop('signup_name', None)
    session.pop('signup_email', None)

    flash(
        "Admin Registered Successfully!",
        "success"
    )

    return redirect('/admin-signup')


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route(
    '/admin-login',
    methods=['GET', 'POST']
)
def admin_login():

    if request.method == 'GET':

        return render_template(
            "admin/admin_login.html"
        )

    email = request.form['email']
    password = request.form['password']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM admin WHERE email=?",
        (email,)
    )

    admin = cursor.fetchone()

    cursor.close()
    conn.close()

    if admin is None:

        flash(
            "Email not found! Please register first.",
            "danger"
        )

        return redirect('/admin-login')

    stored_hashed_password = (
        admin['password'].encode('utf-8')
    )

    if not bcrypt.checkpw(
        password.encode('utf-8'),
        stored_hashed_password
    ):

        flash(
            "Incorrect password! Try again.",
            "danger"
        )

        return redirect('/admin-login')

    session['admin_id'] = admin['admin_id']
    session['admin_name'] = admin['name']
    session['admin_email'] = admin['email']

    flash(
        "Login Successful!",
        "success"
    )

    return redirect('/admin-dashboard')


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route('/admin-dashboard')
def admin_dashboard():

    if 'admin_id' not in session:

        flash(
            "Please login to access dashboard!",
            "danger"
        )

        return redirect('/admin-login')

    return render_template(
        "admin/dashboard.html",
        admin_name=session['admin_name']
    )


# =========================================================
# ADMIN LOGOUT
# =========================================================

@app.route('/admin-logout')
def admin_logout():

    session.pop('admin_id', None)
    session.pop('admin_name', None)
    session.pop('admin_email', None)

    flash(
        "Logged out successfully.",
        "success"
    )

    return redirect('/admin-login')


# =========================================================
# IMAGE UPLOAD PATHS
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads', 'product_images')
ADMIN_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads', 'admin_profiles')
USER_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads', 'user_profiles')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(ADMIN_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(USER_UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ADMIN_UPLOAD_FOLDER'] = ADMIN_UPLOAD_FOLDER
app.config['USER_UPLOAD_FOLDER'] = USER_UPLOAD_FOLDER


# =========================================================
# ADMIN ADD PRODUCT PAGE
# =========================================================

@app.route(
    '/admin/add-item',
    methods=['GET']
)
def add_item_page():

    if 'admin_id' not in session:

        flash(
            "Please login first!",
            "danger"
        )

        return redirect('/admin-login')

    return render_template(
        "admin/add_item.html"
    )


# =========================================================
# ADMIN ADD PRODUCT
# =========================================================

@app.route(
    '/admin/add-item',
    methods=['POST']
)
def add_item():

    if 'admin_id' not in session:

        flash(
            "Please login first!",
            "danger"
        )

        return redirect('/admin-login')

    name = request.form['name']
    description = request.form['description']
    category = request.form['category']
    price = request.form['price']

    image_file = request.files['image']

    if image_file.filename == "":

        flash(
            "Please upload a product image!",
            "danger"
        )

        return redirect('/admin/add-item')

    filename = secure_filename(
        image_file.filename
    )

    image_path = os.path.join(
        app.config['UPLOAD_FOLDER'],
        filename
    )

    image_file.save(image_path)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO products
        (
            name,
            description,
            category,
            price,
            image
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        name,
        description,
        category,
        price,
        filename
    ))

    conn.commit()

    cursor.close()
    conn.close()

    flash(
        "Product added successfully!",
        "success"
    )

    return redirect('/admin/add-item')


# =========================================================
# ADMIN VIEW SINGLE PRODUCT
# =========================================================

@app.route(
    '/admin/view-item/<int:item_id>'
)
def view_item(item_id):

    if 'admin_id' not in session:

        flash(
            "Please login first!",
            "danger"
        )

        return redirect('/admin-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM products
        WHERE product_id=?
        """,
        (item_id,)
    )

    product = cursor.fetchone()

    cursor.close()
    conn.close()

    if not product:

        flash(
            "Product not found!",
            "danger"
        )

        return redirect('/admin/item-list')

    return render_template(
        "admin/view_item.html",
        product=product
    )


# =========================================================
# ADMIN UPDATE PRODUCT PAGE
# =========================================================

@app.route(
    '/admin/update-item/<int:item_id>',
    methods=['GET']
)
def update_item_page(item_id):

    if 'admin_id' not in session:

        flash(
            "Please login!",
            "danger"
        )

        return redirect('/admin-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM products
        WHERE product_id=?
        """,
        (item_id,)
    )

    product = cursor.fetchone()

    cursor.close()
    conn.close()

    if not product:

        flash(
            "Product not found!",
            "danger"
        )

        return redirect('/admin/item-list')

    return render_template(
        "admin/update_item.html",
        product=product
    )


# =========================================================
# ADMIN UPDATE PRODUCT
# =========================================================

@app.route(
    '/admin/update-item/<int:item_id>',
    methods=['POST']
)
def update_item(item_id):

    if 'admin_id' not in session:

        flash(
            "Please login!",
            "danger"
        )

        return redirect('/admin-login')

    name = request.form['name']
    description = request.form['description']
    category = request.form['category']
    price = request.form['price']

    new_image = request.files['image']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM products
        WHERE product_id=?
        """,
        (item_id,)
    )

    product = cursor.fetchone()

    if not product:

        cursor.close()
        conn.close()

        flash(
            "Product not found!",
            "danger"
        )

        return redirect('/admin/item-list')

    old_image_name = product['image']

    if new_image and new_image.filename != "":

        new_filename = secure_filename(
            new_image.filename
        )

        new_image_path = os.path.join(
            app.config['UPLOAD_FOLDER'],
            new_filename
        )

        new_image.save(
            new_image_path
        )

        old_image_path = os.path.join(
            app.config['UPLOAD_FOLDER'],
            old_image_name
        )

        if os.path.exists(old_image_path):
            os.remove(old_image_path)

        final_image_name = new_filename

    else:

        final_image_name = old_image_name

    cursor.execute("""
        UPDATE products
        SET
            name=?,
            description=?,
            category=?,
            price=?,
            image=?
        WHERE product_id=?
    """, (
        name,
        description,
        category,
        price,
        final_image_name,
        item_id
    ))

    conn.commit()

    cursor.close()
    conn.close()

    flash(
        "Product updated successfully!",
        "success"
    )

    return redirect('/admin/item-list')


# =========================================================
# ADMIN PRODUCT LIST
# =========================================================

@app.route('/admin/item-list')
def item_list():

    if 'admin_id' not in session:

        flash(
            "Please login!",
            "danger"
        )

        return redirect('/admin-login')

    search = request.args.get(
        'search',
        ''
    )

    category_filter = request.args.get(
        'category',
        ''
    )

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT DISTINCT category FROM products"
    )

    categories = cursor.fetchall()

    query = (
        "SELECT * FROM products WHERE 1=1"
    )

    params = []

    if search:

        query += " AND name LIKE ?"

        params.append(
            "%" + search + "%"
        )

    if category_filter:

        query += " AND category=?"

        params.append(
            category_filter
        )

    cursor.execute(
        query,
        params
    )

    products = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin/item_list.html",
        products=products,
        categories=categories
    )


# =========================================================
# ADMIN DELETE PRODUCT
# =========================================================

@app.route(
    '/admin/delete-item/<int:item_id>'
)
def delete_item(item_id):

    if 'admin_id' not in session:

        flash(
            "Please login first!",
            "danger"
        )

        return redirect('/admin-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT image
        FROM products
        WHERE product_id=?
        """,
        (item_id,)
    )

    product = cursor.fetchone()

    if not product:

        cursor.close()
        conn.close()

        flash(
            "Product not found!",
            "danger"
        )

        return redirect('/admin/item-list')

    image_name = product['image']

    image_path = os.path.join(
        app.config['UPLOAD_FOLDER'],
        image_name
    )

    if os.path.exists(image_path):
        os.remove(image_path)

    cursor.execute(
        """
        DELETE FROM products
        WHERE product_id=?
        """,
        (item_id,)
    )

    conn.commit()

    cursor.close()
    conn.close()

    flash(
        "Product deleted successfully!",
        "success"
    )

    return redirect('/admin/item-list')


# =========================================================
# ADMIN PROFILE
# =========================================================

@app.route(
    '/admin/profile',
    methods=['GET']
)
def admin_profile():

    if 'admin_id' not in session:

        flash(
            "Please login!",
            "danger"
        )

        return redirect('/admin-login')

    admin_id = session['admin_id']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM admin
        WHERE admin_id=?
        """,
        (admin_id,)
    )

    admin = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template(
        "admin/admin_profile.html",
        admin=admin
    )


# =========================================================
# UPDATE ADMIN PROFILE
# =========================================================

@app.route(
    '/admin/profile',
    methods=['POST']
)
def admin_profile_update():

    if 'admin_id' not in session:

        flash(
            "Please login!",
            "danger"
        )

        return redirect('/admin-login')

    admin_id = session['admin_id']

    name = request.form['name']
    email = request.form['email']
    new_password = request.form['password']
    new_image = request.files['profile_image']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM admin
        WHERE admin_id=?
        """,
        (admin_id,)
    )

    admin = cursor.fetchone()

    old_image_name = admin['profile_image']

    if new_password:

        hashed_password = bcrypt.hashpw(
            new_password.encode('utf-8'),
            bcrypt.gensalt()
        )

    else:

        hashed_password = admin['password']

    if new_image and new_image.filename != "":

        new_filename = secure_filename(
            new_image.filename
        )

        image_path = os.path.join(
            app.config['ADMIN_UPLOAD_FOLDER'],
            new_filename
        )

        new_image.save(image_path)

        if old_image_name:

            old_image_path = os.path.join(
                app.config['ADMIN_UPLOAD_FOLDER'],
                old_image_name
            )

            if os.path.exists(old_image_path):
                os.remove(old_image_path)

        final_image_name = new_filename

    else:

        final_image_name = old_image_name

    cursor.execute("""
        UPDATE admin
        SET
            name=?,
            email=?,
            password=?,
            profile_image=?
        WHERE admin_id=?
    """, (
        name,
        email,
        hashed_password,
        final_image_name,
        admin_id
    ))

    conn.commit()

    cursor.close()
    conn.close()

    session['admin_name'] = name
    session['admin_email'] = email

    flash(
        "Profile updated successfully!",
        "success"
    )

    return redirect('/admin/profile')


# =========================================================
# USER SIGNUP
# =========================================================

@app.route(
    '/user-signup',
    methods=['GET', 'POST']
)
def user_signup():

    if request.method == "GET":

        return render_template(
            "user/user_signup.html"
        )

    name = request.form['name']
    email = request.form['email']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT admin_id
        FROM admin
        WHERE email=?
        """,
        (email,)
    )

    existing_user = cursor.fetchone()

    cursor.close()
    conn.close()

    if existing_user:

        flash(
            "This email is already registered. "
            "Please login instead.",
            "danger"
        )

        return redirect('/user-login')

    session['signup_name'] = name
    session['signup_email'] = email

    otp = random.randint(
        100000,
        999999
    )

    session['otp'] = otp

    try:
        message = Message(
            subject="SmartCart User OTP",
            sender=getattr(config, 'MAIL_USERNAME', 'kavithapolana19@gmail.com'),
            recipients=[email]
        )
        message.body = f"Your OTP for SmartCart user registration is: {otp}"
        mail.send(message)
        flash("OTP sent to your email!", "success")
    except Exception as e:
        app.logger.warning("SMTP Error: %s", str(e))
        flash(f"OTP generated: {otp} (Use this OTP to complete registration)", "info")

    return redirect('/user/verify-otp')


# =========================================================
# USER OTP PAGE
# =========================================================

@app.route(
    '/user/verify-otp',
    methods=['GET']
)
def verify_user_otp_get():

    return render_template(
        "user/verify_otp.html"
    )


# =========================================================
# USER VERIFY OTP
# =========================================================

@app.route(
    '/user/verify-otp',
    methods=['POST']
)
def verify_user_otp_post():

    user_otp = request.form['otp']
    password = request.form['password']

    if str(session.get('otp')) != str(user_otp):

        flash(
            "Invalid OTP. Try again!",
            "danger"
        )

        return redirect('/user/verify-otp')

    hashed_password = bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    )

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO admin
        (name, email, password)
        VALUES (?, ?, ?)
    """, (
        session['signup_name'],
        session['signup_email'],
        hashed_password
    ))

    conn.commit()

    cursor.close()
    conn.close()

    session.pop('otp', None)
    session.pop('signup_name', None)
    session.pop('signup_email', None)

    flash(
        "User Registered Successfully!",
        "success"
    )

    return redirect('/user-login')


# =========================================================
# USER LOGIN
# =========================================================

@app.route(
    '/user-login',
    methods=['GET', 'POST']
)
def user_login():

    if request.method == 'GET':

        return render_template(
            "user/user_login.html"
        )

    email = request.form['email']
    password = request.form['password']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM admin
        WHERE email=?
        """,
        (email,)
    )

    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if user is None:

        flash(
            "Email not found! Please register first.",
            "danger"
        )

        return redirect('/user-login')

    stored_hashed_password = (
        user['password'].encode('utf-8')
    )

    if not bcrypt.checkpw(
        password.encode('utf-8'),
        stored_hashed_password
    ):

        flash(
            "Incorrect password! Try again.",
            "danger"
        )

        return redirect('/user-login')

    session['user_id'] = user['admin_id']
    session['user_name'] = user['name']
    session['user_email'] = user['email']

    # -----------------------------------------------------
    # RESTORE THIS USER'S CART FROM DATABASE
    # -----------------------------------------------------

    session['cart'] = load_user_cart(
        session['user_id']
    )

    flash(
        "Login Successful!",
        "success"
    )

    return redirect('/user-dashboard')


# =========================================================
# USER DASHBOARD
# =========================================================

@app.route('/user-dashboard')
def user_dashboard():

    if 'user_id' not in session:

        flash(
            "Please login!",
            "danger"
        )

        return redirect('/user-login')

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM products ORDER BY product_id DESC LIMIT 12")
    featured_products = cursor.fetchall()

    cursor.execute("SELECT DISTINCT category FROM products")
    categories = cursor.fetchall()

    cursor.execute("""
        SELECT * FROM user_addresses
        WHERE user_id = ?
        ORDER BY is_default DESC, address_id DESC
        LIMIT 1
    """, (user_id,))
    default_address = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template(
        "user/user_dashboard.html",
        user_name=session.get('user_name'),
        products=featured_products,
        categories=categories,
        default_address=default_address
    )


# =========================================================
# USER PROFILE
# =========================================================

@app.route('/user/profile', methods=['GET'])
def user_profile():

    if 'user_id' not in session:

        flash(
            "Please login!",
            "danger"
        )

        return redirect('/user-login')

    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM admin
        WHERE admin_id=?
        """,
        (user_id,)
    )

    user = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template(
        "user/user_profile.html",
        user=user
    )


# =========================================================
# UPDATE USER PROFILE
# =========================================================

@app.route('/user/profile', methods=['POST'])
def user_profile_update():

    if 'user_id' not in session:

        flash(
            "Please login!",
            "danger"
        )

        return redirect('/user-login')

    user_id = session['user_id']

    name = request.form['name']
    email = request.form['email']
    new_password = request.form.get('password', '')
    new_image = request.files.get('profile_image')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM admin
        WHERE admin_id=?
        """,
        (user_id,)
    )

    user = cursor.fetchone()

    old_image_name = user['profile_image'] if user else None

    if new_password:

        hashed_password = bcrypt.hashpw(
            new_password.encode('utf-8'),
            bcrypt.gensalt()
        )

    else:

        hashed_password = user['password'] if user else None

    if new_image and new_image.filename != "":

        new_filename = secure_filename(
            new_image.filename
        )

        image_path = os.path.join(
            app.config['USER_UPLOAD_FOLDER'],
            new_filename
        )

        new_image.save(image_path)

        if old_image_name:

            old_image_path = os.path.join(
                app.config['USER_UPLOAD_FOLDER'],
                old_image_name
            )

            if os.path.exists(old_image_path):
                os.remove(old_image_path)

        final_image_name = new_filename

    else:

        final_image_name = old_image_name

    cursor.execute("""
        UPDATE admin
        SET
            name=?,
            email=?,
            password=?,
            profile_image=?
        WHERE admin_id=?
    """, (
        name,
        email,
        hashed_password,
        final_image_name,
        user_id
    ))

    conn.commit()

    cursor.close()
    conn.close()

    session['user_name'] = name
    session['user_email'] = email

    flash(
        "Profile updated successfully!",
        "success"
    )

    return redirect('/user/profile')


# =========================================================
# USER VIEW PRODUCTS
# =========================================================

@app.route('/user/products')
def user_products():

    if 'user_id' not in session:

        flash(
            "Please login!",
            "danger"
        )

        return redirect('/user-login')

    search = request.args.get(
        'search',
        ''
    )

    category_filter = request.args.get(
        'category',
        ''
    )

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT DISTINCT category FROM products"
    )

    categories = cursor.fetchall()

    query = (
        "SELECT * FROM products WHERE 1=1"
    )

    params = []

    if search:

        query += " AND name LIKE ?"

        params.append(
            "%" + search + "%"
        )

    if category_filter:

        query += " AND category=?"

        params.append(
            category_filter
        )

    cursor.execute(
        query,
        params
    )

    products = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "user/user_products.html",
        products=products,
        categories=categories
    )


# =========================================================
# USER VIEW SINGLE PRODUCT
# =========================================================

@app.route(
    '/user/user-view-item/<int:product_id>'
)
def user_view_item(product_id):

    if 'user_id' not in session:

        flash(
            "Please login!",
            "danger"
        )

        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM products
        WHERE product_id=?
        """,
        (product_id,)
    )

    product = cursor.fetchone()

    cursor.close()
    conn.close()

    if not product:

        flash(
            "Product not found!",
            "danger"
        )

        return redirect('/user/products')

    return render_template(
        "user/user_view_item.html",
        product=product
    )


# =========================================================
# USER ADD TO CART
# =========================================================

@app.route(
    '/user/add-to-cart/<int:product_id>'
)
def add_to_cart(product_id):

    if 'user_id' not in session:

        flash(
            "Please login first!",
            "danger"
        )

        return redirect('/user-login')

    if 'cart' not in session:
        session['cart'] = {}

    cart = session['cart']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM products
        WHERE product_id=?
        """,
        (product_id,)
    )

    product = cursor.fetchone()

    cursor.close()
    conn.close()

    if not product:

        flash(
            "Product not found!",
            "danger"
        )

        return redirect('/user/products')

    pid = str(product_id)

    if pid in cart:

        cart[pid]['quantity'] += 1

    else:

        cart[pid] = {
            'name': product['name'],
            'price': float(product['price']),
            'image': product['image'],
            'quantity': 1
        }

    session['cart'] = cart

    # Save permanently
    save_user_cart(
        session['user_id'],
        cart
    )

    flash(
        "Item added to cart!",
        "success"
    )

    return redirect(
        request.referrer or '/user/products'
    )


# =========================================================
# USER VIEW CART
# =========================================================

@app.route('/user/cart')
def view_cart():

    if 'user_id' not in session:

        flash(
            "Please login first!",
            "danger"
        )

        return redirect('/user-login')

    cart = session.get('cart', {})

    grand_total = sum(
        item['price'] * item['quantity']
        for item in cart.values()
    )

    return render_template(
        "user/cart.html",
        cart=cart,
        grand_total=grand_total
    )


# =========================================================
# NORMAL INCREASE QUANTITY
# =========================================================

@app.route(
    '/user/cart/increase/<pid>'
)
def increase_quantity(pid):

    if 'user_id' not in session:
        return redirect('/user-login')

    cart = session.get('cart', {})

    if pid in cart:

        cart[pid]['quantity'] += 1

        session['cart'] = cart

        save_user_cart(
            session['user_id'],
            cart
        )

    return redirect('/user/cart')


# =========================================================
# NORMAL DECREASE QUANTITY
# =========================================================

@app.route(
    '/user/cart/decrease/<pid>'
)
def decrease_quantity(pid):

    if 'user_id' not in session:
        return redirect('/user-login')

    cart = session.get('cart', {})

    if pid in cart:

        cart[pid]['quantity'] -= 1

        if cart[pid]['quantity'] <= 0:
            cart.pop(pid)

        session['cart'] = cart

        save_user_cart(
            session['user_id'],
            cart
        )

    return redirect('/user/cart')


# =========================================================
# REMOVE FROM CART
# =========================================================

@app.route(
    '/user/cart/remove/<pid>'
)
def remove_from_cart(pid):

    if 'user_id' not in session:
        return redirect('/user-login')

    cart = session.get('cart', {})

    if pid in cart:

        cart.pop(pid)

        session['cart'] = cart

        save_user_cart(
            session['user_id'],
            cart
        )

        flash(
            "Item removed from cart!",
            "success"
        )

    return redirect('/user/cart')


# =========================================================
# AJAX ADD TO CART
# =========================================================

@app.route(
    '/user/add-to-cart-ajax/<int:product_id>'
)
def add_to_cart_ajax(product_id):

    if 'user_id' not in session:

        return {
            "error": "not_logged_in"
        }, 401

    if 'cart' not in session:
        session['cart'] = {}

    cart = session['cart']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM products
        WHERE product_id=?
        """,
        (product_id,)
    )

    product = cursor.fetchone()

    cursor.close()
    conn.close()

    if not product:

        return {
            "error": "Product not found"
        }, 404

    pid = str(product_id)

    if pid in cart:

        cart[pid]['quantity'] += 1

    else:

        cart[pid] = {
            'name': product['name'],
            'price': float(product['price']),
            'image': product['image'],
            'quantity': 1
        }

    session['cart'] = cart

    # Save permanently
    save_user_cart(
        session['user_id'],
        cart
    )

    return {
        "message": "Item added to cart!",
        "cart_count": len(cart)
    }


# =========================================================
# AJAX INCREASE QUANTITY
# =========================================================

@app.route(
    '/user/cart/increase-ajax/<pid>'
)
def increase_quantity_ajax(pid):

    if 'user_id' not in session:

        return {
            "error": "not_logged_in"
        }, 401

    cart = session.get('cart', {})

    if pid not in cart:

        return {
            "error": "Product not found in cart"
        }, 404

    cart[pid]['quantity'] += 1

    session['cart'] = cart

    save_user_cart(
        session['user_id'],
        cart
    )

    item = cart[pid]

    item_total = (
        float(item['price']) *
        int(item['quantity'])
    )

    return {
        "success": True,
        "quantity": item['quantity'],
        "item_total": item_total
    }


# =========================================================
# AJAX DECREASE QUANTITY
# =========================================================

@app.route(
    '/user/cart/decrease-ajax/<pid>'
)
def decrease_quantity_ajax(pid):

    if 'user_id' not in session:

        return {
            "error": "not_logged_in"
        }, 401

    cart = session.get('cart', {})

    if pid not in cart:

        return {
            "error": "Product not found in cart"
        }, 404

    cart[pid]['quantity'] -= 1

    if cart[pid]['quantity'] <= 0:

        cart.pop(pid)

        session['cart'] = cart

        save_user_cart(
            session['user_id'],
            cart
        )

        return {
            "success": True,
            "removed": True
        }

    session['cart'] = cart

    save_user_cart(
        session['user_id'],
        cart
    )

    item = cart[pid]

    item_total = (
        float(item['price']) *
        int(item['quantity'])
    )

    return {
        "success": True,
        "quantity": item['quantity'],
        "item_total": item_total
    }


# =========================================================
# USER BUY NOW
# =========================================================

@app.route(
    '/user/buy-now/<int:product_id>'
)
def buy_now(product_id):

    if 'user_id' not in session:

        flash(
            "Please login first!",
            "danger"
        )

        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM products
        WHERE product_id=?
        """,
        (product_id,)
    )

    product = cursor.fetchone()

    cursor.close()
    conn.close()

    if not product:

        flash(
            "Product not found!",
            "danger"
        )

        return redirect('/user/products')

    # Buy Now = only this product
    session['selected_products'] = [
        str(product_id)
    ]

    session['selected_total'] = float(
        product['price']
    )

    session['purchase_mode'] = 'buy_now'

    return redirect('/user/address')


# =========================================================
# USER ADDRESS PAGE
# ONE ROUTE ONLY - GET + POST
# =========================================================

@app.route(
    '/user/address',
    methods=['GET', 'POST']
)
def user_address():

    if 'user_id' not in session:

        flash(
            "Please login first!",
            "danger"
        )

        return redirect('/user-login')


    # -----------------------------------------------------
    # COMING FROM CART
    # -----------------------------------------------------

    if request.method == 'POST':

        selected_products = request.form.getlist(
            'selected_products'
        )

        if not selected_products:

            flash(
                "Please select at least one product.",
                "danger"
            )

            return redirect('/user/cart')


        cart = session.get(
            'cart',
            {}
        )

        valid_products = []

        selected_total = 0


        for pid in selected_products:

            if pid in cart:

                item = cart[pid]

                selected_total += (
                    float(item['price'])
                    *
                    int(item['quantity'])
                )

                valid_products.append(pid)


        if not valid_products:

            flash(
                "Selected products are not available.",
                "danger"
            )

            return redirect('/user/cart')


        session['selected_products'] = (
            valid_products
        )

        session['selected_total'] = (
            selected_total
        )

        session['purchase_mode'] = 'cart'


    # -----------------------------------------------------
    # CHECK PRODUCT SELECTION
    # -----------------------------------------------------

    selected_products = session.get(
        'selected_products',
        []
    )


    if not selected_products:

        flash(
            "Please select a product first.",
            "danger"
        )

        return redirect('/user/products')


    # -----------------------------------------------------
    # GET SAVED ADDRESSES OF CURRENT USER
    # -----------------------------------------------------

    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )


    cursor.execute("""
        SELECT *
        FROM user_addresses

        WHERE user_id=?

        ORDER BY
            is_default DESC,
            address_id DESC
    """, (
        session['user_id'],
    ))


    saved_addresses = (
        cursor.fetchall()
    )


    cursor.close()
    conn.close()


    default_address = None


    for address in saved_addresses:

        if address['is_default']:

            default_address = address

            break


    # If old addresses exist but none is marked default,
    # show the latest one as default.
    if (
        default_address is None
        and saved_addresses
    ):

        default_address = (
            saved_addresses[0]
        )


    return render_template(
        "user/address.html",

        saved_addresses=
            saved_addresses,

        default_address=
            default_address,

        selected_total=
            session.get(
                'selected_total',
                0
            )
    )


# =========================================================
# SELECT SAVED ADDRESS
# =========================================================

@app.route(
    '/user/address/select/<int:address_id>',
    methods=['POST']
)
def select_saved_address(address_id):

    if 'user_id' not in session:

        flash(
            "Please login first!",
            "danger"
        )

        return redirect('/user-login')


    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )


    cursor.execute("""
        SELECT *
        FROM user_addresses

        WHERE address_id=?
        AND user_id=?
    """, (
        address_id,
        session['user_id']
    ))


    address = cursor.fetchone()


    cursor.close()
    conn.close()


    if not address:

        flash(
            "Address not found.",
            "danger"
        )

        return redirect('/user/address')


    session['address_id'] = (
        address['address_id']
    )


    session['delivery_address'] = {

        'full_name':
            address['full_name'],

        'mobile':
            address['mobile'],

        'house_number':
            address['house_number'],

        'area':
            address['area'],

        'landmark':
            address['landmark'] or '',

        'city':
            address['city'],

        'state':
            address['state'],

        'pincode':
            address['pincode']
    }


    return redirect('/user/payment')


# =========================================================
# SET ADDRESS AS DEFAULT
# =========================================================

@app.route(
    '/user/address/default/<int:address_id>',
    methods=['POST']
)
def set_default_address(address_id):

    if 'user_id' not in session:

        return redirect('/user-login')


    conn = get_db_connection()

    cursor = conn.cursor()


    try:

        # First check address belongs to this user

        cursor.execute("""
            SELECT address_id
            FROM user_addresses

            WHERE address_id=?
            AND user_id=?
        """, (
            address_id,
            session['user_id']
        ))


        address = cursor.fetchone()


        if not address:

            flash(
                "Address not found.",
                "danger"
            )

            return redirect('/user/address')


        # Remove previous default

        cursor.execute("""
            UPDATE user_addresses

            SET is_default=0

            WHERE user_id=?
        """, (
            session['user_id'],
        ))


        # Set selected address default

        cursor.execute("""
            UPDATE user_addresses

            SET is_default=1

            WHERE address_id=?
            AND user_id=?
        """, (
            address_id,
            session['user_id']
        ))


        conn.commit()


        flash(
            "Default address updated.",
            "success"
        )


    except Exception:

        conn.rollback()

        app.logger.error(
            traceback.format_exc()
        )

        flash(
            "Unable to update default address.",
            "danger"
        )


    finally:

        cursor.close()
        conn.close()


    return redirect('/user/address')


# =========================================================
# SAVE NEW ADDRESS + CONTINUE
# =========================================================

@app.route(
    '/user/address/continue',
    methods=['POST']
)
def address_continue():

    if 'user_id' not in session:

        flash(
            "Please login first!",
            "danger"
        )

        return redirect('/user-login')


    full_name = request.form[
        'full_name'
    ]

    mobile = request.form[
        'mobile'
    ]

    house_number = request.form[
        'house_number'
    ]

    area = request.form[
        'area'
    ]

    landmark = request.form.get(
        'landmark',
        ''
    )

    city = request.form[
        'city'
    ]

    state = request.form[
        'state'
    ]

    pincode = request.form[
        'pincode'
    ]


    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )


    try:

        # -------------------------------------------------
        # CHECK WHETHER USER ALREADY HAS AN ADDRESS
        # -------------------------------------------------

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM user_addresses
            WHERE user_id=?
        """, (
            session['user_id'],
        ))


        result = cursor.fetchone()


        address_count = (
            result['total']
        )


        # First address automatically becomes default

        if address_count == 0:

            is_default = 1

        else:

            is_default = 0


        # -------------------------------------------------
        # SAVE ADDRESS
        # -------------------------------------------------

        cursor.execute("""
            INSERT INTO user_addresses
            (
                user_id,
                full_name,
                mobile,
                house_number,
                area,
                landmark,
                city,
                state,
                pincode,
                is_default
            )

            VALUES
            (
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?
            )
        """, (
            session['user_id'],
            full_name,
            mobile,
            house_number,
            area,
            landmark,
            city,
            state,
            pincode,
            is_default
        ))


        conn.commit()


        address_id = (
            cursor.lastrowid
        )


    except Exception:

        conn.rollback()


        app.logger.error(
            traceback.format_exc()
        )


        flash(
            "Unable to save address.",
            "danger"
        )


        return redirect('/user/address')


    finally:

        cursor.close()
        conn.close()


    session['address_id'] = (
        address_id
    )


    session['delivery_address'] = {

        'full_name':
            full_name,

        'mobile':
            mobile,

        'house_number':
            house_number,

        'area':
            area,

        'landmark':
            landmark,

        'city':
            city,

        'state':
            state,

        'pincode':
            pincode
    }


    return redirect('/user/payment')


# =========================================================
# UPDATE EXISTING ADDRESS
# =========================================================

@app.route('/user/address/update/<int:address_id>', methods=['POST'])
def address_update(address_id):

    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    full_name = request.form.get('full_name')
    mobile = request.form.get('mobile')
    house_number = request.form.get('house_number')
    area = request.form.get('area')
    landmark = request.form.get('landmark', '')
    city = request.form.get('city')
    state = request.form.get('state')
    pincode = request.form.get('pincode')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            UPDATE user_addresses
            SET full_name=?, mobile=?, house_number=?, area=?, landmark=?, city=?, state=?, pincode=?
            WHERE address_id=? AND user_id=?
        """, (
            full_name, mobile, house_number, area, landmark, city, state, pincode,
            address_id, session['user_id']
        ))
        conn.commit()

        session['address_id'] = address_id
        session['delivery_address'] = {
            'full_name': full_name,
            'mobile': mobile,
            'house_number': house_number,
            'area': area,
            'landmark': landmark,
            'city': city,
            'state': state,
            'pincode': pincode
        }

        flash("Address updated successfully!", "success")
        return redirect('/user/payment')

    except Exception:
        conn.rollback()
        app.logger.error(traceback.format_exc())
        flash("Unable to update address.", "danger")
        return redirect('/user/address')

    finally:
        cursor.close()
        conn.close()


# =========================================================
# DELETE SAVED ADDRESS
# =========================================================

@app.route('/user/address/delete/<int:address_id>', methods=['POST', 'GET'])
def address_delete(address_id):

    if 'user_id' not in session:
        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            DELETE FROM user_addresses
            WHERE address_id=? AND user_id=?
        """, (address_id, session['user_id']))
        conn.commit()
        flash("Address deleted successfully.", "info")

    except Exception:
        conn.rollback()
        flash("Unable to delete address.", "danger")

    finally:
        cursor.close()
        conn.close()

    return redirect('/user/address')


# =========================================================
# RAZORPAY PAYMENT PAGE
# =========================================================

@app.route('/user/payment')
def user_payment():

    if 'user_id' not in session:

        flash(
            "Please login first!",
            "danger"
        )

        return redirect('/user-login')


    selected_products = session.get(
        'selected_products',
        []
    )


    purchase_mode = session.get(
        'purchase_mode'
    )


    address = session.get(
        'delivery_address'
    )


    if not selected_products:

        flash(
            "No products selected.",
            "danger"
        )

        return redirect('/user/products')


    if not address:

        flash(
            "Please select or enter delivery address.",
            "danger"
        )

        return redirect('/user/address')


    # -----------------------------------------------------
    # CALCULATE TOTAL AGAIN FROM DATABASE
    # -----------------------------------------------------

    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )


    total = 0.0

    cart = session.get(
        'cart',
        {}
    )


    try:

        for pid in selected_products:

            cursor.execute("""
                SELECT
                    product_id,
                    name,
                    price

                FROM products

                WHERE product_id=?
            """, (
                int(pid),
            ))


            product = (
                cursor.fetchone()
            )


            if not product:

                continue


            if purchase_mode == 'cart':

                if str(pid) not in cart:

                    continue


                quantity = int(
                    cart[str(pid)][
                        'quantity'
                    ]
                )


            elif purchase_mode == 'buy_now':

                quantity = 1


            else:

                quantity = 0


            total += (
                float(product['price'])
                *
                quantity
            )


    finally:

        cursor.close()
        conn.close()


    if total <= 0:

        flash(
            "Invalid order amount.",
            "danger"
        )

        return redirect('/user/products')


    session['selected_total'] = total


    amount_in_paise = int(
        round(
            total * 100
        )
    )


    order_data = {

        "amount":
            amount_in_paise,

        "currency":
            "INR",

        "receipt":
            (
                "smartcart_"
                +
                str(
                    session['user_id']
                )
                +
                "_"
                +
                str(
                    random.randint(
                        1000,
                        9999
                    )
                )
            )
    }


    try:

        razorpay_order = (
            razorpay_client.order.create(
                data=order_data
            )
        )


    except Exception:

        app.logger.error(
            traceback.format_exc()
        )


        flash(
            "Unable to start payment. "
            "Please try again.",
            "danger"
        )


        return redirect('/user/cart')


    session['razorpay_order_id'] = (
        razorpay_order['id']
    )


    return render_template(
        "user/payment.html",

        razorpay_key_id=
            config.RAZORPAY_KEY_ID,

        razorpay_order_id=
            razorpay_order['id'],

        amount=
            amount_in_paise,

        total=
            total,

        user_name=
            address['full_name'],

        user_email=
            session.get(
                'user_email',
                ''
            ),

        user_mobile=
            address['mobile']
    )


# =========================================================
# VERIFY RAZORPAY PAYMENT
# SAVE ORDER + ORDER ITEMS
# =========================================================

@app.route(
    '/user/payment-success',
    methods=['POST']
)
def payment_success():

    if 'user_id' not in session:

        return {
            "success": False,
            "error": "not_logged_in"
        }, 401


    data = (
        request.get_json(
            silent=True
        )
        or request.form
    )


    razorpay_payment_id = (
        data.get(
            'razorpay_payment_id'
        )
    )


    razorpay_order_id = (
        data.get(
            'razorpay_order_id'
        )
    )


    razorpay_signature = (
        data.get(
            'razorpay_signature'
        )
    )


    server_order_id = session.get(
        'razorpay_order_id'
    )


    # -----------------------------------------------------
    # CHECK PAYMENT DATA
    # -----------------------------------------------------

    if not (
        razorpay_payment_id
        and razorpay_order_id
        and razorpay_signature
        and server_order_id
    ):

        return {
            "success": False,
            "error": "Missing payment details."
        }, 400


    if (
        razorpay_order_id
        != server_order_id
    ):

        return {
            "success": False,
            "error": "Invalid order."
        }, 400


    # -----------------------------------------------------
    # VERIFY RAZORPAY SIGNATURE
    # -----------------------------------------------------

    try:

        razorpay_client.utility.verify_payment_signature({

            'razorpay_order_id':
                server_order_id,

            'razorpay_payment_id':
                razorpay_payment_id,

            'razorpay_signature':
                razorpay_signature
        })


    except Exception:

        app.logger.error(
            "Payment verification failed:\n%s",
            traceback.format_exc()
        )


        return {
            "success": False,
            "error":
                "Payment verification failed."
        }, 400


    user_id = session[
        'user_id'
    ]


    selected_products = [

        str(pid)

        for pid in session.get(
            'selected_products',
            []
        )
    ]


    purchase_mode = session.get(
        'purchase_mode'
    )


    address_id = session.get(
        'address_id'
    )


    if not selected_products:

        return {
            "success": False,
            "error":
                "Checkout session expired."
        }, 400


    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )


    try:

        # -------------------------------------------------
        # DUPLICATE PAYMENT CHECK
        # -------------------------------------------------

        cursor.execute("""
            SELECT order_id

            FROM orders

            WHERE razorpay_payment_id=?

            LIMIT 1
        """, (
            razorpay_payment_id,
        ))


        existing_order = (
            cursor.fetchone()
        )


        if existing_order:

            existing_order_id = (
                existing_order[
                    'order_id'
                ]
            )


            session[
                'last_order_id'
            ] = existing_order_id


            session[
                'payment_verified'
            ] = True


            return {

                "success":
                    True,

                "order_id":
                    existing_order_id,

                "redirect_url":
                    (
                        "/user/order-success/"
                        +
                        str(
                            existing_order_id
                        )
                    )
            }


        # -------------------------------------------------
        # BUILD ORDER ITEMS
        # -------------------------------------------------

        order_items_to_save = []

        total_amount = 0.0


        cart = session.get(
            'cart',
            {}
        )


        for pid in selected_products:

            cursor.execute("""
                SELECT
                    product_id,
                    name,
                    price

                FROM products

                WHERE product_id=?
            """, (
                int(pid),
            ))


            product = (
                cursor.fetchone()
            )


            if not product:

                continue


            # ---------------------------------------------
            # CART PURCHASE
            # ---------------------------------------------

            if purchase_mode == 'cart':

                if pid not in cart:

                    continue


                quantity = int(
                    cart[pid][
                        'quantity'
                    ]
                )


            # ---------------------------------------------
            # BUY NOW PURCHASE
            # ---------------------------------------------

            elif purchase_mode == 'buy_now':

                quantity = 1


            else:

                conn.rollback()


                return {
                    "success": False,
                    "error":
                        "Invalid purchase mode."
                }, 400


            price = float(
                product['price']
            )


            total_amount += (
                price * quantity
            )


            order_items_to_save.append({

                'product_id':
                    product[
                        'product_id'
                    ],

                'product_name':
                    product[
                        'name'
                    ],

                'quantity':
                    quantity,

                'price':
                    price
            })


        if not order_items_to_save:

            conn.rollback()


            return {
                "success": False,
                "error":
                    "No valid products found."
            }, 400


        # -------------------------------------------------
        # VERIFY PAYMENT AMOUNT
        # -------------------------------------------------

        razorpay_order_details = (
            razorpay_client.order.fetch(
                server_order_id
            )
        )


        razorpay_amount = int(
            razorpay_order_details[
                'amount'
            ]
        )


        expected_amount = int(
            round(
                total_amount * 100
            )
        )


        if (
            razorpay_amount
            != expected_amount
        ):

            conn.rollback()


            return {
                "success": False,
                "error":
                    "Payment amount mismatch."
            }, 400


        # -------------------------------------------------
        # INSERT ORDER
        # -------------------------------------------------

        cursor.execute("""
            INSERT INTO orders
            (
                user_id,
                address_id,
                razorpay_order_id,
                razorpay_payment_id,
                amount,
                payment_status
            )

            VALUES
            (
                ?,
                ?,
                ?,
                ?,
                ?,
                ?
            )
        """, (
            user_id,
            address_id,
            server_order_id,
            razorpay_payment_id,
            total_amount,
            'paid'
        ))


        order_db_id = (
            cursor.lastrowid
        )


        # -------------------------------------------------
        # INSERT ORDER ITEMS
        # -------------------------------------------------

        for item in order_items_to_save:

            cursor.execute("""
                INSERT INTO order_items
                (
                    order_id,
                    product_id,
                    product_name,
                    quantity,
                    price
                )

                VALUES
                (
                    ?,
                    ?,
                    ?,
                    ?,
                    ?
                )
            """, (
                order_db_id,

                item[
                    'product_id'
                ],

                item[
                    'product_name'
                ],

                item[
                    'quantity'
                ],

                item[
                    'price'
                ]
            ))


        # -------------------------------------------------
        # REMOVE ONLY PURCHASED CART ITEMS
        # SAME DATABASE TRANSACTION
        # -------------------------------------------------

        if purchase_mode == 'cart':

            for pid in selected_products:

                cursor.execute("""
                    DELETE FROM cart_items

                    WHERE user_id=?
                    AND product_id=?
                """, (
                    user_id,
                    int(pid)
                ))


        # Order + order items + cart cleanup
        # all succeed together.
        conn.commit()


    except Exception:

        conn.rollback()


        app.logger.error(
            "Order storage failed:\n%s",
            traceback.format_exc()
        )


        return {
            "success": False,
            "error":
                "Order could not be saved."
        }, 500


    finally:

        cursor.close()
        conn.close()


    # -----------------------------------------------------
    # UPDATE SESSION CART
    # -----------------------------------------------------

    if purchase_mode == 'cart':

        cart = session.get(
            'cart',
            {}
        )


        for pid in selected_products:

            cart.pop(
                pid,
                None
            )


        session['cart'] = cart


    # -----------------------------------------------------
    # STORE SUCCESS INFORMATION
    # -----------------------------------------------------

    session['payment_id'] = (
        razorpay_payment_id
    )


    session[
        'payment_verified'
    ] = True


    session[
        'last_order_id'
    ] = order_db_id


    # -----------------------------------------------------
    # CLEAR ONLY TEMP CHECKOUT VALUES
    # -----------------------------------------------------

    session.pop(
        'selected_products',
        None
    )

    session.pop(
        'selected_total',
        None
    )

    session.pop(
        'delivery_address',
        None
    )

    session.pop(
        'address_id',
        None
    )

    session.pop(
        'purchase_mode',
        None
    )

    session.pop(
        'razorpay_order_id',
        None
    )


    return {

        "success":
            True,

        "order_id":
            order_db_id,

        "redirect_url":
            (
                "/user/order-success/"
                +
                str(order_db_id)
            )
    }


# =========================================================
# PAYMENT SUCCESS PAGE
# KEEPING YOUR EXISTING FILE
# payment_success.html
# =========================================================

@app.route(
    '/user/payment-success-page'
)
def payment_success_page():

    if 'user_id' not in session:

        return redirect(
            '/user-login'
        )


    if not session.get(
        'payment_verified'
    ):

        return redirect(
            '/user/products'
        )


    order_id = session.get(
        'last_order_id'
    )


    if order_id:

        return redirect(
            '/user/order-success/'
            +
            str(order_id)
        )


    return render_template(
        "user/payment_success.html",

        payment_id=
            session.get(
                'payment_id'
            )
    )


# =========================================================
# ORDER SUCCESS PAGE
# =========================================================

@app.route(
    '/user/order-success/<int:order_db_id>'
)
def order_success(order_db_id):

    if 'user_id' not in session:

        flash(
            "Please login!",
            "danger"
        )

        return redirect('/user-login')


    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )


    # -----------------------------------------------------
    # FETCH THIS USER'S ORDER ONLY
    # -----------------------------------------------------

    cursor.execute("""
        SELECT *
        FROM orders

        WHERE order_id=?
        AND user_id=?
    """, (
        order_db_id,
        session['user_id']
    ))


    order = cursor.fetchone()


    if not order:

        cursor.close()
        conn.close()


        flash(
            "Order not found.",
            "danger"
        )


        return redirect(
            '/user/my-orders'
        )


    # -----------------------------------------------------
    # FETCH PRODUCTS IN ORDER
    # -----------------------------------------------------

    cursor.execute("""
        SELECT *
        FROM order_items

        WHERE order_id=?
    """, (
        order_db_id,
    ))


    items = cursor.fetchall()


    cursor.close()
    conn.close()


    return render_template(
        "user/order_success.html",

        order=order,

        items=items
    )


# =========================================================
# MY ORDERS PAGE
# =========================================================

@app.route('/user/my-orders')
def my_orders():

    if 'user_id' not in session:

        flash(
            "Please login!",
            "danger"
        )

        return redirect('/user-login')


    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )


    cursor.execute("""
        SELECT *
        FROM orders

        WHERE user_id=?

        ORDER BY created_at DESC
    """, (
        session['user_id'],
    ))


    orders = cursor.fetchall()


    cursor.close()
    conn.close()


    return render_template(
        "user/my_orders.html",
        orders=orders
    )


# =========================================================
# DOWNLOAD INVOICE
# =========================================================

@app.route(
    '/user/download-invoice/<int:order_id>'
)
def download_invoice(order_id):

    if 'user_id' not in session:

        flash(
            "Please login!",
            "danger"
        )

        return redirect('/user-login')


    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )


    # -----------------------------------------------------
    # GET ORDER OF LOGGED-IN USER
    # -----------------------------------------------------

    cursor.execute("""
        SELECT *
        FROM orders

        WHERE order_id=?
        AND user_id=?
    """, (
        order_id,
        session['user_id']
    ))


    order = cursor.fetchone()


    if not order:

        cursor.close()
        conn.close()


        flash(
            "Order not found.",
            "danger"
        )


        return redirect(
            '/user/my-orders'
        )


    # -----------------------------------------------------
    # GET ORDER ITEMS
    # -----------------------------------------------------

    cursor.execute("""
        SELECT *
        FROM order_items

        WHERE order_id=?
    """, (
        order_id,
    ))


    items = cursor.fetchall()


    cursor.close()
    conn.close()


    # -----------------------------------------------------
    # CREATE INVOICE HTML
    # -----------------------------------------------------

    html = render_template(
        "user/invoice.html",

        order=order,

        items=items
    )


    # -----------------------------------------------------
    # HTML -> PDF
    # -----------------------------------------------------

    pdf = generate_pdf(
        html
    )


    if not pdf:

        flash(
            "Error generating invoice.",
            "danger"
        )


        return redirect(
            '/user/my-orders'
        )


    # -----------------------------------------------------
    # DOWNLOAD PDF
    # -----------------------------------------------------

    response = make_response(
        pdf.getvalue()
    )


    response.headers[
        'Content-Type'
    ] = 'application/pdf'


    response.headers[
        'Content-Disposition'
    ] = (
        f'attachment; '
        f'filename=invoice_{order_id}.pdf'
    )


    return response


# =========================================================
# USER LOGOUT
# =========================================================

@app.route('/user-logout')
def user_logout():

    if 'user_id' not in session:

        flash(
            "Please login first!",
            "danger"
        )

        return redirect('/user-login')


    # Cart stays permanently in cart_items table.
    # Only browser session is cleared.

    session.pop(
        'user_id',
        None
    )

    session.pop(
        'user_name',
        None
    )

    session.pop(
        'user_email',
        None
    )

    session.pop(
        'cart',
        None
    )

    session.pop(
        'selected_products',
        None
    )

    session.pop(
        'selected_total',
        None
    )

    session.pop(
        'delivery_address',
        None
    )

    session.pop(
        'address_id',
        None
    )

    session.pop(
        'purchase_mode',
        None
    )

    session.pop(
        'razorpay_order_id',
        None
    )

    session.pop(
        'payment_id',
        None
    )

    session.pop(
        'payment_verified',
        None
    )

    session.pop(
        'last_order_id',
        None
    )


    return render_template(
        "user/user_logout.html"
    )


# =========================================================
# RUN APP
# =========================================================

if __name__ == '__main__':

    app.run(
        debug=True
    )