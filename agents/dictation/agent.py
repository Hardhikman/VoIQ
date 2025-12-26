"""Dictation Agent - Handles writing-based vocabulary tests."""

import random
from typing import Optional, List
from langchain_groq import ChatGroq
import voiq_core
from agents.core.state import VoIQState
from agents.core.prompts import DICTATION_AGENT_PROMPT


# Dictation prompt types (all 12 combinations matching MCQ)
DICTATION_TYPES = [
    ("word", "meaning", "Write the **meaning** of the word"),
    ("meaning", "word", "Write the **word** that means"),
    ("word", "synonym", "Write a **synonym** for"),
    ("word", "antonym", "Write an **antonym** for"),
    ("synonym", "word", "Write the **word** that has this synonym"),
    ("antonym", "word", "Write the **word** that has this antonym"),
    ("meaning", "synonym", "Write a **synonym** for the word meaning"),
    ("meaning", "antonym", "Write an **antonym** for the word meaning"),
    ("synonym", "meaning", "Write the **meaning** of the word with synonym"),
    ("antonym", "meaning", "Write the **meaning** of the word with antonym"),
    ("synonym", "antonym", "Write an **antonym** for the word with synonym"),
    ("antonym", "synonym", "Write a **synonym** for the word with antonym"),
]


def get_words_queue(db_path: str, order: str, letter_filter: Optional[str], categories: Optional[List[str]] = None) -> list:
    """Get word IDs in specified order, filtered by categories."""
    letter = letter_filter[0] if letter_filter else None
    words = voiq_core.get_words_by_order(db_path, order, letter, categories)
    return [w.id for w in words]


def get_field_value(word, field: str) -> str:
    """Get a specific field value from a word (random item if multiple)."""
    if field == "word":
        return word.word
    elif field == "meaning":
        return word.meaning
    elif field == "synonym":
        syns = [s.strip() for s in word.synonyms.split(",") if s.strip()]
        return random.choice(syns) if syns else ""
    elif field == "antonym":
        ants = [a.strip() for a in word.antonyms.split(",") if a.strip()]
        return random.choice(ants) if ants else ""
    return ""


def dictation_node(state: VoIQState, llm: Optional[ChatGroq] = None) -> VoIQState:
    """Dictation agent that presents writing prompts."""
    db_path = state.get("db_path", "data/voiq.db")
    order = state.get("order", "random")
    letter_filter = state.get("letter_filter")
    question_type = state.get("question_type")  # From guided setup
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
    
    if queue_index >= len(word_queue):
        return {
            **state,
            "agent_response": "🎉 **Dictation complete!** Type 'stats' to see your progress!",
            "next_agent": "end",
        }
    
    word_id = word_queue[queue_index]
    
    try:
        word = voiq_core.get_word_by_id(db_path, word_id)
        if not word:
            raise ValueError("Word not found")
        
        # Use question_type from state if specified, otherwise random
        if question_type:
            # Parse question_type like "word_to_meaning"
            parts = question_type.split("_to_")
            if len(parts) == 2:
                given_field, answer_field = parts
                # Find matching prompt template
                prompt_template = f"Write the **{answer_field}**"
                for g, a, template in DICTATION_TYPES:
                    if g == given_field and a == answer_field:
                        prompt_template = template
                        break
            else:
                given_field, answer_field, prompt_template = random.choice(DICTATION_TYPES)
        else:
            given_field, answer_field, prompt_template = random.choice(DICTATION_TYPES)
        
        given_value = get_field_value(word, given_field)
        expected_answer = get_field_value(word, answer_field)
        
        if not given_value or not expected_answer:
            # Skip if missing data
            return {
                **state,
                "word_queue": word_queue,
                "queue_index": queue_index + 1,
                "agent_response": "Skipping (missing data)...",
                "next_agent": "dictation",
            }
        
        timer = state.get("timer_seconds", 10)
        
        response = f"{prompt_template}:\n\n**{given_value}**\n\n⏱️ You have **{timer} seconds**! Type your answer."
        
        return {
            **state,
            "word_queue": word_queue,
            "queue_index": queue_index,
            "current_word_id": word_id,
            "current_question": {
                "word_id": word_id,
                "question_type": f"{given_field}_to_{answer_field}",
                "expected_answer": expected_answer,
                "given_value": given_value,
            },
            "agent_response": response,
            "next_agent": "end",
        }
    except Exception as e:
        return {
            **state,
            "word_queue": word_queue,
            "queue_index": queue_index + 1,
            "agent_response": f"Error: {e}. Skipping...",
            "next_agent": "end",
        }
