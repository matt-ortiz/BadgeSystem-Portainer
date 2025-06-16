# Badging
import os
import pyodbc
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, Response, redirect, url_for, flash, request, session
from flask_bootstrap import Bootstrap
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
from flask_wtf import FlaskForm
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_caching import Cache
import re

from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired
from functools import wraps

from dotenv import load_dotenv
load_dotenv()

from auth import requires_roles

from users import users_data
from people import badged_today
from events import get_all_events, get_calendar_events_range

# Moved config to app.config.update() above

class User(UserMixin):
    def __init__(self, id, role):
        self.id = id
        self.role = role


app = Flask(__name__)

# Enhanced Flask configuration for better session management
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY"),
    
    # Session configuration - More robust settings for TV dashboards
    SESSION_COOKIE_SECURE=False,  # Set to True if using HTTPS
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_NAME='badge_session',  # Custom cookie name to avoid conflicts
    PERMANENT_SESSION_LIFETIME=timedelta(days=365),  # 1 year sessions
    
    # Cache configuration
    CACHE_TYPE="FileSystemCache",
    CACHE_DIR="/app/flask_cache/",
    CACHE_DEFAULT_TIMEOUT=300,
    
    # Additional Flask-Login settings - More robust for long sessions
    REMEMBER_COOKIE_DURATION=timedelta(days=365),  # 365 days
    REMEMBER_COOKIE_SECURE=False,  # Set to True if using HTTPS
    REMEMBER_COOKIE_HTTPONLY=True,
    REMEMBER_COOKIE_NAME='badge_remember',  # Custom remember cookie name
    REMEMBER_COOKIE_REFRESH_EACH_REQUEST=True,  # Refresh remember cookie on each request
)

CORS(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)
cache = Cache(app)

DB_URL = os.getenv("DATABASE_URL")
UID = os.getenv("DATABASE_UID")
DATABASE_PWD = os.getenv("DATABASE_PWD")

login_manager.login_view = "login"  # Specify the name of the login route


from people import ignore_blueprint
# Register the Blueprint
app.register_blueprint(ignore_blueprint)

from calendar_sync import calendar_sync_blueprint
app.register_blueprint(calendar_sync_blueprint)


@login_manager.user_loader
def load_user(user_id):
    """Enhanced user loader with detailed debugging"""
    print(f"[DEBUG] Attempting to load user: {repr(user_id)}")
    try:
        if user_id in users_data:
            user_role = users_data[user_id]["role"]
            print(f"[DEBUG] Successfully loaded user {user_id} with role {user_role}")
            return User(id=user_id, role=user_role)
        else:
            print(f"[DEBUG] User {user_id} not found in users_data. Available users: {list(users_data.keys())}")
            return None
    except Exception as e:
        print(f"[ERROR] Exception loading user {user_id}: {e}")
        import traceback
        traceback.print_exc()
        return None


@login_manager.needs_refresh_handler
def refresh_handler():
    """Handle session refresh - return user to login"""
    return redirect(url_for('login'))


@login_manager.unauthorized_handler
def unauthorized_handler():
    """Handle unauthorized access - check if it's an API call"""
    print(f"[DEBUG] Unauthorized access to {request.path} from {request.remote_addr}")
    print(f"[DEBUG] Current user authenticated: {current_user.is_authenticated}")
    print(f"[DEBUG] Session keys: {list(session.keys())}")
    
    if request.path.startswith('/api/'):
        return jsonify({"error": "Authentication required", "redirect": "/login"}), 401
    else:
        return redirect(url_for('login'))



class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")

# users = {"securitydesk": "securitydesk"}  # Simple in-memory user store

