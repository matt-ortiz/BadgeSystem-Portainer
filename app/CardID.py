import pyodbc
import os
from dotenv import load_dotenv

load_dotenv()

# Use environment variables for database connection
conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={os.getenv('DATABASE_URL')};"
    "DATABASE=multiMAX;"
    f"UID={os.getenv('DATABASE_UID')};"
    f"PWD={os.getenv('DATABASE_PWD')};"
)

# Establish connection
conn = pyodbc.connect(conn_str)

# Create a cursor from the connection
cursor = conn.cursor()

cursor.execute("SELECT CardID, Face FROM CardHolderFaceTable")
rows = cursor.fetchall()

save_directory = 'images'

for row in rows:
    card_id = row.CardID
    image_data = row.Face

    # Define the filename based on the CardID
    filename = os.path.join(save_directory, f"{card_id}.jpg")

    # Check if the file already exists
    if not os.path.exists(filename):
        # If not, write the image data to the file
        with open(filename, 'wb') as img_file:
            img_file.write(image_data)
