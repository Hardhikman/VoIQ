"""Supervisor Agent - Routes user requests with guided quiz setup flow."""

import json
import re
from typing import Optional
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from agents.core.state import VoIQState
from agents.core.prompts import SUPERVISOR_PROMPT


# Setup flow steps (category first for multi-select)
SETUP_STEPS = ["idle", "category", "mode", "order", "target", "display", "timer", "ready"]

# Options for each step (category options loaded dynamically)
STEP_OPTIONS = {
    "mode": ["MCQ", "Dictation"],
    "order": ["A→Z", "Z→A", "Random", "Letter"],
    "target": ["Word", "Meaning", "Synonym", "Antonym"],
    "display": ["Word", "Meaning", "Synonym", "Antonym"],  # Will be filtered
    "timer": ["5s", "10s", "20s"],
}

# Step prompts
STEP_PROMPTS = {
    "category": "📂 **Select categories to quiz** (toggle on/off, type 'done' when ready)",
    "mode": "📚 **Which mode would you like?**",
    "order": "🔀 **What order?**",
    "target": "🎯 **Quiz target** (what should you find)?",
    "display": "👀 **Show you** (the clue)?",
    "timer": "⏱️ **Timer** (seconds per question)?",
}


def get_prev_step(current_step: str) -> str:
    """Get the previous step in the flow."""
    idx = SETUP_STEPS.index(current_step)
    return SETUP_STEPS[max(0, idx - 1)]


def get_next_step(current_step: str) -> str:
    """Get the next step in the flow."""
    idx = SETUP_STEPS.index(current_step)
    return SETUP_STEPS[min(len(SETUP_STEPS) - 1, idx + 1)]


def format_options(options: list, show_back: bool = False, show_cancel: bool = True) -> str:
    """Format options as clickable-looking buttons."""
    btns = " ".join([f"[{opt}]" for opt in options])
    nav = ""
    if show_back:
        nav += " [← Back]"
    if show_cancel:
        nav += " [✖ Cancel]"
    return btns + nav


def parse_option(user_input: str, options: list) -> Optional[str]:
    """Match user input to an option (case-insensitive)."""
    user_input = user_input.strip().lower()
    for opt in options:
        if user_input == opt.lower() or user_input == opt.lower().replace("→", " to "):
            return opt
    # Partial match
    for opt in options:
        if user_input in opt.lower():
            return opt
    return None


def build_question_type(target: str, display: str) -> str:
    """Build question_type from target and display."""
    return f"{display.lower()}_to_{target.lower()}"


