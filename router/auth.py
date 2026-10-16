from fastapi import APIRouter,Depends,UploadFile, File,Request,Form,BackgroundTasks
from schemas.user import *
from db.database import get_db
from sqlalchemy.orm import Session
from db.models import *
from fastapi import APIRouter,Depends,HTTPException,Request,BackgroundTasks
from pwdlib import PasswordHash
from datetime import datetime, timedelta, timezone
import jwt
from core.settings import settings
router=APIRouter()

password_hash=PasswordHash.recommended()
def get_password_hash(plain_password:str):
     return password_hash.hash(plain_password)

def verify_password(plain_password:str,hash_password:str):
     return password_hash.verify(plain_password,hash_password)


@router.post("/register/",response_model=UserResponse)
def register(body:CreateUser, db:Session=Depends(get_db)):
    existing_user=db.query(UserModel).filter(UserModel.username==body.username).first()
    if existing_user:
          raise HTTPException(status_code=400,detail="User already exist")
    user=UserModel(
         username=body.username,
         email=body.email,
         password=get_password_hash(body.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.post("/login/")
def login(body:Login,db:Session=Depends(get_db)):
    existing_user=db.query(UserModel).filter(UserModel.username==body.username).first()
   
    if existing_user is None:
          raise HTTPException(status_code=400,detail="No user exist")
    if not verify_password(body.password,existing_user.password):
        raise HTTPException(status_code=400,detail="Wrong password")
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    token=jwt.encode({"user_id":existing_user.id,"username":existing_user.username,"exp":expire},settings.SECRET_KEY,settings.ALGORITHM)
    response={
       "access_token":token,
       "username":existing_user.username,
       
   }
    return response
