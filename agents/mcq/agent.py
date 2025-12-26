"""MCQ Agent - Generates and presents multiple choice questions."""

import random
from typing import Optional, List
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
import voiq_core
from agents.core.state import VoIQState
from agents.core.prompts import MCQ_AGENT_PROMPT


# All 12 MCQ question types
MCQ_TYPES = [
    "word_to_meaning",
    "meaning_to_word",
    "word_to_synonym",
    "word_to_antonym",
    "synonym_to_word",
    "antonym_to_word",
    "synonym_to_meaning",
    "antonym_to_meaning",
    "meaning_to_synonym",
    "meaning_to_antonym",
    "synonym_to_antonym",
    "antonym_to_synonym",
]


def get_words_queue(db_path: str, order: str, letter_filter: Optional[str], categories: Optional[List[str]] = None) -> list:
    """Get word IDs in specified order, filtered by categories."""
    letter = letter_filter[0] if letter_filter else None
    words = voiq_core.get_words_by_order(db_path, order, letter, categories)
    return [w.id for w in words]


def format_mcq_question(question) -> str:
    """Format MCQ question for display."""
    lines = [
        f"**{question.question_text}**",
        "",
    ]
    
    option_labels = ["A", "B", "C", "D"]
    for i, option in enumerate(question.options):
        marker = "→" if i == question.correct_index else " "
        lines.append(f"{option_labels[i]}. {option}")
    
    return "\n".join(lines)


def mcq_node(state: VoIQState, llm: Optional[ChatGroq] = None) -> VoIQState:
    """MCQ agent that generates and presents questions."""
    db_path = state.get("db_path", "data/voiq.db")
    order = state.get("order", "random")
    letter_filter = state.get("letter_filter")
    question_type = state.get("question_type")
    selected_categories = state.get("selected_categories", [])
    
    # Initialize word queue if empty
    word_queue = state.get("word_queue", [])
    queue_index = state.get("queue_index", 0)
    
    if not word_queue:
        categories = selected_categories if selected_categories else None
        word_queue = get_words_queue(db_path, order, letter_filter, categories)
        queue_index = 0
    
    if not word_queue:
        return {
            **state,
            "agent_response": "No words found! Please upload a vocabulary file first.",
            "next_agent": "end",
        }
    
    # Get current word
    if queue_index >= len(word_queue):
        return {
            **state,
            "agent_response": "🎉 **Quiz complete!** You've gone through all words. Type 'stats' to see your progress!",
            "next_agent": "end",
        }
    
    word_id = word_queue[queue_index]
    
    # Pick question type (random if not specified)
    q_type = question_type if question_type else random.choice(MCQ_TYPES)
    
    try:
        question = voiq_core.generate_mcq(db_path, word_id, q_type)
        formatted = format_mcq_question(question)
        
        timer = state.get("timer_seconds", 10)
        response = f"{formatted}\n\n⏱️ You have **{timer} seconds**! Reply with A, B, C, or D."
        
        return {
            **state,
            "word_queue": word_queue,
            "queue_index": queue_index,
            "current_word_id": word_id,
            "current_question": {
                "word_id": question.word_id,
                "question_type": question.question_type,
                "correct_index": question.correct_index,
                "correct_answer": question.correct_answer,
                "options": question.options,
            },
            "agent_response": response,
            "next_agent": "end",
        }
    except Exception as e:
        # Skip problematic word and try next
        return {
            **state,
            "word_queue": word_queue,
            "queue_index": queue_index + 1,
            "agent_response": f"Skipping word (error: {e}). Moving to next...",
            "next_agent": "end",
        }