def handle_setup_flow(state: VoIQState, user_message: str) -> VoIQState:
    """Handle the guided quiz setup conversation."""
    msg = user_message.strip().lower()
    current_step = state.get("setup_step", "idle")
    
    # Check for cancel/restart
    if msg in ["cancel", "restart", "✖ cancel", "stop"]:
        return {
            **state,
            "setup_step": "idle",
            "mode": None,
            "order": None,
            "quiz_target": None,
            "quiz_display": None,
            "timer_seconds": 10,
            "agent_response": "🔄 Setup cancelled. Type **start** to begin again.",
            "next_agent": "end",
        }
    
    # Check for back
    if msg in ["back", "← back", "<- back"]:
        prev_step = get_prev_step(current_step)
        if prev_step == "idle":
            return {
                **state,
                "setup_step": "mode",
                "agent_response": f"{STEP_PROMPTS['mode']}\n\n{format_options(STEP_OPTIONS['mode'], show_back=False)}",
                "next_agent": "end",
            }
        return {
            **state,
            "setup_step": prev_step,
            "agent_response": f"{STEP_PROMPTS[prev_step]}\n\n{format_options(STEP_OPTIONS[prev_step], show_back=prev_step != 'mode')}",
            "next_agent": "end",
        }
    
    # Process based on current step
    if current_step == "idle":
        # Start the flow - first show category selection
        import voiq_core
        db_path = state.get("db_path", "data/voiq.db")
        try:
            categories = voiq_core.get_categories(db_path)
            if not categories:
                return {
                    **state,
                    "agent_response": "❌ No vocabulary uploaded yet. Please upload a file first (Upload tab).",
                    "next_agent": "end",
                }
            
            cat_list = "\n".join([f"  • **{c.name}** ({c.word_count} words)" for c in categories])
            cat_names = [c.name for c in categories]
            
            return {
                **state,
                "setup_step": "category",
                "selected_categories": cat_names.copy(),  # Start with all selected
                "agent_response": f"""🚀 **Let's set up your quiz!**

📂 **Available categories:**
{cat_list}

✅ All categories selected. Type a category name to toggle, or:
[Done - Continue]  [✖ Cancel]""",
                "next_agent": "end",
            }
        except Exception as e:
            return {
                **state,
                "setup_step": "mode",
                "selected_categories": [],
                "agent_response": f"🚀 **Let's set up your quiz!**\n\n{STEP_PROMPTS['mode']}\n\n{format_options(STEP_OPTIONS['mode'], show_back=False)}",
                "next_agent": "end",
            }
    
    elif current_step == "category":
        import voiq_core
        db_path = state.get("db_path", "data/voiq.db")
        selected = state.get("selected_categories", [])
        
        # Check for "done" to proceed
        if msg in ["done", "continue", "done - continue", "ok", "next"]:
            if not selected:
                return {
                    **state,
                    "agent_response": "⚠️ Please select at least one category!\n\n[Done - Continue]  [✖ Cancel]",
                    "next_agent": "end",
                }
            return {
                **state,
                "setup_step": "mode",
                "agent_response": f"✅ **{len(selected)} categor{'y' if len(selected) == 1 else 'ies'}** selected!\n\n{STEP_PROMPTS['mode']}\n\n{format_options(STEP_OPTIONS['mode'], show_back=True)}",
                "next_agent": "end",
            }
        
        # Toggle category selection
        try:
            categories = voiq_core.get_categories(db_path)
            cat_names = [c.name for c in categories]
            
            # Find matching category (case insensitive)
            matched = None
            for name in cat_names:
                if msg.lower() == name.lower():
                    matched = name
                    break
            
            if matched:
                if matched in selected:
                    selected.remove(matched)
                    action = "❌ Removed"
                else:
                    selected.append(matched)
                    action = "✅ Added"
                
                sel_display = "\n".join([f"  {'✅' if c.name in selected else '⬜'} **{c.name}** ({c.word_count})" for c in categories])
                
                return {
                    **state,
                    "selected_categories": selected,
                    "agent_response": f"""{action}: **{matched}**

{sel_display}

[Done - Continue]  [✖ Cancel]""",
                    "next_agent": "end",
                }
            else:
                sel_display = "\n".join([f"  {'✅' if c.name in selected else '⬜'} **{c.name}** ({c.word_count})" for c in categories])
                return {
                    **state,
                    "agent_response": f"""Type a category name to toggle, or 'done' to continue.

{sel_display}

[Done - Continue]  [✖ Cancel]""",
                    "next_agent": "end",
                }
        except Exception as e:
            return {
                **state,
                "setup_step": "mode",
                "agent_response": f"⚠️ Error: {e}\n\nContinuing to mode selection...\n\n{STEP_PROMPTS['mode']}\n\n{format_options(STEP_OPTIONS['mode'], show_back=False)}",
                "next_agent": "end",
            }
    
    elif current_step == "mode":
        choice = parse_option(user_message, STEP_OPTIONS["mode"])
        if not choice:
            return {
                **state,
                "agent_response": f"Please choose: {format_options(STEP_OPTIONS['mode'])}",
                "next_agent": "end",
            }
        mode = "mcq" if choice == "MCQ" else "dictation"
        return {
            **state,
            "setup_step": "order",
            "mode": mode,
            "agent_response": f"✅ **{choice}** selected!\n\n{STEP_PROMPTS['order']}\n\n{format_options(STEP_OPTIONS['order'], show_back=True)}",
            "next_agent": "end",
        }
    
    elif current_step == "order":
        choice = parse_option(user_message, STEP_OPTIONS["order"])
        if not choice:
            return {
                **state,
                "agent_response": f"Please choose: {format_options(STEP_OPTIONS['order'])}",
                "next_agent": "end",
            }
        order_map = {"A→Z": "a_to_z", "Z→A": "z_to_a", "Random": "random", "Letter": "letter"}
        order = order_map.get(choice, "random")
        
        # If letter, ask for specific letter
        if choice == "Letter":
            return {
                **state,
                "setup_step": "letter",
                "order": order,
                "agent_response": "🔤 **Which letter?** (A-Z)\n\n[← Back] [✖ Cancel]",
                "next_agent": "end",
            }
        
        return {
            **state,
            "setup_step": "target",
            "order": order,
            "agent_response": f"✅ **{choice}** order!\n\n{STEP_PROMPTS['target']}\n\n{format_options(STEP_OPTIONS['target'], show_back=True)}",
            "next_agent": "end",
        }
    
    elif current_step == "letter":
        letter = user_message.strip().upper()
        if len(letter) == 1 and letter.isalpha():
            return {
                **state,
                "setup_step": "target",
                "letter_filter": letter.lower(),
                "agent_response": f"✅ Letter **{letter}**!\n\n{STEP_PROMPTS['target']}\n\n{format_options(STEP_OPTIONS['target'], show_back=True)}",
                "next_agent": "end",
            }
        return {
            **state,
            "agent_response": "Please enter a single letter (A-Z):\n\n[← Back] [✖ Cancel]",
            "next_agent": "end",
        }
    
    elif current_step == "target":
        choice = parse_option(user_message, STEP_OPTIONS["target"])
        if not choice:
            return {
                **state,
                "agent_response": f"Please choose: {format_options(STEP_OPTIONS['target'])}",
                "next_agent": "end",
            }
        # Filter display options (can't show same as target)
        display_options = [opt for opt in STEP_OPTIONS["display"] if opt != choice]
        return {
            **state,
            "setup_step": "display",
            "quiz_target": choice.lower(),
            "agent_response": f"✅ Find **{choice}**!\n\n{STEP_PROMPTS['display']}\n\n{format_options(display_options, show_back=True)}",
            "next_agent": "end",
        }
    
    elif current_step == "display":
        target = state.get("quiz_target", "word")
        display_options = [opt for opt in STEP_OPTIONS["display"] if opt.lower() != target]
        choice = parse_option(user_message, display_options)
        if not choice:
            return {
                **state,
                "agent_response": f"Please choose: {format_options(display_options)}",
                "next_agent": "end",
            }
        return {
            **state,
            "setup_step": "timer",
            "quiz_display": choice.lower(),
            "agent_response": f"✅ Show **{choice}** as clue!\n\n{STEP_PROMPTS['timer']}\n\n{format_options(STEP_OPTIONS['timer'], show_back=True)}",
            "next_agent": "end",
        }
    
    elif current_step == "timer":
        choice = parse_option(user_message, STEP_OPTIONS["timer"])
        if not choice:
            return {
                **state,
                "agent_response": f"Please choose: {format_options(STEP_OPTIONS['timer'])}",
                "next_agent": "end",
            }
        timer = int(choice.replace("s", ""))
        
        # Build question type
        target = state.get("quiz_target", "word")
        display = state.get("quiz_display", "meaning")
        question_type = build_question_type(target, display)
        mode = state.get("mode", "mcq")
        
        return {
            **state,
            "setup_step": "ready",
            "timer_seconds": timer,
            "question_type": question_type,
            "word_queue": [],  # Reset queue
            "queue_index": 0,
            "agent_response": f"🎉 **Ready!**\n\n**Mode:** {mode.upper()}\n**Find:** {target.title()}\n**Clue:** {display.title()}\n**Timer:** {timer}s\n\n*Starting quiz...*",
            "next_agent": mode,
        }
    
    return state


