from app.db.init_db import seed_system_categories
from app.db.session import Base, SessionLocal, engine


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_system_categories(db)
        print("Seeded system categories.")
    finally:
        db.close()
