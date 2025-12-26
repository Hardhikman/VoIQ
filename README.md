# 🧠 VoIQ - Vocabulary IntrepidQ AI System

A **VoCat alternative** — a high-performance vocabulary learning platform built with **Rust** and **Python**, featuring AI-powered quiz generation and intelligent progress tracking.

> **VoIQ** = **Vo**cabulary **I**ntrepid**Q** AI System

## ✨ Features

- **� Category Management** - Organize vocabulary into folders/sets with multi-select quiz support
- **🚀 Guided Setup** - Simple chat-based configuration for your quiz (start → mode → timer)
- **�📚 MCQ Quiz** - 12 question types (word↔meaning↔synonym↔antonym)
- **✍️ Dictation Mode** - Writing tests with fuzzy matching
- **🤖 AI Agents** - Stable LangGraph multi-agent system with Groq LLM
- **⚡ Rust Core** - High-performance SQLite, Excel parsing, fuzzy matching
- **📊 Progress Tracking** - Failed words, accuracy stats, session tracking
- **🎯 Smart Ordering** - A-Z, Z-A, Random, or Letter-wise filtering

## 🚀 Quick Start

```bash
# 1. Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Build Rust module
cd voiq_core && python -m maturin develop --release && cd ..

# 4. Configure (optional - for LLM features)
copy .env.example .env
# Edit .env and add GROQ_API_KEY

# 5. Run
python app.py
```

Open http://127.0.0.1:7860 🎉

## 📖 Usage

### Core Commands
| Command | Action |
|---------|--------|
| `start` | **Guided Quiz Setup** (Category → Mode → Order → Timer) |
| `categories` | List all available vocabulary sets |
| `delete category` | Remove a set and its words |
| `add word` | Add a single word to a category |
| `stats` | View progress & failed words |
| `review` | Review words you got wrong |

### Quick Actions
The web UI provides a sidebar with one-click buttons for all major features:
- **🚀 Start Quiz**
- **📂 Categories**
- **➕ Add Word**
- **📝 Review Failed**
- **📊 My Stats**

## 🏗️ Architecture

```
┌──────────────┐     ┌──────────────────────────┐     ┌─────────────┐
│  Gradio UI   │ ──▶ │  LangGraph Agents (5)    │ ──▶ │ Rust Core   │
│   (Web)      │     │ (Supervisor/MCQ/Dict...) │     │  (PyO3)     │
└──────────────┘     └──────────────────────────┘     └─────────────┘
                                                             │
                                                       ┌─────▼─────┐
                                                       │  SQLite   │
                                                       └───────────┘
```

## 📁 Project Structure

```
VoIQ/
├── app.py              # Gradio web application
├── config.py           # Configuration
├── agents/             # LangGraph multi-agent system
│   ├── core/           # Shared state & prompts
│   ├── supervisor/     # Intent parsing
│   ├── mcq/            # MCQ questions
│   ├── dictation/      # Writing tests
│   ├── evaluation/     # Answer scoring
│   └── progress/       # Statistics
├── voiq_core/          # Rust module (PyO3)
│   └── src/
│       ├── db.rs       # SQLite operations
│       ├── excel.rs    # Excel parsing
│       ├── fuzzy.rs    # Levenshtein matching
│       ├── questions.rs # MCQ generation
│       └── progress.rs # Attempt tracking
```

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **UI** | Gradio |
| **Agents** | LangGraph + Groq |
| **Core** | Rust (PyO3/Maturin) |
| **Database** | SQLite |
| **Fuzzy Match** | Levenshtein (strsim) |


## 📄 License

MIT License

---

Built with ❤️ using Rust + Python + LangGraph
