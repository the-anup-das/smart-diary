import os
import psycopg2
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    # Use standard DATABASE_URL for psycopg2
    db_url = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5432/diary")
    
    # Clean the DSN if it has query parameters (like ?schema=public)
    if '?' in db_url:
        db_url = db_url.split('?')[0]
        
    try:
        conn = psycopg2.connect(db_url)
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        # Try fallback if running locally
        try:
            print("Trying fallback connection...")
            conn = psycopg2.connect("postgresql://user:password@localhost:5432/diary")
            return conn
        except Exception as e2:
            print(f"Fallback connection failed: {e2}")
            return None

def migrate():
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database. Migration aborted.")
        return
        
    cur = conn.cursor()
    
    try:
        # 1. Add new columns to feedback_reports
        print("Updating feedback_reports table with new insight columns...")
        columns_to_add = [
            ("detected_decision", "VARCHAR NULL"),
            ("self_focus_score", "INTEGER NULL"),
            ("self_focus_feedback", "TEXT NULL"),
            ("repetitive_wording", "JSON NULL")
        ]
        
        for col_name, col_type in columns_to_add:
            try:
                cur.execute(f"ALTER TABLE feedback_reports ADD COLUMN {col_name} {col_type};")
                print(f"Successfully added {col_name}.")
            except psycopg2.errors.DuplicateColumn:
                print(f"Column {col_name} already exists. Skipping.")
                conn.rollback()
            except Exception as e:
                print(f"Error adding {col_name}: {e}")
                conn.rollback()
            
        # 2. Create the decisions table
        print("Creating decisions table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                topic VARCHAR NOT NULL,
                status VARCHAR DEFAULT 'active',
                framework VARCHAR NULL,
                factors JSON NULL,
                options JSON NULL,
                primary_option_id VARCHAR NULL,
                expected_outcome TEXT NULL,
                actual_outcome TEXT NULL,
                review_date TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("Successfully created decisions table.")
        
        # 3. Add analysis_result column to decisions (idempotent)
        print("Adding analysis_result to decisions table...")
        try:
            cur.execute("ALTER TABLE decisions ADD COLUMN analysis_result JSON NULL;")
            print("Successfully added analysis_result.")
        except psycopg2.errors.DuplicateColumn:
            print("Column analysis_result already exists. Skipping.")
            conn.rollback()
        
        conn.commit()
        print("Migration complete!")
        
    except Exception as e:
        conn.rollback()
        print(f"An error occurred during migration: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    migrate()
