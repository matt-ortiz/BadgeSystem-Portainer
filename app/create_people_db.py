import sqlite3

def init_db():
    conn = sqlite3.connect('people.db')
    cursor = conn.cursor()

    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ignore_data (
            CardID INTEGER PRIMARY KEY,
            Name TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vip_data (
            CardID INTEGER PRIMARY KEY,
            Name TEXT NOT NULL,
            NinjaID INTEGER NOT NULL
        )
    ''')

    # Commit changes and close the connection
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
