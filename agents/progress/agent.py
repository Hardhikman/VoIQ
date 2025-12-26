"""Progress Agent - Shows learning statistics and failed words."""

from typing import Optional
from langchain_groq import ChatGroq
import voiq_core
from agents.core.state import VoIQState
from agents.core.prompts import PROGRESS_AGENT_PROMPT


def progress_node(state: VoIQState, llm: Optional[ChatGroq] = None) -> VoIQState:
    """Progress agent that shows statistics and failed words."""
    db_path = state.get("db_path", "data/voiq.db")
    mode = state.get("mode", "stats")
    
    try:
        stats = voiq_core.get_stats(db_path)
        failed_words = voiq_core.get_failed_words(db_path, 10)  # Top 10 failed
    except Exception as e:
        return {
            **state,
            "agent_response": f"Could not load stats: {e}. Have you completed any quizzes yet?",
            "next_agent": "end",
        }
    
    # Build stats display
    lines = [
        "## 📊 Your Progress",
        "",
        f"**Total Attempts:** {stats.total_attempts}",
        f"**Correct:** {stats.correct_count} ✅",
        f"**Incorrect:** {stats.incorrect_count} ❌",
        f"**Accuracy:** {stats.accuracy_percent:.1f}% 🎯",
    ]
    
    if failed_words:
        lines.extend([
            "",
            "## 📝 Words to Review",
            "",
        ])
        for word, fail_count in failed_words[:10]:
            lines.append(f"- **{word.word}** ({fail_count} mistakes)")
        
        if mode == "review":
            lines.extend([
                "",
                "💡 **Tip:** Start a quiz with these words to practice!",
                "Type 'MCQ random' or 'Dictation random' to begin.",
            ])
    else:
        lines.extend([
            "",
            "🌟 **Great job!** No failed words yet. Keep it up!",
        ])
    
    return {
        **state,
        "agent_response": "\n".join(lines),
        "next_agent": "end",
    }
