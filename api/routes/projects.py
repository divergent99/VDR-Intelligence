# api/routes/projects.py
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select
from typing import List

from models.db import User, Project, ProjectAccess
from api.dependencies import get_session, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["projects"])

class ShareRequest(BaseModel):
    email: str

class ProjectOut(BaseModel):
    doc_id: str
    name: str
    owner_email: str
    role: str # "owner" or "collaborator"


@router.get("/me", response_model=List[ProjectOut])
def get_my_projects(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    owned = session.exec(select(Project).where(Project.owner_id == current_user.id)).all()
    shared = session.exec(select(ProjectAccess).where(ProjectAccess.user_id == current_user.id)).all()
    
    results = []
    for p in owned:
        results.append(ProjectOut(doc_id=p.doc_id, name=p.name, owner_email=current_user.email, role="owner"))
        
    for access in shared:
        p = session.exec(select(Project).where(Project.doc_id == access.doc_id)).first()
        if p:
            owner = session.exec(select(User).where(User.id == p.owner_id)).first()
            results.append(ProjectOut(
                doc_id=p.doc_id, name=p.name, 
                owner_email=owner.email if owner else "unknown", 
                role="collaborator"
            ))
        
    return results

@router.post("/{doc_id}/share")
def share_project(doc_id: str, req: ShareRequest, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    project = session.exec(select(Project).where(Project.doc_id == doc_id)).first()
    
    if not project:
        # Auto-create: the current user becomes the owner
        project = Project(doc_id=doc_id, name="Shared Project", owner_id=current_user.id)
        session.add(project)
        session.commit()
        session.refresh(project)

    # Self-heal orphaned projects
    owner = session.exec(select(User).where(User.id == project.owner_id)).first()
    if not owner:
        logger.info("Orphaned project %s — reassigning to %s", doc_id[:12], current_user.email)
        project.owner_id = current_user.id
        session.add(project)
        session.commit()

    # Allow both owners AND collaborators to share (Google Docs model)
    is_owner = project.owner_id == current_user.id
    is_collaborator = session.exec(
        select(ProjectAccess)
        .where(ProjectAccess.doc_id == doc_id)
        .where(ProjectAccess.user_id == current_user.id)
    ).first() is not None

    if not is_owner and not is_collaborator:
        # Auto-add the current user as collaborator (they have the link)
        session.add(ProjectAccess(doc_id=doc_id, user_id=current_user.id))
        session.commit()

    target_user = session.exec(select(User).where(User.email == req.email)).first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"User '{req.email}' not found. They need to register first.")
        
    if target_user.id == current_user.id:
        return {"msg": "You already have access to this project"}
        
    existing_access = session.exec(
        select(ProjectAccess)
        .where(ProjectAccess.doc_id == doc_id)
        .where(ProjectAccess.user_id == target_user.id)
    ).first()
    
    if existing_access:
        return {"msg": f"{req.email} already has access"}

    # Check if target is the owner
    if target_user.id == project.owner_id:
        return {"msg": f"{req.email} is the project owner"}
    
    access = ProjectAccess(doc_id=doc_id, user_id=target_user.id)
    session.add(access)
    session.commit()
    
    return {"msg": f"Shared successfully with {req.email}"}
