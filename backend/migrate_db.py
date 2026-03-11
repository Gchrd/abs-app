import sqlite3
import os

def migrate():
    db_path = os.getenv("DB_PATH", "data/abs.db")
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}. Skipping migration.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(devices)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if "last_ack_backup_id" not in columns:
            print("Adding 'last_ack_backup_id' column to 'devices' table...")
            cursor.execute("ALTER TABLE devices ADD COLUMN last_ack_backup_id INTEGER")
            conn.commit()
            print("Migration successful.")
        else:
            print("Column 'last_ack_backup_id' already exists. Skipping.")
            
    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
