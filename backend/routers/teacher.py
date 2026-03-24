from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import List

from backend import models, schemas, auth
from backend.database import get_db

router = APIRouter(prefix="/teacher", tags=["Teacher"])

def get_utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

# ==========================================
# ASSIGNMENTS
# ==========================================

@router.get("/assignments")
def get_my_assignments(db: Session = Depends(get_db), teacher: models.User = Depends(auth.get_current_teacher)):
    assigns = db.query(models.TeacherAssignment).filter_by(teacher_id=teacher.id).all()
    return [{
        "class_id": a.class_id,
        "class_name": db.query(models.Class).get(a.class_id).name,
        "subject_id": a.subject_id,
        "subject_name": db.query(models.Subject).get(a.subject_id).name,
        "subject_code": db.query(models.Subject).get(a.subject_id).code
    } for a in assigns]

# ==========================================
# QUIZZES
# ==========================================

@router.post("/quizzes", response_model=schemas.QuizResponse)
def create_quiz(quiz: schemas.QuizCreate, db: Session = Depends(get_db), teacher: models.User = Depends(auth.get_current_teacher)):
    assignment = db.query(models.TeacherAssignment).filter_by(
        teacher_id=teacher.id, 
        subject_id=quiz.subject_id
    ).first()
    
    if not assignment:
        raise HTTPException(status_code=403, detail="Not authorized for this subject.")

    quiz_data = quiz.model_dump()
    # Handle dates: Convert to UTC and make naive for MySQL storage
    if quiz_data.get("available_from"):
        quiz_data["available_from"] = quiz_data["available_from"].astimezone(timezone.utc).replace(tzinfo=None)
    if quiz_data.get("available_until"):
        quiz_data["available_until"] = quiz_data["available_until"].astimezone(timezone.utc).replace(tzinfo=None)

    is_published_val = quiz_data.pop("is_published", False)

    new_quiz = models.Quiz(
        **quiz_data,
        created_by=teacher.id,
        is_published=is_published_val
    )
    
    db.add(new_quiz)
    db.commit()
    db.refresh(new_quiz)
    return new_quiz

@router.get("/quizzes", response_model=List[schemas.QuizResponse])
def list_my_quizzes(db: Session = Depends(get_db), teacher: models.User = Depends(auth.get_current_teacher)):
    return db.query(models.Quiz).filter(models.Quiz.created_by == teacher.id).all()

