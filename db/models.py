from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    Boolean
)
from db.database import Base
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
class UserModel(Base):
    __tablename__="user"
    id=Column(Integer,primary_key=True,index=True)
    username=Column(String(20),nullable=False)
    password=Column(String(255),nullable=False)
    email=Column(String(50),nullable=False)
    is_active=Column(Boolean,nullable=False,default=False)


class Project(Base):
    __tablename__="project"
    id=Column(Integer,primary_key=True,index=True)
    user_id=Column(Integer,ForeignKey("user.id"),nullable=False)
    name=Column(String(20),nullable=False)
    description=Column(String(100),nullable=False)
    created_at=Column(DateTime,default=datetime.utcnow)
    updated_at=Column(DateTime,default=datetime.utcnow)

class Project_Source(Base):
    __tablename__='project_source'
    id=Column(Integer,primary_key=True,index=True)
    project_id=Column(Integer,ForeignKey("project.id"),nullable=False)
    source_type=Column(String(20),nullable=False)  #"github","upload"
    repository_url: Mapped[str | None] = mapped_column(String(500),nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(500),nullable=True)
    created_at=Column(DateTime,default=datetime.utcnow)
    updated_at=Column(DateTime,default=datetime.utcnow)

class Conversation(Base):
    __tablename__ = "conversation"

    id = Column(Integer, primary_key=True, index=True)

    project_id = Column(
        Integer,
        ForeignKey("project.id"),
        nullable=False
    )

    user_id = Column(
        Integer,
        ForeignKey("user.id"),
        nullable=False
    )

    title = Column(String(255), default="New Conversation")

    created_at = Column(DateTime, default=datetime.utcnow)

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )


class ChatMessage(Base):
    __tablename__ = "chat_message"

    id = Column(Integer, primary_key=True, index=True)

    conversation_id = Column(
        Integer,
        ForeignKey("conversation.id"),
        nullable=False
    )

    role = Column(String(20), nullable=False)

    message = Column(Text, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)