def parse_intent(user_message: str) -> dict:
    """Parse user intent using regex patterns (fast path before LLM)."""
    message = user_message.lower().strip()
    
    result = {
        "mode": "unknown",
        "order": "random",
        "letter_filter": None,
        "timer_seconds": 10,
        "question_type": None,
    }
    
    # Detect mode
    if any(word in message for word in ["mcq", "quiz", "multiple", "choice", "test"]):
        result["mode"] = "mcq"
    elif any(word in message for word in ["dictation", "write", "spell", "type"]):
        result["mode"] = "dictation"
    elif any(word in message for word in ["review", "failed", "wrong", "weak", "mistakes"]):
        result["mode"] = "review"
    elif any(word in message for word in ["stats", "statistics", "progress", "score", "how am i"]):
        result["mode"] = "stats"
    elif any(word in message for word in ["upload", "load", "import", "excel"]):
        result["mode"] = "upload"
    
    # Detect order
    if "a to z" in message or "a-z" in message or "alphabetical" in message:
        result["order"] = "a_to_z"
    elif "z to a" in message or "z-a" in message or "reverse" in message:
        result["order"] = "z_to_a"
    elif "random" in message or "shuffle" in message:
        result["order"] = "random"
    elif "letter" in message:
        result["order"] = "letter"
        # Extract letter filter
        letter_match = re.search(r'letter\s+([a-z])', message)
        if letter_match:
            result["letter_filter"] = letter_match.group(1)
    
    # Detect timer
    timer_match = re.search(r'(\d+)\s*(?:sec|second|s\b)', message)
    if timer_match:
        secs = int(timer_match.group(1))
        if secs in [5, 10, 20]:
            result["timer_seconds"] = secs
    
    return result


