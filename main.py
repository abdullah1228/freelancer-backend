# app.py - Python Flask Backend for Freelancerrr

from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
import datetime
import textwrap  # Import textwrap for dedent

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes - IMPORTANT for connecting frontend

# --- MySQL Database Configuration ---
# IMPORTANT: Replace with your actual MySQL database credentials
DB_CONFIG = {
    'host': 'localhost',  # Or your database host (e.g., '127.0.0.1' or a remote IP)
    'user': 'root',  # Assuming XAMPP default
    'password': '',  # Assuming XAMPP default (empty)
    'database': 'Freelancerrr',
    'auth_plugin': 'mysql_native_password'  # Often needed for modern MySQL/older connectors
}


def get_db_connection():
    """Establishes a new database connection."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to MySQL: {err}")
        return None


# --- Utility Functions ---
def row_to_dict(row, cursor_description):
    """Converts a database row to a dictionary using cursor description."""
    if row is None:
        return None
    columns = [col[0] for col in cursor_description]
    return dict(zip(columns, row))


# --- API Endpoints ---

# User Registration
@app.route('/api/register', methods=['POST'])
def register_user():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')  # WARNING: In a real app, hash this password!
    user_type = data.get('user_type')
    join_date = datetime.date.today().isoformat()

    if not all([name, email, password, user_type]):
        return jsonify({'message': 'Missing required fields'}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Database connection failed'}), 500

    cursor = conn.cursor()
    try:
        # Check if email already exists
        cursor.execute("SELECT user_id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({'message': 'User with this email already exists'}), 409

        sql = "INSERT INTO users (name, email, password, user_type, join_date) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(sql, (name, email, password, user_type, join_date))
        conn.commit()

        # Get the ID of the newly inserted user
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

    cursor = conn.cursor(dictionary=True)  # Use dictionary=True for easier access to column names
    try:
        sql = "SELECT user_id, name, email, user_type, join_date FROM users WHERE email = %s AND password = %s"  # WARNING: Plain text password check
        cursor.execute(sql, (email, password))
        user = cursor.fetchone()

        if user:
            # Convert date object to string for JSON serialization
            if isinstance(user['join_date'], datetime.date):
                user['join_date'] = user['join_date'].isoformat()
            return jsonify({'message': 'Login successful', 'user': user}), 200
        else:
            return jsonify({'message': 'Invalid email or password'}), 401
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
        sql = "SELECT user_id, name, email, user_type, join_date FROM users WHERE user_id = %s"
        cursor.execute(sql, (user_id,))
        user = cursor.fetchone()

        if user:
            if isinstance(user['join_date'], datetime.date):
                user['join_date'] = user['join_date'].isoformat()
            return jsonify(user), 200
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
    category_name = data.get('category')  # Frontend sends category name
    price = data.get('price')

    if not all([user_id, title, description, category_name, price]):
        return jsonify({'message': 'Missing required fields'}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Database connection failed'}), 500

    try:
        # Cursor for SELECT operation to get category_id
        select_cursor = conn.cursor()
        select_cursor.execute("SELECT category_id FROM categories WHERE name = %s", (category_name,))
        category_result = select_cursor.fetchone()

        # Explicitly consume any remaining results to avoid 'Unread result found'
        select_cursor.fetchall()
        select_cursor.close()

        if not category_result:
            # If category name from frontend doesn't exist in categories table
            return jsonify({'message': 'Invalid category provided. Category name not found.'}), 400
        category_id = category_result[0]

        # New cursor for INSERT operation
        insert_cursor = conn.cursor()
        # Corrected INSERT SQL: Ensures 'category_id' is used, not 'category' name.
        # This matches the schema where 'Category_ID' is in 'Gigs' table.
        sql = "INSERT INTO gigs (user_id, title, description, price, category_id) VALUES (%s, %s, %s, %s, %s)"
        insert_cursor.execute(sql, (user_id, title, description, price, category_id))
        conn.commit()
        gig_id = insert_cursor.lastrowid
        insert_cursor.close()

        return jsonify({'message': 'Gig created successfully', 'gig_id': gig_id}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Error creating gig: {err}")
        return jsonify({'message': f'Database error: {err}'}), 500
    finally:
        if conn:
            conn.close()


# Get all Gigs
@app.route('/api/gigs', methods=['GET'])
def get_all_gigs():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        # SELECT SQL for fetching all gigs, joining with categories to get the name
        sql = textwrap.dedent("""
                              SELECT g.gig_id AS id,
                                     g.user_id,
                                     g.title,
                                     g.description,
                                     c.name   AS category, -- Alias 'name' from categories to 'category'
                                     g.price,
                                     g.created_at
                              FROM gigs AS g
                                       JOIN categories AS c ON g.category_id = c.category_id
                              ORDER BY g.created_at DESC
                              """)
        print(f"Executing SQL (get_all_gigs): {sql}")  # Debug print
        cursor.execute(sql)
        gigs = cursor.fetchall()

        # Convert datetime objects to strings for JSON serialization
        for gig in gigs:
            if isinstance(gig['created_at'], datetime.datetime):
                gig['created_at'] = gig['created_at'].isoformat()
            # Ensure price is float
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
        # SELECT SQL for fetching a single gig, joining with categories to get the name
        sql = textwrap.dedent("""
                              SELECT g.gig_id AS id,
                                     g.user_id,
                                     g.title,
                                     g.description,
                                     c.name   AS category, -- Alias 'name' from categories to 'category'
                                     g.price,
                                     g.created_at
                              FROM gigs AS g
                                       JOIN categories AS c ON g.category_id = c.category_id
                              WHERE g.gig_id = %s
                              """)
        print(f"Executing SQL (get_gig_by_id): {sql} with gig_id={gig_id}")  # Debug print
        cursor.execute(sql, (gig_id,))
        gig = cursor.fetchone()

        if gig:
            if isinstance(gig['created_at'], datetime.datetime):
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
    status = 'pending'  # Default status
    order_date = datetime.date.today().isoformat()
    delivery_date = None  # To be set later

    if not all([gig_id, buyer_id, freelancer_id]):
        return jsonify({'message': 'Missing required fields'}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Database connection failed'}), 500

    cursor = conn.cursor()
    try:
        sql = "INSERT INTO orders (gig_id, buyer_id, freelancer_id, status, order_date, delivery_date) VALUES (%s, %s, %s, %s, %s, %s)"
        cursor.execute(sql, (gig_id, buyer_id, freelancer_id, status, order_date, delivery_date))
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
            sql = "SELECT order_id AS id, gig_id, buyer_id, freelancer_id, status, order_date, delivery_date FROM orders WHERE buyer_id = %s"
        elif user_type == 'freelancer':
            sql = "SELECT order_id AS id, gig_id, buyer_id, freelancer_id, status, order_date, delivery_date FROM orders WHERE freelancer_id = %s"
        else:
            return jsonify({'message': 'Invalid user_type'}), 400

        cursor.execute(sql, (user_id,))
        orders = cursor.fetchall()

        # Convert date objects to strings for JSON serialization
        for order in orders:
            if isinstance(order['order_date'], datetime.date):
                order['order_date'] = order['order_date'].isoformat()
            if isinstance(order['delivery_date'], datetime.date):
                order['delivery_date'] = order['delivery_date'].isoformat()
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
            params = [new_status, datetime.date.today().isoformat(), order_id]

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
        # Corrected SQL: Assumes 'order_id' now exists in 'messages' table
        sql = textwrap.dedent("""
                              SELECT message_id AS id,
                                     sender_id,
                                     receiver_id,
                                     message,
                                     sent_at
                              FROM messages
                              WHERE order_id = %s
                              ORDER BY sent_at ASC
                              """)
        print(f"Executing SQL (get_messages_by_order): {sql} with order_id={order_id}")  # Debug print
        cursor.execute(sql, (order_id,))
        messages = cursor.fetchall()

        for msg in messages:
            if isinstance(msg['sent_at'], datetime.datetime):
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
        # Corrected INSERT SQL: Added 'order_id' to the column list and values
        sql = "INSERT INTO messages (order_id, sender_id, receiver_id, message, sent_at) VALUES (%s, %s, %s, %s, NOW())"
        cursor.execute(sql, (order_id, sender_id, receiver_id, message_text))
        conn.commit()
        message_id = cursor.lastrowid
        return jsonify({'message': 'Message sent successfully', 'message_id': message_id}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Error sending message: {err}")
        return jsonify({'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        conn.close()


# Get Reviews by Order ID
@app.route('/api/reviews', methods=['GET'])
def get_reviews_by_order():
    order_id = request.args.get('order_id', type=int)
    if not order_id:
        return jsonify({'message': 'Missing order_id parameter'}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        sql = "SELECT review_id AS id, order_id, rating, comment, review_date FROM reviews WHERE order_id = %s ORDER BY review_date DESC"
        cursor.execute(sql, (order_id,))
        reviews = cursor.fetchall()

        for review in reviews:
            if isinstance(review['review_date'], datetime.date):
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
    review_date = datetime.date.today().isoformat()

    if not all([order_id, reviewer_id, rating]):
        return jsonify({'message': 'Missing required fields'}), 400
    if not (1 <= rating <= 5):
        return jsonify({'message': 'Rating must be between 1 and 5'}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Database connection failed'}), 500

    cursor = conn.cursor()
    try:
        sql = "INSERT INTO reviews (order_id, rating, comment, review_date) VALUES (%s, %s, %s, %s)"
        cursor.execute(sql, (order_id, rating, comment, review_date))
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


# --- NEW: Database Test Endpoint ---
@app.route('/api/test_db', methods=['GET'])
def test_db_connection():
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({'status': 'error', 'message': 'Failed to connect to database. Check DB_CONFIG.'}), 500
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
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


# --- Main execution block ---
if __name__ == '__main__':
    app.run(debug=True, port=5000)
