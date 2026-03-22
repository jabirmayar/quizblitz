from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone
from backend import models, schemas, auth
from backend.database import get_db

router = APIRouter(tags=["Admin"])

def get_utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

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
    db: Session = Depends(get_db), 
    admin_user: models.User = Depends(auth.get_current_admin)
):
    query = db.query(models.Class).filter(models.Class.semester_id == sem_id)

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
    
    full_name = f"{prog.name} — {n}{suf} Semester (Section {sec})"
    p_pre = prog.name.replace("BS ","")[:4].upper().strip()
    gen_code = f"{prog.department_id}-{p_pre}-{n}{sec}-{sess.code}".upper().replace(" ","")
    
    if db.query(models.Class).filter_by(code=gen_code).first():
        raise HTTPException(400, "Class Group exists")
        
    new_c = models.Class(program_id=cls.program_id, semester_id=cls.semester_id, semester_number=n, section=sec, name=full_name, code=gen_code, is_active=True)
    db.add(new_c); db.commit(); db.refresh(new_c); return new_c

@router.get("/semesters/{sem_id}/classes", response_model=List[schemas.ClassResponse])
def list_context_classes(sem_id: int, program_id: int, db: Session = Depends(get_db), admin_user: models.User = Depends(auth.get_current_admin)):
    return db.query(models.Class).filter_by(semester_id=sem_id, program_id=program_id).all()

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
    new_t = models.User(registration_id=t.registration_id, display_name=t.display_name, password_hash=auth.get_password_hash(t.password), role="teacher", is_active=True)
    db.add(new_t); db.commit(); db.refresh(new_t); return new_t

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
    for s in sessions:
        u, q = db.query(models.User).get(s.user_id), db.query(models.Quiz).get(s.quiz_id)
        qc = db.query(models.QuizClass).filter_by(quiz_id=q.id).first()
        c = db.query(models.Class).get(qc.class_id) if qc else None
        tp_raw = db.query(models.Question).filter_by(quiz_id=q.id).with_entities(models.func.sum(models.Question.points)).scalar()
        tp = float(tp_raw or 0)
        
        # Get cheat events for this session
        cheat_events = db.query(models.CheatEvent).filter_by(session_id=s.id).order_by(models.CheatEvent.occurred_at).all()
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
            "flags": s.cheat_flag_count, 
            "cheat_events": cheat_events_list,
            "submitted_at": s.submitted_at,
            "pass_percentage": q.pass_percentage,
            "percentage_score": round(percentage_score, 1),
            "is_passed": is_passed
        })
    return output

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