def supervisor_node(state: VoIQState, llm: Optional[ChatGroq] = None) -> VoIQState:
    """Supervisor agent that parses user intent and routes to specialists."""
    user_message = state.get("user_message", "")
    current_step = state.get("setup_step", "idle")
    add_word_step = state.get("add_word_step", "idle")
    review_step = state.get("review_step", "idle")
    
    # Check if we're at end of quiz with wrong answers (review prompt)
    if review_step in ["end_prompt", "save_prompt"]:
        return handle_review_flow(state, user_message)
    
    # Check if we're answering a quiz question
    if state.get("current_question") and user_message.lower().strip() not in ["stop", "exit", "cancel", "restart"]:
        return {
            **state,
            "next_agent": "evaluation",
        }
    
    # Check if we're in add word flow
    if add_word_step != "idle" or user_message.lower().strip() in ["add word", "add", "new word", "add vocabulary"]:
        return handle_add_word_flow(state, user_message)
    
    # Check for delete category flow
    delete_step = state.get("delete_category_step", "idle")
    if delete_step != "idle" or user_message.lower().strip() in ["delete category", "remove category", "delete"]:
        return handle_delete_category_flow(state, user_message)
    
    # Check for show categories command
    if user_message.lower().strip() in ["categories", "show categories", "list categories", "my categories"]:
        return handle_show_categories(state)
    
    # Check if we're in guided setup flow
    if current_step != "idle" or user_message.lower().strip() in ["start", "begin", "quiz", "go", "new"]:
        return handle_setup_flow(state, user_message)
    
    # Fast path: Try regex parsing first
    parsed = parse_intent(user_message)
    
    # If mode is unknown and LLM is available, use it
    if parsed["mode"] == "unknown" and llm is not None:
        try:
            messages = [
                SystemMessage(content=SUPERVISOR_PROMPT),
                HumanMessage(content=f"Parse this user request: {user_message}")
            ]
            response = llm.invoke(messages)
            
            # Try to extract JSON from response
            content = response.content
            json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
            if json_match:
                llm_parsed = json.loads(json_match.group())
                parsed.update({k: v for k, v in llm_parsed.items() if v is not None})
        except Exception as e:
            print(f"LLM parsing failed: {e}, using regex result")
    
    # Determine next agent
    mode = parsed.get("mode", "unknown")
    next_agent = {
        "mcq": "mcq",
        "dictation": "dictation",
        "review": "progress",
        "stats": "progress",
        "upload": "end",
        "unknown": "end",
    }.get(mode, "end")
    
    # Generate response for unknown mode
    if mode == "unknown":
        response = (
            "I didn't quite understand that. Try:\n\n"
            "• Type **start** for guided quiz setup\n"
            "• Type **add word** to add new vocabulary\n"
            "• Or commands like: **Start MCQ A to Z 10 sec**\n"
            "• **Review my failed words**\n"
            "• **Show my stats**"
        )
    else:
        response = f"Starting {mode.upper()} mode with {parsed['order'].replace('_', ' ')} order, {parsed['timer_seconds']}s timer..."
    
    return {
        **state,
        **parsed,
        "next_agent": next_agent,
        "agent_response": response,
    }


# ============= Category Management =============

