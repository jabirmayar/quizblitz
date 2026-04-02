from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from datetime import datetime, timezone
from backend import models, schemas, auth
from backend.database import get_db

router = APIRouter(tags=["Admin"])

def get_utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def normalize_pagination(page: int = 1, page_size: int = 50, max_page_size: int = 200) -> tuple[int, int, int]:
    safe_page = max(1, int(page or 1))
    safe_page_size = max(1, min(int(page_size or 50), int(max_page_size)))
    offset = (safe_page - 1) * safe_page_size
    return safe_page, safe_page_size, offset

def to_utc_iso(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    # DB stores naive UTC; annotate as UTC for clients.
    return dt.replace(tzinfo=timezone.utc).isoformat()

# ==========================================
# 1. DEPARTMENTS
# ==========================================

@router.get("/departments", response_model=List[schemas.DepartmentResponse])
def list_departments(db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    return db.query(models.Department).all()

@router.post("/departments", response_model=schemas.DepartmentResponse)
def create_department(dept: schemas.DepartmentCreate, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    new_dept = models.Department(name=dept.name, description=dept.description)
    db.add(new_dept); db.commit(); db.refresh(new_dept); return new_dept

@router.put("/departments/{id}", response_model=schemas.DepartmentResponse)
def update_department(id: int, dept: schemas.DepartmentUpdate, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    db_dept = db.query(models.Department).get(id)
    if not db_dept: raise HTTPException(404)

    data = dept.model_dump(exclude_unset=True)
    if "name" in data:
        db_dept.name = data["name"]
    if "description" in data:
        db_dept.description = data["description"]
    if "is_active" in data:
        db_dept.is_active = data["is_active"]
    db.commit(); return db_dept

@router.delete("/departments/{id}")
def delete_department(id: int, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    dept = db.query(models.Department).get(id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    dept.is_active = False
    db.commit()
    return {"status": "ok"}

# ==========================================
# 2. PROGRAMS
# ==========================================

@router.get("/departments/{dept_id}/programs", response_model=List[schemas.ProgramResponse])
def get_dept_programs(dept_id: int, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    return db.query(models.Program).filter_by(department_id=dept_id).all()

@router.post("/programs", response_model=schemas.ProgramResponse)
def create_program(data: schemas.ProgramCreate, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    new_prog = models.Program(name=data.name, department_id=data.department_id)
    db.add(new_prog); db.commit(); db.refresh(new_prog); return new_prog

@router.put("/programs/{id}", response_model=schemas.ProgramResponse)
def update_program(id: int, data: schemas.ProgramCreate, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    prog = db.query(models.Program).get(id)
    if not prog: raise HTTPException(404)
    prog.name = data.name
    db.commit(); return prog

@router.delete("/programs/{id}")
def delete_program(id: int, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    db.query(models.Program).filter_by(id=id).delete()
    db.commit(); return {"status": "ok"}

# ==========================================
# 3. SEMESTERS (SESSIONS)
# ==========================================

@router.post("/semesters", response_model=schemas.SemesterResponse)
def create_semester(sem: schemas.SemesterCreate, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    gen_code = f"{sem.season[0]}{str(sem.year)[-2:]}".upper()
    existing = db.query(models.Semester).filter_by(season=sem.season, year=sem.year).first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            existing.code = gen_code
            db.commit()
            db.refresh(existing)
        return existing
    new_s = models.Semester(season=sem.season, year=sem.year, code=gen_code)
    db.add(new_s); db.commit(); db.refresh(new_s); return new_s

@router.get("/departments/{dept_id}/semesters", response_model=List[schemas.SemesterResponse])
def list_dept_semesters(dept_id: int, db: Session = Depends(get_db), admin: models.User = Depends(auth.get_current_admin)):
    links = db.query(models.DeptSemester).filter_by(department_id=dept_id).all()
    return db.query(models.Semester).filter(models.Semester.id.in_([l.semester_id for l in links])).all()

@router.post("/dept-semesters")
def link_dept_semester(link: schemas.DeptSemesterCreate, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    existing = db.query(models.DeptSemester).filter_by(department_id=link.department_id, semester_id=link.semester_id).first()
    if existing:
        existing.is_active = True
    else:
        db.add(models.DeptSemester(department_id=link.department_id, semester_id=link.semester_id, is_active=True))
    db.commit()
    return {"status": "ok"}

@router.put("/semesters/{sem_id}", response_model=schemas.SemesterResponse)
def update_semester(sem_id: int, sem_update: schemas.SemesterUpdate, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    sem = db.query(models.Semester).get(sem_id)
    if not sem:
        raise HTTPException(status_code=404, detail="Session not found")

    data = sem_update.model_dump(exclude_unset=True)
    if "season" in data:
        sem.season = data["season"]
    if "year" in data:
        sem.year = data["year"]
    if "is_active" in data:
        sem.is_active = data["is_active"]

    if ("season" in data) or ("year" in data):
        sem.code = f"{sem.season[0]}{str(sem.year)[-2:]}".upper()

    db.commit()
    db.refresh(sem)
    return sem

@router.delete("/semesters/{sem_id}")
def deactivate_semester(sem_id: int, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    sem = db.query(models.Semester).get(sem_id)
    if not sem:
        raise HTTPException(status_code=404, detail="Session not found")

    sem.is_active = False
    db.query(models.DeptSemester).filter_by(semester_id=sem_id).update({"is_active": False})
    db.commit()
    return {"status": "ok"}

# ==========================================
# 4. SUBJECTS (ADMIN REGISTRY)
# ==========================================

@router.get("/subjects", response_model=List[schemas.SubjectResponse])
def list_subjects(dept_id: Optional[int] = None, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    query = db.query(models.Subject)
    if dept_id: query = query.filter_by(department_id=dept_id)
    return query.all()

@router.post("/subjects", response_model=schemas.SubjectResponse)
def create_subject(data: schemas.SubjectCreate, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    new_sub = models.Subject(**data.model_dump())
    db.add(new_sub); db.commit(); db.refresh(new_sub); return new_sub

@router.put("/subjects/{id}", response_model=schemas.SubjectResponse)
def update_subject(id: int, data: schemas.SubjectUpdate, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    sub = db.query(models.Subject).get(id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subject not found")

    payload = data.model_dump(exclude_unset=True)
    if "name" in payload and payload["name"] is not None:
        sub.name = payload["name"]
    if "code" in payload and payload["code"] is not None:
        sub.code = payload["code"].strip().upper()

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Subject code already exists")

    db.refresh(sub)
    return sub

@router.delete("/subjects/{id}")
def delete_subject(id: int, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    db.query(models.Subject).filter_by(id=id).delete()
    db.commit(); return {"status": "ok"}

# ==========================================
# 5. CLASSES (GROUPS) & CURRICULUM
# ==========================================

@router.get("/classes", response_model=List[schemas.ClassResponse])
def list_all_classes(db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    return db.query(models.Class).all()

@router.get("/departments/{dept_id}/classes", response_model=List[schemas.ClassResponse])
def get_classes_by_department(dept_id: int, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    return db.query(models.Class).join(models.Program).filter(models.Program.department_id == dept_id).all()

@router.get("/semesters/{sem_id}/classes", response_model=List[schemas.ClassResponse])
def get_classes_by_context(
    sem_id: int, 
    program_id: Optional[int] = None, 
    department_id: Optional[int] = None, 
    include_inactive: bool = False,
    db: Session = Depends(get_db), 
    admin_user: models.User = Depends(auth.get_current_admin)
):
    query = db.query(models.Class).filter(models.Class.semester_id == sem_id)

    if not include_inactive:
        query = query.filter(models.Class.is_active == True)

    if program_id:
        query = query.filter(models.Class.program_id == program_id)
    
    elif department_id:
        query = query.join(models.Program).filter(models.Program.department_id == department_id)

    return query.all()

@router.post("/classes", response_model=schemas.ClassResponse)
def create_class(cls: schemas.ClassCreate, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    prog = db.query(models.Program).get(cls.program_id)
    sess = db.query(models.Semester).get(cls.semester_id)
    
    n = cls.semester_number
    suf = "th" if 11 <= n <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    sec = cls.section.strip().upper()
    
    full_name = f"{prog.name} - {n}{suf} (Section {sec})"
    p_pre = prog.name.replace("BS ","")[:4].upper().strip()
    gen_code = f"{prog.department_id}-{p_pre}-{n}{sec}-{sess.code}".upper().replace(" ","")
    
    if db.query(models.Class).filter_by(code=gen_code).first():
        raise HTTPException(400, "Class Group exists")
        
    new_c = models.Class(program_id=cls.program_id, semester_id=cls.semester_id, semester_number=n, section=sec, name=full_name, code=gen_code, is_active=True)
    db.add(new_c); db.commit(); db.refresh(new_c); return new_c

@router.put("/classes/{class_id}", response_model=schemas.ClassResponse)
def update_class(class_id: int, update: schemas.ClassUpdate, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    cls = db.query(models.Class).get(class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")

    data = update.model_dump(exclude_unset=True)
    if "is_active" in data:
        cls.is_active = data["is_active"]

    recompute = False
    if "semester_number" in data and data["semester_number"] is not None:
        cls.semester_number = int(data["semester_number"])
        recompute = True
    if "section" in data and data["section"] is not None:
        cls.section = data["section"].strip().upper()
        recompute = True

    if recompute:
        prog = db.query(models.Program).get(cls.program_id)
        sess = db.query(models.Semester).get(cls.semester_id)
        if not prog or not sess:
            raise HTTPException(status_code=400, detail="Invalid class data")

        n = int(cls.semester_number)
        suf = "th" if 11 <= n <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        sec = (cls.section or "").strip().upper()

        full_name = f"{prog.name} - {n}{suf} (Section {sec})"
        p_pre = prog.name.replace("BS ", "")[:4].upper().strip()
        gen_code = f"{prog.department_id}-{p_pre}-{n}{sec}-{sess.code}".upper().replace(" ", "")

        existing = db.query(models.Class).filter(models.Class.code == gen_code, models.Class.id != cls.id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Class code already exists")

        cls.name = full_name
        cls.code = gen_code

    db.commit()
    db.refresh(cls)
    return cls

# Mapping Subjects to a Class Group
@router.post("/classes/{class_id}/subjects")
def assign_subjects_to_class(class_id: int, subject_ids: List[int], db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    db.query(models.ClassSubject).filter_by(class_id=class_id).delete()
    for sid in subject_ids:
        db.add(models.ClassSubject(class_id=class_id, subject_id=sid))
    db.commit(); return {"status": "ok"}

@router.get("/classes/{class_id}/subjects")
def get_class_subject_ids(class_id: int, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    links = db.query(models.ClassSubject).filter_by(class_id=class_id).all()
    return [l.subject_id for l in links]

@router.get("/classes/{class_id}/subjects-detailed", response_model=List[schemas.SubjectResponse])
def get_class_subjects_detailed(class_id: int, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    links = db.query(models.ClassSubject).filter_by(class_id=class_id).all()
    subject_ids = [l.subject_id for l in links]
    return db.query(models.Subject).filter(models.Subject.id.in_(subject_ids)).all()

# ==========================================
# 6. FACULTY & TRIPLE ASSIGNMENTS
# ==========================================

@router.post("/teachers", response_model=schemas.UserResponse)
def provision_teacher(t: schemas.TeacherCreate, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    reg_id = auth.normalize_registration_id(t.registration_id)
    existing = db.query(models.User).filter(func.lower(models.User.registration_id) == reg_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Registration ID already exists")

    new_t = models.User(registration_id=reg_id, display_name=t.display_name, password_hash=auth.get_password_hash(t.password), role="teacher", is_active=True)
    db.add(new_t)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Could not create teacher (duplicate or invalid data)")
    db.refresh(new_t)
    return new_t

@router.put("/teachers/{teacher_id}", response_model=schemas.UserResponse)
def update_teacher(teacher_id: int, update: schemas.TeacherUpdate, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    teacher = db.query(models.User).get(teacher_id)
    if not teacher or teacher.role != "teacher":
        raise HTTPException(status_code=404, detail="Teacher not found")

    data = update.model_dump(exclude_unset=True)
    if "display_name" in data and data["display_name"] is not None:
        teacher.display_name = data["display_name"]

    if "registration_id" in data and data["registration_id"] is not None:
        reg_id = auth.normalize_registration_id(data["registration_id"])
        existing = db.query(models.User).filter(func.lower(models.User.registration_id) == reg_id, models.User.id != teacher.id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Registration ID already exists")
        teacher.registration_id = reg_id

    if "is_active" in data and data["is_active"] is not None:
        teacher.is_active = bool(data["is_active"])

    if "password" in data and data["password"]:
        teacher.password_hash = auth.get_password_hash(data["password"])

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Could not update teacher (duplicate or invalid data)")

    db.refresh(teacher)
    return teacher

@router.delete("/teachers/{teacher_id}")
def delete_teacher(teacher_id: int, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    teacher = db.query(models.User).get(teacher_id)
    if not teacher or teacher.role != "teacher":
        raise HTTPException(status_code=404, detail="Teacher not found")

    assignments_count = db.query(models.TeacherAssignment).filter_by(teacher_id=teacher_id).count()
    quizzes_count = db.query(models.Quiz).filter_by(created_by=teacher_id).count()
    graded_count = db.query(models.Answer).filter_by(graded_by=teacher_id).count()
    sessions_count = db.query(models.QuizSession).filter_by(user_id=teacher_id).count()
    overrides_count = db.query(models.QuizSession).filter_by(score_overridden_by=teacher_id).count()

    reasons: list[str] = []
    if assignments_count:
        reasons.append(f"{assignments_count} subject assignment(s)")
    if quizzes_count:
        reasons.append(f"{quizzes_count} quiz(zes) created")
    if graded_count:
        reasons.append(f"{graded_count} graded answer(s)")
    if sessions_count:
        reasons.append(f"{sessions_count} quiz session(s) under this user")
    if overrides_count:
        reasons.append(f"{overrides_count} score override(s) recorded")

    if reasons:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "This faculty account has linked data and cannot be deleted.",
                "reasons": reasons,
                "suggestion": "Deactivate the account instead (Active = false)."
            },
        )

    db.query(models.User).filter_by(id=teacher_id).delete()
    db.commit()
    return {"status": "deleted"}

# Triple Junction Assignment: Teacher + Class + Subject
class AssignmentRequest(BaseModel):
    teacher_id: int
    class_id: int
    subject_id: int

@router.post("/faculty-assignments")
def assign_faculty(data: AssignmentRequest, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    # Check for existing duplicate assignment
    exist = db.query(models.TeacherAssignment).filter_by(class_id=data.class_id, subject_id=data.subject_id).first()
    if exist:
        exist.teacher_id = data.teacher_id
    else:
        db.add(models.TeacherAssignment(**data.model_dump()))
    db.commit(); return {"status": "ok"}

@router.get("/faculty-assignments/{teacher_id}")
def get_teacher_assignments(teacher_id: int, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    assigns = db.query(models.TeacherAssignment).filter_by(teacher_id=teacher_id).all()
    return [{
        "id": a.id,
        "class_name": db.query(models.Class).get(a.class_id).name,
        "subject_name": db.query(models.Subject).get(a.subject_id).name
    } for a in assigns]

@router.delete("/faculty-assignments/{id}")
def revoke_assignment(id: int, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    db.query(models.TeacherAssignment).filter_by(id=id).delete()
    db.commit(); return {"status": "ok"}

# ==========================================
# 7. USERS, RESULTS & MAINTENANCE
# ==========================================

@router.get("/users", response_model=List[dict])
def list_users(role: Optional[str] = None, db: Session = Depends(get_db), admin: models.User = Depends(auth.get_current_admin)):
    query = db.query(models.User)
    if role: query = query.filter(models.User.role == role)
    users = query.all()
    res = []
    for u in users:
        data = {"id": u.id, "registration_id": u.registration_id, "display_name": u.display_name, "role": u.role, "is_active": u.is_active, "created_at": u.created_at, "class_name": "Unassigned"}
        if u.role == "student":
            link = db.query(models.StudentClass).filter_by(student_id=u.id).first()
            if link:
                c = db.query(models.Class).get(link.class_id)
                data["class_name"] = c.name if c else "Unassigned"
        res.append(data)
    return res

@router.get("/students")
def list_students_paged(
    dept_id: Optional[int] = None,
    sem_id: Optional[int] = None,
    class_id: Optional[int] = None,
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
    db: Session = Depends(get_db),
    admin: models.User = Depends(auth.get_current_admin)
):
    safe_page, safe_page_size, offset = normalize_pagination(page, page_size, max_page_size=200)

    # One class per student (best-effort): pick the smallest class_id link.
    sc_one = db.query(
        models.StudentClass.student_id.label("student_id"),
        func.min(models.StudentClass.class_id).label("class_id")
    ).group_by(models.StudentClass.student_id).subquery()

    query = db.query(
        models.User.id,
        models.User.registration_id,
        models.User.display_name,
        models.User.is_active,
        models.User.created_at,
        sc_one.c.class_id.label("class_id"),
        models.Class.name.label("class_name"),
    ).outerjoin(sc_one, sc_one.c.student_id == models.User.id)\
     .outerjoin(models.Class, models.Class.id == sc_one.c.class_id)\
     .outerjoin(models.Program, models.Program.id == models.Class.program_id)

    query = query.filter(models.User.role == "student")

    if dept_id is not None:
        query = query.filter(models.Program.department_id == dept_id)
    if sem_id is not None:
        query = query.filter(models.Class.semester_id == sem_id)
    if class_id is not None:
        query = query.filter(sc_one.c.class_id == class_id)

    if q:
        q_norm = f"%{q.strip().lower()}%"
        query = query.filter(
            func.lower(models.User.display_name).like(q_norm) |
            func.lower(models.User.registration_id).like(q_norm)
        )

    total = query.count()
    rows = query.order_by(models.User.created_at.desc()).offset(offset).limit(safe_page_size).all()

    items = [{
        "id": r.id,
        "registration_id": r.registration_id,
        "display_name": r.display_name,
        "is_active": r.is_active,
        "created_at": to_utc_iso(r.created_at),
        "class_id": r.class_id,
        "class_name": r.class_name or "Unassigned",
    } for r in rows]

    return {"items": items, "total": total, "page": safe_page, "page_size": safe_page_size}

@router.get("/global-results")
def get_global_results(dept_id: Optional[int] = None, sem_id: Optional[int] = None, class_id: Optional[int] = None, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    query = db.query(models.QuizSession).filter(models.QuizSession.status == "done")
    if dept_id or sem_id or class_id:
        query = query.join(models.Quiz).join(models.QuizClass).join(models.Class)
        if dept_id: query = query.filter(models.Class.program_id.in_(db.query(models.Program.id).filter_by(department_id=dept_id)))
        if sem_id: query = query.filter(models.Class.semester_id == sem_id)
        if class_id: query = query.filter(models.Class.id == class_id)
    sessions = query.all()
    output = []
    any_flag_repairs = False
    for s in sessions:
        u, q = db.query(models.User).get(s.user_id), db.query(models.Quiz).get(s.quiz_id)
        qc = db.query(models.QuizClass).filter_by(quiz_id=q.id).first()
        c = db.query(models.Class).get(qc.class_id) if qc else None
        tp_raw = db.query(models.Question).filter_by(quiz_id=q.id).with_entities(models.func.sum(models.Question.points)).scalar()
        tp = float(tp_raw or 0)
        
        # Get cheat events for this session
        cheat_events = db.query(models.CheatEvent).filter_by(session_id=s.id).order_by(models.CheatEvent.occurred_at).all()
        computed_flag_count = len(cheat_events)
        if s.cheat_flag_count != computed_flag_count:
            s.cheat_flag_count = computed_flag_count
            any_flag_repairs = True
        cheat_events_list = [{
            "id": e.id,
            "event_type": e.event_type,
            "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
            "detail": e.detail
        } for e in cheat_events]
        
        # Calculate pass/fail status
        effective_score = s.score_override if s.score_override is not None else (s.score or 0)
        percentage_score = (effective_score / tp * 100) if tp > 0 else 0
        is_passed = percentage_score >= q.pass_percentage
        
        output.append({
            "id": s.id, 
            "student_name": u.display_name, 
            "registration_id": u.registration_id, 
            "quiz_title": q.title, 
            "class_name": c.name if c else "Unknown", 
            "score": effective_score,
            "raw_score": s.score,
            "is_score_overridden": s.score_override is not None,
            "score_override_reason": s.score_override_reason,
            "total_points": tp, 
            "flags": computed_flag_count, 
            "cheat_events": cheat_events_list,
            "submitted_at": s.submitted_at,
            "pass_percentage": q.pass_percentage,
            "percentage_score": round(percentage_score, 1),
            "is_passed": is_passed
        })

    if any_flag_repairs:
        db.commit()
    return output

@router.get("/global-results/paged")
def get_global_results_paged(
    dept_id: Optional[int] = None,
    sem_id: Optional[int] = None,
    class_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 25,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(auth.get_current_admin)
):
    safe_page, safe_page_size, offset = normalize_pagination(page, page_size, max_page_size=200)

    # Quiz -> (first) class mapping to avoid exploding rows when a quiz is assigned to multiple classes.
    qc_one = db.query(
        models.QuizClass.quiz_id.label("quiz_id"),
        func.min(models.QuizClass.class_id).label("class_id")
    ).group_by(models.QuizClass.quiz_id).subquery()

    # Total points per quiz
    tp = db.query(
        models.Question.quiz_id.label("quiz_id"),
        func.coalesce(func.sum(models.Question.points), 0).label("total_points")
    ).group_by(models.Question.quiz_id).subquery()

    base = db.query(
        models.QuizSession,
        models.User.display_name.label("student_name"),
        models.User.registration_id.label("registration_id"),
        models.Quiz.title.label("quiz_title"),
        models.Quiz.pass_percentage.label("pass_percentage"),
        models.Class.name.label("class_name"),
        tp.c.total_points.label("total_points"),
    ).join(models.User, models.User.id == models.QuizSession.user_id)\
     .join(models.Quiz, models.Quiz.id == models.QuizSession.quiz_id)\
     .outerjoin(qc_one, qc_one.c.quiz_id == models.Quiz.id)\
     .outerjoin(models.Class, models.Class.id == qc_one.c.class_id)\
     .outerjoin(models.Program, models.Program.id == models.Class.program_id)\
     .outerjoin(tp, tp.c.quiz_id == models.Quiz.id)\
     .filter(models.QuizSession.status == "done")

    if dept_id is not None:
        base = base.filter(models.Program.department_id == dept_id)
    if sem_id is not None:
        base = base.filter(models.Class.semester_id == sem_id)
    if class_id is not None:
        base = base.filter(models.Class.id == class_id)

    total = base.count()

    rows = base.order_by(models.QuizSession.submitted_at.desc(), models.QuizSession.id.desc())\
        .offset(offset).limit(safe_page_size).all()

    session_ids = [r.QuizSession.id for r in rows]
    cheat_events = []
    if session_ids:
        cheat_events = db.query(models.CheatEvent).filter(models.CheatEvent.session_id.in_(session_ids))\
            .order_by(models.CheatEvent.occurred_at).all()

    events_by_session: dict[int, list[models.CheatEvent]] = {}
    for e in cheat_events:
        events_by_session.setdefault(e.session_id, []).append(e)

    any_flag_repairs = False
    items = []
    for r in rows:
        s = r.QuizSession
        events = events_by_session.get(s.id, [])
        computed_flag_count = len(events)
        if s.cheat_flag_count != computed_flag_count:
            s.cheat_flag_count = computed_flag_count
            any_flag_repairs = True

        total_points = float(r.total_points or 0)
        effective_score = float(s.score_override if s.score_override is not None else (s.score or 0))
        percentage_score = (effective_score / total_points * 100) if total_points > 0 else 0
        is_passed = percentage_score >= float(r.pass_percentage or 0)

        items.append({
            "id": s.id,
            "student_name": r.student_name,
            "registration_id": r.registration_id,
            "quiz_title": r.quiz_title,
            "class_name": r.class_name or "Unknown",
            "score": effective_score,
            "raw_score": s.score,
            "is_score_overridden": s.score_override is not None,
            "score_override_reason": s.score_override_reason,
            "total_points": total_points,
            "flags": computed_flag_count,
            "cheat_events": [{
                "id": e.id,
                "event_type": e.event_type,
                "occurred_at": to_utc_iso(e.occurred_at),
                "detail": e.detail
            } for e in events],
            "submitted_at": to_utc_iso(s.submitted_at),
            "pass_percentage": float(r.pass_percentage or 0),
            "percentage_score": round(percentage_score, 1),
            "is_passed": is_passed
        })

    if any_flag_repairs:
        db.commit()

    return {"items": items, "total": total, "page": safe_page, "page_size": safe_page_size}

@router.post("/sessions/{session_id}/override-zero")
def admin_override_session_zero(session_id: int, data: schemas.SessionZeroOverride, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    session = db.query(models.QuizSession).get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status != "done":
        raise HTTPException(status_code=400, detail="Session not submitted yet")

    session.score_override = 0.0
    session.score_override_reason = data.reason
    session.score_overridden_by = admin_user.id
    session.score_overridden_at = get_utc_now()
    session.result_released = True
    db.commit()

    return {"status": "ok", "score": 0.0, "is_score_overridden": True}

@router.delete("/sessions/{session_id}/override-zero")
def admin_clear_session_zero_override(session_id: int, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    session = db.query(models.QuizSession).get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.score_override = None
    session.score_override_reason = None
    session.score_overridden_by = None
    session.score_overridden_at = None

    if session.status == "done":
        ungraded = db.query(models.Answer).join(models.Question).filter(
            models.Answer.session_id == session.id,
            models.Question.type == "qa",
            models.Answer.graded_at == None
        ).count()
        session.result_released = (ungraded == 0)
    else:
        session.result_released = False

    db.commit()
    return {"status": "ok", "is_score_overridden": False}

class BulkMoveRequest(BaseModel):
    student_ids: List[int]
    new_class_id: int

@router.post("/students/bulk-move")
def bulk_move(data: BulkMoveRequest, db: Session = Depends(get_db), admin: models.User = Depends(auth.get_current_admin)):
    for sid in data.student_ids:
        db.query(models.StudentClass).filter_by(student_id=sid).delete()
        db.add(models.StudentClass(student_id=sid, class_id=data.new_class_id))
    db.commit(); return {"status": "ok"}

class PasswordResetRequest(BaseModel):
    user_id: int
    new_password: str

@router.post("/users/reset-password")
def reset_pw(data: PasswordResetRequest, db: Session = Depends(get_db), admin: models.User = Depends(auth.get_current_admin)):
    u = db.query(models.User).get(data.user_id)
    if u: u.password_hash = auth.get_password_hash(data.new_password); db.commit()
    return {"status": "ok"}
