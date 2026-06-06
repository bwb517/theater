from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from database import get_db
from auth import hash_password, verify_password, create_access_token, get_current_user
from limiter import limiter
import models

router = APIRouter(prefix="/api/auth", tags=["auth"])

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=8, max_length=128)

class LoginRequest(BaseModel):
    username: str = Field(..., max_length=50)
    password: str = Field(..., max_length=128)

@router.post("/register")
@limiter.limit("10/minute")
def register(request: Request, req: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.username == req.username).first():
        raise HTTPException(400, "Username already taken")
    if db.query(models.User).filter(models.User.email == req.email).first():
        raise HTTPException(400, "Email already registered")
    user = models.User(
        username=req.username,
        email=req.email,
        hashed_password=hash_password(req.password),
        role="player"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": user.id, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "user": {
        "id": user.id, "username": user.username, "email": user.email, "role": user.role
    }}

@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == req.username).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    token = create_access_token({"sub": user.id, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "user": {
        "id": user.id, "username": user.username, "email": user.email, "role": user.role
    }}

@router.get("/me")
def me(user: models.User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username, "email": user.email, "role": user.role}
