from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

# Load from root .env
load_dotenv(dotenv_path="../.env")
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "postgresql://diary_user:diary_password@localhost:5432/diary_db"

if "?schema=" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.split("?")[0]

engine = create_engine(DATABASE_URL)

def migrate():
    with engine.connect() as conn:
        print("Starting migration for energy feature...")
        
        # Add preferences to users
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN preferences JSONB"))
            conn.commit()
            print("Added users.preferences.")
        except Exception as e:
            print(f"users.preferences may already exist or error: {e}")

        # Add energy_data to feedback_reports
        try:
            conn.execute(text("ALTER TABLE feedback_reports ADD COLUMN energy_data JSONB"))
            conn.commit()
            print("Added feedback_reports.energy_data.")
        except Exception as e:
            print(f"feedback_reports.energy_data may already exist or error: {e}")

        # Add detected_decision to feedback_reports (just in case)
        try:
            conn.execute(text("ALTER TABLE feedback_reports ADD COLUMN detected_decision TEXT"))
            conn.commit()
            print("Added feedback_reports.detected_decision.")
        except Exception as e:
            print(f"feedback_reports.detected_decision may already exist or error: {e}")

    print("Migration complete.")

if __name__ == "__main__":
    migrate()
