from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base

# ==========================================
# 1. ORGANISATION
# ==========================================

class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    programs = relationship("Program", back_populates="department")
    semesters = relationship("DeptSemester", back_populates="department")
    subjects = relationship("Subject", back_populates="department")

class Semester(Base):
    __tablename__ = "semesters"
    id = Column(Integer, primary_key=True, index=True)
    season = Column(String(50), nullable=False) 
    year = Column(Integer, nullable=False)
    code = Column(String(50), nullable=False) 
    is_active = Column(Boolean, default=True)

    departments = relationship("DeptSemester", back_populates="semester")
    classes = relationship("Class", back_populates="semester")

class DeptSemester(Base):
    __tablename__ = "dept_semesters"
    department_id = Column(Integer, ForeignKey("departments.id"), primary_key=True)
    semester_id = Column(Integer, ForeignKey("semesters.id"), primary_key=True)
    is_active = Column(Boolean, default=True)

    department = relationship("Department", back_populates="semesters")
    semester = relationship("Semester", back_populates="departments")

class Program(Base):
    __tablename__ = "programs"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100)) 
    department_id = Column(Integer, ForeignKey("departments.id"))

    department = relationship("Department", back_populates="programs")
    classes = relationship("Class", back_populates="program")

class Subject(Base):
    __tablename__ = "subjects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False) 
    code = Column(String(50), unique=True, nullable=False) 
    department_id = Column(Integer, ForeignKey("departments.id"))

    department = relationship("Department", back_populates="subjects")
    quizzes = relationship("Quiz", back_populates="subject")
    # Link to classes that offer this subject
    classes = relationship("ClassSubject", back_populates="subject")

class Class(Base):
    __tablename__ = "classes"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255)) 
    program_id = Column(Integer, ForeignKey("programs.id"))
    semester_id = Column(Integer, ForeignKey("semesters.id")) 
    semester_number = Column(Integer) 
    section = Column(String(10)) 
    code = Column(String(50), unique=True) 
    is_active = Column(Boolean, default=True)

    program = relationship("Program", back_populates="classes")
    semester = relationship("Semester", back_populates="classes")
    # Link to subjects offered to this class
    subjects = relationship("ClassSubject", back_populates="class_")

class ClassSubject(Base):
    """Junction table to define which subjects are taught in a Class Group"""
    __tablename__ = "class_subjects"
    class_id = Column(Integer, ForeignKey("classes.id"), primary_key=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), primary_key=True)

    class_ = relationship("Class", back_populates="subjects")
    subject = relationship("Subject", back_populates="classes")


# ==========================================
# 2. USERS & TEACHER ASSIGNMENTS
# ==========================================

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    registration_id = Column(String(100), unique=True, index=True, nullable=False)
    display_name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False) 
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    sessions = relationship("QuizSession", back_populates="user", foreign_keys="QuizSession.user_id")
    # Precise assignments (which subject in which class)
    assignments = relationship("TeacherAssignment", back_populates="teacher")

class TeacherAssignment(Base):
    """Triple Junction: Which teacher teaches which subject to which class"""
    __tablename__ = "teacher_assignments"
    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"))
    class_id = Column(Integer, ForeignKey("classes.id"))
    subject_id = Column(Integer, ForeignKey("subjects.id"))

    teacher = relationship("User", back_populates="assignments")
    class_ = relationship("Class")
    subject = relationship("Subject")

class StudentClass(Base):
    __tablename__ = "student_classes"
    student_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    class_id = Column(Integer, ForeignKey("classes.id"), primary_key=True)


# ==========================================
# 3. QUIZZES
# ==========================================

class Quiz(Base):
    __tablename__ = "quizzes"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    description = Column(Text, nullable=True)
    duration_seconds = Column(Integer, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_published = Column(Boolean, default=False)
    max_attempts = Column(Integer, default=1)
    shuffle_questions = Column(Boolean, default=True)
    show_answers_after = Column(Boolean, default=False)
    anti_cheat_enabled = Column(Boolean, default=True)
    available_from = Column(DateTime, nullable=True)
    available_until = Column(DateTime, nullable=True)
    pass_percentage = Column(Float, default=50.0)  # Pass threshold percentage

    subject = relationship("Subject", back_populates="quizzes")
    questions = relationship("Question", back_populates="quiz", cascade="all, delete-orphan")
    sessions = relationship("QuizSession", back_populates="quiz")

class QuizClass(Base):
    __tablename__ = "quiz_classes"
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), primary_key=True)
    class_id = Column(Integer, ForeignKey("classes.id"), primary_key=True)

class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    body = Column(Text, nullable=False)
    type = Column(String(50), nullable=False) 
    options = Column(JSON, nullable=True) 
    correct_answer = Column(Text, nullable=True) 
    points = Column(Integer, default=1)
    order_index = Column(Integer, default=0)

    quiz = relationship("Quiz", back_populates="questions")


# ==========================================
# 4. SESSIONS & RESULTS
# ==========================================

class QuizSession(Base):
    __tablename__ = "quiz_sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    attempt_number = Column(Integer, default=1)
    question_order = Column(JSON, nullable=False) 
    started_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
    submitted_at = Column(DateTime, nullable=True)
    status = Column(String(50), default="in_progress") 
    score = Column(Float, nullable=True)
    score_override = Column(Float, nullable=True)  # If set, overrides score for final result display
    score_override_reason = Column(Text, nullable=True)
    score_overridden_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    score_overridden_at = Column(DateTime, nullable=True)
    cheat_flag_count = Column(Integer, default=0)
    result_released = Column(Boolean, default=False)

    user = relationship("User", back_populates="sessions", foreign_keys=[user_id])
    quiz = relationship("Quiz", back_populates="sessions")
    answers = relationship("Answer", back_populates="session", cascade="all, delete-orphan")
    cheat_events = relationship("CheatEvent", back_populates="session", cascade="all, delete-orphan")

class Answer(Base):
    __tablename__ = "answers"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("quiz_sessions.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    answer_value = Column(Text, nullable=True)
    answered_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    is_correct = Column(Boolean, nullable=True) 
    marks_awarded = Column(Float, nullable=True) 
    graded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    graded_at = Column(DateTime, nullable=True)
    is_overridden = Column(Boolean, default=False)  # Track manual grade overrides

    session = relationship("QuizSession", back_populates="answers")
    question = relationship("Question")

class CheatEvent(Base):
    __tablename__ = "cheat_events"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("quiz_sessions.id"), nullable=False)
    event_type = Column(String(100), nullable=False) 
    occurred_at = Column(DateTime, server_default=func.now())
    detail = Column(Text, nullable=True)

    session = relationship("QuizSession", back_populates="cheat_events")
