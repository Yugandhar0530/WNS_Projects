from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

SUPPORTED_MODELS = ("mistral", "llama3.2", "llama3")

STORY_LENGTH_HINTS = {
    "Brief": "about 150–250 words",
    "Standard": "about 400–600 words",
    "Extended": "about 800–1000 words",
}


def create_chat_model(model: str, temperature: float) -> ChatOllama:
    if model not in SUPPORTED_MODELS:
        raise ValueError(f"Unsupported model: {model}")
    return ChatOllama(model=model, temperature=temperature)


def stream_reply(llm: ChatOllama, user_text: str):
    return llm.stream(user_text)


def generate_story(llm: ChatOllama, topic: str, genre: str, length_key: str) -> str:
    word_hint = STORY_LENGTH_HINTS.get(length_key, STORY_LENGTH_HINTS["Standard"])
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a fiction author. Write engaging prose. "
                "Genre: {genre}. Target length: {word_hint}. "
                "Start with a short title on the first line, then the story body.",
            ),
            ("user", "Theme or prompt: {topic}"),
        ]
    )
    chain = template | llm | StrOutputParser()
    return chain.invoke({"genre": genre, "word_hint": word_hint, "topic": topic})


def generate_joke(llm: ChatOllama, topic: str, style: str) -> str:
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You write short {style} jokes for a given subject. "
                "Rules:\n"
                "- The joke must be clearly about \"{topic}\" (use the word or obvious wordplay).\n"
                "- Do not swap in other animals, objects, or unrelated stock jokes.\n"
                "- Output only the joke text, no explanation.\n"
                "- Keep it family-friendly and under 80 words.\n"
                "For knock-knock format: the setup and punchline must tie to \"{topic}\".",
            ),
            ("user", "Write one {style} joke about: {topic}"),
        ]
    )
    chain = template | llm | StrOutputParser()
    return chain.invoke({"style": style, "topic": topic})


def joke_model(model: str, ui_temperature: float) -> ChatOllama:
    """Jokes need lower randomness so the subject is not dropped."""
    temp = min(ui_temperature, 0.45)
    return create_chat_model(model, temp)