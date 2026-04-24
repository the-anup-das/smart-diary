from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

# Load from root .env
load_dotenv(dotenv_path="../.env")
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "postgresql://diary_user:diary_password@localhost/diary_db"

if "?schema=" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.split("?")[0]

engine = create_engine(DATABASE_URL)

def migrate():
    with engine.connect() as conn:
        print("Starting migration for writing style insights...")
        
        # Add self_focus_score
        try:
            conn.execute(text("ALTER TABLE feedback_reports ADD COLUMN self_focus_score INTEGER"))
            conn.commit()
            print("Added self_focus_score.")
        except Exception as e:
            print("self_focus_score may already exist.")

        # Add self_focus_feedback
        try:
            conn.execute(text("ALTER TABLE feedback_reports ADD COLUMN self_focus_feedback TEXT"))
            conn.commit()
            print("Added self_focus_feedback.")
        except Exception as e:
            print("self_focus_feedback may already exist.")

        # Add repetitive_wording
        try:
            conn.execute(text("ALTER TABLE feedback_reports ADD COLUMN repetitive_wording JSONB"))
            conn.commit()
            print("Added repetitive_wording.")
        except Exception as e:
            # Fallback for SQLite if it's being used in dev
            try:
                conn.execute(text("ALTER TABLE feedback_reports ADD COLUMN repetitive_wording JSON"))
                conn.commit()
                print("Added repetitive_wording (JSON).")
            except:
                print("repetitive_wording may already exist.")

    print("Migration complete.")

if __name__ == "__main__":
    migrate()
