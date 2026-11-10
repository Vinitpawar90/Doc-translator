
from .database import engine, SessionLocal, Base
from .models import APIKey
from .auth import generate_api_key, hash_api_key

# Create database tables
Base.metadata.create_all(bind=engine)

# Generate API key
new_key = generate_api_key()

# Store hashed key in database
db = SessionLocal()

try:
    record = APIKey(
        name="Manager Project",
        key_hash=hash_api_key(new_key),
        is_active=True
    )

    db.add(record)
    db.commit()

    print("\nAPI KEY GENERATED SUCCESSFULLY")
    print("--------------------------------")
    print(new_key)
    print("--------------------------------")
    print("Save this key securely.")
    print("It will not be displayed again.")

finally:
    db.close()
