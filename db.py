import pymysql
import json
import os
from dotenv import load_dotenv

load_dotenv(override=True)

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASS = os.environ.get("DB_PASS", "")
DB_NAME = os.environ.get("DB_NAME", "vorniity")

def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )

def init_db():
    """Initialize the MySQL database for caching results."""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS results_cache_v2 (
                    usn VARCHAR(20),
                    url VARCHAR(255),
                    data JSON,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (usn, url)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS subject_credits (
                    subject_code VARCHAR(50) PRIMARY KEY,
                    credits INT NOT NULL
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS classes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    start_usn VARCHAR(20) NOT NULL,
                    end_usn VARCHAR(20) NOT NULL
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scrape_history (
                    id VARCHAR(255) PRIMARY KEY,
                    start_usn VARCHAR(20),
                    end_usn VARCHAR(20),
                    total_usns INT,
                    completed INT,
                    time_taken FLOAT,
                    status VARCHAR(50),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] Failed to initialize DB: {e}")

def seed_credits_if_empty(hardcoded_map):
    """Seed the database with the hardcoded credit map if the table is empty."""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM subject_credits")
            count = cursor.fetchone()['count']
            
            if count == 0:
                print("[DB] Seeding subject_credits from hardcoded map...")
                for code, credit in hardcoded_map.items():
                    cursor.execute(
                        "INSERT INTO subject_credits (subject_code, credits) VALUES (%s, %s)",
                        (code, credit)
                    )
                conn.commit()
                print(f"[DB] Seeded {len(hardcoded_map)} subjects.")
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] Failed to seed credits: {e}")

def get_all_credits():
    """Retrieve all subject credits as a dictionary."""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT subject_code, credits FROM subject_credits")
            rows = cursor.fetchall()
        conn.close()
        return {row['subject_code']: row['credits'] for row in rows}
    except Exception as e:
        print(f"[DB ERROR] Failed to fetch credits: {e}")
        return {}

def save_credit(subject_code, credits):
    """Save or update a subject credit."""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "REPLACE INTO subject_credits (subject_code, credits) VALUES (%s, %s)",
                (subject_code.upper(), int(credits))
            )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB ERROR] Failed to save credit: {e}")
        return False

def delete_credit(subject_code):
    """Delete a subject credit."""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM subject_credits WHERE subject_code = %s", (subject_code.upper(),))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB ERROR] Failed to delete credit: {e}")
        return False

# --- Classes Logic ---

def create_class(name, start_usn, end_usn):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO classes (name, start_usn, end_usn) VALUES (%s, %s, %s)",
                (name, start_usn.upper(), end_usn.upper())
            )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB ERROR] Failed to create class: {e}")
        return False

def get_all_classes():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, name, start_usn, end_usn FROM classes ORDER BY id DESC")
            rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"[DB ERROR] Failed to fetch classes: {e}")
        return []

def delete_class(class_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM classes WHERE id = %s", (class_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB ERROR] Failed to delete class: {e}")
        return False

def update_class(class_id, name, start_usn, end_usn):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE classes SET name = %s, start_usn = %s, end_usn = %s WHERE id = %s",
                (name, start_usn.upper(), end_usn.upper(), class_id)
            )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB ERROR] Failed to update class: {e}")
        return False

# --- Scrape History Logic ---

def save_scrape_history(job_id, start_usn, end_usn, total_usns, completed, time_taken, status):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "REPLACE INTO scrape_history (id, start_usn, end_usn, total_usns, completed, time_taken, status) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (job_id, start_usn, end_usn, total_usns, completed, time_taken, status)
            )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB ERROR] Failed to save scrape history: {e}")
        return False

def get_scrape_history():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, start_usn, end_usn, total_usns, completed, time_taken, status, timestamp FROM scrape_history ORDER BY timestamp DESC")
            rows = cursor.fetchall()
        conn.close()
        
        # Format timestamp to ISO string
        for row in rows:
            if row['timestamp']:
                row['timestamp'] = row['timestamp'].isoformat()
        return rows
    except Exception as e:
        print(f"[DB ERROR] Failed to fetch scrape history: {e}")
        return []

def delete_student(usn):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM results_cache_v2 WHERE usn = %s", (usn.upper(),))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB ERROR] Failed to delete student: {e}")
        return False

def get_cached_result(usn, url):
    """Retrieve a cached result for a given USN and URL if it exists."""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT data FROM results_cache_v2 WHERE usn = %s AND url = %s", (usn.upper(), url))
            row = cursor.fetchone()
        conn.close()
        
        if row:
            if isinstance(row['data'], str):
                return json.loads(row['data'])
            return row['data']
    except Exception as e:
        print(f"[CACHE ERROR] Failed to read cache for {usn}: {e}")
    return None

def save_cached_result(usn, url, result_dict):
    """Save a successfully parsed result to the cache."""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # REPLACE INTO handles updating the record if it already exists
            cursor.execute(
                "REPLACE INTO results_cache_v2 (usn, url, data) VALUES (%s, %s, %s)",
                (usn.upper(), url, json.dumps(result_dict))
            )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[CACHE ERROR] Failed to save cache for {usn}: {e}")
