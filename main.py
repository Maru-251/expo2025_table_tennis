from typing import Optional, List, Generator
from datetime import datetime, timedelta
import secrets

from fastapi import (
    FastAPI,
    Request,
    Depends,
    HTTPException,
    status,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from sqlmodel import SQLModel, Field, Session, create_engine, select
from jose import JWTError, jwt
from passlib.context import CryptContext

# =============================================================================
# Database --------------------------------------------------------------------
# =============================================================================
DATABASE_URL = "sqlite:///./database.db"
engine = create_engine(DATABASE_URL, echo=False)

# =============================================================================
# Security utils --------------------------------------------------------------
# =============================================================================
SECRET_KEY = secrets.token_hex(32)          # ★本番は環境変数等で管理
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[str]:
    """JWT から username を取り出す"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


# =============================================================================
# ORM Models ------------------------------------------------------------------
# =============================================================================
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


class Note(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    category: str
    title: str
    description: str
    owner_id: Optional[int] = Field(default=None, foreign_key="user.id")
    # API レスポンス専用。DB には保存しない
    author: Optional[str] = Field(default=None, sa_column=None)


# =============================================================================
# Dependency ------------------------------------------------------------------
# =============================================================================
def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


async def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    """
    認証必須版  
    - Authorization: Bearer xxx  または Cookie(access_token) を読む  
    - 未認証なら 401 を投げる
    """
    if not token:
        token = request.cookies.get("access_token")

    username = decode_token(token) if token else None
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


async def get_current_user_optional(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> Optional[User]:
    """
    認証オプション版  
    - トークンが無ければ None を返すだけ
    """
    if not token:
        token = request.cookies.get("access_token")

    username = decode_token(token) if token else None
    if not username:
        return None

    return session.exec(select(User).where(User.username == username)).first()


# =============================================================================
# FastAPI app ------------------------------------------------------------------
# =============================================================================
app = FastAPI()


@app.on_event("startup")
def on_startup():
    """初回起動時にテーブルを作成（列変更時は database.db を削除してね）"""
    SQLModel.metadata.create_all(engine)


# ----------------------------- Static & Jinja2 -------------------------------
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# =============================================================================
# Registration -----------------------------------------------------------------
# =============================================================================
@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})


@app.post("/register")
async def register(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    username = form.get("username")
    password = form.get("password")

    if not username or not password:
        return templates.TemplateResponse(
            "signup.html", {"request": request, "error": "すべて入力してください"}, status_code=400
        )

    if session.exec(select(User).where(User.username == username)).first():
        return templates.TemplateResponse(
            "signup.html", {"request": request, "error": "ユーザー名は既に存在します"}, status_code=400
        )

    user = User(username=username, hashed_password=get_password_hash(password))
    session.add(user)
    session.commit()

    return RedirectResponse("/login", status_code=303)

# =============================================================================
# Login / Logout ---------------------------------------------------------------
# =============================================================================
@app.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    # 既にログイン済みならトップへ
    if current_user:
        return RedirectResponse("/", status_code=303)

    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    username = form.get("username")
    password = form.get("password")

    user = session.exec(select(User).where(User.username == username)).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "ユーザー名またはパスワードが違います"}, status_code=400
        )

    access_token = create_access_token({"sub": user.username})
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        "access_token",
        access_token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    return response


@app.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("access_token", path="/")
    return response

# =============================================================================
# Token API (for programmatic login) ------------------------------------------
# =============================================================================
@app.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    user = session.exec(select(User).where(User.username == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token = create_access_token({"sub": user.username})
    return Token(access_token=access_token)

# =============================================================================
# Front pages ------------------------------------------------------------------
# =============================================================================
@app.get("/", response_class=HTMLResponse)
async def read_root(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    # 未ログインなら /login へ
    if current_user is None:
        return RedirectResponse("/login", status_code=303)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "username": current_user.username,
        },
    )

# =============================================================================
# Notes API --------------------------------------------------------------------
# =============================================================================
@app.get("/api/notes", response_model=List[Note])
async def list_notes(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),   # 認証必須
):
    db_notes = session.exec(
        select(Note).where(Note.owner_id == current_user.id)
    ).all()
    return [
        Note(**n.dict(exclude={"author"}), author=current_user.username)
        for n in db_notes
    ]


@app.post("/api/notes", response_model=Note)
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


@app.put("/api/notes/{note_id}", response_model=Note)
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


@app.delete("/api/notes/{note_id}")
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


@app.get("/api/all_notes", response_model=List[Note])
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


@app.get("/public", response_class=HTMLResponse)
async def public_notes_page(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return templates.TemplateResponse(
        "public.html", {"request": request, "username": current_user.username}
    )
