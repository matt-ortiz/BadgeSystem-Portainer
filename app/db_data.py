import pyodbc
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Connection string using environment variables
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

# Sample query
# cursor.execute("SELECT * FROM ActivityDataPDView")
cursor.execute("SELECT TOP 25 * FROM ActivityDataPDView ORDER BY TxnID DESC")
rows = cursor.fetchall()

data_list = []

for row in rows:
    card_id = row.CardID
    if not card_id:
        continue

    data = {
        "DateTimeOfTxn": str(row.DateTimeOfTxn),
        "WhereName": row.WhereName,
        "TxnConditionName": row.TxnConditionName,
        "CardNumber": row.CardID,
        "Name": f"{row.FirstName} {row.LastName}"
    }
    data_list.append(data)

# Don't forget to close the connection when done
conn.close()

# Convert list to JSON string
data_json = json.dumps(data_list)
print(data_json)  # Or you can return this from your Flask route