def handle_show_categories(state: VoIQState) -> VoIQState:
    """Show all categories with word counts."""
    import voiq_core
    db_path = state.get("db_path", "data/voiq.db")
    
    try:
        categories = voiq_core.get_categories(db_path)
        if not categories:
            return {
                **state,
                "agent_response": "📂 No categories found. Upload a vocabulary file first!",
                "next_agent": "end",
            }
        
        total_words = sum(c.word_count for c in categories)
        cat_list = "\n".join([f"  • **{c.name}** - {c.word_count} words" for c in categories])
        
        return {
            **state,
            "agent_response": f"""📂 **Your Categories:**

{cat_list}

📊 **Total:** {total_words} words across {len(categories)} categories

**Commands:**
• `start` - Quiz with category selection
• `delete category` - Remove a category""",
            "next_agent": "end",
        }
    except Exception as e:
        return {
            **state,
            "agent_response": f"❌ Error: {e}",
            "next_agent": "end",
        }


def handle_delete_category_flow(state: VoIQState, user_message: str) -> VoIQState:
    """Handle category deletion flow."""
    import voiq_core
    
    msg = user_message.strip().lower()
    delete_step = state.get("delete_category_step", "idle")
    db_path = state.get("db_path", "data/voiq.db")
    
    # Check for cancel
    if msg in ["cancel", "nevermind", "stop"]:
        return {
            **state,
            "delete_category_step": "idle",
            "category_to_delete": None,
            "agent_response": "🔄 Cancelled.",
            "next_agent": "end",
        }
    
    if delete_step == "idle":
        # Show categories to choose from
        try:
            categories = voiq_core.get_categories(db_path)
            if not categories:
                return {
                    **state,
                    "agent_response": "📂 No categories to delete!",
                    "next_agent": "end",
                }
            
            cat_list = "\n".join([f"  • **{c.name}** ({c.word_count} words)" for c in categories])
            return {
                **state,
                "delete_category_step": "select",
                "agent_response": f"""🗑️ **Delete which category?**

{cat_list}

Type the category name to delete, or 'cancel' to abort.""",
                "next_agent": "end",
            }
        except Exception as e:
            return {
                **state,
                "agent_response": f"❌ Error: {e}",
                "next_agent": "end",
            }
    
    elif delete_step == "select":
        # User typed a category name
        try:
            categories = voiq_core.get_categories(db_path)
            cat_names = [c.name for c in categories]
            
            matched = None
            matched_count = 0
            for c in categories:
                if msg.lower() == c.name.lower():
                    matched = c.name
                    matched_count = c.word_count
                    break
            
            if matched:
                return {
                    **state,
                    "delete_category_step": "confirm",
                    "category_to_delete": matched,
                    "agent_response": f"""⚠️ **Delete '{matched}' with {matched_count} words?**

This cannot be undone!

[Yes - Delete]  [No - Cancel]""",
                    "next_agent": "end",
                }
            else:
                return {
                    **state,
                    "agent_response": f"Category '{user_message}' not found. Try again or 'cancel'.",
                    "next_agent": "end",
                }
        except Exception as e:
            return {
                **state,
                "delete_category_step": "idle",
                "agent_response": f"❌ Error: {e}",
                "next_agent": "end",
            }
    
    elif delete_step == "confirm":
        category = state.get("category_to_delete", "")
        
        if msg in ["yes", "y", "delete", "yes - delete"]:
            try:
                deleted = voiq_core.delete_category(db_path, category)
                return {
                    **state,
                    "delete_category_step": "idle",
                    "category_to_delete": None,
                    "agent_response": f"✅ **Deleted '{category}'** ({deleted} words removed)\n\nType `categories` to see remaining.",
                    "next_agent": "end",
                }
            except Exception as e:
                return {
                    **state,
                    "delete_category_step": "idle",
                    "agent_response": f"❌ Error deleting: {e}",
                    "next_agent": "end",
                }
        else:
            return {
                **state,
                "delete_category_step": "idle",
                "category_to_delete": None,
                "agent_response": "👍 Cancelled. Category kept.",
                "next_agent": "end",
            }
    
    return state


# ============= Review Wrong Answers Flow =============

