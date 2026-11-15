# Text Generator

Streamlit app for local GenAI text generation: multi-turn chat, themed short stories, and topic-based jokes. Inference runs on your machine through [Ollama](https://ollama.com).

## Features

- **Assistant chat** — streaming replies with session history and a clear-history control
- **Short story** — genre, size, and theme controls with structured prompts
- **Humor** — one-liners, puns, dad jokes, and knock-knock jokes from a subject line
- **Configurable models** — `mistral`, `llama3.2`, or `llama3` with adjustable randomness

## Project Background

Skense delivery training covers NLP and GenAI module development. This project shows how to wrap a local LLM in a small Python UI: LangChain prompt templates, Ollama as the backend, and three focused generation flows in one app. It is suitable for demos, coursework submission, and as a starting point for richer RAG or API-backed services.

## Prerequisites

- Python 3.10 or later
- [Ollama](https://ollama.com) installed and running
- At least one pulled model, for example:

```powershell
ollama pull llama3.2
```

Optional additional models:

```powershell
ollama pull mistral
ollama pull llama3
```

## How to Run

From the repository root:

```powershell
cd WNS_Projects\Text_Generator
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

The app opens in your browser (default `http://localhost:8501`).

Confirm Ollama is reachable:

```powershell
ollama list
```

## How It Works

1. **Sidebar** — pick an Ollama model and temperature; optionally clear chat history.
2. **Chat** — user messages are sent directly to the model; responses stream into the UI.
3. **Story** — a system prompt sets genre and target length; the user theme drives the plot.
4. **Joke** — a system prompt fixes the joke format; the subject line sets the topic.

Core logic lives in `llm_client.py` (`ChatOllama`, `ChatPromptTemplate`, `StrOutputParser`). The UI is in `app.py`.

## Sample Output

![Assistant chat — multi-turn conversation](screenshots/chat_demo.png)

![Short story — generated narrative from theme and genre](screenshots/story_demo.png)

![Humor — subject-based joke output](screenshots/joke_demo.png)

## Notes

- All generation is local; no cloud API keys are required.
- First reply can be slow while the model loads into memory.
- GPU-backed Ollama reduces latency when a supported GPU is available.

## Project Layout

```
Text_Generator/
├── app.py              # Streamlit UI
├── llm_client.py         # Ollama + LangChain helpers
├── requirements.txt
├── screenshots/          # UI captures for README
└── README.md
```