@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = form.username.data
        password = form.password.data

        user_data = users_data.get(user)
        
        # Check if user exists
        if not user_data:
            flash("Invalid credentials", "danger")
            return render_template("login.html", form=form)

        # Check password
        try:
            if bcrypt.check_password_hash(user_data["password"], password):
                user_obj = User(user, user_data["role"])
                
                # Enhanced session setup for TV dashboards
                session.permanent = True
                session.modified = True  # Force session save
                
                # Clear any existing cache issues (temporarily disabled for debugging)
                # try:
                #     cache.clear()
                # except Exception as e:
                #     print(f"Warning: Could not clear cache: {e}")
                
                # Login with remember=True for long sessions
                login_successful = login_user(user_obj, remember=True, duration=timedelta(days=365))
                
                if login_successful:
                    print(f"User {user} logged in successfully with permanent session")
                    flash(f"Welcome back, {user}! Session valid for 1 year.", "success")
                    return redirect(url_for("index"))
                else:
                    print(f"Login failed for user {user} - login_user returned False")
                    flash("Login failed. Please try again.", "danger")
                    return render_template("login.html", form=form)
            else:
                flash("Invalid credentials", "danger")
                return render_template("login.html", form=form)
        except ValueError as e:
            print(f"Password verification error for user {user}: {e}")
            flash("An error occurred. Please try again.", "danger")
            return render_template("login.html", form=form)
        except Exception as e:
            print(f"Unexpected login error for user {user}: {e}")
            flash("An unexpected error occurred. Please try again.", "danger")
            return render_template("login.html", form=form)

    return render_template("login.html", form=form)



@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/protected")
@login_required
def protected_route():
    return "You've accessed the protected route!"

# def requires_roles(*roles):
#     def wrapper(f):
#         @wraps(f)
#         def wrapped(*args, **kwargs):
#             user_info = users_data.get(current_user.get_id())  # Assuming current_user returns a User object with a method get_id()
#             if user_info and user_info['role'] not in roles:
#                 # Flash a message or return an error response
#                 return "Access denied!", 403
#             return f(*args, **kwargs)
#         return wrapped
#     return wrapper



# In-memory storage for demo purposes; in a real-world scenario, you'd use a database.
API_KEYS = {
    "IT_Dashboard": "Wp4GB88gwX4mpbFAj3QyV6e3s",
    "user2": "Wp4GB88gwX4mpbFAj3QyV6e3sasdfaweadfwgadf"
}

def require_api_key(view_function):
    @wraps(view_function)
    def decorated_function(*args, **kwargs):
        if 'api_key' not in request.args:
            return jsonify(error="API key required"), 403
        if request.args['api_key'] not in API_KEYS.values():
            return jsonify(error="Invalid API key"), 403
        return view_function(*args, **kwargs)
    return decorated_function

@app.route('/protected_endpoint', methods=['GET'])
@require_api_key
def protected_endpoint():
    return jsonify(data="This is a protected endpoint")


