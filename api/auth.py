
import os

from fastapi import Header, HTTPException
from typing import Optional

API_KEY = os.getenv("TIXLY_API_KEY", "")


def require_key(key: Optional[str] = Header(default=None)):
    if not API_KEY or key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
 
