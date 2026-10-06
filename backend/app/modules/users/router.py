from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.modules.users.models import Subscription, User
from app.modules.users.schemas import RegisterRequest, TokenResponse, UserOut

router = APIRouter(tags=["users"])


def _to_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        subscription_status=user.subscription.status if user.subscription else None,
    )


@router.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(email=email, password_hash=hash_password(body.password), display_name=body.display_name)
    user.subscription = Subscription(status="trial")
    db.add(user)
    db.commit()
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/auth/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/users/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return _to_out(user)