# Custom decorator for API endpoints that returns JSON instead of redirects
def api_auth_required(roles=None):
    """
    Custom decorator for API endpoints that returns JSON instead of redirects
    """
    if roles is None:
        roles = ['admin', 'superuser']
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({"error": "Authentication required", "redirect": "/login"}), 401
            
            if not hasattr(current_user, 'role') or current_user.role not in roles:
                return jsonify({"error": "Insufficient privileges"}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# Add an auth status endpoint for frontend checking
@app.route('/api/auth/status')
def auth_status():
    """
    Simple endpoint to check authentication status
    """
    return jsonify({
        "authenticated": current_user.is_authenticated,
        "role": getattr(current_user, 'role', None) if current_user.is_authenticated else None
    })


# Add a route to clear cache if needed
@app.route('/admin/clear-cache')
@login_required
@requires_roles('admin', 'superuser')
def clear_cache():
    """
    Clear application cache - useful for debugging
    """
    try:
        cache.clear()
        flash("Cache cleared successfully", "success")
    except Exception as e:
        flash(f"Error clearing cache: {e}", "danger")
    
    return redirect(request.referrer or url_for('index'))


# Debug route for session information
@app.route('/admin/session-debug')
@login_required
@requires_roles('admin', 'superuser')
def session_debug():
    """
    Show session debug information - useful for troubleshooting
    """
    debug_info = {
        "current_user_authenticated": current_user.is_authenticated,
        "current_user_id": getattr(current_user, 'id', 'No ID'),
        "current_user_role": getattr(current_user, 'role', 'No role'),
        "session_permanent": session.permanent,
        "session_keys": list(session.keys()),
        "permanent_session_lifetime": str(app.config.get('PERMANENT_SESSION_LIFETIME')),
        "remember_cookie_duration": str(app.config.get('REMEMBER_COOKIE_DURATION')),
        "session_cookie_name": app.config.get('SESSION_COOKIE_NAME', 'session'),
        "remember_cookie_name": app.config.get('REMEMBER_COOKIE_NAME', 'remember_token'),
    }
    
    return jsonify(debug_info)








def badging_txn(date=None):
    """
    Retrieve badging transactions from the database.
    Can filter by a specific date if provided.
    
    Args:
        date (str, optional): Date in YYYY-MM-DD format to filter transactions
        
    Returns:
        str: JSON string containing transaction data
    """
    import json
    import pyodbc
    from datetime import datetime, timedelta
    import traceback
    
    try:
        # Connection string
        conn_str = (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            f"SERVER={DB_URL};"
            "DATABASE=multiMAXTxn;"
            f"UID={UID};"
            f"PWD={DATABASE_PWD};"
        )
        
        # Establish connection
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        print(f"Date parameter received: {repr(date)}")  # Debug log with repr() to show exact value
        
        # Remove any caching parameters that might be in the date string
        if date and '_=' in date:
            date = date.split('&')[0]
            print(f"Cleaned date parameter: {date}")
        
        if date:
            try:
                # Convert the provided date string to datetime format
                start_date = datetime.strptime(date, '%Y-%m-%d')
                end_date = start_date + timedelta(days=1)  # Add 1 day to get the end of the day
                
                print(f"Querying for date range: {start_date} to {end_date}")  # Debug log
                
                # SQL query with explicit date format to avoid any confusion
                query = """
                    SELECT DateTimeOfTxn, WhereName, TxnConditionName, CardID, FirstName, LastName
                    FROM AlarmEventTransactionTable
                    WHERE DateTimeOfTxn >= ? AND DateTimeOfTxn < ?
                    ORDER BY TxnID DESC
                """
                print(f"Executing query: {query} with params {start_date}, {end_date}")
                
                cursor.execute(query, (start_date, end_date))
                
            except Exception as e:
                print(f"Error parsing date: {e}")
                print(traceback.format_exc())  # Detailed error traceback
                # If date parsing fails, default to top 10 records
                cursor.execute("""
                    SELECT TOP 10 DateTimeOfTxn, WhereName, TxnConditionName, CardID, FirstName, LastName
                    FROM AlarmEventTransactionTable
                    WHERE CardID IS NOT NULL AND CardID <> ''
                    ORDER BY TxnID DESC
                """)
        else:
            # No date provided, get top 10 records
            cursor.execute("""
                SELECT TOP 10 DateTimeOfTxn, WhereName, TxnConditionName, CardID, FirstName, LastName
                FROM AlarmEventTransactionTable
                WHERE CardID IS NOT NULL AND CardID <> ''
                ORDER BY TxnID DESC
            """)
        
        rows = cursor.fetchall()
        print(f"Fetched {len(rows)} rows from database")  # Debug log
        
        data_list = []
        for row in rows:
            try:
                card_id = row.CardID
                if not card_id:
                    continue
                
                # Get the datetime from the row - handle it carefully
                dt_object = row.DateTimeOfTxn
                print(f"Raw DateTimeOfTxn: {repr(dt_object)}, Type: {type(dt_object)}")
                
                # Different handling based on type
                if isinstance(dt_object, datetime):
                    # Already a datetime object
                    formatted_datetime = dt_object.strftime('%-m/%-d/%Y %I:%M:%S %p')
                elif isinstance(dt_object, str):
                    # String that needs to be parsed
                    dt_object = datetime.strptime(dt_object, '%Y-%m-%d %H:%M:%S')
                    formatted_datetime = dt_object.strftime('%-m/%-d/%Y %I:%M:%S %p')
                else:
                    # Some other format, convert to string first
                    formatted_datetime = str(dt_object)
                
                data = {
                    "DateTimeOfTxn": formatted_datetime,
                    "WhereName": row.WhereName if row.WhereName else "",
                    "TxnConditionName": row.TxnConditionName if row.TxnConditionName else "",
                    "CardNumber": card_id,
                    "Name": f"{row.FirstName if row.FirstName else ''} {row.LastName if row.LastName else ''}"
                }
                data_list.append(data)
            except Exception as e:
                print(f"Error processing row: {e}")
                print(f"Row data: {repr(row)}")
                print(traceback.format_exc())  # Detailed error traceback
                continue
        
        # Convert list to JSON string
        data_json = json.dumps(data_list)
        print(f"Returning {len(data_list)} records as JSON for date: {date}")  # Debug log with date
        
        return data_json
    
    except Exception as e:
        print(f"Database error: {e}")
        print(traceback.format_exc())  # Detailed error traceback
        return json.dumps({"error": str(e)})
    
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            print("Database connection closed")






# Import and set up your get_card_image function here
def get_card_image(card_id):
    conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={DB_URL};"
    "DATABASE=multiMAX;"
    f"UID={UID};"
    f"PWD={DATABASE_PWD};"
    )

    # Establish connection
    conn = pyodbc.connect(conn_str)

    # Create a cursor from the connection
    cursor = conn.cursor()

    # cursor.execute("SELECT CardID, Face FROM CardHolderFaceTable")
    # rows = cursor.fetchall()

    query = f"SELECT CardID, Face FROM CardHolderFaceTable WHERE CardID = '{card_id}'"
    cursor.execute(query)
    row = cursor.fetchone()

    save_directory = 'static/staff/'

    if row:
        card_id = row.CardID
        image_data = row.Face

        # Define the filename based on the CardID
        filename = os.path.join(save_directory, f"{card_id}.jpg")

        # Check if the file already exists
        if not os.path.exists(filename):
            # If not, write the image data to the file
            with open(filename, 'wb') as img_file:
                img_file.write(image_data)

        return filename  # Return the image data

    else:
        return None # CardID not found


    return "image_data_or_path"


