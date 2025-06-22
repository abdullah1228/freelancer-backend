import mysql.connector
from mysql.connector import pooling
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from datetime import datetime, date
from flask_socketio import SocketIO, emit

app = Flask(__name__)

# IMPORTANT: Database Configuration using Environment Variables
# These variables MUST be set on your Render.com dashboard under the "Environment" tab.
# Example values (replace with your actual MariaDB credentials):
# DB_HOST = 'mariadb-198695-0.cloudclusters.net'
# DB_PORT = '16326' # New: Port for your MariaDB (often non-standard on cloud DBs)
# DB_USER = 'Abdullah2' # Your MariaDB/MySQL Username - UPDATED
# DB_PASSWORD = 'abdullah' # Your MariaDB/MySQL Password - UPDATED
# DB_NAME = 'freelancerrr' # Your MariaDB/MySQL Database Name - UPDATED

# Get database credentials from environment variables, with fallbacks for local development
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = int(os.environ.get('DB_PORT', 3306))
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
DB_NAME = os.environ.get('DB_NAME', 'freelancerrr')

# Setup CORS - Crucial for connecting your GitHub Pages frontend
# This includes both the base domain and the specific repository path for robustness.
# Allow WebSocket origins explicitly for Flask-SocketIO
CORS(app, resources={r"/api/*": {"origins": ["https://abdullah1228.github.io/freelancer-frontend/", "https://abdullah1228.github.io"]}},
     supports_credentials=True)

# Initialize Flask-SocketIO
# async_mode='gevent' or 'eventlet' is recommended for production.
# For simplicity in Render deployment, we'll start with 'threading' if no explicit async library.
# If you have Gunicorn config, ensure it's set up for eventlet/gevent workers.
socketio = SocketIO(app, cors_allowed_origins=["https://abdullah1228.github.io", "https://abdullah1228.github.io/freelancer-frontend/"],
                    message_queue=os.environ.get('REDIS_URL', 'redis://localhost:6379/0'))

