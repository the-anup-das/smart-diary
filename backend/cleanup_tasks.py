from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import models
from database import SessionLocal

def purge_old_deleted_entries():
    """
    Permanently deletes journal entries that were soft-deleted more than 90 days ago.
    This script is intended to be run by a system cron job every few months.
    """
    db: Session = SessionLocal()
    try:
        threshold = datetime.utcnow() - timedelta(days=90)
        
        # Find entries marked for deletion older than the threshold
        to_purge = db.query(models.JournalEntry).filter(
            models.JournalEntry.is_deleted == True,
            models.JournalEntry.deleted_at <= threshold
        ).all()
        
        count = len(to_purge)
        if count > 0:
            for entry in to_purge:
                db.delete(entry)
            db.commit()
            print(f"[{datetime.utcnow()}] Successfully purged {count} entries older than 90 days.")
        else:
            print(f"[{datetime.utcnow()}] No entries found for purging.")
            
    except Exception as e:
        print(f"[{datetime.utcnow()}] Error during purge: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    purge_old_deleted_entries()