# #########################
# IGNORE Functions 
# Includes Building, IT and Front Desk Staff
# Moved to people.py
# #########################



@app.route('/api/events')
def get_events():
    date_str = request.args.get('date')
    events_data = get_all_events(date_str)
    return jsonify(events_data)

@app.route('/events', defaults={'date': None})
@app.route('/events/', defaults={'date': None})
@app.route('/events/<date>')
@app.route('/events/<date>/')
def calendar_page(date=None):
    # Validate date format if provided
    if date:
        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            # If invalid date, redirect to base events page
            return redirect(url_for('calendar_page'))
    return render_template('calendar.html')






@app.route('/get_card_image/<card_id>', methods=['GET'])
@requires_roles('admin', 'superuser')
@login_required
def fetch_card_image(card_id):
    img_path = get_card_image(card_id)
    return jsonify({"img_path": img_path})


@app.route('/api/AMAG/today')
@require_api_key
@cache.cached(timeout=60)
def api_AMAG_today():
    today = badged_today()  # Replace this with your function to get the room data
    return today



@app.route('/api/AMAG/badging')
@cache.cached(timeout=2)
@api_auth_required(['admin', 'superuser'])
def api_AMAG_badging():
    """
    Updated badging API endpoint with better authentication handling
    """
    try:
        # Get the badging data
        badging = badging_txn()
        
        # Parse the JSON string to ensure it's valid
        try:
            parsed_data = json.loads(badging)
            return jsonify(parsed_data)
        except json.JSONDecodeError:
            # If badging_txn returned an error or invalid JSON
            return jsonify({"error": "Invalid data format"}), 500
            
    except Exception as e:
        print(f"Error in api_AMAG_badging: {e}")
        return jsonify({"error": "Internal server error"}), 500


# mainly used for the /activity page
@app.route('/api/AMAG/badging_date')
@cache.cached(timeout=300, key_prefix=lambda: f"badging_date_{request.args.get('date', '')}")
@api_auth_required(['admin', 'superuser'])
def api_AMAG_badging_date():
    """
    Updated badging date API endpoint with better authentication handling
    """
    try:
        date = request.args.get('date')
        badging = badging_txn(date)
        
        # Parse the JSON string to ensure it's valid
        try:
            parsed_data = json.loads(badging)
            return jsonify(parsed_data)
        except json.JSONDecodeError:
            return jsonify({"error": "Invalid data format"}), 500
            
    except Exception as e:
        print(f"Error in api_AMAG_badging_date: {e}")
        return jsonify({"error": "Internal server error"}), 500


# @app.route('/transactions', methods=['GET'])
# @login_required
# @requires_roles('admin', 'superuser')
# def get_transactions():
#     date = request.args.get('date', None)
#     return render_template('transactions.html')


