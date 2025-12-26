"""Evaluation Agent - Scores answers and provides feedback."""

from typing import Optional
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
import voiq_core
from agents.core.state import VoIQState
from agents.core.prompts import EVALUATION_AGENT_PROMPT


def evaluate_mcq_answer(user_answer: str, correct_index: int) -> tuple[bool, str]:
    """Evaluate MCQ answer (A, B, C, D)."""
    answer_map = {"a": 0, "b": 1, "c": 2, "d": 3}
    user_idx = answer_map.get(user_answer.strip().lower())
    
    if user_idx is None:
        return False, "Please answer with A, B, C, or D."
    
    is_correct = user_idx == correct_index
    return is_correct, ""


def evaluation_node(state: VoIQState, llm: Optional[ChatGroq] = None) -> VoIQState:
    """Evaluation agent that scores answers and provides feedback."""
    db_path = state.get("db_path", "data/voiq.db")
    user_answer = state.get("user_answer", "")
    current_question = state.get("current_question", {})
    mode = state.get("mode", "mcq")
    word_queue = state.get("word_queue", [])
    queue_index = state.get("queue_index", 0)
    session_wrong = state.get("session_wrong", [])
    is_review_mode = state.get("is_review_mode", False)
    
    if not current_question:
        return {
            **state,
            "agent_response": "No question to evaluate. Start a quiz first!",
            "next_agent": "supervisor",
        }
    
    word_id = current_question.get("word_id")
    question_type = current_question.get("question_type", "")
    expected_answer = current_question.get("correct_answer") or current_question.get("expected_answer", "")
    
    # Evaluate based on mode
    if mode == "mcq":
        correct_index = current_question.get("correct_index", 0)
        is_correct, error_msg = evaluate_mcq_answer(user_answer, correct_index)
        
        if error_msg:
            return {
                **state,
                "agent_response": error_msg,
                "next_agent": "end",
            }
        
        feedback = "✅ **Correct!** " if is_correct else f"❌ **Incorrect.** The answer was: {expected_answer}"
    else:
        # Dictation mode - use fuzzy matching
        match_result = voiq_core.check_match(user_answer, expected_answer, 0.75)
        is_correct = match_result.is_correct
        feedback = match_result.feedback
    
    # Handle correct vs wrong differently
    if is_correct:
        # Save CORRECT answers to database immediately
        try:
            voiq_core.save_attempt(
                db_path, word_id, mode, question_type,
                True, user_answer, expected_answer, None
            )
        except Exception as e:
            print(f"Failed to save attempt: {e}")
    else:
        # Track WRONG answers in session memory (not DB yet)
        session_wrong.append({
            "word_id": word_id,
            "question_type": question_type,
            "user_answer": user_answer,
            "expected_answer": expected_answer,
            "mode": mode,
        })
    
    # Update session stats
    session_correct = state.get("session_correct", 0) + (1 if is_correct else 0)
    session_total = state.get("session_total", 0) + 1
    new_queue_index = queue_index + 1
    
    # Check if quiz/review is complete
    is_quiz_complete = new_queue_index >= len(word_queue)
    
    if is_quiz_complete and session_wrong:
        # Quiz ended with wrong answers - show review prompt
        wrong_count = len(session_wrong)
        accuracy = (session_correct / session_total * 100) if session_total > 0 else 0
        
        response = f"""{feedback}

📊 **Quiz Complete!** {session_correct}/{session_total} ({accuracy:.0f}%)

⚠️ **{wrong_count} wrong answer{'s' if wrong_count > 1 else ''}**

[🔄 Review Wrong Answers]  [🚪 Exit]"""
        
        return {
            **state,
            "is_correct": is_correct,
            "feedback": feedback,
            "session_correct": session_correct,
            "session_total": session_total,
            "queue_index": new_queue_index,
            "session_wrong": session_wrong,
            "review_step": "end_prompt",
            "current_question": None,
            "agent_response": response,
            "next_agent": "end",
        }
    
    elif is_quiz_complete and not session_wrong:
        # Quiz ended, all correct!
        accuracy = (session_correct / session_total * 100) if session_total > 0 else 0
        response = f"""{feedback}

🎉 **Perfect Score!** {session_correct}/{session_total} ({accuracy:.0f}%)

All answers correct! Great job!"""
        
        return {
            **state,
            "is_correct": is_correct,
            "feedback": feedback,
            "session_correct": session_correct,
            "session_total": session_total,
            "queue_index": new_queue_index,
            "session_wrong": [],
            "review_step": "idle",
            "current_question": None,
            "agent_response": response,
            "next_agent": "end",
        }
    
    # Quiz continues
    accuracy = (session_correct / session_total * 100) if session_total > 0 else 0
    stats_line = f"\n\n📊 Session: {session_correct}/{session_total} ({accuracy:.0f}%)"
    continue_prompt = "\n\nPress **Enter** or type 'next' to continue, or 'stop' to end."
    response = feedback + stats_line + continue_prompt
    
    return {
        **state,
        "is_correct": is_correct,
        "feedback": feedback,
        "session_correct": session_correct,
        "session_total": session_total,
        "queue_index": new_queue_index,
        "session_wrong": session_wrong,
        "current_question": None,
        "agent_response": response,
        "next_agent": mode,
    }

