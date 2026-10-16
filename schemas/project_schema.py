from pydantic import BaseModel,Field
from typing import List, Optional

class CreateProject(BaseModel):
    name:str
    description:str

class ProjectResponse(BaseModel):
    id:int
    user_id:int
    name:str
    description:str

class CreateProjectSource(BaseModel):
    project_id: int
    repository_url:str | None=None
    storage_path: str | None=None

class ProjectSourceResponse(BaseModel):
    id:int
    project_id:int
    source_type:str
    repository_url: str | None=None
    storage_path:str | None=None


class CreateConversation(BaseModel):
    project_id:int
    user_id:int
    title:str | None=None

class ConversationResponse(BaseModel):
    id:int
    project_id:int
    user_id:int
    title:str | None=None

class CreateMessage(BaseModel):
    message:str 

class MessageResponse(BaseModel):
    id:int
    conversation_id:int
    role:str
    message:str 

class AIResponse(BaseModel):
    answer: str = Field(
        description="Answer to the user's question based on the indexed codebase"
    )