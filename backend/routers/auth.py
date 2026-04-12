from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie
from sqlalchemy.orm import Session
import bcrypt
from jose import jwt, JWTError
from datetime import datetime, timedelta
from pydantic import BaseModel
from database import get_db
import models
import os

router = APIRouter()
SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-diary-key-you-should-change")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

class UserCreate(BaseModel):
    email: str
    password: str
    name: str

class UserLogin(BaseModel):
    email: str
    password: str

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_session(session: str = Cookie(None)):
    if not session:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        payload = jwt.decode(session, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("userId")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Unauthorized")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Unauthorized")

@router.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, response: Response, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=409, detail="User already exists")
    
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), salt).decode('utf-8')
    new_user = models.User(email=user.email, password=hashed_password, name=user.name)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    token = create_access_token(data={"userId": new_user.id})
    response.set_cookie(key="session", value=token, httponly=True, max_age=604800, samesite="lax", path="/")
    return {"success": True, "userId": new_user.id}

@router.post("/api/auth/login", status_code=status.HTTP_200_OK)
def login(user: UserLogin, response: Response, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    is_valid = False
    if db_user:
        try:
            is_valid = bcrypt.checkpw(user.password.encode('utf-8'), db_user.password.encode('utf-8'))
        except Exception:
            is_valid = False
            
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token(data={"userId": db_user.id})
    response.set_cookie(key="session", value=token, httponly=True, max_age=604800, samesite="lax", path="/")
    return {"success": True, "userId": db_user.id}
