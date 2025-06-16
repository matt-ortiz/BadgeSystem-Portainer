import pyodbc
import json
import os
from datetime import datetime, timezone, timedelta
import pytz
import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for, make_response, current_app
from io import BytesIO
from PIL import Image, ImageDraw
import base64
from weasyprint import HTML, CSS
import traceback
from dotenv import load_dotenv

load_dotenv()


from auth import login_required, requires_roles


ignore_blueprint = Blueprint('ignore', __name__, template_folder='templates')
# ignore_blueprint = Blueprint('ignore_blueprint', __name__)


est = pytz.timezone('US/Eastern')



def get_db_connection():
    conn = sqlite3.connect('people.db')
    conn.row_factory = sqlite3.Row
    return conn



def get_active_cardholders():
    conn_str = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={os.getenv('DATABASE_URL')};"
        "DATABASE=multiMAX;"
        f"UID={os.getenv('DATABASE_UID')};"
        f"PWD={os.getenv('DATABASE_PWD')};"
    )

    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT CardID, FirstName, LastName
        FROM CardHolderTable
        ORDER BY FirstName
    """)

    cardholders = cursor.fetchall()
    conn.close()

    return cardholders


def rows_to_dict(rows):
    return [dict(row) for row in rows]


@ignore_blueprint.route('/ignore', methods=['GET', 'POST'])
@login_required
@requires_roles('admin', 'superuser')
def manage_ignore():
    if request.method == 'POST':
        card_id = request.form.get('CardID')
        if card_id:
            cardholders = get_active_cardholders()
            cardholder = next((ch for ch in cardholders if ch.CardID == int(card_id)), None)
            if cardholder:
                name = f"{cardholder.FirstName} {cardholder.LastName}"
                conn = get_db_connection()
                conn.execute('INSERT INTO ignore_data (CardID, Name) VALUES (?, ?)', (int(card_id), name))
                conn.commit()
                conn.close()
        return redirect(url_for('ignore.manage_ignore'))
    
    conn = get_db_connection()
    ignore_data = conn.execute('SELECT * FROM ignore_data').fetchall()
    conn.close()
    cardholders = get_active_cardholders()
    return render_template('manage_ignore.html', ignore_data=ignore_data, cardholders=cardholders)

@ignore_blueprint.route('/ignore/remove/<int:card_id>', methods=['POST'])
@login_required
@requires_roles('admin', 'superuser')
def remove_ignore(card_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM ignore_data WHERE CardID = ?', (card_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('ignore.manage_ignore'))

@ignore_blueprint.route('/vip', methods=['GET', 'POST'])
@login_required
@requires_roles('admin', 'superuser')
def manage_vip():
    if request.method == 'POST':
        card_id = request.form.get('CardID')
        ninja_id = request.form.get('NinjaID')
        if card_id and ninja_id:
            cardholders = get_active_cardholders()
            cardholder = next((ch for ch in cardholders if ch.CardID == int(card_id)), None)
            if cardholder:
                name = f"{cardholder.FirstName} {cardholder.LastName}"
                conn = get_db_connection()
                conn.execute('INSERT INTO vip_data (CardID, Name, NinjaID) VALUES (?, ?, ?)', (int(card_id), name, int(ninja_id)))
                conn.commit()
                conn.close()
        return redirect(url_for('ignore.manage_vip'))
    
    conn = get_db_connection()
    vip_data = conn.execute('SELECT * FROM vip_data').fetchall()
    conn.close()
    cardholders = get_active_cardholders()
    return render_template('manage_vip.html', vip_data=vip_data, cardholders=cardholders)

@ignore_blueprint.route('/vip/remove/<int:card_id>', methods=['POST'])
@login_required
@requires_roles('admin', 'superuser')
def remove_vip(card_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM vip_data WHERE CardID = ?', (card_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('ignore.manage_vip'))


def all_users_lookup():
    conn_str = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={os.getenv('DATABASE_URL')};"
        "DATABASE=multiMAX;"
        f"UID={os.getenv('DATABASE_UID')};"
        f"PWD={os.getenv('DATABASE_PWD')};"
    )

    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT CardID, FirstName, LastName, DateTimeOfTxn
        FROM CardHolderTable
        ORDER BY FirstName
    """)

    cardholders = cursor.fetchall()
    conn.close()

    # Set the timezones
    utc = pytz.UTC
    est = pytz.timezone('US/Eastern')
    
    # Get the current time in UTC
    current_time = datetime.now(timezone.utc)

    print("Current Time (UTC):", current_time)

    # Convert the fetched data into a list of dictionaries and calculate elapsed time
    cardholders_list = []
    for row in cardholders:
        date_of_txn = row.DateTimeOfTxn
        print("Raw DateTimeOfTxn:", date_of_txn)
        if date_of_txn:
            # Assume date_of_txn is in EST and convert to UTC
            if date_of_txn.tzinfo is None:
                date_of_txn = est.localize(date_of_txn).astimezone(utc)
            else:
                date_of_txn = date_of_txn.astimezone(utc)
            elapsed_time = current_time - date_of_txn
            print(f"CardID: {row.CardID}, Elapsed Time: {elapsed_time}")
            days = elapsed_time.days
            hours = elapsed_time.seconds // 3600
            minutes = (elapsed_time.seconds // 60) % 60
            years = days // 365  # Approximate number of years
            days = days % 365   # Remainder of days after calculating years
        else:
            days = hours = minutes = years = None

        cardholders_list.append({
            'CardID': row.CardID,
            'FirstName': row.FirstName,
            'LastName': row.LastName,
            'DateTimeOfTxn': date_of_txn,
            'ElapsedTime': {
                'years': years,
                'days': days,
                'hours': hours,
                'minutes': minutes
            }
        })

    return cardholders_list, current_time

@ignore_blueprint.route('/all', methods=['GET'])
@login_required
@requires_roles('admin', 'superuser')
def all_badges():
    sort_by = request.args.get('sort_by', 'LastName')
    cardholders, server_time = all_users_lookup()

    if sort_by == 'LastScanned':
        cardholders.sort(key=lambda x: (x['DateTimeOfTxn'] is None, x['DateTimeOfTxn']), reverse=True)
    elif sort_by == 'CardID':
        cardholders.sort(key=lambda x: x['CardID'])
    else:  # Default to sorting by LastName
        cardholders.sort(key=lambda x: x['LastName'])

    return render_template('all_people.html', cardholders=cardholders, server_time=server_time, sort_by=sort_by)


# @ignore_blueprint.route('/all', methods=['GET'])
# @login_required
# @requires_roles('admin', 'superuser')
# def all_badges():
#     cardholders = get_active_cardholders()
#     return render_template('all_people.html', cardholders=cardholders)





def badged_today():
    # Connection string
    conn_str = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={os.getenv('DATABASE_URL')};"
        "DATABASE=multiMAXTxn;"
        f"UID={os.getenv('DATABASE_UID')};"
        f"PWD={os.getenv('DATABASE_PWD')};"
    )

    # Establish connection
    conn = pyodbc.connect(conn_str)

    # Create a cursor from the connection
    cursor = conn.cursor()



    # Current datetime at the beginning of today
    start_date = datetime.now(est).replace(hour=0, minute=0, second=0, microsecond=0)

    # Datetime at the beginning of tomorrow
    end_date = start_date + timedelta(days=1)

    #cursor.execute("SELECT * FROM ActivityDataPDView WHERE DateTimeOfTxn BETWEEN ? AND ? AND (CardNumber IS NOT NULL AND CardNumber <> '') ORDER BY TxnID DESC;", start_date, end_date)
    cursor.execute("""
        SELECT DateTimeOfTxn, WhereName, TxnConditionName, CardID, FirstName, LastName
        FROM AlarmEventTransactionTable
        WHERE DateTimeOfTxn BETWEEN ? AND ?
        AND (CardNumber IS NOT NULL AND CardNumber <> '')
        ORDER BY TxnID DESC
    """, (start_date, end_date))

    rows = cursor.fetchall()
    
    # Don't forget to close the connection when done
    conn.close()


    data_list = []
    processed_entries = set()  # This set will keep track of the unique (CardNumber, Name) tuples
    conn = get_db_connection()
    ignore_data = rows_to_dict(conn.execute('SELECT * FROM ignore_data').fetchall())
    vip_data = rows_to_dict(conn.execute('SELECT * FROM vip_data').fetchall())
    conn.close()

    # Convert the structured ignore_data into a set of (CardID, Name) tuples
    ignore_set = {(entry["CardID"], entry["Name"]) for entry in ignore_data}

    vip_lookup = {entry["CardID"]: entry["NinjaID"] for entry in vip_data}
    vip_set = {(entry["CardID"], entry["Name"]) for entry in vip_data}

    for row in rows:
        name = f"{row.FirstName} {row.LastName}"
        unique_key = (row.CardID, name)  # Tuple containing both CardNumber and Name

        # Check if the unique_key is in the ignore_set, if yes then skip the current loop iteration
        if unique_key in ignore_set:
            continue

        # Check if the unique_key is not in processed_entries
        if unique_key not in processed_entries:
            is_vip = unique_key in vip_set  # Check if the user is a VIP using the tuple

            ninja_id = None  # Default value for NinjaID
            if is_vip:
                ninja_id = vip_lookup.get(row.CardID)  # Fetch the NinjaID for VIP user


            data = {
                "CardID": row.CardID,
                "Name": name,
                "is_vip": is_vip,  # Add the VIP status
                "NinjaID": ninja_id  # Add the NinjaID or None if not a VIP
            }
            data_list.append(data)
            processed_entries.add(unique_key)  # Add the tuple to the set

    vip_count = sum(1 for user in data_list if user["is_vip"])

    result = {
        "total_count": len(data_list),
        "details": data_list,
        "ignore_details": ignore_data,
        "vip_count": vip_count,
        "vip_details": vip_data
    }

    # Convert list to JSON string
    data_json = json.dumps(data_list)
    return result # Or you can return this from your Flask route

