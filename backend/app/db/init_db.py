from sqlalchemy.orm import Session

from app.models import Category


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
