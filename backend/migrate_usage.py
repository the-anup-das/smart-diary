import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://diary_user:diary_password@localhost:5432/diary_db")
engine = create_engine(DATABASE_URL)

def migrate():
    print("Starting migration for usage tracking...")
    with engine.connect() as conn:
        # Add columns to feedback_reports
        try:
            conn.execute(text("ALTER TABLE feedback_reports ADD COLUMN prompt_tokens INTEGER DEFAULT 0"))
            print("Added feedback_reports.prompt_tokens.")
        except Exception as e:
            print(f"Column prompt_tokens already exists or error: {e}")

        try:
            conn.execute(text("ALTER TABLE feedback_reports ADD COLUMN completion_tokens INTEGER DEFAULT 0"))
            print("Added feedback_reports.completion_tokens.")
        except Exception as e:
            print(f"Column completion_tokens already exists or error: {e}")

        try:
            conn.execute(text("ALTER TABLE feedback_reports ADD COLUMN total_tokens INTEGER DEFAULT 0"))
            print("Added feedback_reports.total_tokens.")
        except Exception as e:
            print(f"Column total_tokens already exists or error: {e}")

        conn.commit()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