@router.get("/quizzes/{quiz_id}", response_model=schemas.QuizResponse)
def get_quiz_detail(quiz_id: int, db: Session = Depends(get_db), teacher: models.User = Depends(auth.get_current_teacher)):
    quiz = db.query(models.Quiz).filter(models.Quiz.id == quiz_id, models.Quiz.created_by == teacher.id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return quiz

@router.patch("/quizzes/{quiz_id}/toggle-status")
def toggle_quiz_status(quiz_id: int, db: Session = Depends(get_db), teacher: models.User = Depends(auth.get_current_teacher)):
    """Safe toggle that does not touch available_from/until dates."""
    quiz = db.query(models.Quiz).filter(models.Quiz.id == quiz_id, models.Quiz.created_by == teacher.id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    quiz.is_published = not quiz.is_published
    db.commit()
    return {"is_published": quiz.is_published}

# ==========================================
# ELIGIBLE CLASSES
# ==========================================

@router.get("/quizzes/{quiz_id}/eligible-classes")
def get_eligible_classes(quiz_id: int, db: Session = Depends(get_db), teacher: models.User = Depends(auth.get_current_teacher)):
    quiz = db.query(models.Quiz).get(quiz_id)
    if not quiz or quiz.created_by != teacher.id:
        raise HTTPException(403)

    assigns = db.query(models.TeacherAssignment).filter_by(
        teacher_id=teacher.id,
        subject_id=quiz.subject_id
    ).all()
    
    return [{
        "id": a.class_id,
        "name": db.query(models.Class).get(a.class_id).name,
        "code": db.query(models.Class).get(a.class_id).code
    } for a in assigns]

@router.get("/quizzes/{quiz_id}/assigned-classes")
def get_quiz_assigned_class_ids(quiz_id: int, db: Session = Depends(get_db), teacher: models.User = Depends(auth.get_current_teacher)):
    links = db.query(models.QuizClass).filter_by(quiz_id=quiz_id).all()
    return [link.class_id for link in links]

# ==========================================
# QUESTIONS
# ==========================================

@router.get("/quizzes/{quiz_id}/questions", response_model=List[schemas.QuestionResponse])
def get_quiz_questions(quiz_id: int, db: Session = Depends(get_db), teacher: models.User = Depends(auth.get_current_teacher)):
    return db.query(models.Question).filter(models.Question.quiz_id == quiz_id).all()

@router.post("/quizzes/{quiz_id}/questions", response_model=schemas.QuestionResponse)
def add_question(quiz_id: int, question: schemas.QuestionCreate, db: Session = Depends(get_db), teacher: models.User = Depends(auth.get_current_teacher)):
    quiz = db.query(models.Quiz).filter(models.Quiz.id == quiz_id, models.Quiz.created_by == teacher.id).first()
    if not quiz:
        raise HTTPException(status_code=403, detail="Not authorized")

    new_question = models.Question(quiz_id=quiz_id, **question.model_dump())
    db.add(new_question)
    db.commit()
    db.refresh(new_question)
    return new_question

# ==========================================
# ASSIGNMENTS
# ==========================================

@router.post("/quizzes/{quiz_id}/assign")
def assign_quiz_to_classes(quiz_id: int, assignment: schemas.QuizAssign, db: Session = Depends(get_db), teacher: models.User = Depends(auth.get_current_teacher)):
    quiz = db.query(models.Quiz).filter(models.Quiz.id == quiz_id, models.Quiz.created_by == teacher.id).first()
    if not quiz:
        raise HTTPException(status_code=403, detail="Not authorized")

    db.query(models.QuizClass).filter(models.QuizClass.quiz_id == quiz_id).delete()
    for class_id in assignment.class_ids:
        db.add(models.QuizClass(quiz_id=quiz_id, class_id=class_id))
    
    quiz.is_published = True
    db.commit()
    return {"message": "Quiz assigned and published"}

# ==========================================
# RESULTS & GRADING
# ==========================================

@router.get("/quizzes/{quiz_id}/results")
def get_quiz_results(quiz_id: int, db: Session = Depends(get_db), teacher: models.User = Depends(auth.get_current_teacher)):
    quiz = db.query(models.Quiz).filter_by(id=quiz_id).first()
    sessions = db.query(models.QuizSession).filter_by(quiz_id=quiz_id).all()
    
    res_list = []
    any_flag_repairs = False
    for s in sessions:
        student = db.query(models.User).get(s.user_id)
        class_link = db.query(models.QuizClass).filter_by(quiz_id=quiz_id).first()
        class_obj = db.query(models.Class).get(class_link.class_id) if class_link else None
        
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
        
        # Calculate total points and pass/fail status
        total_points_raw = db.query(models.Question).filter_by(quiz_id=quiz_id).with_entities(models.func.sum(models.Question.points)).scalar()
        total_points = float(total_points_raw or 0)
        effective_score = s.score_override if s.score_override is not None else (s.score or 0)
        percentage_score = (effective_score / total_points * 100) if total_points > 0 else 0
        is_passed = percentage_score >= quiz.pass_percentage
        
        res_list.append({
            "id": s.id,
            "class_name": class_obj.name if class_obj else "General",
            "student_name": student.display_name,
            "registration_id": student.registration_id,
            "status": s.status,
            "score": effective_score,
            "raw_score": s.score,
            "is_score_overridden": s.score_override is not None,
            "score_override_reason": s.score_override_reason,
            "total_points": total_points,
            "result_released": s.result_released,
            "cheat_flag_count": computed_flag_count,
            "cheat_events": cheat_events_list,
            "pass_percentage": quiz.pass_percentage,
            "percentage_score": round(percentage_score, 1),
            "is_passed": is_passed
        })

    if any_flag_repairs:
        db.commit()
    return {"quiz": {"title": quiz.title}, "sessions": res_list}

@router.get("/sessions/{session_id}/grade")
def get_session_grading(session_id: int, db: Session = Depends(get_db), teacher: models.User = Depends(auth.get_current_teacher)):
    results = db.query(models.Answer, models.Question).join(
        models.Question, models.Answer.question_id == models.Question.id
    ).filter(
        models.Answer.session_id == session_id,
        models.Question.type == "qa",
        models.Answer.graded_at == None
    ).all()

    return [{
        "id": ans.id,
        "question_body": q.body,
        "max_points": q.points,
        "answer_value": ans.answer_value,
        "marks_awarded": ans.marks_awarded,
        "is_overridden": ans.is_overridden
    } for ans, q in results]

@router.post("/answers/{answer_id}/grade")
def submit_grade(answer_id: int, grade: schemas.GradeSubmit, db: Session = Depends(get_db), teacher: models.User = Depends(auth.get_current_teacher)):
    ans = db.query(models.Answer).get(answer_id)
    ans.marks_awarded = grade.marks_awarded
    ans.is_overridden = grade.is_overridden
    ans.graded_by = teacher.id
    ans.graded_at = get_utc_now()
    db.commit()
    
    session = db.query(models.QuizSession).get(ans.session_id)
    ungraded = db.query(models.Answer).join(models.Question).filter(
        models.Answer.session_id == session.id,
        models.Question.type == "qa",
        models.Answer.graded_at == None
    ).count()

    if ungraded == 0:
        session.result_released = True
        total = db.query(models.Answer).filter_by(session_id=session.id).all()
        session.score = sum([a.marks_awarded for a in total if a.marks_awarded is not None])
        db.commit()
    
    return {"message": "Grade saved"}

# ==========================================
# SESSION SCORE OVERRIDES
# ==========================================

@router.post("/sessions/{session_id}/override-zero")
def override_session_zero(session_id: int, data: schemas.SessionZeroOverride, db: Session = Depends(get_db), teacher: models.User = Depends(auth.get_current_teacher)):
    session = db.query(models.QuizSession).get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    quiz = db.query(models.Quiz).get(session.quiz_id)
    if not quiz or quiz.created_by != teacher.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if session.status != "done":
        raise HTTPException(status_code=400, detail="Session not submitted yet")

    session.score_override = 0.0
    session.score_override_reason = data.reason
    session.score_overridden_by = teacher.id
    session.score_overridden_at = get_utc_now()
    session.result_released = True
    db.commit()

    return {"status": "ok", "score": 0.0, "is_score_overridden": True}

@router.delete("/sessions/{session_id}/override-zero")
def clear_session_zero_override(session_id: int, db: Session = Depends(get_db), teacher: models.User = Depends(auth.get_current_teacher)):
    session = db.query(models.QuizSession).get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    quiz = db.query(models.Quiz).get(session.quiz_id)
    if not quiz or quiz.created_by != teacher.id:
        raise HTTPException(status_code=403, detail="Not authorized")

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

# ==========================================
# UPDATES & DELETES
# ==========================================

@router.put("/quizzes/{quiz_id}", response_model=schemas.QuizResponse)
def update_quiz(quiz_id: int, quiz_update: schemas.QuizCreate, db: Session = Depends(get_db), teacher: models.User = Depends(auth.get_current_teacher)):
    db_quiz = db.query(models.Quiz).filter(models.Quiz.id == quiz_id, models.Quiz.created_by == teacher.id).first()
    if not db_quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    update_data = quiz_update.model_dump()
    
    # Standardize incoming dates to Naive UTC for MySQL
    if update_data.get("available_from"):
        update_data["available_from"] = update_data["available_from"].astimezone(timezone.utc).replace(tzinfo=None)
    if update_data.get("available_until"):
        update_data["available_until"] = update_data["available_until"].astimezone(timezone.utc).replace(tzinfo=None)

    for key, value in update_data.items():
        setattr(db_quiz, key, value)
    
    db.commit()
    db.refresh(db_quiz)
    return db_quiz

@router.delete("/quizzes/{quiz_id}")
def delete_quiz(quiz_id: int, db: Session = Depends(get_db), teacher: models.User = Depends(auth.get_current_teacher)):
    db_quiz = db.query(models.Quiz).filter(models.Quiz.id == quiz_id, models.Quiz.created_by == teacher.id).first()
    if not db_quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    db.delete(db_quiz)
    db.commit()
    return {"message": "Quiz deleted"}

@router.put("/questions/{question_id}", response_model=schemas.QuestionResponse)
def update_question(question_id: int, q_update: schemas.QuestionCreate, db: Session = Depends(get_db), teacher: models.User = Depends(auth.get_current_teacher)):
    db_q = db.query(models.Question).get(question_id)
    quiz = db.query(models.Quiz).filter(models.Quiz.id == db_q.quiz_id, models.Quiz.created_by == teacher.id).first()
    if not quiz: raise HTTPException(status_code=403)

    for key, value in q_update.model_dump().items():
        setattr(db_q, key, value)
    
    db.commit()
    db.refresh(db_q)
    return db_q

@router.delete("/questions/{question_id}")
def delete_question(question_id: int, db: Session = Depends(get_db), teacher: models.User = Depends(auth.get_current_teacher)):
    db_q = db.query(models.Question).get(question_id)
    db.delete(db_q)
    db.commit()
    return {"message": "Question deleted"}