def handle_review_flow(state: VoIQState, user_message: str) -> VoIQState:
    """Handle review/exit prompts after quiz ends with wrong answers."""
    import voiq_core
    
    msg = user_message.strip().lower()
    review_step = state.get("review_step", "idle")
    session_wrong = state.get("session_wrong", [])
    db_path = state.get("db_path", "data/voiq.db")
    mode = state.get("mode", "mcq")
    
    if review_step == "end_prompt":
        # User just finished quiz, choosing: Review or Exit
        if msg in ["review", "🔄 review", "🔄 review wrong answers", "r"]:
            # Start review mode - rebuild queue with wrong word IDs
            wrong_word_ids = [w["word_id"] for w in session_wrong]
            question_type = session_wrong[0].get("question_type") if session_wrong else None
            
            return {
                **state,
                "word_queue": wrong_word_ids,
                "queue_index": 0,
                "session_wrong": [],  # Reset for review round
                "is_review_mode": True,
                "review_step": "reviewing",
                "session_correct": 0,
                "session_total": 0,
                "agent_response": f"🔄 **Reviewing {len(wrong_word_ids)} wrong answer{'s' if len(wrong_word_ids) > 1 else ''}...**\n\n",
                "next_agent": mode,
            }
        
        elif msg in ["exit", "🚪 exit", "e", "quit", "stop", "no"]:
            # User wants to exit - ask about saving
            wrong_count = len(session_wrong)
            return {
                **state,
                "review_step": "save_prompt",
                "agent_response": f"💾 **Save {wrong_count} wrong answer{'s' if wrong_count > 1 else ''} for future review?**\n\n[Yes - Save]  [No - Just Exit]",
                "next_agent": "end",
            }
        
        else:
            # Invalid input
            return {
                **state,
                "agent_response": "Please choose:\n\n[🔄 Review Wrong Answers]  [🚪 Exit]",
                "next_agent": "end",
            }
    
    elif review_step == "save_prompt":
        # User choosing whether to save wrong answers to DB
        if msg in ["yes", "save", "y"]:
            # Save all wrong answers to DB
            saved_count = 0
            for wrong in session_wrong:
                try:
                    voiq_core.save_attempt(
                        db_path,
                        wrong["word_id"],
                        wrong["mode"],
                        wrong["question_type"],
                        False,  # is_correct = 0
                        wrong["user_answer"],
                        wrong["expected_answer"],
                        None
                    )
                    saved_count += 1
                except Exception as e:
                    print(f"Failed to save wrong attempt: {e}")
            
            return {
                **state,
                "review_step": "idle",
                "session_wrong": [],
                "is_review_mode": False,
                "agent_response": f"✅ Saved {saved_count} wrong answer{'s' if saved_count > 1 else ''} for future review.\n\nType **start** for a new quiz or **review** to see failed words.",
                "next_agent": "end",
            }
        
        else:  # "no", "n", or anything else (default: don't save)
            return {
                **state,
                "review_step": "idle",
                "session_wrong": [],
                "is_review_mode": False,
                "agent_response": "👋 **Quiz complete!** Wrong answers not saved.\n\nType **start** for a new quiz.",
                "next_agent": "end",
            }
    
    return state


# ============= Add Word Flow =============

ADD_WORD_STEPS = ["idle", "word", "meaning", "synonyms", "antonyms", "confirm"]

