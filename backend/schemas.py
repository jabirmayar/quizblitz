from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime
import re

# --- Auth & Tokens ---
class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    display_name: Optional[str] = None

class TokenData(BaseModel):
    user_id: Optional[int] = None
    role: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class ChangePassword(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str):
        if len(v) < 8:
            raise ValueError("New password must be at least 8 characters")
        return v

# --- Users ---
class UserCreate(BaseModel):
    registration_id: str
    display_name: str
    password: str
    role: str = "student"
    class_ids: Optional[List[int]] = []
    # Bot/spam reduction (public registration only)
    website: Optional[str] = None  # honeypot: must stay empty
    form_started_at: Optional[int] = None  # epoch ms from client

    @field_validator('registration_id')
    @classmethod
    def validate_reg_id(cls, v):
        if len(v) < 8:
            raise ValueError('Registration ID must be at least 8 characters')
        if not re.match(r'^[A-Za-z0-9_-]+$', v):
            raise ValueError('Invalid registration ID format. Use letters, numbers, -, or _')
        return v

    @field_validator("website")
    @classmethod
    def validate_honeypot(cls, v: Optional[str]):
        if v and v.strip():
            raise ValueError("Invalid form submission")
        return v

class UserResponse(BaseModel):
    id: int
    registration_id: str
    display_name: str
    role: str
    is_active: bool
    created_at: datetime
    class_name: Optional[str] = None
    class Config:
        from_attributes = True

# --- Organization: Departments ---
class DepartmentCreate(BaseModel):
    name: str
    description: Optional[str] = None

class DepartmentResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    is_active: bool
    class Config:
        from_attributes = True

class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

# --- Organization: Programs ---
class ProgramCreate(BaseModel):
    name: str
    department_id: int

class ProgramResponse(BaseModel):
    id: int
    name: str
    department_id: int
    class Config:
        from_attributes = True

# --- Organization: Semesters / Sessions ---
class SemesterCreate(BaseModel):
    season: str
    year: int
    code: Optional[str] = None

class SemesterResponse(BaseModel):
    id: int
    season: str
    year: int
    code: str
    is_active: bool
    class Config:
        from_attributes = True

class SemesterUpdate(BaseModel):
    season: Optional[str] = None
    year: Optional[int] = None
    is_active: Optional[bool] = None

class DeptSemesterCreate(BaseModel):
    department_id: int
    semester_id: int

# --- Organization: Subjects (Admin Managed) ---
class SubjectCreate(BaseModel):
    name: str
    code: str
    department_id: int

class SubjectResponse(BaseModel):
    id: int
    name: str
    code: str
    department_id: int
    class Config:
        from_attributes = True

# --- Organization: Classes ---
class ClassCreate(BaseModel):
    name: str
    program_id: int
    semester_id: int
    semester_number: int
    section: str
    code: Optional[str] = None 

class ClassResponse(BaseModel):
    id: int
    name: str
    code: str
    program_id: int
    semester_id: int
    semester_number: int
    section: str
    is_active: bool
    class Config:
        from_attributes = True

class ClassUpdate(BaseModel):
    semester_number: Optional[int] = None
    section: Optional[str] = None
    is_active: Optional[bool] = None

# --- Teacher Specific ---
class TeacherCreate(BaseModel):
    registration_id: str
    display_name: str
    password: str

class TeacherUpdate(BaseModel):
    registration_id: Optional[str] = None
    display_name: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None

class TeacherClassAssign(BaseModel):
    teacher_id: int
    class_ids: List[int]

# --- Quiz Schemas ---
class QuizCreate(BaseModel):
    title: str
    subject_id: int
    description: Optional[str] = None
    duration_seconds: int
    max_attempts: int = 1
    shuffle_questions: bool = True
    show_answers_after: bool = False
    anti_cheat_enabled: bool = True
    available_from: datetime
    available_until: datetime
    is_published: bool = False
    pass_percentage: float = 50.0

    @field_validator("pass_percentage")
    @classmethod
    def validate_pass_percentage(cls, v: float):
        if v < 0 or v > 100:
            raise ValueError("pass_percentage must be between 0 and 100")
        return float(v)

class QuizResponse(BaseModel):
    id: int
    title: str
    subject_id: int
    description: Optional[str] = None
    duration_seconds: int
    created_by: int
    max_attempts: int
    shuffle_questions: bool
    show_answers_after: bool
    anti_cheat_enabled: bool
    is_published: bool
    available_from: Optional[datetime] = None
    available_until: Optional[datetime] = None
    pass_percentage: float
    class Config:
        from_attributes = True

class QuizAssign(BaseModel):
    class_ids: List[int]

# --- Question Schemas ---
class QuestionCreate(BaseModel):
    body: str
    type: str  # "mcq" or "qa"
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    points: int = 1
    order_index: int = 0

class QuestionResponse(BaseModel):
    id: int
    quiz_id: int
    body: str
    type: str
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    points: int
    class Config:
        from_attributes = True

# --- Student & Session Schemas ---
class StudentQuizResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    duration_seconds: int
    max_attempts: int
    session_status: Optional[str] = "new"
    session_id: Optional[int] = None
    score: Optional[float] = 0.0
    result_released: Optional[bool] = False
    class Config:
        from_attributes = True

class QuizStartResponse(BaseModel):
    session_id: int
    expires_at: datetime
    question_order: List[int]

class AnswerCreate(BaseModel):
    question_id: int
    answer_value: str

class CheatEventCreate(BaseModel):
    event_type: str
    detail: Optional[str] = None

# --- Grading Schemas ---
class GradeSubmit(BaseModel):
    marks_awarded: float
    is_overridden: bool = False

class SessionZeroOverride(BaseModel):
    reason: Optional[str] = None