def optimize_image_for_pdf(card_id):
    """Optimize an image for PDF inclusion by resizing and compressing it"""
    # Get the absolute path using Flask's app root path
    img_path = os.path.join(current_app.root_path, 'static', 'staff', f'{card_id}.jpg')
    
    # If no image exists, return a placeholder
    if not os.path.exists(img_path):
        # Create a simple placeholder image
        placeholder = Image.new('RGB', (100, 100), color=(238, 238, 238))
        draw = ImageDraw.Draw(placeholder)
        draw.text((50, 50), "No Image", fill=(153, 153, 153), anchor="mm")
        
        # Save to BytesIO
        buffer = BytesIO()
        placeholder.save(buffer, format='JPEG', optimize=True, quality=40)
        buffer.seek(0)
        
        # Convert to base64 for embedding
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return f"data:image/jpeg;base64,{img_base64}"
    
    try:
        # Open the image
        with Image.open(img_path) as img:
            # Keep original color (remove grayscale conversion)
            
            # Resize to a smaller size for PDF
            max_size = (100, 100)
            img.thumbnail(max_size, Image.LANCZOS)
            
            # Save to BytesIO with compression
            buffer = BytesIO()
            img.save(buffer, format='JPEG', optimize=True, quality=60)  # Increased quality
            buffer.seek(0)
            
            # Convert to base64 for embedding
            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return f"data:image/jpeg;base64,{img_base64}"
    except Exception as e:
        print(f"Error optimizing image {card_id}: {e}")
        
        # Create a simple error placeholder
        placeholder = Image.new('RGB', (100, 100), color=(255, 235, 235))
        draw = ImageDraw.Draw(placeholder)
        draw.text((50, 50), "Error", fill=(255, 0, 0), anchor="mm")
        
        # Save to BytesIO
        buffer = BytesIO()
        placeholder.save(buffer, format='JPEG', optimize=True, quality=40)
        buffer.seek(0)
        
        # Convert to base64 for embedding
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return f"data:image/jpeg;base64,{img_base64}"

