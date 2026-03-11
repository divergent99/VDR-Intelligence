# models/db.py
from typing import Optional, List
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel, Relationship

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    projects: List["Project"] = Relationship(back_populates="owner")
    shared_projects: List["ProjectAccess"] = Relationship(back_populates="user")


class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    doc_id: str = Field(index=True, unique=True) # The ChromaDB cache key
    name: str = Field(default="Untitled Project")
    owner_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    owner: User = Relationship(back_populates="projects")
    collaborators: List["ProjectAccess"] = Relationship(back_populates="project")


class ProjectAccess(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    doc_id: str = Field(foreign_key="project.doc_id")
    user_id: int = Field(foreign_key="user.id")
    granted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    user: User = Relationship(back_populates="shared_projects")
    project: Project = Relationship(back_populates="collaborators")


class ChatMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    doc_id: str = Field(index=True)
    role: str = Field(index=True) # 'user' or 'assistant'
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
