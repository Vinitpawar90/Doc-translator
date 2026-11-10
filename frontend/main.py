import hashlib
import os
import time

import requests
import streamlit as st
from dotenv import load_dotenv


load_dotenv()

SAMPLE_PHRASES = {
    "A friendly hello": "Hello! It's lovely to meet you.",
    "Ask for directions": "Could you show me the way to the station?",
    "Say thank you": "Thank you for your help. I really appreciate it."
}
DOCUMENT_OUTPUT_FORMAT = "pdf"
DOCX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

st.set_page_config(
    page_title="DeepL Translator",
    page_icon=":material/translate:",
    layout="wide"
)

st.html(
    """
    <style>
    :root {
        --bg: #f1f3ef;
        --panel: #ffffff;
        --panel-strong: #f7f8f5;
        --line: #e2e8e2;
        --text: #203b35;
        --muted: #64736d;
        --accent: #bd805d;
        --green: #55766b;
        --button: #849b91;
        --button-strong: #6f897e;
        --shadow: rgba(32, 59, 53, 0.09);
    }

    [data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] {
        gap: 0.7rem;
    }

    html, body, .stApp {
        background: var(--bg) !important;
        color: var(--text);
        font-family: "Georgia", "Times New Roman", serif;
    }

    .stApp {
        background: var(--bg);
    }

    [data-testid="stMainBlockContainer"] {
        width: min(90vw, 920px) !important;
        max-width: 920px !important;
        min-height: min(90vw, 920px);
        box-sizing: border-box;
        margin: 4.5rem auto 1rem !important;
        padding: 1rem !important;
        border: 1px solid var(--line);
        border-radius: 22px;
        background: #ffffff !important;
        box-shadow: 0 16px 42px var(--shadow);
    }

    @media (max-width: 640px) {
        [data-testid="stMainBlockContainer"] {
            width: calc(100vw - 1rem) !important;
            min-height: auto;
            margin: 4.5rem auto 0.5rem !important;
            padding: 1rem !important;
        }
    }

    .translator-hero {
        text-align: center;
        max-width: 1000px;
        margin: 0 auto 0.55rem;
        padding-top: 0;
    }

    .translator-eyebrow {
        color: var(--text);
        letter-spacing: 0.24em;
        text-transform: uppercase;
        font-size: 0.7rem;
        font-weight: 600;
        font-family: "Segoe UI", sans-serif;
        margin: 0 auto 0.8rem;
        display: inline-block;
        position: relative;
    }

    .translator-eyebrow::before,
    .translator-eyebrow::after {
        content: "";
        display: inline-block;
        width: 30px;
        height: 1px;
        background: rgba(33, 58, 54, 0.5);
        vertical-align: middle;
        margin: 0 0.8rem;
    }

    .translator-hero h1 {
        font-size: clamp(2.5rem, 4vw, 3.8rem);
        line-height: 0.96;
        letter-spacing: -0.055em;
        font-weight: 500;
        margin: 0;
        color: var(--text);
    }

    .translator-hero h1 .accent {
        display: block;
        color: var(--accent);
        font-style: italic;
        font-weight: 500;
    }

    .translator-hero p {
        margin: 0.35rem auto 0;
        max-width: 620px;
        font-size: 0.98rem;
        color: var(--muted);
        font-family: "Segoe UI", sans-serif;
        font-weight: 400;
    }

    [data-testid="stHeader"] {
        background: transparent;
        box-shadow: none;
    }

    [data-testid="stAppDeployButton"] {
        display: none !important;
    }

    [data-testid="stMainMenu"] {
        display: none !important;
    }

    .translator-site-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        min-height: 54px;
        width: 100vw;
        box-sizing: border-box;
        position: fixed;
        top: 0;
        left: 0;
        z-index: 1000001;
        margin: 0;
        padding: 0.45rem clamp(0.75rem, 1.2vw, 1.25rem) 0.65rem;
        border-bottom: 1px solid #edf0ec;
        background: lightblue;
        font-family: "Segoe UI", sans-serif;
    }

    .translator-logo {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 90px;
        min-height: 32px;
        padding: 0.3rem 0.65rem;
        border: 1px solid #000000;
        border-radius: 6px;
        background: #000000;
        color: #ffffff;
        font-size: 0.64rem;
        font-weight: 700;
        letter-spacing: 0.1em;
    }

    .translator-profile {
        position: relative;
    }

    .translator-profile summary {
        display: flex;
        align-items: center;
        gap: 0.45rem;
        list-style: none;
        padding: 0.3rem 0.65rem 0.3rem 0.35rem;
        border: 1px solid #000000 !important;
        border-radius: 999px;
        background: #000000 !important;
        color: #ffffff !important;
        font-size: 0.78rem;
        cursor: pointer;
        transition: background 150ms ease, border-color 150ms ease;
    }

    .translator-profile summary:hover {
        background: #292929 !important;
        border-color: #000000 !important;
    }

    .translator-profile summary span {
        color: #ffffff !important;
    }

    .translator-profile summary::-webkit-details-marker {
        display: none;
    }

    .translator-profile-avatar {
        position: relative;
        display: inline-block;
        width: 23px;
        height: 23px;
        border-radius: 50%;
        background: #000000;
    }

    .translator-profile-avatar::before {
        content: "";
        position: absolute;
        top: 4px;
        left: 8px;
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: #ffffff;
    }

    .translator-profile-avatar::after {
        content: "";
        position: absolute;
        bottom: 4px;
        left: 5px;
        width: 13px;
        height: 7px;
        border-radius: 8px 8px 5px 5px;
        background: #ffffff;
    }

    .translator-profile-chevron {
        color: #ffffff;
        font-size: 0.7rem;
    }

    .translator-profile-menu {
        position: absolute;
        z-index: 20;
        top: calc(100% + 0.4rem);
        right: 0;
        min-width: 180px;
        padding: 0.75rem;
        border: 1px solid var(--line);
        border-radius: 10px;
        background: #ffffff;
        box-shadow: 0 8px 24px var(--shadow);
        color: var(--muted);
        font-size: 0.75rem;
    }

    .stBadge {
        display: none !important;
    }

    .stMarkdownBadge {
        background-color: #e8eee9 !important;
        color: #48665c !important;
        border: 1px solid #dce5df;
        border-radius: 999px;
        padding: 0.25rem 0.65rem;
    }

    .stMarkdownBadge * {
        color: inherit !important;
    }

    [data-testid="stTabs"] [role="tablist"] {
        display: flex;
        gap: 0.3rem;
        padding: 0.25rem;
        border: 0;
        border-radius: 10px;
        background: #f0f3f0;
    }

    [data-testid="stTabs"] [data-testid="stTab"] {
        flex: 1;
        justify-content: center;
        color: var(--muted) !important;
        font-family: "Segoe UI", sans-serif;
        font-weight: 600;
        padding: 0.55rem 1rem;
        border: 0 !important;
        border-radius: 8px;
        transition: background 150ms ease, box-shadow 150ms ease, color 150ms ease;
    }

    [data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"] {
        color: var(--green) !important;
        background: #ffffff;
        box-shadow: 0 1px 5px rgba(32, 59, 53, 0.12);
    }

    [data-testid="stTabs"] [data-testid="stTab"] p {
        margin: 0;
    }

    [data-testid="stTabs"] [data-testid="stTab"]::after {
        display: none !important;
    }

    .stButton > button {
        border-radius: 12px;
        border: 1px solid var(--line);
        background: #ffffff;
        color: var(--text);
        font-family: "Segoe UI", sans-serif;
        font-weight: 600;
        transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
    }

    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 8px 18px var(--shadow);
        border-color: rgba(33, 58, 54, 0.2);
    }

    .stButton > button[kind="primary"],
    .stDownloadButton > button {
        background: linear-gradient(135deg, #8da49a, #71897f);
        color: #ffffff;
        border-color: rgba(33,58,54,0.04);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.23);
    }

    div[data-testid="stTabPanel"] {
        border: 1px solid var(--line);
        border-radius: 18px;
        background: #ffffff !important;
        box-shadow: 0 12px 32px var(--shadow);
        padding: 0.8rem;
    }

    div[data-testid="stLayoutWrapper"]:has(
        > [data-testid="stVerticalBlock"] [data-testid="stSelectbox"]
    ) {
        border: 1px solid var(--line);
        border-radius: 16px;
        background-color: #ffffff !important;
        box-shadow: 0 8px 24px var(--shadow);
        padding: 0.65rem;
    }

    div[data-testid="stFileUploader"] {
        margin-top: 0.65rem;
    }

    section[data-testid="stFileUploaderDropzone"] {
        display: flex !important;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 0.45rem;
        min-height: 185px;
        padding: 1rem !important;
        border: 1px dashed #cbd9ce !important;
        border-radius: 12px !important;
        background: #fcfdfb !important;
        text-align: center;
        transition: background 150ms ease, border-color 150ms ease;
    }

    section[data-testid="stFileUploaderDropzone"]:hover {
        background: #f6f9f6 !important;
        border-color: #8da49a !important;
    }

    section[data-testid="stFileUploaderDropzone"]::before {
        content: "↑";
        order: 0;
        display: grid;
        place-items: center;
        width: 40px;
        height: 40px;
        border: 1px solid #dce5df;
        border-radius: 12px;
        background: #ffffff;
        color: var(--green);
        font: 1.6rem/1 "Segoe UI", sans-serif;
    }

    section[data-testid="stFileUploaderDropzone"]::after {
        content: "Drop your document here";
        order: 1;
        color: var(--text);
        font: 600 0.95rem/1.35 "Segoe UI", sans-serif;
    }

    section[data-testid="stFileUploaderDropzone"] > span:has(button) {
        order: 2;
    }

    [data-testid="stFileUploaderDropzoneInstructions"] {
        order: 3;
        justify-content: center;
        text-align: center;
        color: var(--muted);
        font-size: 0.75rem;
    }

    [data-testid="stFileUploader"] [data-testid="stBaseButton-secondary"] {
        background: linear-gradient(135deg, #8da49a, #71897f) !important;
        border: 1px solid #71897f !important;
        border-radius: 10px !important;
        color: #ffffff !important;
    }

    [data-testid="stFileUploader"] [data-testid="stBaseButton-secondary"]:hover {
        background: #617d72 !important;
        border-color: #617d72 !important;
        color: #ffffff !important;
    }

    [data-testid="stFileUploader"] [data-testid="stBaseButton-secondary"] * {
        color: #ffffff !important;
    }

    .stSelectbox > div > div,
    .stTextInput > div > div > input,
    .stTextArea > div > textarea {
        background: #ffffff !important;
        border: 1px solid rgba(33, 58, 54, 0.15);
        border-radius: 12px;
        color: #1f2e2d !important;
        font-family: "Segoe UI", sans-serif;
    }

    .stSelectbox > div > div {
        min-height: 54px;
    }

    [data-testid="stSelectbox"] input {
        color: var(--text) !important;
    }

    [data-testid="stSelectbox"] button[aria-label="Open"],
    [data-testid="stSelectbox"] button[aria-label="Open"] svg {
        color: #000000 !important;
        fill: #000000 !important;
    }

    .stTextArea > div > textarea,
    .stTextInput > div > div > input {
        color: #1f2e2d !important;
    }

    .st-key-deepl_text_result_display textarea:not(:placeholder-shown) {
        background: #36584e !important;
        border-color: #36584e !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }

    .block-container,
    .block-container p,
    .block-container [data-testid="stCaptionContainer"],
    .block-container [data-testid="stWidgetLabel"],
    .block-container [data-testid="stMarkdownContainer"] {
        color: var(--text);
    }

    .block-container [data-testid="stWidgetLabel"],
    .block-container [data-testid="stWidgetLabel"] *,
    .block-container [data-testid="stCaptionContainer"],
    .block-container [data-testid="stCaptionContainer"] *,
    .block-container [data-testid="stMarkdownContainer"] {
        color: var(--text) !important;
    }

    .translator-hero h1 .accent {
        color: var(--accent) !important;
    }

    .block-container [data-baseweb="select"] * {
        color: var(--text) !important;
    }

    .block-container input::placeholder,
    .block-container textarea::placeholder {
        color: #78827d !important;
        opacity: 1;
    }

    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        font-family: "Georgia", "Times New Roman", serif;
        color: var(--text);
    }

    .stAlert,
    .stInfo,
    .stSuccess,
    .stError,
    .stWarning,
    .stChatMessage {
        border-radius: 12px;
    }

    .block-container .stSelectbox label,
    .block-container .stTextArea label,
    .block-container .stTextInput label {
        letter-spacing: 0.15em;
        text-transform: uppercase;
        font-size: 0.66rem;
        color: var(--muted) !important;
        font-family: "Segoe UI", sans-serif;
        margin-bottom: 0.45rem;
    }

    .translation-panel-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin: 0.15rem 0 0.7rem;
        gap: 1rem;
    }

    .translation-panel-title {
        margin: 0;
        font-size: 1.4rem;
        line-height: 1.1;
        font-family: "Segoe UI", sans-serif;
        color: var(--text);
        font-weight: 600;
    }

    .translation-panel-note {
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.14em;
        font-size: 0.62rem;
        font-family: "Segoe UI", sans-serif;
        white-space: nowrap;
    }

    .translation-panel-note::before {
        content: "* ";
        color: var(--text);
    }
    </style>
    """
)
st.markdown(
    """
    <header class="translator-site-header">
        <div class="translator-logo">YOUR LOGO</div>
        <details class="translator-profile">
            <summary>
                <span class="translator-profile-avatar" aria-hidden="true"></span>
                <span>Your name</span>
                <span class="translator-profile-chevron">⌄</span>
            </summary>
            <div class="translator-profile-menu">Translation workspace</div>
        </details>
    </header>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    """
    <section class="translator-hero">
        <div class="translator-eyebrow">Your words, anywhere</div>
        <h1>Making Every Document Speak <span class="accent">feel  Your Language.</span></h1>
        <p>Translate your documents while keeping the meaning clear and natural.</p>
    </section>
    """,
    unsafe_allow_html=True
)


def get_secret_api_key():
    api_key = os.getenv("DEEPL_API_KEY", "").strip()
    if api_key:
        return api_key
    try:
        return str(st.secrets.get("DEEPL_API_KEY", "")).strip()
    except (FileNotFoundError, AttributeError):
        return ""


def load_sample_phrase():
    selected = st.session_state.get("deepl_sample_phrase")
    if selected:
        st.session_state["deepl_source_text"] = SAMPLE_PHRASES[selected]


def get_api_base(api_key):
    if api_key.endswith(":fx"):
        return "https://api-free.deepl.com"
    return "https://api.deepl.com"


def get_error_message(response):
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    message = payload.get("message") if isinstance(payload, dict) else None
    trace_id = response.headers.get("X-Trace-ID")
    if message and trace_id:
        return f"{message} (DeepL trace ID: {trace_id})"
    if message:
        return message
    if trace_id:
        return f"{response.text or 'DeepL request failed.'} (Trace ID: {trace_id})"
    return response.text or f"DeepL request failed with HTTP {response.status_code}."


def raise_for_deepl_error(response):
    if not response.ok:
        raise RuntimeError(get_error_message(response))


@st.cache_data(ttl=3600)
def get_languages(api_base, api_key, resource):
    response = requests.get(
        f"{api_base}/v3/languages",
        headers={"Authorization": f"DeepL-Auth-Key {api_key}"},
        params={"resource": resource},
        timeout=20
    )
    raise_for_deepl_error(response)
    payload = response.json()
    if not isinstance(payload, list):
        raise RuntimeError("DeepL returned an unexpected language list.")
    return payload


def translate_text(api_base, api_key, text, target_lang, source_lang):
    if len(text.encode("utf-8")) > 128 * 1024:
        raise ValueError(
            "Text is over the 128 KiB per-request limit. Split it into "
            "smaller sections and translate them separately."
        )
    data = {
        "text": [text],
        "target_lang": target_lang
    }
    if source_lang != "AUTO":
        data["source_lang"] = source_lang

    response = requests.post(
        f"{api_base}/v2/translate",
        headers={"Authorization": f"DeepL-Auth-Key {api_key}"},
        json=data,
        timeout=60
    )
    raise_for_deepl_error(response)
    translations = response.json().get("translations", [])
    if not translations or not translations[0].get("text"):
        raise RuntimeError("DeepL did not return a translated text.")
    return translations[0]["text"]


def translate_document(
    api_base,
    api_key,
    file_name,
    file_content,
    content_type,
    target_lang,
    source_lang,
    output_format=DOCUMENT_OUTPUT_FORMAT
):
    headers = {"Authorization": f"DeepL-Auth-Key {api_key}"}
    data = {
        "target_lang": target_lang,
        "output_format": output_format
    }
    if source_lang != "AUTO":
        data["source_lang"] = source_lang

    upload_response = requests.post(
        f"{api_base}/v2/document",
        headers=headers,
        files={
            "file": (
                file_name,
                file_content,
                content_type or "application/octet-stream"
            )
        },
        data=data,
        timeout=90
    )
    raise_for_deepl_error(upload_response)
    document_data = upload_response.json()
    document_id = document_data.get("document_id")
    document_key = document_data.get("document_key")
    if not document_id or not document_key:
        raise RuntimeError("DeepL did not return document credentials.")

    deadline = time.monotonic() + 600
    status_poll_interval = 2
    with st.status("Translating your document with DeepL...", expanded=True) as status:
        while time.monotonic() < deadline:
            time.sleep(status_poll_interval)
            status_response = requests.post(
                f"{api_base}/v2/document/{document_id}",
                headers=headers,
                data={"document_key": document_key},
                timeout=30
            )
            raise_for_deepl_error(status_response)
            status_data = status_response.json()
            state = status_data.get("status")

            if state == "done":
                status.update(
                    label="Document translation complete",
                    state="complete",
                    expanded=False
                )
                break
            if state == "error":
                message = status_data.get("message")
                raise RuntimeError(
                    message or "DeepL could not translate this document."
                )
            if state not in {"queued", "translating"}:
                raise RuntimeError(
                    f"DeepL returned an unexpected document status: {state!r}"
                )
            remaining = status_data.get("seconds_remaining")
            if remaining is None:
                status.write(f"Status: {state}")
            else:
                status.write(
                    f"Status: {state} · about {remaining} seconds remaining"
                )
        else:
            raise TimeoutError("Document translation timed out after 10 minutes.")

    result_response = requests.post(
        f"{api_base}/v2/document/{document_id}/result",
        headers=headers,
        data={"document_key": document_key},
        timeout=90
    )
    raise_for_deepl_error(result_response)
    if not result_response.content:
        raise RuntimeError("DeepL returned an empty translated document.")
    return result_response.content


def render_file_translation(
    uploaded_file,
    file_kind,
    state_key,
    api_base,
    api_key,
    target_code,
    target_name,
    source_code
):
    if uploaded_file is None:
        st.session_state.pop(state_key, None)
        return

    file_content = uploaded_file.getvalue()
    signature = (
        uploaded_file.name,
        hashlib.sha256(file_content).hexdigest(),
        target_code,
        source_code,
        DOCUMENT_OUTPUT_FORMAT
    )
    saved_result = st.session_state.get(state_key)
    if saved_result and saved_result["signature"] != signature:
        st.session_state.pop(state_key, None)

    st.caption(
        f"Selected: **{uploaded_file.name}** · "
        f"{uploaded_file.size / (1024 * 1024):.2f} MB"
    )
    if st.button(
        f"Translate {file_kind}",
        type="primary",
        icon=":material/translate:",
        key=f"{state_key}_translate"
    ):
        try:
            with st.spinner(
                f"Translating {file_kind.lower()} into {target_name}..."
            ):
                translated_file = translate_document(
                    api_base,
                    api_key,
                    uploaded_file.name,
                    file_content,
                    uploaded_file.type,
                    target_code,
                    source_code,
                    output_format=DOCUMENT_OUTPUT_FORMAT
                )
            translated_name = (
                f"{os.path.splitext(uploaded_file.name)[0]}_"
                f"{target_code.lower()}.{DOCUMENT_OUTPUT_FORMAT}"
            )
            st.session_state[state_key] = {
                "signature": signature,
                "data": translated_file,
                "file_name": translated_name,
                "mime_type": DOCX_MIME_TYPE
            }
        except (
            requests.RequestException,
            RuntimeError,
            TimeoutError,
            ValueError
        ) as error:
            st.error(f"{file_kind} translation failed: {error}")

    saved_result = st.session_state.get(state_key)
    if saved_result and saved_result["signature"] == signature:
        st.success(f"Translated into {target_name}.")
        st.download_button(
            "Download translated DOCX",
            data=saved_result["data"],
            file_name=saved_result["file_name"],
            mime=saved_result["mime_type"],
            type="primary",
            icon=":material/download:",
            key=f"{state_key}_download"
        )


api_key = get_secret_api_key()

if not api_key:
    st.info(
        "Set `DEEPL_API_KEY` in your `.env` file or Streamlit secrets to "
        "start translating."
    )
    st.stop()

api_base = get_api_base(api_key)
try:
    target_languages = get_languages(api_base, api_key, "translate_text")
except (requests.RequestException, RuntimeError, ValueError) as error:
    st.error(f"Could not load supported languages from DeepL: {error}")
    st.stop()

targets = {
    language["name"]: language["lang"]
    for language in target_languages
    if language.get("usable_as_target", True)
}
sources = {
    language["name"]: language["lang"]
    for language in target_languages
    if language.get("usable_as_source", True)
}

target_options = dict(sorted(targets.items()))
source_options = dict(sorted(sources.items()))

if not target_options:
    st.error(
        "This DeepL API key did not return any supported target languages. "
        "Check the key or DeepL account availability."
    )
    st.stop()

def swap_languages():
    selected_source = st.session_state.get("deepl_source_language")
    selected_target = st.session_state.get("deepl_target_language")
    if selected_source in target_options and selected_target in source_options:
        st.session_state["deepl_source_language"] = selected_target
        st.session_state["deepl_target_language"] = selected_source


st.markdown(
    """
    <div class="translation-panel-header">
        <h2 class="translation-panel-title">Start translating</h2>
        <div class="translation-panel-note">DeepL key stays server-side</div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.container(border=True):
    source_col, swap_col, target_col = st.columns(
        [1, 0.16, 1],
        vertical_alignment="bottom"
    )
    with source_col:
        source_name = st.selectbox(
            "Translate from",
            ["Detect automatically", *source_options],
            key="deepl_source_language"
        )
    with swap_col:
        can_swap = (
            source_name != "Detect automatically"
            and source_name in target_options
            and source_name != st.session_state.get("deepl_target_language")
        )
        st.button(
            "Swap",
            icon=":material/swap_horiz:",
            help="Swap source and target languages",
            key="deepl_swap_languages",
            on_click=swap_languages,
            disabled=not can_swap
        )
    with target_col:
        target_name = st.selectbox(
            "Translate into",
            list(target_options),
            key="deepl_target_language"
        )

target_code = target_options[target_name]
source_code = (
    "AUTO"
    if source_name == "Detect automatically"
    else source_options[source_name]
)
with st.container(horizontal=True, horizontal_alignment="left"):
    st.badge(
        f"{len(target_options)} target languages",
        icon=":material/language:",
        color="green"
    )
    st.badge("Text, PDF & documents", icon=":material/folder_open:")

upload_tab, text_tab = st.tabs(["↑  Upload document", "≡  Paste text"])

with text_tab:
    with st.container(border=True):
        input_col, output_col = st.columns(2, gap="small")
        with input_col:
            st.subheader("Your text")
            st.caption("Choose a sample or type your own.")
            #st.pills(
                #"Try a sample",
                #list(SAMPLE_PHRASES),
                #key="deepl_sample_phrase",
                #on_change=load_sample_phrase,
                #help="Choose a phrase to add it to the text box."
            #)
            source_text = st.text_area(
                "Text to translate",
                placeholder="Type or paste your text here...",
                height=130,
                key="deepl_source_text"
            )
            st.caption(
                f"{len(source_text):,} characters · "
                f"{len(source_text.encode('utf-8')) / 1024:.1f} KiB"
            )
            if st.button(
                "Translate text",
                type="primary",
                icon=":material/translate:",
                disabled=not source_text.strip(),
                key="deepl_translate_text"
            ):
                try:
                    with st.spinner(f"Translating into {target_name}..."):
                        translated_text = translate_text(
                            api_base,
                            api_key,
                            source_text,
                            target_code,
                            source_code
                        )
                    st.session_state["deepl_text_result"] = {
                        "text": translated_text,
                        "signature": (source_text, target_code, source_code)
                    }
                except (
                    requests.RequestException,
                    RuntimeError,
                    ValueError
                ) as error:
                    st.error(f"Text translation failed: {error}")

        result = st.session_state.get("deepl_text_result")
        current_signature = (source_text, target_code, source_code)
        translated_text = (
            result["text"]
            if result and result["signature"] == current_signature
            else ""
        )
        with output_col:
            st.subheader("Translation")
            st.caption(f"Translation in {target_name}")
            st.session_state["deepl_text_result_display"] = translated_text
            st.text_area(
                "Translation",
                height=130,
                key="deepl_text_result_display",
                disabled=True,
                placeholder="Your translation will appear here."
            )
            if translated_text:
                st.download_button(
                    "Download translation",
                    data=translated_text,
                    file_name=f"translation_{target_code.lower()}.txt",
                    mime="text/plain",
                    icon=":material/download:",
                    key="deepl_download_text"
                )

with upload_tab:
    with st.container(border=True):
        st.subheader("Add a document to translate")
        st.caption(
            f"Choose a PDF, Office document, text, or supported image. "
            f"Translation will be returned in {target_name}."
        )
        uploaded_file = st.file_uploader(
            "Choose a document",
            type=[
                "pdf", "docx", "pptx", "xlsx", "xlsm", "htm", "html", "txt",
                "xlf", "xliff", "srt", "vtt", "idml", "xml", "json", "yaml",
                "yml", "properties", "strings", "md", "markdown", "dita",
                "mif", "zip", "odt", "rtf", "resx", "jpg", "jpeg", "png"
            ],
            help=(
                "Files are sent to DeepL for translation. Avoid uploading "
                "sensitive documents unless your organization allows it."
            ),
            key="deepl_document_file"
        )
        if uploaded_file is not None:
            file_kind = (
                "PDF"
                if os.path.splitext(uploaded_file.name)[1].lower() == ".pdf"
                else "file"
            )
        render_file_translation(
            uploaded_file,
            file_kind if uploaded_file is not None else "file",
            "deepl_document_file_result",
            api_base,
            api_key,
            target_code,
            target_name,
            source_code
        )