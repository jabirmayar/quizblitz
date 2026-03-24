import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session
from backend import models
from backend.auth import get_password_hash
from backend.database import SessionLocal

def seed_admin():
    db: Session = SessionLocal()
    try:
        # Check if any admin exists
        admin = db.query(models.User).filter(models.User.role == "admin").first()
        if not admin:
            print("🌱 Seeding default Admin user...")
            hashed_password = get_password_hash("admin123")
            new_admin = models.User(
                id=1,  # Force ID=1 as per architecture
                registration_id="admin",
                display_name="System Administrator",
                password_hash=hashed_password,
                role="admin",
                is_active=True
            )
            db.add(new_admin)
            db.commit()
            print("✅ Admin created! Username: 'admin' | Password: 'admin123'")
        else:
            print("✅ Admin user already exists. Skipping seed.")
    except Exception as e:
        print(f"❌ Error seeding admin: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_admin()
