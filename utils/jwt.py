import os
import jwt
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
SECRET = os.getenv("JWT_SECRET")
ALGORITHM = os.getenv("JWT_ALGORITHM")
EXP_MIN = int(os.getenv("JWT_EXPIRY_MINUTES", 15))

def create_jwt_token(payload: dict) -> str:
    payload.update({"exp": datetime.utcnow() + timedelta(minutes=EXP_MIN)})
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)
