from fastapi import Request,HTTPException,Depends,WebSocket,WebSocketException,status
import jwt
from db.database import get_db
from core.settings import settings
from db.models import *
from sqlalchemy.orm import Session


def is_authenticated(request:Request,db:Session = Depends(get_db),):
    token=request.headers.get("authorization")
    if not token:
        raise HTTPException(status_code=404,detail="You are unauthorized")
    token=token.split(" ")[-1]
    data=jwt.decode(token,settings.SECRET_KEY,settings.ALGORITHM)
    user_id=data.get("user_id")
    user=db.query(UserModel).filter(UserModel.id== user_id).first()

    return user