def handle_add_word_flow(state: VoIQState, user_message: str) -> VoIQState:
    """Handle the guided add word conversation."""
    import voiq_core
    
    msg = user_message.strip()
    current_step = state.get("add_word_step", "idle")
    new_word = state.get("new_word", {})
    db_path = state.get("db_path", "data/voiq.db")
    
    # Check for cancel
    if msg.lower() in ["cancel", "✖ cancel", "stop", "quit"]:
        return {
            **state,
            "add_word_step": "idle",
            "new_word": {},
            "agent_response": "🔄 Cancelled. Type **add word** to start again.",
            "next_agent": "end",
        }
    
    # Check for back
    if msg.lower() in ["back", "← back", "<- back"]:
        idx = ADD_WORD_STEPS.index(current_step)
        prev_step = ADD_WORD_STEPS[max(1, idx - 1)]  # Don't go back to idle
        prompts = {
            "word": "📝 **Enter the word:**",
            "meaning": f"📖 **Enter meaning for '{new_word.get('word', '')}':**\n\n[← Back] [✖ Cancel]",
            "synonyms": f"🔗 **Enter synonyms** (comma-separated, or type 'skip'):\n\n[← Back] [Skip] [✖ Cancel]",
            "antonyms": f"↔️ **Enter antonyms** (comma-separated, or type 'skip'):\n\n[← Back] [Skip] [✖ Cancel]",
        }
        return {
            **state,
            "add_word_step": prev_step,
            "agent_response": prompts.get(prev_step, ""),
            "next_agent": "end",
        }
    
    # Process steps
    if current_step == "idle":
        return {
            **state,
            "add_word_step": "word",
            "new_word": {},
            "agent_response": "📝 **Enter the word:**\n\n[✖ Cancel]",
            "next_agent": "end",
        }
    
    elif current_step == "word":
        if not msg:
            return {
                **state,
                "agent_response": "Please enter a word:\n\n[✖ Cancel]",
                "next_agent": "end",
            }
        new_word["word"] = msg
        return {
            **state,
            "add_word_step": "meaning",
            "new_word": new_word,
            "agent_response": f"✅ Word: **{msg}**\n\n📖 **Enter meaning:**\n\n[← Back] [✖ Cancel]",
            "next_agent": "end",
        }
    
    elif current_step == "meaning":
        if not msg:
            return {
                **state,
                "agent_response": "Please enter a meaning:\n\n[← Back] [✖ Cancel]",
                "next_agent": "end",
            }
        new_word["meaning"] = msg
        return {
            **state,
            "add_word_step": "synonyms",
            "new_word": new_word,
            "agent_response": f"✅ Meaning saved!\n\n🔗 **Enter synonyms** (comma-separated, or type 'skip'):\n\n[← Back] [Skip] [✖ Cancel]",
            "next_agent": "end",
        }
    
    elif current_step == "synonyms":
        new_word["synonyms"] = "" if msg.lower() == "skip" else msg
        return {
            **state,
            "add_word_step": "antonyms",
            "new_word": new_word,
            "agent_response": f"✅ Synonyms: {new_word['synonyms'] or '(none)'}\n\n↔️ **Enter antonyms** (comma-separated, or type 'skip'):\n\n[← Back] [Skip] [✖ Cancel]",
            "next_agent": "end",
        }
    
    elif current_step == "antonyms":
        new_word["antonyms"] = "" if msg.lower() == "skip" else msg
        
        # Validate: at least one field besides word
        if not new_word.get("meaning") and not new_word.get("synonyms") and not new_word.get("antonyms"):
            return {
                **state,
                "add_word_step": "meaning",
                "new_word": new_word,
                "agent_response": "⚠️ At least one of meaning/synonyms/antonyms is required!\n\n📖 **Enter meaning:**\n\n[← Back] [✖ Cancel]",
                "next_agent": "end",
            }
        
        # Show confirmation
        summary = f"""📋 **Confirm new word:**

**Word:** {new_word.get('word', '')}
**Meaning:** {new_word.get('meaning', '') or '(none)'}
**Synonyms:** {new_word.get('synonyms', '') or '(none)'}
**Antonyms:** {new_word.get('antonyms', '') or '(none)'}

[✓ Save] [← Back] [✖ Cancel]"""
        
        return {
            **state,
            "add_word_step": "confirm",
            "new_word": new_word,
            "agent_response": summary,
            "next_agent": "end",
        }
    
    elif current_step == "confirm":
        if msg.lower() in ["save", "yes", "✓ save", "confirm", "ok", "y"]:
            try:
                word_id = voiq_core.add_word(
                    db_path,
                    new_word.get("word", ""),
                    new_word.get("meaning", ""),
                    new_word.get("synonyms", ""),
                    new_word.get("antonyms", ""),
                )
                return {
                    **state,
                    "add_word_step": "idle",
                    "new_word": {},
                    "agent_response": f"✅ **Word '{new_word.get('word')}' added successfully!** (ID: {word_id})\n\nType **add word** to add another, or **start** for a quiz.",
                    "next_agent": "end",
                }
            except Exception as e:
                return {
                    **state,
                    "agent_response": f"❌ Error saving word: {e}\n\n[✓ Save] [← Back] [✖ Cancel]",
                    "next_agent": "end",
                }
        else:
            return {
                **state,
                "agent_response": "Type **save** to confirm, or use [← Back] [✖ Cancel]",
                "next_agent": "end",
            }
    
    return state
