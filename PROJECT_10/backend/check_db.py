import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'data', 'foundry.db')
print(f"Looking for database at: {db_path}")
print(f"Exists: {os.path.exists(db_path)}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('Tables:', tables)
for t in tables:
    cursor.execute(f'PRAGMA table_info({t[0]})')
    cols = cursor.fetchall()
    print(f'  {t[0]}: {[(c[1], c[2]) for c in cols]}')
conn.close()