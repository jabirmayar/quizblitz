from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import random
from typing import List

from backend import models, schemas, auth
from backend.database import get_db

router = APIRouter(prefix="/student", tags=["Student"])

def get_utc_now():
    # Standard UTC time for database consistency
    return datetime.now(timezone.utc).replace(tzinfo=None)

# ==========================================
# VIEW & START QUIZZES
# ==========================================

@router.get("/quizzes")
def get_available_quizzes(db: Session = Depends(get_db), student: models.User = Depends(auth.get_current_student)):
    now = get_utc_now()
    
    # 1. Get IDs of all classes the student is enrolled in
    student_class_ids = [sc.class_id for sc in db.query(models.StudentClass).filter(models.StudentClass.student_id == student.id).all()]
    
    # 2. Get all published quizzes assigned to those classes (ignoring time for now to categorize)
    quizzes = db.query(models.Quiz).join(models.QuizClass).filter(
        models.QuizClass.class_id.in_(student_class_ids),
        models.Quiz.is_published == True
    ).all()

    response = []
    for q in quizzes:
        # Get the latest session
        subject = db.query(models.Subject).get(q.subject_id)

        last_session = db.query(models.QuizSession).filter(
            models.QuizSession.quiz_id == q.id,
            models.QuizSession.user_id == student.id
        ).order_by(models.QuizSession.attempt_number.desc()).first()

        # Determine UI State
        ui_state = "live"
        if last_session and last_session.status == "done":
            ui_state = "completed"
        elif last_session and last_session.status == "in_progress":
            ui_state = "in_progress"
        elif now < q.available_from:
            ui_state = "upcoming"
        elif now > q.available_until:
            ui_state = "expired"

        # Calculate Total Points
        total_points_raw = db.query(models.Question).filter_by(quiz_id=q.id).with_entities(func.sum(models.Question.points)).scalar()
        total_points = float(total_points_raw or 0)

        response.append({
            "id": q.id,
            "title": q.title,
            "subject_name": subject.name if subject else "General", 
            "subject_code": subject.code if subject else "N/A",     
            "description": q.description,
            "duration_seconds": q.duration_seconds,
            "max_attempts": q.max_attempts,
            "available_from": q.available_from,
            "available_until": q.available_until,
            "ui_state": ui_state, # upcoming, live, in_progress, completed, expired
            "session_id": last_session.id if last_session else None,
            "session_status": last_session.status if last_session else "new",
            "score": (last_session.score_override if last_session and last_session.score_override is not None else (last_session.score if last_session else 0)),
            "total_points": total_points,
            "result_released": last_session.result_released if last_session else False
        })
    
    return response

