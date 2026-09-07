from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from app.core.security import verify_password, get_password_hash, create_access_token
from app.db.supabase_client import supabase

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str = "customer"

@router.post("/register", status_code=201)
async def register_user(user: UserRegister):
    """Registers a new user and hashes password before saving to Supabase."""
    existing = supabase.table("users").select("id").eq("email", user.email).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pwd = get_password_hash(user.password)
    user_data = {
        "email": user.email,
        "password_hash": hashed_pwd,
        "full_name": user.full_name,
        "role": user.role
    }
    supabase.table("users").insert(user_data).execute()
    return {"status": "success", "message": "User registered successfully"}

@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """OAuth2 compatible token login for authentication."""
    res = supabase.table("users").select("*").eq("email", form_data.username).execute()
    if not res.data:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    db_user = res.data[0]
    if not isinstance(db_user, dict):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    if not verify_password(form_data.password, str(db_user.get("password_hash"))):
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    access_token = create_access_token(
        data={"sub": str(db_user.get("id")), "role": db_user.get("role", "customer"), "email": db_user.get("email")}
    )
    return {"access_token": access_token, "token_type": "bearer", "role": db_user.get("role", "customer")}