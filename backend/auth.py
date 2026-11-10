#This file will generate and validate API key

import hashlib

from fastapi import HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from .database import get_db
from .models import APIKey


api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False
)


def hash_api_key(api_key):
    return hashlib.sha256(
        api_key.encode()
    ).hexdigest()


def validate_api_key(
    api_key: str = Security(api_key_header),
    db: Session = Depends(get_db)
):

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key missing"
        )

    key_hash = hash_api_key(api_key)

    record = db.query(APIKey).filter(
        APIKey.key_hash == key_hash,
        APIKey.is_active.is_(True)
    ).first()

    if not record:
        raise HTTPException(
            status_code=403,
            detail="Invalid or inactive API key"
        )

    return record