@app.route('/activity', methods=['GET'])
@login_required
@requires_roles('admin', 'superuser')
def get_activity():
    date = request.args.get('date', None)
    return render_template('activity.html')


@app.route('/today')
@requires_roles('admin', 'superuser')
@login_required
def today():
    return render_template('today.html')



@app.route('/')
@requires_roles('admin', 'superuser', 'user')
@login_required
def index():
    # room_info = get_zoom_room_info(access_token)
    return render_template('dashboard.html')


@app.route('/senators', defaults={'date': None})
@app.route('/senators/', defaults={'date': None})
@app.route('/senators/<date>')
@app.route('/senators/<date>/')
def senators_page(date=None):
    # Validate date format if provided
    if date:
        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            # If invalid date, redirect to base senators page
            return redirect(url_for('senators_page'))
    return render_template('senators.html')

@app.route('/api/senators')
def get_senator_events():
    date_str = request.args.get('date')
    events_data = get_all_events(date_str)
    
    # Define search terms for important meetings
    search_terms = [
        "senator", "sen", 
        "chairman", "chair",
        "leader",
        "vice-chair", "vice chair",
        "pac",
        "chief"
    ]
    
    # Filter for senator and leadership events
    senator_events = {
        "events": [
            event for event in events_data["events"]
            if any(term in event["summary"].lower() 
                  for term in search_terms)
        ]
    }
    
    return jsonify(senator_events)

@app.route('/rooms')
def rooms_calendar():
    # Pass the calendar data to the template
    calendar_sources = [
        {
            'id': 'boardroom-a',
            'url': f'/api/calendar/c_18863bgm0phmiif0k8os19o87hgb8@resource.calendar.google.com',
            'color': '#e75480',
            'name': 'Boardroom Suite A'
        },
        {
            'id': 'boardroom-b',
            'url': f'/api/calendar/c_1888u94ghequqibin6rslnjckorf8@resource.calendar.google.com',
            'color': '#FFA500',
            'name': 'Boardroom Suite B'
        },
        {
            'id': 'majority-room',
            'url': f'/api/calendar/c_1880v02okvj4agt1kn4mb7j2hu32u@resource.calendar.google.com',
            'color': '#00A300',
            'name': 'Majority Room'
        },
        {
            'id': 'senate-boardroom',
            'url': f'/api/calendar/c_188et5rt1alm8ghgkbso0kitm6i9g@resource.calendar.google.com',
            'color': '#800080',
            'name': 'Senate Boardroom'
        },
        {
            'id': 'chairman-office',
            'url': f'/api/calendar/c_1889kg01mgd2ogd8mpcej910ui0jq@resource.calendar.google.com',
            'color': '#0000FF',
            'name': "Chairman's Office"
        },
        {
            'id': '2nd-floor-conf',
            'url': f'/api/calendar/c_1884gm72dmd2sh42gh2rg0ffqu4ec@resource.calendar.google.com',
            'color': '#FF4500',
            'name': '2nd Floor Conference Room'
        },
        {
            'id': 'thune-conf',
            'url': f'/api/calendar/c_1884giitap2dci8on6b6bm09jkdre@resource.calendar.google.com',
            'color': '#4B0082',
            'name': 'John Thune Conference Room'
        },
        {
            'id': '3rd-floor-conf-a',
            'url': f'/api/calendar/c_188b7hdp53liciehjeamigaho54q6@resource.calendar.google.com',
            'color': '#008080',
            'name': '3rd Floor Conference Room - A'
        },
        {
            'id': '3rd-floor-conf-b',
            'url': f'/api/calendar/c_1889llbfhgiq2hd7m257ko1jkocoa@resource.calendar.google.com',
            'color': '#FF1493',
            'name': '3rd Floor Conference Room - B'
        },
        {
            'id': '3rd-floor-conf-c',
            'url': f'/api/calendar/c_1889llbfhgiq2hd7m257ko1jkocoa@resource.calendar.google.com',
            'color': '#FFD700',
            'name': '3rd Floor Conference Room - C'
        },
        {
            'id': 'studio',
            'url': f'/api/calendar/c_18896mg9ssuomjuvk1t0h5htgv3sc@resource.calendar.google.com',
            'color': '#FF6347',
            'name': 'Studio'
        },
        {
            'id': 'call-suite-1',
            'url': f'/api/calendar/c_1884v1gbm5k9uja1gn45og3ve490i@resource.calendar.google.com',
            'color': '#20B2AA',
            'name': 'Call Suite 1'
        },
        {
            'id': 'call-suite-2',
            'url': f'/api/calendar/c_18863ks7hk6scg71hq2nhkaapno5q@resource.calendar.google.com',
            'color': '#BA55D3',
            'name': 'Call Suite 2'
        },
        {
            'id': 'call-suite-3',
            'url': f'/api/calendar/c_18822lp908sukh1nmq8p3tsh73olo@resource.calendar.google.com',
            'color': '#98FB98',
            'name': 'Call Suite 3'
        },
        {
            'id': 'call-suite-4',
            'url': f'/api/calendar/c_188eog8j7a9t0hvql0859a3m1d4hi@resource.calendar.google.com',
            'color': '#DDA0DD',
            'name': 'Call Suite 4'
        },
        {
            'id': 'call-suite-5',
            'url': f'/api/calendar/c_188dcrv2hh4qgigmln9kjistokekq@resource.calendar.google.com',
            'color': '#F0E68C',
            'name': 'Call Suite 5'
        },
        {
            'id': 'call-suite-6',
            'url': f'/api/calendar/c_18819kul9gcfgiv8i0ob55la9m02g@resource.calendar.google.com',
            'color': '#87CEEB',
            'name': 'Call Suite 6'
        },
        {
            'id': 'call-suite-7',
            'url': f'/api/calendar/c_1885vpj43qp9ujm4ik1g1kud1vhk6@resource.calendar.google.com',
            'color': '#CD853F',
            'name': 'Call Suite 7'
        }
    ]
    return render_template('fullcalendar.html', calendar_sources=calendar_sources)