@router.post("/quizzes/{quiz_id}/start")
def start_quiz(quiz_id: int, db: Session = Depends(get_db), student: models.User = Depends(auth.get_current_student)):
    quiz = db.query(models.Quiz).filter(models.Quiz.id == quiz_id, models.Quiz.is_published == True).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found or not published")

    now = get_utc_now()
    
    # Check time availability
    if now < quiz.available_from:
        raise HTTPException(status_code=400, detail="Quiz is not available yet")
    if now > quiz.available_until:
        raise HTTPException(status_code=400, detail="Quiz has expired")

    # Check attempt limits
    attempts = db.query(models.QuizSession).filter_by(user_id=student.id, quiz_id=quiz_id).count()
    if attempts >= quiz.max_attempts:
        raise HTTPException(status_code=400, detail="Maximum attempts reached")

    # Get question IDs and shuffle if settings allow
    questions = db.query(models.Question.id).filter_by(quiz_id=quiz_id).all()
    q_ids = [q.id for q in questions]
    if quiz.shuffle_questions:
        random.shuffle(q_ids)

    # Set the server-side expiration time
    expires_at = get_utc_now() + timedelta(seconds=quiz.duration_seconds)

    # Create the session (question_order is stored as a JSON list)
    new_session = models.QuizSession(
        user_id=student.id,
        quiz_id=quiz_id,
        attempt_number=attempts + 1,
        question_order=q_ids,
        expires_at=expires_at,
        started_at=get_utc_now(),
        status="in_progress",
        cheat_flag_count=0
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    return {"session_id": new_session.id}

# ==========================================
# TAKING THE QUIZ (QUIZ ENGINE SUPPORT)
# ==========================================

@router.get("/sessions/{session_id}/resume")
def resume_quiz(session_id: int, db: Session = Depends(get_db), student: models.User = Depends(auth.get_current_student)):
    session = db.query(models.QuizSession).filter_by(id=session_id, user_id=student.id).first()
    if not session or session.status == "done":
        raise HTTPException(status_code=404, detail="Active session not found")
    
    quiz = db.query(models.Quiz).filter_by(id=session.quiz_id).first()

    # CRITICAL: Fetch question content in the specific order saved in the session
    ordered_questions = []
    for q_id in session.question_order:
        q = db.query(models.Question).filter_by(id=q_id).first()
        if q:
            ordered_questions.append({
                "id": q.id,
                "body": q.body,
                "type": q.type,
                "options": q.options, # JSON list
                "points": q.points
            })

    # Fetch any answers already saved during this session
    answers = db.query(models.Answer).filter_by(session_id=session_id).all()
    ans_dict = {a.question_id: a.answer_value for a in answers}

    return {
        "quiz": {
            "title": quiz.title,
            "anti_cheat_enabled": quiz.anti_cheat_enabled
        },
        "question_order": session.question_order,
        "questions": ordered_questions,
        "answers_so_far": ans_dict,
        "expires_at": session.expires_at,
        "server_now": get_utc_now() # Used by UI to sync the countdown timer
    }

@router.post("/sessions/{session_id}/answer")
def save_answer(session_id: int, answer: schemas.AnswerCreate, db: Session = Depends(get_db), student: models.User = Depends(auth.get_current_student)):
    session = db.query(models.QuizSession).filter_by(id=session_id, user_id=student.id).first()
    if not session or session.status == "done":
        raise HTTPException(status_code=400, detail="Invalid or completed session")
    
    # Check if time has expired
    if get_utc_now() > session.expires_at:
        session.status = "done"
        db.commit()
        raise HTTPException(status_code=400, detail="Time expired")

    # Upsert answer (Save or Update)
    existing = db.query(models.Answer).filter_by(session_id=session_id, question_id=answer.question_id).first()
    if existing:
        existing.answer_value = answer.answer_value
        existing.answered_at = get_utc_now()
    else:
        new_answer = models.Answer(
            session_id=session_id,
            question_id=answer.question_id,
            answer_value=answer.answer_value,
            answered_at=get_utc_now()
        )
        db.add(new_answer)
    
    db.commit()
    return {"saved": True}

@router.post("/sessions/{session_id}/cheat")
def log_cheat(session_id: int, cheat: schemas.CheatEventCreate, db: Session = Depends(get_db), student: models.User = Depends(auth.get_current_student)):
    session = db.query(models.QuizSession).filter_by(id=session_id, user_id=student.id).first()
    if session and session.status != "done":
        new_event = models.CheatEvent(
            session_id=session_id,
            event_type=cheat.event_type,
            detail=cheat.detail or "",
            occurred_at=get_utc_now()
        )
        session.cheat_flag_count += 1
        db.add(new_event)
        db.commit()
    return {"logged": True}

@router.post("/sessions/{session_id}/submit")
def submit_quiz(session_id: int, db: Session = Depends(get_db), student: models.User = Depends(auth.get_current_student)):
    session = db.query(models.QuizSession).filter_by(id=session_id, user_id=student.id).first()
    if not session or session.status == "done":
        return {"message": "Already submitted"}

    # 1. Fetch all quiz content and student answers
    questions = db.query(models.Question).filter_by(quiz_id=session.quiz_id).all()
    answers = db.query(models.Answer).filter_by(session_id=session_id).all()
    ans_map = {a.question_id: a for a in answers}

    score = 0.0
    has_qa = False

    # 2. Score Multiple Choice (MCQ) automatically
    for q in questions:
        ans = ans_map.get(q.id)
        if q.type == "mcq":
            if ans:
                is_correct = (ans.answer_value == q.correct_answer)
                ans.is_correct = is_correct
                ans.marks_awarded = q.points if is_correct else 0
                ans.graded_at = get_utc_now()
                score += ans.marks_awarded
        else:
            # Quiz contains Essay questions, so result cannot be released yet
            has_qa = True

    # 3. Finalize the session
    session.status = "done"
    session.submitted_at = get_utc_now()
    session.score = score
    # Release results instantly if there are no Q&A questions to be graded
    session.result_released = not has_qa 

    db.commit()
    return {"message": "Submitted successfully", "result_released": session.result_released}

@router.get("/sessions/{session_id}/result")
def get_session_result(session_id: int, db: Session = Depends(get_db), student: models.User = Depends(auth.get_current_student)):
    # 1. Fetch the session and verify it belongs to this student
    session = db.query(models.QuizSession).filter_by(id=session_id, user_id=student.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 2. Calculate Total Points possible for this quiz
    total_points_raw = db.query(models.Question).filter_by(quiz_id=session.quiz_id).with_entities(models.func.sum(models.Question.points)).scalar()
    total_points = float(total_points_raw or 0)

    quiz = db.query(models.Quiz).filter_by(id=session.quiz_id).first()

    effective_score = session.score_override if session.score_override is not None else (session.score or 0)

    # Calculate pass/fail status
    pass_percentage = quiz.pass_percentage or 50.0
    percentage_score = (effective_score / total_points * 100) if total_points > 0 else 0
    is_passed = percentage_score >= pass_percentage

    return {
        "status": session.status,
        "attempt_number": session.attempt_number,
        "show_answers_after": quiz.show_answers_after,
        "score": effective_score,
        "raw_score": session.score,
        "is_score_overridden": session.score_override is not None,
        "score_override_reason": session.score_override_reason if session.score_override is not None else None,
        "total_points": total_points,
        "result_released": session.result_released,
        "submitted_at": session.submitted_at,
        "pass_percentage": pass_percentage,
        "percentage_score": round(percentage_score, 1),
        "is_passed": is_passed
    }

@router.get("/sessions/{session_id}/review")
def get_quiz_review(session_id: int, db: Session = Depends(get_db), student: models.User = Depends(auth.get_current_student)):
    session = db.query(models.QuizSession).filter_by(id=session_id, user_id=student.id).first()
    if not session or not session.result_released:
        raise HTTPException(status_code=403, detail="Results not available for review yet.")

    quiz = db.query(models.Quiz).filter_by(id=session.quiz_id).first()
    if not quiz.show_answers_after:
        raise HTTPException(status_code=403, detail="Teacher has disabled answer review for this quiz.")

    # Fetch questions and answers together
    review_data = []
    for q_id in session.question_order:
        q = db.query(models.Question).filter_by(id=q_id).first()
        ans = db.query(models.Answer).filter_by(session_id=session_id, question_id=q_id).first()
        
        review_data.append({
            "body": q.body,
            "type": q.type,
            "options": q.options,
            "correct_answer": q.correct_answer,
            "points": q.points,
            "student_answer": ans.answer_value if ans else None,
            "is_correct": ans.is_correct if ans else False,
            "marks_awarded": ans.marks_awarded if ans else 0
        })

    return {"quiz_title": quiz.title, "review": review_data}
