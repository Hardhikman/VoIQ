"""Shared state for VoIQ LangGraph agents."""

from typing import TypedDict, Optional, List, Literal
from dataclasses import dataclass

class VoIQState(TypedDict, total=False):
    """Shared state passed between agents."""
    
    # User input
    user_message: str
    
    # Setup flow state (for guided quiz configuration)
    setup_step: Literal["idle", "category", "mode", "order", "target", "display", "timer", "ready"]
    quiz_target: Optional[str]  # What to find: word, meaning, synonym, antonym
    quiz_display: Optional[str]  # What to show as clue
    selected_categories: List[str]  # Categories selected for quiz (multi-select)
    
    # Add word flow state
    add_word_step: Literal["idle", "word", "meaning", "synonyms", "antonyms", "confirm"]
    new_word: Optional[dict]  # {word, meaning, synonyms, antonyms}
    
    # Delete category flow state
    delete_category_step: Literal["idle", "select", "confirm"]
    category_to_delete: Optional[str]
    
    # Parsed intent
    mode: Literal["mcq", "dictation", "review", "stats", "upload"]
    order: Literal["a_to_z", "z_to_a", "random", "letter"]
    letter_filter: Optional[str]
    timer_seconds: int
    question_type: Optional[str]
    
    # Quiz state
    current_word_id: Optional[int]
    current_question: Optional[dict]
    word_queue: List[int]
    queue_index: int
    
    # Wrong answer tracking (in-session, not DB)
    session_wrong: List[dict]  # [{word_id, question_type, user_answer, expected_answer}]
    is_review_mode: bool  # True when reviewing wrong answers
    review_step: Literal["idle", "reviewing", "end_prompt", "save_prompt"]
    
    # Answer evaluation
    user_answer: Optional[str]
    is_correct: Optional[bool]
    feedback: str
    
    # Session stats
    session_correct: int
    session_total: int
    
    # Agent responses
    agent_response: str
    next_agent: Literal["supervisor", "mcq", "dictation", "evaluation", "progress", "end"]
    
    # Database path
    db_path: str