@ignore_blueprint.route('/all/pdf', methods=['GET'])
@login_required
@requires_roles('admin', 'superuser')
def all_badges_pdf():
    """Generate an optimized PDF of all badges"""
    sort_by = request.args.get('sort_by', 'LastName')
    cardholders, server_time = all_users_lookup()

    if sort_by == 'LastScanned':
        cardholders.sort(key=lambda x: (x['DateTimeOfTxn'] is None, x['DateTimeOfTxn']), reverse=True)
    elif sort_by == 'CardID':
        cardholders.sort(key=lambda x: x['CardID'])
    else:  # Default to sorting by LastName
        cardholders.sort(key=lambda x: x['LastName'])
    
    # Optimize images for PDF
    for cardholder in cardholders:
        cardholder['optimized_image'] = optimize_image_for_pdf(cardholder['CardID'])
    
    # Render the template
    html = render_template('all_people_pdf.html', cardholders=cardholders, server_time=server_time, sort_by=sort_by)
    
    # Generate PDF
    pdf = HTML(string=html, base_url=request.url).write_pdf(
        stylesheets=[
            CSS(string='''
                @page {
                    size: letter;
                    margin: 1cm;
                }
                body {
                    font-family: Arial, sans-serif;
                    font-size: 10pt;
                }
                .grid-container {
                    display: grid;
                    grid-template-columns: repeat(3, 1fr);
                    gap: 5px;
                }
                .grid-list {
                    list-style-type: none;
                    padding: 0;
                    margin: 0;
                }
                .grid-list li {
                    padding: 5px;
                    margin-bottom: 5px;
                    page-break-inside: avoid;
                }
                .photo {
                    width: 60px;
                    height: auto;
                }
                .p_meta {
                    font-size: 9pt;
                    line-height: 1.2;
                    padding-left: 5px;
                }
            ''')
        ]
    )
    
    # Create response
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=all_badges.pdf'
    
    return response

