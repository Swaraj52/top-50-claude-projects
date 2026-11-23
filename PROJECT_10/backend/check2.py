import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'data', 'foundry.db')
print(f"Database path: {db_path}")
print(f"Exists: {os.path.exists(db_path)}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('Tables:', tables)
conn.close()