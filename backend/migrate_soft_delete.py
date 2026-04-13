from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "postgresql://diary_user:diary_password@localhost/diary_db"

engine = create_engine(DATABASE_URL)

def migrate():
    with engine.connect() as conn:
        # We run each statement in its own transaction to avoid "InFailedSqlTransaction"
        
        # 1. Add is_deleted
        try:
            print("Attempting to add 'is_deleted' column...")
            conn.execute(text("ALTER TABLE journal_entries ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE"))
            conn.commit()
            print("Successfully added 'is_deleted'.")
        except Exception as e:
            # Re-connect or reset if needed, but since we are in a block, we might need a fresh one or just catch "already exists"
            print(f"Note: Could not add 'is_deleted' (it may already exist).")
            # We don't need a rollback here if we use autocommit or just catch and continue with a fresh start
        
    with engine.connect() as conn:
        # 2. Add deleted_at
        try:
            print("Attempting to add 'deleted_at' column...")
            conn.execute(text("ALTER TABLE journal_entries ADD COLUMN deleted_at TIMESTAMP WITHOUT TIME ZONE"))
            conn.commit()
            print("Successfully added 'deleted_at'.")
        except Exception as e:
            print(f"Note: Could not add 'deleted_at' (it may already exist).")

if __name__ == "__main__":
    migrate()
