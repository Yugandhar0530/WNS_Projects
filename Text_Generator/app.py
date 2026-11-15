import streamlit as st

from llm_client import (
    SUPPORTED_MODELS,
    create_chat_model,
    generate_joke,
    generate_story,
    joke_model,
    stream_reply,
)

st.set_page_config(page_title="GenAI Text Studio", page_icon="📝", layout="centered")

st.sidebar.header("Model settings")
selected_model = st.sidebar.selectbox("Ollama model", list(SUPPORTED_MODELS))
temperature = st.sidebar.slider("Response randomness", 0.0, 1.0, 0.75, 0.05)

if st.sidebar.button("Clear chat history", use_container_width=True):
    st.session_state.pop("chat_turns", None)
    st.session_state.chat_awaiting_reply = False

st.title("GenAI Text Studio")
st.caption("Local text generation with Ollama — chat, stories, and jokes.")

tab_chat, tab_story, tab_joke = st.tabs(
    ["Assistant chat", "Short story", "Humor"]
)


def active_llm():
    return create_chat_model(selected_model, temperature)


with tab_chat:
    st.subheader("Conversational assistant")

    if "chat_turns" not in st.session_state:
        st.session_state.chat_turns = []
    if "chat_awaiting_reply" not in st.session_state:
        st.session_state.chat_awaiting_reply = False

    for turn in st.session_state.chat_turns:
        with st.chat_message(turn["role"]):
            st.markdown(turn["content"])

    if st.session_state.chat_awaiting_reply and st.session_state.chat_turns:
        user_text = st.session_state.chat_turns[-1]["content"]
        with st.chat_message("assistant"):
            try:
                llm = active_llm()
                reply = st.write_stream(stream_reply(llm, user_text))
            except Exception as exc:
                reply = (
                    "Could not reach Ollama. Start the Ollama app and pull a model, "
                    f"then try again. ({exc})"
                )
                st.markdown(reply)
        st.session_state.chat_turns.append({"role": "assistant", "content": reply})
        st.session_state.chat_awaiting_reply = False
        st.rerun()

    if user_msg := st.chat_input("Ask anything…"):
        st.session_state.chat_turns.append({"role": "user", "content": user_msg})
        st.session_state.chat_awaiting_reply = True
        st.rerun()

with tab_story:
    st.subheader("Prompt-to-story")
    left, right = st.columns(2)

    with left:
        theme = st.text_area(
            "Theme or opening idea",
            placeholder="A lighthouse keeper discovers a message in a bottle…",
            height=100,
        )
        genre = st.selectbox(
            "Genre",
            ["Adventure", "Science fiction", "Mystery", "Romance", "Slice of life"],
        )
        length = st.radio("Story size", ["Brief", "Standard", "Extended"], horizontal=True)
        run_story = st.button("Generate story", type="primary", use_container_width=True)

    with right:
        if run_story:
            if not theme.strip():
                st.warning("Enter a theme before generating.")
            else:
                with st.spinner("Writing…"):
                    try:
                        text = generate_story(active_llm(), theme.strip(), genre, length)
                        st.markdown("**Output**")
                        st.markdown(text)
                    except Exception as exc:
                        st.error(
                            "Story generation failed. Confirm Ollama is running and the "
                            f"selected model is installed. ({exc})"
                        )

with tab_joke:
    st.subheader("Topic-based jokes")
    subject = st.text_input(
        "Joke subject",
        placeholder="Cloud computing, coffee, commuting…",
    )
    humor_type = st.selectbox(
        "Format",
        ["One-liner", "Pun", "Dad joke", "Knock-knock"],
    )
    generate_joke_btn = st.button("Make me laugh", use_container_width=True)

    if "last_joke" not in st.session_state:
        st.session_state.last_joke = ""

    if generate_joke_btn:
        if not subject.strip():
            st.warning("Enter a subject for the joke.")
            st.session_state.last_joke = ""
        else:
            with st.spinner("Thinking…"):
                try:
                    st.session_state.last_joke = generate_joke(
                        joke_model(selected_model, temperature),
                        subject.strip(),
                        humor_type,
                    )
                except Exception as exc:
                    st.session_state.last_joke = ""
                    st.error(
                        "Joke generation failed. Confirm Ollama is running and the "
                        f"selected model is installed. ({exc})"
                    )

    if st.session_state.last_joke:
        st.markdown("**Generated joke**")
        st.container(border=True).markdown(st.session_state.last_joke)