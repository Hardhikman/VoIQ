"""
VoIQ - Vocabulary Intelligence Quiz System
Main Gradio Application
"""

import gradio as gr
import os
from pathlib import Path

import voiq_core
from agents.graph import VoIQAgent
from config import DATABASE_PATH, DATA_DIR

# Initialize agent
agent = VoIQAgent(db_path=DATABASE_PATH)

# Custom CSS for modern styling
CUSTOM_CSS = """
:root {
    --primary: #6366f1;
    --primary-light: #818cf8;
    --secondary: #8b5cf6;
    --success: #10b981;
    --error: #ef4444;
    --bg-dark: #0f172a;
    --bg-card: #1e293b;
    --text: #f1f5f9;
}

.gradio-container {
    max-width: 900px !important;
    margin: auto !important;
}

.main-title {
    text-align: center;
    background: linear-gradient(135deg, #6366f1, #8b5cf6, #a855f7);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 2.5rem !important;
    font-weight: 800 !important;
    margin-bottom: 0.5rem !important;
}

.subtitle {
    text-align: center;
    color: #94a3b8;
    font-size: 1.1rem;
    margin-bottom: 1rem;
}

.chat-container {
    border-radius: 16px !important;
    background: linear-gradient(145deg, #1e293b, #0f172a) !important;
}

.stats-box {
    background: linear-gradient(145deg, #1e293b, #0f172a);
    border-radius: 12px;
    padding: 1rem;
    border: 1px solid #334155;
}

.quick-btn {
    border-radius: 8px !important;
    font-weight: 600 !important;
    transition: transform 0.2s !important;
}

.quick-btn:hover {
    transform: scale(1.02);
}
"""


def upload_vocabulary(file):
    """Handle vocabulary file upload (Excel or CSV)."""
    if file is None:
        return "Please select an Excel or CSV file to upload.", gr.update()
    
    try:
        # Initialize database
        voiq_core.init_database(DATABASE_PATH)
        
        # Parse and load Excel
        count = voiq_core.parse_excel(file.name, DATABASE_PATH)
        
        # Reset agent state for new vocabulary
        agent.reset_session()
        
        return f"✅ Successfully loaded **{count} words**! Start your quiz now.", gr.update()
    except Exception as e:
        return f"❌ Error loading file: {str(e)}", gr.update()


def chat_response(message, history):
    """Process user message through agent system."""
    if not message.strip():
        return "", history
    
    try:
        response = agent.chat(message)
        # Use messages format: list of dicts with role and content
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": response})
    except Exception as e:
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": f"❌ Error: {str(e)}"})
    
    return "", history


def quick_command(command, history):
    """Handle quick command button clicks."""
    response = agent.chat(command)
    history.append({"role": "user", "content": command})
    history.append({"role": "assistant", "content": response})
    return history


def get_stats_display():
    """Get current statistics for display."""
    try:
        stats = voiq_core.get_stats(DATABASE_PATH)
        return f"""
        ### 📊 Your Progress
        - **Total Attempts:** {stats.total_attempts}
        - **Correct:** {stats.correct_count} ✅
        - **Accuracy:** {stats.accuracy_percent:.1f}%
        """
    except Exception:
        return "No stats yet. Start a quiz to track progress!"


