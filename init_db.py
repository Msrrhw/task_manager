import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
# -------------------------
# PostgreSQL connection details
# -------------------------
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}

# -------------------------
# Create table
# -------------------------
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    date DATE,
    status TEXT DEFAULT 'pending'
);
"""
print(DB_CONFIG) 

def init_db():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(CREATE_TABLE_SQL)
    conn.commit()
    cur.close()
    conn.close()
    print("✅ PostgreSQL table 'tasks' initialized successfully.")

if __name__ == "__main__":
    init_db()