@app.route('/api/calendar/<calendar_id>')
#@cache.cached(timeout=300, query_string=True)
def get_fullcalendar_events(calendar_id):
    start = request.args.get('start')
    end = request.args.get('end')
    
    if not start or not end:
        return jsonify({"error": "Missing start or end parameter"}), 400

    try:
        start_date = datetime.fromisoformat(start.replace('Z', '+00:00')).date()
        end_date = datetime.fromisoformat(end.replace('Z', '+00:00')).date()
    except ValueError as e:
        return jsonify({
            "error": "Invalid date format",
            "detail": str(e),
            "start": start,
            "end": end
        }), 400

    events = get_calendar_events_range(calendar_id, start_date, end_date)
    return jsonify(events)






# ✅ **Helper function to clean room names**
def cleanRoomName(location):
    """Extract room name from location and filter out Zoom links."""
    if not location or "http" in location:
        return "Virtual Meeting"  # Default for Zoom meetings
    return location.split(",")[0]  # Extract first part of location



def cleanRoomName(location):
    """Extract the main room name from the location string"""
    if not location:
        return 'Unknown'
    
    # Remove NRSC prefix and capacity
    room = location.split(',')[0]  # Take first part if multiple locations
    room = re.sub(r'NRSC-\w+[-\s]', '', room)  # Remove NRSC prefix
    room = re.sub(r'\s*\(\d+\)$', '', room)    # Remove capacity
    return room.strip()

# #########################
# Badge Stats
# #########################

@app.route('/badge_stats')
@requires_roles('admin', 'superuser')
@login_required
def badge_stats():
    from people import get_badge_holder_stats, get_stats_ignore_list, calculate_office_wide_average
    
    include_ignored = request.args.get('include_ignored', 'false').lower() == 'true'
    
    # Get office-wide average
    office_stats = calculate_office_wide_average(include_ignored)
    
    # Get individual stats and ignore count
    ignore_list = get_stats_ignore_list()
    ignore_count = len(ignore_list)
    badge_holders = get_badge_holder_stats(include_ignored)
    
    print("Office stats:", office_stats)  # Debug print
    
    return render_template('badge_stats.html', 
                         badge_holders=badge_holders,
                         office_wide_avg=office_stats['average_time'],
                         total_morning_events=office_stats['total_events'],
                         employee_count=office_stats['employee_count'],
                         ignore_count=ignore_count,
                         include_ignored=include_ignored)


if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=80)
