from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List
from collections import deque
import time
from backend import models, schemas, auth
from backend.database import get_db

router = APIRouter(tags=["Public"])

_REGISTER_ATTEMPTS: dict[str, deque[float]] = {}
_REGISTER_WINDOW_SECONDS = 60.0
_REGISTER_MAX_ATTEMPTS_PER_WINDOW = 10

# ==========================================
# AUTHENTICATION
# ==========================================

@router.post("/auth/login", response_model=schemas.Token)
def login(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    username = auth.normalize_registration_id(payload.username)
    user = db.query(models.User).filter(func.lower(models.User.registration_id) == username).first()
    if not user or not auth.verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account inactive")

    token = auth.create_access_token(data={"user_id": str(user.id), "role": user.role})
    return {"access_token": token, "token_type": "bearer", "role": user.role, "display_name": user.display_name}

@router.post("/auth/register", response_model=schemas.UserResponse)
def register_student(user: schemas.UserCreate, request: Request, db: Session = Depends(get_db)):
    # Basic per-IP rate limit (best-effort, in-memory)
    ip = (request.client.host if request.client else "unknown") or "unknown"
    now = time.time()
    q = _REGISTER_ATTEMPTS.get(ip)
    if not q:
        q = deque()
        _REGISTER_ATTEMPTS[ip] = q
    while q and (now - q[0]) > _REGISTER_WINDOW_SECONDS:
        q.popleft()
    if len(q) >= _REGISTER_MAX_ATTEMPTS_PER_WINDOW:
        raise HTTPException(status_code=429, detail="Too many registration attempts. Please try again later.")
    q.append(now)

    # Time-based bot check (client must spend at least ~1.5s on the form)
    if user.form_started_at is not None:
        now_ms = int(now * 1000)
        started_at = int(user.form_started_at)
        if 0 < started_at < (now_ms + 5000):
            delta = now_ms - started_at
            if 0 <= delta < 1500:
                raise HTTPException(status_code=400, detail="Please try again.")

    # 1. Check if ID exists
    reg_id = auth.normalize_registration_id(user.registration_id)
    if db.query(models.User).filter(func.lower(models.User.registration_id) == reg_id).first():
        raise HTTPException(status_code=400, detail="Registration ID already registered")

    # 2. Create Student
    new_user = models.User(
        registration_id=reg_id,
        display_name=user.display_name,
        password_hash=auth.get_password_hash(user.password),
        role="student",
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # 3. Link to Class Group
    if user.class_ids:
        for cid in user.class_ids:
            db.add(models.StudentClass(student_id=new_user.id, class_id=cid))
        db.commit()

    return new_user

@router.post("/auth/change-password")
def change_password(payload: schemas.ChangePassword, db: Session = Depends(get_db), user: models.User = Depends(auth.get_current_user)):
    if not auth.verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Old password is incorrect")

    user.password_hash = auth.get_password_hash(payload.new_password)
    db.commit()
    return {"status": "ok"}

# ==========================================
# REGISTRATION
# ==========================================

# Step 1: Get Departments
@router.get("/departments", response_model=List[schemas.DepartmentResponse])
def get_public_departments(db: Session = Depends(get_db)):
    return db.query(models.Department).filter_by(is_active=True).all()

# Step 2: Get Programs for selected Dept
@router.get("/departments/{dept_id}/programs", response_model=List[schemas.ProgramResponse])
def get_public_programs(dept_id: int, db: Session = Depends(get_db)):
    return db.query(models.Program).filter_by(department_id=dept_id).all()

# Step 3: Get Sessions (Semesters) for selected Dept
@router.get("/departments/{dept_id}/semesters", response_model=List[schemas.SemesterResponse])
def get_public_sessions(dept_id: int, db: Session = Depends(get_db)):
    links = db.query(models.DeptSemester).filter_by(department_id=dept_id, is_active=True).all()
    sem_ids = [l.semester_id for l in links]
    return db.query(models.Semester).filter(
        models.Semester.id.in_(sem_ids),
        models.Semester.is_active == True
    ).all()

# Step 4: Get Classes for selected Session + Program
@router.get("/semesters/{sem_id}/classes", response_model=List[schemas.ClassResponse])
def get_public_classes(sem_id: int, program_id: int, db: Session = Depends(get_db)):
    return db.query(models.Class).filter_by(
        semester_id=sem_id, 
        program_id=program_id, 
        is_active=True
    ).all()
