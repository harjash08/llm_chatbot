from pydantic import BaseModel
class CreateUser(BaseModel):
    username:str
    password:str
    email:str


class UserResponse(BaseModel):
    id:int
    username:str
    email:str
    is_active:bool

class Login(BaseModel):
    username:str
    password:str