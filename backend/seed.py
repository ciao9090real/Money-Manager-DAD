from app.db.init_db import seed_demo
from app.db.session import Base, SessionLocal, engine


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = seed_demo(db)
        print(f"Seeded demo user: {user.email} / demo-password")
    finally:
        db.close()
