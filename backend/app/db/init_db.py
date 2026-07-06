from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Category, User, UserSettings


DEFAULT_CATEGORIES = {
    "income": ["Salary", "Freelance", "Dividends", "Refunds"],
    "expense": [
        "Food",
        "Groceries",
        "Restaurants",
        "Transport",
        "Rent/Mortgage",
        "Bills",
        "Health",
        "Insurance",
        "Taxes",
        "Shopping",
        "Subscriptions",
        "Travel",
    ],
    "investment": ["Buy", "Sell", "Dividend", "Broker fee", "Tax"],
}


def seed_system_categories(db: Session) -> None:
    for category_type, names in DEFAULT_CATEGORIES.items():
        for name in names:
            exists = db.query(Category).filter_by(user_id=None, name=name, type=category_type).first()
            if not exists:
                db.add(Category(name=name, type=category_type, is_system=True))
    db.commit()


def seed_demo(db: Session) -> User:
    seed_system_categories(db)
    user = db.query(User).filter_by(email="demo@example.com").first()
    if user:
        return user
    user = User(email="demo@example.com", full_name="Demo User", password_hash=hash_password("demo-password"))
    db.add(user)
    db.flush()
    db.add(UserSettings(user_id=user.id, favorite_language="en", default_currency="EUR"))
    db.commit()
    db.refresh(user)
    return user