# Database Connection Pool
try:
    db_pool = pooling.MySQLConnectionPool(
        pool_name="freelancerrr_pool",
        pool_size=5,
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    print("MySQL connection pool created successfully.")
except mysql.connector.Error as err:
    print(f"Error creating MySQL connection pool: {err}")

def get_db_connection():
    """Gets a connection from the pool."""
    global db_pool
    try:
        return db_pool.get_connection()
    except mysql.connector.Error as err:
        print(f"Error getting connection from pool: {err}. Attempting to recreate pool...")
        try:
            db_pool = pooling.MySQLConnectionPool(
                pool_name="freelancerrr_pool",
                pool_size=5,
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME
            )
            return db_pool.get_connection()
        except mysql.connector.Error as pool_err:
            print(f"Failed to recreate MySQL connection pool: {pool_err}")
            return None

# --- NEW: Simple Test Route for Root URL ---
@app.route('/')
def home():
    return "Hello from Freelancerrr Backend!", 200

# --- API Endpoints ---

# User Registration
@app.route('/api/register', methods=['POST'])
def register_user():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    user_type = data.get('user_type')
    join_date = datetime.now().date().isoformat()

    if not all([name, email, password, user_type]):
        return jsonify({'message': 'Missing required fields'}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT user_id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({'message': 'User with this email already exists'}), 409

        sql = "INSERT INTO users (name, email, password, user_type, created_at) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(sql, (name, email, password, user_type, join_date))
        conn.commit()

        user_id = cursor.lastrowid
        new_user = {
            "user_id": user_id,
            "name": name,
            "email": email,
            "user_type": user_type,
            "join_date": join_date
        }
        return jsonify({'message': 'User registered successfully', 'user': new_user}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Error during user registration: {err}")
        return jsonify({'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        conn.close()


# User Login
@app.route('/api/login', methods=['POST'])
def login_user():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    if not all([email, password]):
        return jsonify({'message': 'Missing email or password'}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        sql = "SELECT user_id, name, email, user_type, created_at FROM users WHERE email = %s AND password = %s"
        cursor.execute(sql, (email, password))
        user = cursor.fetchone()

        if user:
            if isinstance(user['created_at'], (datetime, date)):
                user['created_at'] = user['created_at'].isoformat()

            user_data_for_frontend = {
                "user_id": user['user_id'],
                "name": user['name'],
                "email": user['email'],
                "user_type": user['user_type'],
                "join_date": user['created_at']
            }
            return jsonify({'message': 'Login successful', 'user': user_data_for_frontend}), 200
        else:
            return jsonify({'message': 'Wrong username or password'}), 401
    except mysql.connector.Error as err:
        print(f"Error during user login: {err}")
        return jsonify({'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        conn.close()


# Get User by ID
@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user_by_id(user_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        sql = "SELECT user_id, name, email, user_type, created_at FROM users WHERE user_id = %s"
        cursor.execute(sql, (user_id,))
        user = cursor.fetchone()

        if user:
            if isinstance(user['created_at'], (datetime, date)):
                user['created_at'] = user['created_at'].isoformat()

            user_data_for_frontend = {
                "user_id": user['user_id'],
                "name": user['name'],
                "email": user['email'],
                "user_type": user['user_type'],
                "join_date": user['created_at']
            }
            return jsonify(user_data_for_frontend), 200
        else:
            return jsonify({'message': 'User not found'}), 404
    except mysql.connector.Error as err:
        print(f"Error fetching user: {err}")
        return jsonify({'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        conn.close()


# Create Gig
@app.route('/api/gigs', methods=['POST'])
def create_gig():
    data = request.json
    user_id = data.get('user_id')
    title = data.get('title')
    description = data.get('description')
    category_name = data.get('category')
    price = data.get('price')

    if not all([user_id, title, description, category_name, price]):
        return jsonify({'message': 'Missing required fields'}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT category_id FROM categories WHERE name = %s", (category_name,))
        category_result = cursor.fetchone()

        if not category_result:
            return jsonify({'message': 'Invalid category provided. Category name not found.'}), 400
        category_id = category_result['category_id']

        sql = "INSERT INTO gigs (user_id, title, description, category_id, price) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(sql, (user_id, title, description, category_id, price))
        conn.commit()
        gig_id = cursor.lastrowid

        return jsonify({'message': 'Gig created successfully', 'gig_id': gig_id}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Error creating gig: {err}")
        return jsonify({'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        conn.close()


# Get all Gigs
@app.route('/api/gigs', methods=['GET'])
def get_all_gigs():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        sql = """
            SELECT g.gig_id AS id,
                   g.user_id,
                   g.title,
                   g.description,
                   c.name AS category,
                   g.price,
                   g.created_at
            FROM gigs AS g
            JOIN categories AS c ON g.category_id = c.category_id
            ORDER BY g.created_at DESC
        """
        cursor.execute(sql)
        gigs = cursor.fetchall()

        for gig in gigs:
            if isinstance(gig['created_at'], (datetime, date)):
                gig['created_at'] = gig['created_at'].isoformat()
            gig['price'] = float(gig['price'])
        return jsonify(gigs), 200
    except mysql.connector.Error as err:
        print(f"Error fetching gigs: {err}")
        return jsonify({'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        conn.close()


# Get single Gig by ID
@app.route('/api/gigs/<int:gig_id>', methods=['GET'])
def get_gig_by_id(gig_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        sql = """
            SELECT g.gig_id AS id,
                   g.user_id,
                   g.title,
                   g.description,
                   c.name AS category,
                   g.price,
                   g.created_at
            FROM gigs AS g
            JOIN categories AS c ON g.category_id = c.category_id
            WHERE g.gig_id = %s
        """
        cursor.execute(sql, (gig_id,))
        gig = cursor.fetchone()

        if gig:
            if isinstance(gig['created_at'], (datetime, date)):
                gig['created_at'] = gig['created_at'].isoformat()
            gig['price'] = float(gig['price'])
            return jsonify(gig), 200
        else:
            return jsonify({'message': 'Gig not found'}), 404
    except mysql.connector.Error as err:
        print(f"Error fetching gig: {err}")
        return jsonify({'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        conn.close()


# Get all Categories
@app.route('/api/categories', methods=['GET'])
def get_all_categories():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        sql = "SELECT category_id AS id, name FROM categories"
        cursor.execute(sql)
        categories = cursor.fetchall()
        return jsonify(categories), 200
    except mysql.connector.Error as err:
        print(f"Error fetching categories: {err}")
        return jsonify({'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        conn.close()


# Create Order
@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.json
    gig_id = data.get('gig_id')
    buyer_id = data.get('buyer_id')
    freelancer_id = data.get('freelancer_id')
    status = 'pending'
    order_date = datetime.now().date().isoformat()

    if not all([gig_id, buyer_id, freelancer_id]):
        return jsonify({'message': 'Missing required fields'}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Database connection failed'}), 500

    cursor = conn.cursor()
    try:
        cursor.execute("SELECT gig_id FROM gigs WHERE gig_id = %s", (gig_id,))
        if not cursor.fetchone():
            return jsonify({'message': 'Gig not found'}), 404

        cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (buyer_id,))
        if not cursor.fetchone():
            return jsonify({'message': 'Buyer not found'}), 404

        cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (freelancer_id,))
        if not cursor.fetchone():
            return jsonify({'message': 'Freelancer not found'}), 404

        sql = "INSERT INTO orders (gig_id, buyer_id, freelancer_id, status, order_date) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(sql, (gig_id, buyer_id, freelancer_id, status, order_date))
        conn.commit()
        order_id = cursor.lastrowid
        return jsonify({'message': 'Order created successfully', 'order_id': order_id}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Error creating order: {err}")
        return jsonify({'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        conn.close()


# Get Orders by User ID (buyer_id or freelancer_id)
@app.route('/api/orders', methods=['GET'])
def get_orders_by_user():
    user_id = request.args.get('user_id', type=int)
    user_type = request.args.get('user_type')

    if not user_id or not user_type:
        return jsonify({'message': 'Missing user_id or user_type parameter'}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        if user_type == 'buyer':
            sql = "SELECT order_id AS id, gig_id, buyer_id, freelancer_id, status, order_date, delivery_date FROM orders WHERE buyer_id = %s ORDER BY order_date DESC"
        elif user_type == 'freelancer':
            sql = "SELECT order_id AS id, gig_id, buyer_id, freelancer_id, status, order_date, delivery_date FROM orders WHERE freelancer_id = %s ORDER BY order_date DESC"
        else:
            return jsonify({'message': 'Invalid user_type'}), 400

        cursor.execute(sql, (user_id,))
        orders = cursor.fetchall()

        for order in orders:
            if isinstance(order['order_date'], (datetime, date)):
                order['order_date'] = order['order_date'].isoformat()
            if order['delivery_date'] and isinstance(order['delivery_date'], (datetime, date)):
                order['delivery_date'] = order['delivery_date'].isoformat()
            else:
                order['delivery_date'] = None
        return jsonify(orders), 200
    except mysql.connector.Error as err:
        print(f"Error fetching orders: {err}")
        return jsonify({'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        conn.close()


# Update Order Status
@app.route('/api/orders/<int:order_id>/status', methods=['PUT'])
def update_order_status(order_id):
    data = request.json
    new_status = data.get('status')

    if new_status not in ['pending', 'in_progress', 'completed', 'cancelled']:
        return jsonify({'message': 'Invalid status provided'}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Database connection failed'}), 500

    cursor = conn.cursor()
    try:
        sql = "UPDATE orders SET status = %s WHERE order_id = %s"
        params = [new_status, order_id]
        if new_status == 'completed':
            sql = "UPDATE orders SET status = %s, delivery_date = %s WHERE order_id = %s"
            params = [new_status, datetime.now().date().isoformat(), order_id]

        cursor.execute(sql, tuple(params))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({'message': 'Order not found or no change'}), 404
        return jsonify({'message': f'Order {order_id} status updated to {new_status}'}), 200
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Error updating order status: {err}")
        return jsonify({'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        conn.close()


# Get Messages by Order ID
@app.route('/api/messages', methods=['GET'])
def get_messages_by_order():
    order_id = request.args.get('order_id', type=int)
    if not order_id:
        return jsonify({'message': 'Missing order_id parameter'}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        sql = """
            SELECT message_id AS id,
                   order_id,
                   sender_id,
                   receiver_id,
                   message_text AS message,
                   sent_at
            FROM messages
            WHERE order_id = %s
            ORDER BY sent_at ASC
        """
        cursor.execute(sql, (order_id,))
        messages = cursor.fetchall()

        for msg in messages:
            if isinstance(msg['sent_at'], datetime):
                msg['sent_at'] = msg['sent_at'].isoformat()
        return jsonify(messages), 200
    except mysql.connector.Error as err:
        print(f"Error fetching messages: {err}")
        return jsonify({'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        conn.close()


# Send Message
@app.route('/api/messages', methods=['POST'])
def send_message():
    data = request.json
    order_id = data.get('order_id')
    sender_id = data.get('sender_id')
    receiver_id = data.get('receiver_id')
    message_text = data.get('message')

    if not all([order_id, sender_id, receiver_id, message_text]):
        return jsonify({'message': 'Missing required fields'}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Database connection failed'}), 500

    cursor = conn.cursor()
    try:
        sql = "INSERT INTO messages (order_id, sender_id, receiver_id, message_text, sent_at) VALUES (%s, %s, %s, %s, NOW())"
        cursor.execute(sql, (order_id, sender_id, receiver_id, message_text))
        conn.commit()
        message_id = cursor.lastrowid

        socketio.emit('new_message', {
            'id': message_id,
            'order_id': order_id,
            'sender_id': sender_id,
            'receiver_id': receiver_id,
            'message': message_text,
            'sent_at': datetime.now().isoformat()
        }, room=str(order_id))

        return jsonify({'message': 'Message sent successfully', 'message_id': message_id}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Error sending message: {err}")
        return jsonify({'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        conn.close()


# Get Reviews by Order ID or Gig ID
@app.route('/api/reviews', methods=['GET'])
def get_reviews_by_order():
    order_id = request.args.get('order_id', type=int)
    gig_id = request.args.get('gig_id', type=int)

    if not order_id and not gig_id:
        return jsonify({'message': 'Missing order_id or gig_id parameter'}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        if order_id:
            sql = "SELECT review_id AS id, order_id, reviewer_id, rating, comment, review_date FROM reviews WHERE order_id = %s ORDER BY review_date DESC"
            cursor.execute(sql, (order_id,))
        elif gig_id:
            sql = """
                SELECT r.review_id AS id, r.order_id, r.reviewer_id, r.rating, r.comment, r.review_date
                FROM reviews AS r
                JOIN orders AS o ON r.order_id = o.order_id
                WHERE o.gig_id = %s
                ORDER BY r.review_date DESC
            """
            cursor.execute(sql, (gig_id,))

        reviews = cursor.fetchall()

        for review in reviews:
            if isinstance(review['review_date'], (datetime, date)):
                review['review_date'] = review['review_date'].isoformat()
        return jsonify(reviews), 200
    except mysql.connector.Error as err:
        print(f"Error fetching reviews: {err}")
        return jsonify({'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        conn.close()


# Submit Review
@app.route('/api/reviews', methods=['POST'])
def submit_review():
    data = request.json
    order_id = data.get('order_id')
    reviewer_id = data.get('reviewer_id')
    rating = data.get('rating')
    comment = data.get('comment')
    review_date = datetime.now().date().isoformat()

    if not all([order_id, reviewer_id, rating]):
        return jsonify({'message': 'Missing required fields'}), 400
    if not (1 <= rating <= 5):
        return jsonify({'message': 'Rating must be between 1 and 5'}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Database connection failed'}), 500

    cursor = conn.cursor()
    try:
        sql_check = "SELECT review_id FROM reviews WHERE order_id = %s AND reviewer_id = %s"
        cursor.execute(sql_check, (order_id, reviewer_id))
        if cursor.fetchone():
            return jsonify({'message': 'You have already reviewed this order'}), 409

        sql_insert = "INSERT INTO reviews (order_id, reviewer_id, rating, comment, review_date) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(sql_insert, (order_id, reviewer_id, rating, comment, review_date))
        conn.commit()
        review_id = cursor.lastrowid
        return jsonify({'message': 'Review submitted successfully', 'review_id': review_id}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Error submitting review: {err}")
        return jsonify({'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        conn.close()


# --- Database Test Endpoint (Useful for debugging deployment) ---
@app.route('/api/test_db', methods=['GET'])
def test_db_connection():
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({'status': 'error', 'message': 'Failed to connect to database. Check environment variables and database availability.'}), 500
        cursor = conn.cursor()
        sql = "SELECT COUNT(*) FROM users"
        cursor.execute(sql)
        user_count = cursor.fetchone()[0]
        cursor.close()
        return jsonify({
            'status': 'success',
            'message': 'Successfully connected to Freelancerrr database!',
            'users_in_db': user_count
        }), 200
    except mysql.connector.Error as err:
        print(f"Error during database test: {err}")
        return jsonify({'status': 'error', 'message': f'Database error: {err}'}), 500
    finally:
        if conn:
            conn.close()


# --- SocketIO Event Handlers ---
@socketio.on('connect')
def test_connect():
    print('Client connected')

@socketio.on('disconnect')
def test_disconnect():
    print('Client disconnected')

@socketio.on('join_order_room')
def on_join(data):
    order_id = data['order_id']
    from flask_socketio import join_room
    join_room(str(order_id))
    print(f"Client joined room: {order_id}")
    emit('status', {'msg': f'Joined order room: {order_id}'})


# --- Main execution block ---
if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000)
