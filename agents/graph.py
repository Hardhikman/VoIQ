"""LangGraph workflow for VoIQ multi-agent system."""

import os
from typing import Optional
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from dotenv import load_dotenv

from agents.core.state import VoIQState
from agents.supervisor import supervisor_node
from agents.mcq import mcq_node
from agents.dictation import dictation_node
from agents.evaluation import evaluation_node
from agents.progress import progress_node

# Load environment variables
load_dotenv()


def get_llm() -> Optional[ChatGroq]:
    """Get Groq LLM if API key is available."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "your_groq_api_key_here":
        return None
    return ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0.3,
        api_key=api_key,
    )


def route_next_agent(state: VoIQState) -> str:
    """Route to next agent based on state."""
    next_agent = state.get("next_agent", "end")
    if next_agent == "end":
        return END
    return next_agent


def create_voiq_graph(db_path: str = "data/voiq.db"):
    """Create the LangGraph workflow for VoIQ."""
    llm = get_llm()
    
    # Create graph with VoIQState
    graph = StateGraph(VoIQState)
    
    # Add nodes with LLM injection
    graph.add_node("supervisor", lambda s: supervisor_node(s, llm))
    graph.add_node("mcq", lambda s: mcq_node(s, llm))
    graph.add_node("dictation", lambda s: dictation_node(s, llm))
    graph.add_node("evaluation", lambda s: evaluation_node(s, llm))
    graph.add_node("progress", lambda s: progress_node(s, llm))
    
    # Set entry point
    graph.set_entry_point("supervisor")
    
    # Add conditional edges
    graph.add_conditional_edges(
        "supervisor",
        route_next_agent,
        {
            "mcq": "mcq",
            "dictation": "dictation",
            "evaluation": "evaluation",
            "progress": "progress",
            END: END,
        }
    )
    
    graph.add_conditional_edges(
        "mcq",
        route_next_agent,
        {
            "evaluation": "evaluation",
            "mcq": "mcq",
            END: END,
        }
    )
    
    graph.add_conditional_edges(
        "dictation",
        route_next_agent,
        {
            "evaluation": "evaluation",
            "dictation": "dictation",
            END: END,
        }
    )
    
    graph.add_conditional_edges(
        "evaluation",
        route_next_agent,
        {
            "mcq": "mcq",
            "dictation": "dictation",
            "evaluation": "evaluation",
            "supervisor": "supervisor",
            "progress": "progress",
            END: END,
        }
    )
    
    graph.add_edge("progress", END)
    
    # Compile and return
    return graph.compile()


class VoIQAgent:
    """High-level interface for VoIQ agent system."""
    
    def __init__(self, db_path: str = "data/voiq.db"):
        self.db_path = db_path
        self.graph = create_voiq_graph(db_path)
        self.state: VoIQState = self._initial_state()
    
    def _initial_state(self) -> VoIQState:
        """Create initial state with all required fields."""
        return {
            "db_path": self.db_path,
            "session_correct": 0,
            "session_total": 0,
            "word_queue": [],
            "queue_index": 0,
            # Flow states - all idle
            "setup_step": "idle",
            "add_word_step": "idle",
            "delete_category_step": "idle",
            "review_step": "idle",
            "selected_categories": [],
            "session_wrong": [],
            "is_review_mode": False,
        }
    
    def chat(self, message: str) -> str:
        """Process a user message and return agent response."""
        # Handle special commands
        if message.lower().strip() in ["stop", "quit", "exit"]:
            self.reset_session()
            return "Quiz stopped. Type a command to start again!"
        
        # Check if continuing a quiz
        if message.lower().strip() in ["", "next", "continue", "n"]:
            # If we have a current question, we need to evaluate first
            if self.state.get("current_question"):
                self.state["user_answer"] = message
                result = self.graph.invoke(self.state)
                self.state = result
                return result.get("agent_response", "")
        
        # Update state with user message
        self.state["user_message"] = message
        
        # If we have a current question, treat as answer
        if self.state.get("current_question"):
            self.state["user_answer"] = message
        
        # Run graph
        result = self.graph.invoke(self.state)
        self.state = result
        
        response = result.get("agent_response", "Something went wrong!")
        return str(response) if response else "No response received."
    
    def reset_session(self):
        """Reset session state for a new quiz."""
        self.state = self._initial_state()
    
    def load_vocabulary(self, excel_path: str) -> int:
        """Load vocabulary from Excel file."""
        import voiq_core
        voiq_core.init_database(self.db_path)
        count = voiq_core.parse_excel(excel_path, self.db_path)
        return count
