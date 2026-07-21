from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie
from sqlalchemy.orm import Session
import bcrypt
import hashlib
import smtplib
from email.message import EmailMessage
from jose import jwt, JWTError
from datetime import datetime, timedelta
from pydantic import BaseModel
from database import get_db
from rate_limit import rate_limit
import models
import os

router = APIRouter()
SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-diary-key-you-should-change")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7
RESET_TOKEN_EXPIRE_MINUTES = 30

class UserCreate(BaseModel):
    email: str
    password: str
    name: str

class UserLogin(BaseModel):
    email: str
    password: str

class ForgotPassword(BaseModel):
    email: str

class ResetPassword(BaseModel):
    token: str
    new_password: str

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

def _password_fingerprint(hashed_password: str) -> str:
    # Bound to the current hash so a reset token becomes single-use:
    # once the password changes, the fingerprint no longer matches.
    return hashlib.sha256(hashed_password.encode("utf-8")).hexdigest()[:16]


def _send_reset_link(email: str, reset_url: str):
    """Email the reset link if SMTP is configured; otherwise log it.

    Self-hosted deployments often have no mail server — printing the link to
    the backend logs lets the operator recover an account without one.
    """
    smtp_host = os.getenv("SMTP_HOST")
    if not smtp_host:
        print(f"[password-reset] SMTP not configured. Reset link for {email}: {reset_url}")
        return

    msg = EmailMessage()
    msg["Subject"] = "Reset your Notebook password"
    msg["From"] = os.getenv("SMTP_FROM", "notebook@localhost")
    msg["To"] = email
    msg.set_content(
        "A password reset was requested for your Notebook journal.\n\n"
        f"Reset it here (valid for {RESET_TOKEN_EXPIRE_MINUTES} minutes): {reset_url}\n\n"
        "If you didn't request this, you can safely ignore this email."
    )
    port = int(os.getenv("SMTP_PORT", "587"))
    with smtplib.SMTP(smtp_host, port) as server:
        server.starttls()
        smtp_user = os.getenv("SMTP_USER")
        if smtp_user:
            server.login(smtp_user, os.getenv("SMTP_PASSWORD", ""))
        server.send_message(msg)


@router.post("/api/auth/register", status_code=status.HTTP_201_CREATED, dependencies=[Depends(rate_limit("register", 5, 3600))])
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

@router.post("/api/auth/login", status_code=status.HTTP_200_OK, dependencies=[Depends(rate_limit("login", 10, 300))])
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

@router.post("/api/auth/forgot-password", status_code=status.HTTP_200_OK, dependencies=[Depends(rate_limit("forgot", 3, 900))])
def forgot_password(payload: ForgotPassword, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == payload.email).first()
    if db_user:
        reset_token = jwt.encode(
            {
                "userId": db_user.id,
                "purpose": "pwreset",
                "pwfp": _password_fingerprint(db_user.password),
                "exp": datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES),
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )
        app_url = os.getenv("APP_URL", "http://localhost:3000").rstrip("/")
        try:
            _send_reset_link(payload.email, f"{app_url}/reset-password?token={reset_token}")
        except Exception as e:
            print(f"[password-reset] Failed to deliver reset email: {e}")
    # Identical response whether or not the account exists — don't leak membership
    return {"success": True, "message": "If that account exists, a reset link has been sent."}

@router.post("/api/auth/reset-password", status_code=status.HTTP_200_OK, dependencies=[Depends(rate_limit("reset", 5, 900))])
def reset_password(payload: ResetPassword, db: Session = Depends(get_db)):
    if len(payload.new_password) < 5 or len(payload.new_password) > 71:
        raise HTTPException(status_code=422, detail="Password must be between 5 and 71 characters.")
    try:
        data = jwt.decode(payload.token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=400, detail="Reset link is invalid or has expired.")
    if data.get("purpose") != "pwreset":
        raise HTTPException(status_code=400, detail="Reset link is invalid or has expired.")

    db_user = db.query(models.User).filter(models.User.id == data.get("userId")).first()
    # Fingerprint mismatch means the password already changed since the token was
    # issued (token is single-use) — treat it the same as an expired link.
    if not db_user or data.get("pwfp") != _password_fingerprint(db_user.password):
        raise HTTPException(status_code=400, detail="Reset link is invalid or has expired.")

    salt = bcrypt.gensalt()
    db_user.password = bcrypt.hashpw(payload.new_password.encode("utf-8"), salt).decode("utf-8")
    db.commit()
    return {"success": True, "message": "Password updated. You can now log in."}