@ignore_blueprint.route('/all/optimized', methods=['GET'])
@login_required
@requires_roles('admin', 'superuser')
def all_badges_optimized():
    """Render the all badges page with optimized images for better printing"""
    sort_by = request.args.get('sort_by', 'LastName')
    cardholders, server_time = all_users_lookup()

    if sort_by == 'LastScanned':
        cardholders.sort(key=lambda x: (x['DateTimeOfTxn'] is None, x['DateTimeOfTxn']), reverse=True)
    elif sort_by == 'CardID':
        cardholders.sort(key=lambda x: x['CardID'])
    else:  # Default to sorting by LastName
        cardholders.sort(key=lambda x: x['LastName'])
    
    return render_template('all_people_optimized.html', 
                         cardholders=cardholders, 
                         server_time=server_time, 
                         sort_by=sort_by,
                         optimize_image_for_pdf=optimize_image_for_pdf)

def get_card_assignments():
    """Get card assignments with cardholder information"""
    conn_str = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={os.getenv('DATABASE_URL')};"
        "DATABASE=multiMAX;"
        f"UID={os.getenv('DATABASE_UID')};"
        f"PWD={os.getenv('DATABASE_PWD')};"
    )

    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            ch.CardID,
            ch.FirstName,
            ch.LastName,
            ci.CardNumber,
            ci.Inactive,
            ci.ForcedInactive,
            ci.Lost,
            ci.CardWatch,
            ci.PrintBadge,
            ci.PrimaryCard,
            ci.CardIssueLevel,
            CASE ci.CardIssueLevel
                WHEN 0 THEN 'Standard'
                WHEN 1 THEN 'Level 1'
                WHEN 2 THEN 'Level 2'
                WHEN 3 THEN 'Level 3'
                WHEN 4 THEN 'Level 4'
                WHEN 5 THEN 'Level 5'
                ELSE 'Unknown'
            END as CardIssueLevelDesc,
            ci.DateTimeOfTxn
        FROM CardHolderTable ch
        LEFT JOIN CardInfoTable ci ON ch.CardID = ci.CardID
        ORDER BY ch.LastName, ch.FirstName
    """)

    assignments = cursor.fetchall()
    conn.close()

    return assignments

@ignore_blueprint.route('/badges', methods=['GET'])
@login_required
@requires_roles('admin', 'superuser')
def view_badges():
    """View all badge assignments"""
    sort_by = request.args.get('sort_by', 'LastName')
    assignments = get_card_assignments()
    
    # Convert to list of dicts for easier handling
    assignments_list = []
    for row in assignments:
        assignment = {
            'CardID': row.CardID,
            'FirstName': row.FirstName,
            'LastName': row.LastName,
            'CardNumber': row.CardNumber,
            'Inactive': row.Inactive,
            'ForcedInactive': row.ForcedInactive,
            'Lost': row.Lost,
            'CardWatch': row.CardWatch,
            'PrintBadge': row.PrintBadge,
            'PrimaryCard': row.PrimaryCard,
            'CardIssueLevel': row.CardIssueLevel,
            'CardIssueLevelDesc': row.CardIssueLevelDesc,
            'DateTimeOfTxn': row.DateTimeOfTxn
        }
        assignments_list.append(assignment)
    
    # Sort the list based on the sort_by parameter
    if sort_by == 'CardNumber':
        assignments_list.sort(key=lambda x: (x['CardNumber'] is None, x['CardNumber']))
    elif sort_by == 'LastScanned':
        assignments_list.sort(key=lambda x: (x['DateTimeOfTxn'] is None, x['DateTimeOfTxn']), reverse=True)
    else:  # Default to LastName
        assignments_list.sort(key=lambda x: f"{x['LastName']}, {x['FirstName']}")
    
    return render_template('badges.html', 
                         assignments=assignments_list, 
                         sort_by=sort_by,
                         server_time=datetime.now(timezone.utc))

@ignore_blueprint.route('/badges/pdf', methods=['GET'])
@login_required
@requires_roles('admin', 'superuser')
def badges_pdf():
    """Generate PDF of badge assignments"""
    sort_by = request.args.get('sort_by', 'LastName')
    assignments = get_card_assignments()
    
    # Convert to list of dicts
    assignments_list = []
    for row in assignments:
        assignment = {
            'CardID': row.CardID,
            'FirstName': row.FirstName,
            'LastName': row.LastName,
            'CardNumber': row.CardNumber,
            'Inactive': row.Inactive,
            'ForcedInactive': row.ForcedInactive,
            'Lost': row.Lost,
            'CardWatch': row.CardWatch,
            'PrintBadge': row.PrintBadge,
            'PrimaryCard': row.PrimaryCard,
            'CardIssueLevel': row.CardIssueLevel,
            'DateTimeOfTxn': row.DateTimeOfTxn,
            'optimized_image': optimize_image_for_pdf(row.CardID)
        }
        assignments_list.append(assignment)
    
    # Sort the list
    if sort_by == 'CardNumber':
        assignments_list.sort(key=lambda x: (x['CardNumber'] is None, x['CardNumber']))
    elif sort_by == 'LastScanned':
        assignments_list.sort(key=lambda x: (x['DateTimeOfTxn'] is None, x['DateTimeOfTxn']), reverse=True)
    else:  # Default to LastName
        assignments_list.sort(key=lambda x: f"{x['LastName']}, {x['FirstName']}")
    
    # Render the template
    html = render_template('badges_pdf.html', 
                         assignments=assignments_list,
                         server_time=datetime.now(timezone.utc))
    
    # Generate PDF
    pdf = HTML(string=html, base_url=request.url).write_pdf(
        stylesheets=[
            CSS(string='''
                @page {
                    size: letter;
                    margin: 1cm;
                }
                body {
                    font-family: Arial, sans-serif;
                    font-size: 10pt;
                }
                .badge-grid {
                    width: 100%;
                    border-collapse: collapse;
                }
                .badge-grid th {
                    background-color: #f5f5f5;
                    padding: 8px;
                    text-align: left;
                    border-bottom: 2px solid #ddd;
                }
                .badge-grid td {
                    padding: 8px;
                    border-bottom: 1px solid #ddd;
                }
                .photo {
                    width: 60px;
                    height: auto;
                }
                .status-indicator {
                    display: inline-block;
                    width: 8px;
                    height: 8px;
                    border-radius: 50%;
                    margin-right: 5px;
                }
                .status-active { background-color: #4CAF50; }
                .status-inactive { background-color: #f44336; }
                .status-lost { background-color: #ff9800; }
                .status-watch { background-color: #2196F3; }
            ''')
        ]
    )
    
    # Create response
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=badge_assignments.pdf'
    
    return response


def get_badge_holder_stats(include_ignored=False):
    """Get badge holder statistics."""
    # Get the ignore list from SQLite
    ignore_list = get_stats_ignore_list()
    
    # Get active cardholders using existing function
    cardholders = get_active_cardholders()
    
    # Connect to AMAG database for transactions
    conn_str = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={os.getenv('DATABASE_URL')};"
        "DATABASE=multiMAXTxn;"
        f"UID={os.getenv('DATABASE_UID')};"
        f"PWD={os.getenv('DATABASE_PWD')};"
    )
    
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    
    # Set up timezone handling
    est = pytz.timezone('US/Eastern')
    
    stats = []
    for holder in cardholders:
        # Skip ignored users unless include_ignored is True
        if not include_ignored and holder.CardID in ignore_list:
            continue
            
        card_id = holder.CardID
        
        # Get badge transactions for this holder
        cursor.execute("""
            SELECT 
                DateTimeOfTxn,
                TxnConditionName,
                WhereName
            FROM AlarmEventTransactionTable 
            WHERE CardID = ? 
            ORDER BY DateTimeOfTxn ASC
        """, (card_id,))
        
        rows = cursor.fetchall()
        
        # Store only the first badge-in time for each day
        first_badge_ins = {}
        daily_events = {}
        
        for row in rows:
            try:
                dt = row.DateTimeOfTxn
                if isinstance(dt, str):
                    dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
                
                # Ensure proper timezone handling
                if dt.tzinfo is None:
                    dt = est.localize(dt)
                
                date_key = dt.date()
                
                # Store the first badge-in time for each day (earliest time)
                if date_key not in first_badge_ins:
                    first_badge_ins[date_key] = dt
                    daily_events[date_key] = {
                        'datetime': dt,
                        'formatted': dt.strftime('%-I:%M %p - %b %-d, %Y')
                    }
                    
            except (ValueError, TypeError) as e:
                print(f"Error processing datetime for CardID {card_id}: {e}")
                continue
        
        # Calculate statistics based on first badge-ins only
        morning_times = []
        after_noon_count = 0
        
        for dt in first_badge_ins.values():
            if dt.hour < 12:
                morning_times.append(dt.hour * 60 + dt.minute)
            else:
                after_noon_count += 1
        
        # Calculate average morning time
        if morning_times:
            avg_minutes = sum(morning_times) / len(morning_times)
            avg_hour = int(avg_minutes // 60)
            avg_minute = int(avg_minutes % 60)
            avg_time = f"{avg_hour:02d}:{avg_minute:02d}"
        else:
            avg_time = "N/A"
        
        # Sort by actual datetime and get formatted strings (latest first)
        all_badge_times = [
            event['formatted']
            for event in sorted(
                daily_events.values(),
                key=lambda x: x['datetime'],
                reverse=True  # Added reverse=True to show latest dates first
            )
        ]
        
        stats.append({
            'card_id': card_id,
            'first_name': holder.FirstName,
            'last_name': holder.LastName,
            'avg_time': avg_time,
            'morning_badge_count': len(morning_times),
            'after_noon_count': after_noon_count,
            'all_badge_times': all_badge_times,
            'total_transactions': len(daily_events)
        })
    
    conn.close()
    return stats

def get_stats_ignore_list():
    """Get a list of CardIDs to ignore in statistics"""
    try:
        conn = get_db_connection()
        result = conn.execute('SELECT CardID FROM stats_ignore_data').fetchall()
        conn.close()
        return [row['CardID'] for row in result]
    except Exception as e:
        print(f"Error getting stats ignore list: {e}")
        return []

@ignore_blueprint.route('/stats-ignore', methods=['GET', 'POST'])
@login_required
@requires_roles('admin', 'superuser')
def manage_stats_ignore():
    if request.method == 'POST':
        card_id = request.form.get('CardID')
        if card_id:
            cardholders = get_active_cardholders()
            cardholder = next((ch for ch in cardholders if ch.CardID == int(card_id)), None)
            if cardholder:
                name = f"{cardholder.FirstName} {cardholder.LastName}"
                conn = get_db_connection()
                conn.execute('INSERT OR REPLACE INTO stats_ignore_data (CardID, Name) VALUES (?, ?)', 
                           (int(card_id), name))
                conn.commit()
                conn.close()
        return redirect(url_for('ignore.manage_stats_ignore'))
    
    conn = get_db_connection()
    ignore_data = conn.execute('SELECT * FROM stats_ignore_data').fetchall()
    conn.close()
    cardholders = get_active_cardholders()
    return render_template('manage_stats_ignore.html', ignore_data=ignore_data, cardholders=cardholders)



@ignore_blueprint.route('/stats-ignore/remove/<int:card_id>', methods=['POST'])
@login_required
@requires_roles('admin', 'superuser')
def remove_stats_ignore(card_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM stats_ignore_data WHERE CardID = ?', (card_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('ignore.manage_stats_ignore'))

def calculate_office_wide_average(include_ignored=False):
    """Calculate the office-wide average first badge time for morning events."""
    ignore_list = get_stats_ignore_list()
    cardholders = get_active_cardholders()
    
    conn_str = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={os.getenv('DATABASE_URL')};"
        "DATABASE=multiMAXTxn;"
        f"UID={os.getenv('DATABASE_UID')};"
        f"PWD={os.getenv('DATABASE_PWD')};"
    )
    
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    est = pytz.timezone('US/Eastern')
    
    all_morning_times = []
    employee_count = 0  # Track number of employees with morning badges
    
    for holder in cardholders:
        if not include_ignored and holder.CardID in ignore_list:
            continue
            
        cursor.execute("""
            SELECT DateTimeOfTxn
            FROM AlarmEventTransactionTable 
            WHERE CardID = ? 
            ORDER BY DateTimeOfTxn ASC
        """, (holder.CardID,))
        
        first_badge_ins = {}
        has_morning_badges = False
        
        for row in cursor.fetchall():
            try:
                dt = row.DateTimeOfTxn
                if isinstance(dt, str):
                    dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
                
                if dt.tzinfo is None:
                    dt = est.localize(dt)
                
                date_key = dt.date()
                
                # Store only first badge of each day
                if date_key not in first_badge_ins:
                    first_badge_ins[date_key] = dt
                    
            except (ValueError, TypeError) as e:
                continue
        
        # Process morning events only
        for dt in first_badge_ins.values():
            if dt.hour < 12:
                all_morning_times.append(dt.hour * 60 + dt.minute)
                has_morning_badges = True
        
        if has_morning_badges:
            employee_count += 1
    
    conn.close()
    
    # Calculate office-wide average
    if all_morning_times:
        avg_minutes = sum(all_morning_times) / len(all_morning_times)
        avg_hour = int(avg_minutes // 60)
        avg_minute = int(avg_minutes % 60)
        return {
            'average_time': f"{avg_hour:02d}:{avg_minute:02d}",
            'total_events': len(all_morning_times),
            'employee_count': employee_count
        }
    
    return {
        'average_time': 'N/A',
        'total_events': 0,
        'employee_count': 0
    }

@ignore_blueprint.route('/badge-stats', methods=['GET'])
@login_required
@requires_roles('admin', 'superuser')
def badge_stats():
    print("Badge stats route hit!")  # Debug print
    include_ignored = request.args.get('include_ignored', 'false').lower() == 'true'
    
    # Get office-wide average first to ensure it works
    office_stats = calculate_office_wide_average(include_ignored)
    print("Office stats calculated:", office_stats)  # Debug print
    
    # Get individual badge holder stats (we'll need to see this function)
    badge_holders = []  # Temporary until we see get_badge_holder_stats()
    
    # Get ignore count for display
    conn = get_db_connection()
    ignore_count = len(conn.execute('SELECT CardID FROM stats_ignore_data').fetchall())
    conn.close()
    
    print("Rendering template with:", {  # Debug print
        'office_wide_avg': office_stats['average_time'],
        'total_morning_events': office_stats['total_events'],
        'employee_count': office_stats['employee_count']
    })
    
    return render_template('badge_stats.html',
                         badge_holders=badge_holders,
                         office_wide_avg=office_stats['average_time'],
                         total_morning_events=office_stats['total_events'],
                         employee_count=office_stats['employee_count'],
                         include_ignored=include_ignored,
                         ignore_count=ignore_count)