# Build Gradio Interface
with gr.Blocks(
    title="VoIQ - Vocabulary Intelligence Quiz",
    theme=gr.themes.Soft(
        primary_hue="indigo",
        secondary_hue="purple",
    ),
    css=CUSTOM_CSS,
) as app:
    
    # Header
    gr.HTML("""
        <h1 class="main-title">🧠 VoIQ</h1>
        <p class="subtitle">Vocabulary Intelligence Quiz System</p>
    """)
    
    with gr.Tabs():
        # Quiz Tab
        with gr.Tab("📝 Quiz", id="quiz"):
            with gr.Row():
                with gr.Column(scale=3):
                    chatbot = gr.Chatbot(
                        label="VoIQ Assistant",
                        height=450,
                        placeholder="Start a quiz by typing a command or clicking a quick action below!",
                    )
                    
                    with gr.Row():
                        msg_input = gr.Textbox(
                            placeholder="Type your answer or command (e.g., 'Start MCQ A to Z 10 sec')...",
                            label="Your Message",
                            scale=5,
                            container=False,
                        )
                        send_btn = gr.Button("Send", variant="primary", scale=1)
                
                with gr.Column(scale=1):
                    gr.Markdown("### ⚡ Quick Actions")
                    
                    start_btn = gr.Button("� Start Quiz", elem_classes="quick-btn", variant="primary")
                    categories_btn = gr.Button("📂 Categories", elem_classes="quick-btn")
                    add_word_btn = gr.Button("➕ Add Word", elem_classes="quick-btn")
                    review = gr.Button("📝 Review Failed", elem_classes="quick-btn")
                    stats_btn = gr.Button("📊 My Stats", elem_classes="quick-btn")
                    
                    gr.Markdown("---")
                    gr.Markdown("*Type `start` for guided quiz setup*")
            
            # Event handlers
            msg_input.submit(chat_response, [msg_input, chatbot], [msg_input, chatbot])
            send_btn.click(chat_response, [msg_input, chatbot], [msg_input, chatbot])
            
            start_btn.click(
                lambda h: quick_command("start", h),
                chatbot, chatbot
            )
            categories_btn.click(
                lambda h: quick_command("categories", h),
                chatbot, chatbot
            )
            add_word_btn.click(
                lambda h: quick_command("add word", h),
                chatbot, chatbot
            )
            review.click(
                lambda h: quick_command("review", h),
                chatbot, chatbot
            )
            stats_btn.click(
                lambda h: quick_command("stats", h),
                chatbot, chatbot
            )
        
        # Upload Tab
        with gr.Tab("📤 Upload", id="upload"):
            gr.Markdown("""
                ### 📚 Upload Your Vocabulary
                
                Upload an **Excel (.xlsx)** or **CSV** file with the following columns:
                - **Words** - The vocabulary word
                - **Meaning** - Definition of the word
                - **Synonyms** - Comma-separated synonyms (optional)
                - **Antonyms** - Comma-separated antonyms (optional)
            """)
            
            with gr.Row():
                file_input = gr.File(
                    label="Select File (.xlsx or .csv)",
                    file_types=[".xlsx", ".xls", ".csv"],
                )
            
            upload_btn = gr.Button("📥 Upload & Load", variant="primary", size="lg")
            upload_status = gr.Markdown("")
            
            upload_btn.click(
                upload_vocabulary,
                inputs=[file_input],
                outputs=[upload_status, file_input]
            )
        
        # Stats Tab
        with gr.Tab("📊 Progress", id="stats"):
            gr.Markdown("### 📈 Learning Progress")
            
            stats_display = gr.Markdown(get_stats_display)
            refresh_btn = gr.Button("🔄 Refresh Stats", variant="secondary")
            
            refresh_btn.click(
                get_stats_display,
                outputs=[stats_display]
            )
            
            gr.Markdown("""
                ---
                ### 💡 Tips for Success
                
                1. **Regular Practice** - Quiz yourself daily for best retention
                2. **Review Failed Words** - Use the Review feature to focus on weak areas
                3. **Mix It Up** - Alternate between MCQ and Dictation modes
                4. **Challenge Yourself** - Try shorter timers as you improve!
            """)
    
    # Footer
    gr.Markdown("""
        ---
        <p style="text-align: center; color: #64748b; font-size: 0.875rem;">
            🚀 Powered by <strong>Rust + LangGraph + Groq</strong> | 
            Built with ❤️ for vocabulary mastery
        </p>
    """)


# Main entry point
if __name__ == "__main__":
    # Ensure data directory exists
    DATA_DIR.mkdir(exist_ok=True)
    
    # Initialize database
    voiq_core.init_database(DATABASE_PATH)
    
    # Launch app
    app.launch(
        share=False,
        server_name="127.0.0.1",
        server_port=7860,
    )
