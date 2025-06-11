from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from main import Note, User, get_session, get_current_user

router = APIRouter(prefix="/api")


@router.get("/notes", response_model=List[Note])
async def list_notes(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    db_notes = session.exec(
        select(Note).where(Note.owner_id == current_user.id)
    ).all()
    return [
        Note(**n.dict(exclude={"author"}), author=current_user.username)
        for n in db_notes
    ]


@router.post("/notes", response_model=Note)
async def create_note(
    note: Note,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    note.id = None
    note.owner_id = current_user.id
    note.author = None
    session.add(note)
    session.commit()
    session.refresh(note)
    return Note(**note.dict(exclude={"author"}), author=current_user.username)


@router.put("/notes/{note_id}", response_model=Note)
async def update_note(
    note_id: int,
    data: Note,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    db_note = session.get(Note, note_id)
    if not db_note:
        raise HTTPException(status_code=404, detail="Note not found")
    if db_note.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    db_note.category, db_note.title, db_note.description = (
        data.category,
        data.title,
        data.description,
    )
    session.add(db_note)
    session.commit()
    session.refresh(db_note)
    return Note(**db_note.dict(exclude={"author"}), author=current_user.username)


@router.delete("/notes/{note_id}")
async def delete_note(
    note_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    db_note = session.get(Note, note_id)
    if not db_note:
        raise HTTPException(status_code=404, detail="Note not found")
    if db_note.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    session.delete(db_note)
    session.commit()
    return {"ok": True}


@router.get("/all_notes", response_model=List[Note])
async def list_all_notes(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Return notes from all users for browsing."""
    db_notes = session.exec(select(Note)).all()
    users = session.exec(select(User)).all()
    user_map = {u.id: u.username for u in users}
    return [
        Note(**n.dict(exclude={"author"}), author=user_map.get(n.owner_id))
        for n in db_notes
    ]

