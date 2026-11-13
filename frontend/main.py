import base64
import hashlib
import html
import logging
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

if __package__:
    from . import data_shield, document_shield, sidebar_store
else:
    import data_shield
    import document_shield
    import sidebar_store


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
FEEDBACK_API_URL = os.getenv(
    "FEEDBACK_API_URL",
    "http://localhost:8000/feedback"
).strip()
BACKEND_API_URL = os.getenv(
    "BACKEND_API_URL",
    FEEDBACK_API_URL.rsplit("/", 1)[0]
).rstrip("/")
LOGO_DATA = base64.b64encode(
    (Path(__file__).resolve().parents[1] / "pictures" / "bl logo.webp").read_bytes()
).decode("ascii")
LOGGER = logging.getLogger(__name__)

st.set_page_config(
    page_title="DeepL Translator",
    page_icon=":material/translate:",
    layout="wide",
    initial_sidebar_state="expanded",
)

@st.cache_resource(show_spinner=False)
def initialize_sidebar_database():
    sidebar_store.initialize_database()


initialize_sidebar_database()
st.session_state.setdefault("data_shield_enabled", True)
st.session_state.setdefault("deepl_file_uploader_generation", 0)
st.session_state.setdefault("sidebar_history_collapsed", False)

_COPY_BUTTON_HTML = """
<div class="copy-wrap">
    <span class="copy-feedback" role="status" aria-live="polite"></span>
    <button
        class="copy-circle"
        type="button"
        title="Copy translation"
        aria-label="Copy translation"
    >
        <svg class="icon-svg clipboard-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
        </svg>
        <svg class="icon-svg check-icon" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polyline class="check-path" points="20 6 9 17 4 12"></polyline>
        </svg>
    </button>
</div>
"""

_COPY_BUTTON_CSS = """
:host {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    width: 100%;
    height: 52px;
}

.copy-wrap {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.6rem;
    width: 100%;
    height: 52px;
}

.copy-circle {
    position: relative;
    width: 40px;
    height: 40px;
    flex: 0 0 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #64748b;
    background: #e8edf5;
    border: 1px solid #d1d9e6;
    border-radius: 50%;
    cursor: pointer;
    box-shadow: 3px 3px 6px #c5ccd8, -3px -3px 6px #ffffff;
    transition: transform 0.15s ease, box-shadow 0.2s ease, border-color 0.25s ease;
    outline: none;
}

.copy-circle:hover {
    color: #334155;
    transform: translateY(-1px);
}

.copy-circle:disabled {
    opacity: 0.55;
    cursor: not-allowed;
}

.copy-circle:disabled:hover {
    color: #64748b;
    transform: none;
}

.copy-circle:focus-visible {
    outline: 2px solid #55766b;
    outline-offset: 3px;
}

.copy-circle:active {
    transform: scale(0.92);
    box-shadow: inset 2px 2px 5px #c5ccd8, inset -2px -2px 5px #ffffff;
}

.copy-circle::after {
    content: "";
    position: absolute;
    inset: -3px;
    border-radius: 50%;
    border: 2px solid #10b981;
    opacity: 0;
    transform: scale(0.8);
    pointer-events: none;
}

.copy-circle.copied {
    border-color: #10b981;
    box-shadow: 0 0 10px rgba(16, 185, 129, 0.25), inset 1px 1px 3px #ffffff;
}

.copy-circle.copy-error {
    border-color: #dc2626;
    color: #b91c1c;
}

.copy-circle.copied::after {
    animation: ripple-pulse 0.6s ease-out forwards;
}

@keyframes ripple-pulse {
    0% { opacity: 0.8; transform: scale(0.85); }
    100% { opacity: 0; transform: scale(1.35); }
}

.icon-svg {
    position: absolute;
    transition: opacity 0.2s ease, transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.clipboard-icon {
    opacity: 1;
    transform: scale(1) rotate(0deg);
}

.copy-circle.copied .clipboard-icon {
    opacity: 0;
    transform: scale(0.5) rotate(-20deg);
}

.check-icon {
    opacity: 0;
    transform: scale(0.5);
}

.copy-circle.copied .check-icon {
    opacity: 1;
    transform: scale(1);
}

.check-path {
    stroke-dasharray: 24;
    stroke-dashoffset: 24;
}

.copy-circle.copied .check-path {
    animation: draw-check 0.35s 0.1s ease-out forwards;
}

@keyframes draw-check {
    to { stroke-dashoffset: 0; }
}

.copy-feedback {
    color: #55766b;
    font: 0.8rem "Segoe UI", sans-serif;
}

.copy-feedback.copy-error {
    color: #b91c1c;
}
"""

_COPY_BUTTON_JS = """
export default function(component) {
    const { data, parentElement } = component;
    const button = parentElement.querySelector(".copy-circle");
    const feedback = parentElement.querySelector(".copy-feedback");
    if (!button || !feedback) return;

    const text = typeof data?.text === "string" ? data.text : "";
    button.onclick = null;
    button.classList.remove("copied", "copy-error");
    feedback.classList.remove("copy-error");
    feedback.textContent = "";
    button.disabled = text.length === 0;
    button.title = button.disabled
        ? "Translate text first to enable copying."
        : "Copy translation";
    button.setAttribute("aria-label", button.title);

    if (button.disabled) {
        return;
    }

    let resetTimer;
    button.onclick = async () => {
        try {
            await navigator.clipboard.writeText(text);
            button.classList.remove("copied", "copy-error");
            feedback.classList.remove("copy-error");
            void button.offsetWidth;
            button.classList.add("copied");
            button.title = "Copied to clipboard";
            button.setAttribute("aria-label", "Copied to clipboard");
            feedback.textContent = "Copied";

            clearTimeout(resetTimer);
            resetTimer = setTimeout(() => {
                button.classList.remove("copied");
                button.title = "Copy translation";
                button.setAttribute("aria-label", "Copy translation");
                feedback.textContent = "";
            }, 1600);
        } catch (error) {
            button.classList.remove("copied");
            button.classList.add("copy-error");
            feedback.classList.add("copy-error");
            button.title = "Copy failed. Check browser clipboard permissions.";
            button.setAttribute("aria-label", button.title);
            feedback.textContent = button.title;
            console.error("Could not copy the translated text.", error);
        }
    };

    return () => {
        button.onclick = null;
        clearTimeout(resetTimer);
    };
}
"""

_COPY_BUTTON = st.components.v2.component(
    "translation_copy_button",
    html=_COPY_BUTTON_HTML,
    css=_COPY_BUTTON_CSS,
    js=_COPY_BUTTON_JS
)

_APP_CSS = """
<style>
    @import url("https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600&display=swap");

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
        background: #ffffff !important;
        color: var(--text);
        font-family: "Georgia", "Times New Roman", serif;
    }

    .stApp {
        background: var(--bg);
    }

    [data-testid="stMainBlockContainer"] {
        width: min(920px, calc(100% - 2rem)) !important;
        max-width: 920px !important;
        min-height: 0;
        flex-shrink: 0;
        box-sizing: border-box;
        margin: 4.5rem auto 1rem !important;
        padding: 1rem !important;
        border: 1px solid var(--line);
        border-radius: 22px;
        background: #edf7f1 !important;
        box-shadow: 0 16px 42px var(--shadow);
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
        font-size: 3rem;
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
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        min-height: 68px;
        box-sizing: border-box;
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        z-index: 1000001;
        margin: 0;
        padding: 0.25rem 1rem;
        border-bottom: 1px solid #edf0ec;
        background: #f0f2f1;
        font-family: "Segoe UI", sans-serif;
    }

    .translator-logo {
        width: 96px;
        height: 60px;
        overflow: hidden;
    }

    .translator-logo img {
        display: block;
        width: 96px;
        height: 96px;
        transform: translateY(-17px);
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

    [data-testid="stExpander"] > details > summary [data-testid="stMarkdownContainer"],
    [data-testid="stExpander"] > details > summary [data-testid="stMarkdownContainer"] * {
        color: #ffffff !important;
    }

    [data-testid="stExpander"],
    [data-testid="stExpander"] > details {
        border: none !important;
        box-shadow: none !important;
    }

    .neumorphic-track {
        width: min(82%, 600px);
        height: 34px;
        background: #dde3ec;
        border-radius: 999px;
        box-shadow: inset 2px 2px 5px #c5ccd8, inset -2px -2px 5px #ffffff;
        padding: 3px;
        position: relative;
        display: flex;
        align-items: center;
        margin: 16px auto;
        box-sizing: border-box;
    }

    .neumorphic-fill {
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, #eadcf8 0%, #dcf4f5 50%, #dafae6 100%);
        box-shadow: 0 2px 6px rgba(175, 205, 215, 0.55), inset 0 1px 2px #ffffff;
        transition: width 0.25s ease;
    }

    .neumorphic-text {
        position: absolute;
        left: 16px;
        font-family: "Courier New", Consolas, monospace;
        font-size: 13px;
        font-weight: 600;
        letter-spacing: 0.5px;
        color: #7c8594;
        pointer-events: none;
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

    .st-key-deepl_swap_languages [data-testid="stIconMaterial"] {
        color: #000000 !important;
        opacity: 1 !important;
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
        width: min(95%, 850px);
        margin-inline: auto;
        border: 2px solid var(--line);
        border-radius: 25px;
        background-color: #ffffff !important;
        box-shadow: 0 8px 24px var(--shadow);
        padding: 0.40rem;
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
        min-height: 140px;
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
        display: block !important;
        width: 100%;
        min-width: 0;
        max-width: 100%;
        box-sizing: border-box;
        text-align: center;
        color: var(--muted);
        font-size: 0.75rem;
        line-height: 1.4;
        white-space: normal;
        overflow-wrap: anywhere;
    }

    [data-testid="stFileUploaderDropzoneInstructions"] > div {
        display: block !important;
        width: 100%;
        min-width: 0;
        max-width: 100%;
        white-space: normal;
        overflow-wrap: anywhere;
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

    [data-testid="stAlert"]:has(
        [data-testid="stAlertContentSuccess"]
    ) [data-testid="stAlertContainer"] {
        background-color: #d9f5e1 !important;
        border: 1px solid #c5e8ce !important;
    }

    [data-testid="stAlertContentSuccess"] [data-testid="stMarkdownContainer"],
    [data-testid="stAlertContentSuccess"] [data-testid="stMarkdownContainer"] * {
        color: #203b35 !important;
    }

    [data-testid="stAlertContentSuccess"] [data-testid="stAlertDynamicIcon"] {
        color: #55766b !important;
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
        flex-wrap: wrap;
        justify-content: space-between;
        align-items: center;
        margin: 0.15rem 0 0.7rem;
        gap: 1rem;
    }

    .translation-panel-title {
        margin: 0;
        font-size: 1.6rem;
        line-height: 1.6;
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
        white-space: normal;
    }

    .translation-panel-note::before {
        content: "* ";
        color: var(--text);
    }

    .st-key-translator_feedback_link button {
        padding: 0.1rem 0.2rem;
        border: 0;
        border-radius: 0;
        background: transparent !important;
        box-shadow: none;
        color: var(--muted);
        font-style: italic;
    }

    .st-key-translator_feedback_link button:hover {
        background: transparent;
        color: var(--text);
        text-decoration: underline;
    }

    [role="dialog"] {
        background: #fffaf1 !important;
        border: 1px solid #e6ddd0 !important;
        border-radius: 16px !important;
        box-shadow: 0 20px 56px rgba(32, 59, 53, 0.18) !important;
        color: #203b35 !important;
    }

    [role="dialog"] h1,
    [role="dialog"] h2,
    [role="dialog"] h3,
    [role="dialog"] p,
    [role="dialog"] label {
        color: #203b35;
    }

    [role="dialog"] textarea {
        background: #ffffff !important;
        border: 1px solid #d8d1c5 !important;
        border-radius: 10px !important;
        color: #203b35 !important;
    }

    [role="dialog"] textarea:focus {
        border-color: #55766b !important;
        box-shadow: 0 0 0 1px #55766b !important;
    }

    [role="dialog"] [data-testid="stFileUploaderDropzone"] {
        background: #fffdf9 !important;
        border: 1px dashed #d9cdbb !important;
        border-radius: 12px !important;
    }

    [role="dialog"] [data-testid="stBaseButton-secondaryFormSubmit"] {
        background: #55766b !important;
        border: 1px solid #55766b !important;
        border-radius: 9px !important;
        color: #ffffff !important;
    }

    [role="dialog"] [data-testid="stBaseButton-secondaryFormSubmit"] p {
        color: #ffffff !important;
    }

    [role="dialog"] [data-testid="stBaseButton-secondaryFormSubmit"]:hover {
        background: #45655b !important;
        border-color: #45655b !important;
    }

    [data-testid="stSidebar"] {
        background: #F4F8F6 !important;
        border-right: 1px solid #DCE8E2 !important;
        color: #17352D !important;
    }

    [data-testid="stSidebar"][aria-expanded="true"] {
        flex: 0 0 312px !important;
        width: 312px !important;
        min-width: 312px !important;
    }

    /* Spacer that keeps sidebar content below the fixed site header (68px). */
    [data-testid="stSidebarHeader"] {
        position: static;
        height: 80px;
        min-height: 80px;
        padding: 0 !important;
        background: #F4F8F6;
    }

    /* Collapse button sits on the same row as "+ New translation". */
    [data-testid="stSidebarCollapseButton"] {
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
    }

    [data-testid="stSidebarCollapseButton"] button,
    [data-testid="stExpandSidebarButton"] {
        position: fixed !important;
        top: 96px !important;
        width: 38px !important;
        height: 38px !important;
        min-height: 38px !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center;
        justify-content: center;
        background: #DCE8E2 !important;
        border: 1px solid #AFC7BD !important;
        border-radius: 10px !important;
        color: #17352D !important;
    }

    [data-testid="stSidebarCollapseButton"] button {
        left: 243px !important;
    }

    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarCollapseButton"] {
        display: none !important;
    }

    [data-testid="stExpandSidebarButton"] {
        left: 16px !important;
        z-index: 1000002 !important;
    }

    [data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"] {
        color: #17352D !important;
        font-size: 1.3rem;
    }

    [data-testid="stSidebarCollapseButton"] button:hover {
        background: #2F6B5A !important;
        color: #FFFFFF !important;
    }

    [data-testid="stSidebarCollapseButton"] button:hover [data-testid="stIconMaterial"] {
        color: #FFFFFF !important;
    }

    [data-testid="stSidebar"] .st-key-sidebar_new_translation {
        width: calc(100% - 46px) !important;
    }

    [data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"] {
        color: #17352D !important;
        font-size: 1.3rem;
    }

    [data-testid="stExpandSidebarButton"]:hover {
        background: #2F6B5A !important;
        color: #FFFFFF !important;
    }

    [data-testid="stExpandSidebarButton"]:hover [data-testid="stIconMaterial"] {
        color: #FFFFFF !important;
    }


    [data-testid="stSidebar"] > div,
    [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
        background: #F4F8F6 !important;
    }

    [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
        height: 100vh;
        overflow-y: auto;
        scrollbar-width: thin;
    }

    [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
        padding-bottom: 0.75rem !important;
    }

    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.5rem !important;
    }

    /* Streamlit pulls HTML markdown blocks up with a -1rem bottom margin,
       which makes labels overlap the next element in the sidebar. */
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
        margin-bottom: 0 !important;
    }

    /* Cards keep their natural height instead of being squeezed. */
    [data-testid="stSidebar"] [data-testid="stLayoutWrapper"],
    [data-testid="stSidebar"] [data-testid="stElementContainer"] {
        flex-shrink: 0 !important;
    }

    /* Compact history list: at most ~260px tall, shrinking on short
       windows so the whole sidebar still fits without page scrolling. */
    [data-testid="stSidebar"] [data-testid="stLayoutWrapper"]:has(> .st-key-sidebar_history_list),
    [data-testid="stSidebar"] .st-key-sidebar_history_list {
        flex: 0 0 auto !important;
        height: min(260px, max(150px, calc(100vh - 515px))) !important;
        min-height: 150px !important;
        max-height: none !important;
    }

    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] {
        color: #17352D;
        font-family: "Inter", sans-serif;
    }

    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: #17352D;
        font-family: "Fraunces", Georgia, serif;
    }

    [data-testid="stSidebar"] .sidebar-brand {
        color: #17352D;
        font-family: "Fraunces", Georgia, serif;
        font-size: 1.65rem;
        font-weight: 600;
        line-height: 1.2;
        margin: 0.1rem 0 0.55rem;
    }

    [data-testid="stSidebar"] .sidebar-section-label {
        color: #50645D;
        font-family: "Inter", sans-serif;
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.12em;
        line-height: 1.2;
        margin: 0 0 0.3rem;
        text-transform: uppercase;
    }

    [data-testid="stSidebar"] .sidebar-muted {
        color: #50645D;
        font-family: "Inter", sans-serif;
        font-size: 0.82rem;
        line-height: 1.45;
    }

    [data-testid="stSidebar"] .sidebar-history-group {
        color: #50645D;
        font-family: "Inter", sans-serif;
        font-size: 0.68rem;
        font-weight: 600;
        letter-spacing: 0.04em;
        margin: 0.15rem 0 0.1rem 0.4rem;
    }

    [data-testid="stSidebar"] .st-key-sidebar_history_header {
        gap: 0.25rem !important;
        min-height: 24px;
    }

    [data-testid="stSidebar"] .st-key-sidebar_history_header .sidebar-section-label {
        margin: 0;
    }

    [data-testid="stSidebar"] .st-key-sidebar_history_toggle button {
        min-height: 24px !important;
        width: 26px;
        height: 24px;
        padding: 0 !important;
        border-radius: 6px !important;
        color: #50645D !important;
    }

    [data-testid="stSidebar"] .st-key-sidebar_history_toggle button:hover {
        background: #EEF4F1 !important;
        color: #17352D !important;
    }

    [data-testid="stSidebar"] .st-key-sidebar_history_toggle [data-testid="stIconMaterial"] {
        font-size: 1.2rem;
    }

    [data-testid="stSidebar"] .st-key-sidebar_history_search input {
        background: #FFFFFF !important;
        color: #17352D !important;
        -webkit-text-fill-color: #17352D !important;
        border-radius: 9px !important;
    }

    [data-testid="stSidebar"] .st-key-sidebar_history_search input::placeholder {
        color: #7A8C85 !important;
        -webkit-text-fill-color: #7A8C85 !important;
    }

    [data-testid="stSidebar"] .st-key-sidebar_history_list {
        padding-right: 0.25rem;
        scrollbar-width: thin;
        scrollbar-color: #AFC7BD transparent;
    }

    [data-testid="stSidebar"] .st-key-sidebar_history_list,
    [data-testid="stSidebar"] .st-key-sidebar_history_list [data-testid="stVerticalBlock"] {
        gap: 0 !important;
    }

    [data-testid="stSidebar"] .st-key-sidebar_history_list button {
        justify-content: flex-start !important;
        min-height: 24px !important;
        padding: 0.1rem 0.4rem !important;
        background: transparent !important;
        border: 1px solid transparent !important;
        border-radius: 6px !important;
        box-shadow: none !important;
        transform: none !important;
    }

    [data-testid="stSidebar"] .st-key-sidebar_history_list button:hover {
        background: #EEF4F1 !important;
        border-color: #DCE8E2 !important;
    }

    [data-testid="stSidebar"] .st-key-sidebar_history_list button > div,
    [data-testid="stSidebar"] .st-key-sidebar_history_list button span,
    [data-testid="stSidebar"] .st-key-sidebar_history_list button [data-testid="stMarkdownContainer"] {
        display: block !important;
        width: 100% !important;
        min-width: 0;
        text-align: left !important;
    }

    [data-testid="stSidebar"] .st-key-sidebar_history_list button p {
        color: #17352D !important;
        font-size: 0.78rem !important;
        font-weight: 500 !important;
        line-height: 1.3 !important;
        text-align: left !important;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    [data-testid="stSidebar"] .sidebar-history-meta {
        color: #6B7F78;
        font-family: "Inter", sans-serif;
        font-size: 0.66rem;
        line-height: 1.2;
        margin: 0 0 0.3rem 0.4rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    [data-testid="stSidebar"] .sidebar-history-done {
        color: #2F6B5A;
        font-weight: 600;
    }

    [data-testid="stSidebar"] .sidebar-history-failed {
        color: #B42318;
        font-weight: 600;
    }

    [data-testid="stSidebar"] .sidebar-shield-status {
        color: #50645D;
        font-family: "Inter", sans-serif;
        font-size: 0.82rem;
        font-weight: 600;
        text-align: right;
    }

    [data-testid="stSidebar"] .sidebar-muted {
        font-size: 0.75rem !important;
        line-height: 1.35 !important;
    }

    [data-testid="stSidebar"] [data-testid="stCheckbox"] label[data-selected="true"] > div:first-of-type {
        background: #2F6B5A !important;
    }

    [data-testid="stSidebar"] [data-testid="stProgressBarTrack"] {
        background: #E4EEE9 !important;
    }

    [data-testid="stSidebar"] [data-testid="stProgressBarTrack"] > div {
        background: #2F6B5A !important;
    }

    [data-testid="stSidebar"] .st-key-sidebar_history_card,
    [data-testid="stSidebar"] .st-key-sidebar_data_shield_card,
    [data-testid="stSidebar"] .st-key-sidebar_usage {
        background: #FFFFFF;
        border: 1px solid #CFDDD6 !important;
        border-radius: 13px;
        padding: 0.6rem 0.7rem !important;
        gap: 0.35rem !important;
    }

    [data-testid="stSidebar"] .st-key-sidebar_usage [data-testid="stProgress"] {
        margin: 0.15rem 0;
    }

    /* Pin the usage card to the bottom of the sidebar. The sidebar column
       is stretched to full height so margin-top:auto pushes the card down
       when content is short; sticky keeps it visible when history is long. */
    [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
        display: flex;
        flex-direction: column;
    }

    [data-testid="stSidebar"] [data-testid="stSidebarUserContent"],
    [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] > div {
        flex: 1 0 auto;
        display: flex;
        flex-direction: column;
    }

    [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlock"] {
        flex: 1 0 auto;
    }

    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] > :has(.st-key-sidebar_usage),
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] > .st-key-sidebar_usage {
        margin-top: auto;
        position: sticky;
        bottom: 0.75rem;
        z-index: 2;
        box-shadow: 0 -6px 12px -8px rgba(23, 53, 45, 0.18);
        border-radius: 13px;
    }

    [data-testid="stSidebar"] button {
        font-family: "Inter", sans-serif;
        min-height: 38px;
    }

    [data-testid="stSidebar"] .st-key-sidebar_history_search input {
        min-height: 36px;
        padding: 0.35rem 0.7rem !important;
        font-size: 0.85rem;
    }

    [data-testid="stSidebar"] button[kind="primary"] {
        background: #2F6B5A !important;
        border-color: #2F6B5A !important;
        color: #FFFFFF !important;
    }

    [data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] p {
        color: #FFFFFF !important;
    }

    [data-testid="stSidebar"] button:focus-visible,
    [data-testid="stSidebar"] input:focus-visible,
    [data-testid="stSidebar"] textarea:focus-visible,
    [data-testid="stSidebar"] [role="switch"]:focus-visible {
        outline: 3px solid #2F6B5A !important;
        outline-offset: 2px !important;
    }

    @media (max-width: 720px) {
        [data-testid="stSidebar"][aria-expanded="true"] {
            width: min(312px, 86vw) !important;
            min-width: min(312px, 86vw) !important;
            flex-basis: min(312px, 86vw) !important;
        }
    }

    </style>
"""
st.markdown(_APP_CSS, unsafe_allow_html=True)
st.markdown(
    f"""
    <header class="translator-site-header">
        <div class="translator-logo">
            <img src="data:image/webp;base64,{LOGO_DATA}" alt="Bajaj Life">
        </div>
        <details class="translator-profile">
            <summary>
                <span class="translator-profile-avatar" aria-hidden="true"></span>
                <span></span>
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
        <!--<p>Translate your documents while keeping the meaning clear and natural.</p>-->
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


@st.dialog("Send feedback")
def feedback_dialog():
    st.markdown("Describe your feedback (required)")
    with st.form("translator_feedback_form"):
        message = st.text_area(
            "Describe your feedback",
            placeholder="Tell us what prompted this feedback...",
            max_chars=1000,
            label_visibility="collapsed",
            key="translator_feedback_message"
        )
        st.caption(
            "Please don't include any sensitive information "
            ":material/help_outline:"
        )
        st.markdown(
            "A screenshot will help us better understand your feedback."
        )
        screenshot = st.file_uploader(
            "Capture screenshot",
            type=["png", "jpg", "jpeg"],
            max_upload_size=5,
            label_visibility="collapsed",
            key="translator_feedback_screenshot"
        )
        with st.container(horizontal_alignment="right"):
            submitted = st.form_submit_button(
                "Send feedback",
                type="secondary"
            )

    if submitted:
        if not message.strip():
            st.warning("Enter feedback before sending.")
            return

        try:
            request_data = {"message": message}
            request_files = None
            if screenshot is not None:
                request_files = {
                    "screenshot": (
                        screenshot.name,
                        screenshot.getvalue(),
                        screenshot.type
                    )
                }
            response = requests.post(
                FEEDBACK_API_URL,
                data=request_data,
                files=request_files,
                timeout=8
            )
            response.raise_for_status()
        except requests.RequestException as error:
            st.error(f"Could not send feedback: {error}")
        else:
            st.toast("Feedback sent.")
            st.rerun()


def render_feedback_footer():
    with st.container(horizontal_alignment="center"):
        if st.button(
            "Send feedback",
            key="translator_feedback_link",
            type="tertiary"
        ):
            feedback_dialog()


@st.cache_data(ttl=60, show_spinner=False)
def _parse_usage(payload: object) -> dict[str, int]:
    if not isinstance(payload, dict):
        raise ValueError("The usage endpoint returned an unexpected response.")

    character_count = payload.get("character_count")
    character_limit = payload.get("character_limit")
    if type(character_count) is not int or type(character_limit) is not int:
        raise ValueError("The usage endpoint returned invalid character counts.")
    return {
        "character_count": character_count,
        "character_limit": character_limit
    }


def get_backend_usage(api_base: str) -> dict[str, int]:
    response = requests.get(f"{api_base}/usage", timeout=5)
    response.raise_for_status()
    return _parse_usage(response.json())


def get_deepl_usage(api_base: str, api_key: str) -> dict[str, int]:
    # TEMPORARY: asks DeepL directly when the backend /usage route is down.
    # Remove once the backend is always available.
    response = requests.get(
        f"{api_base}/v2/usage",
        headers={"Authorization": f"DeepL-Auth-Key {api_key}"},
        timeout=5,
    )
    raise_for_deepl_error(response)
    return _parse_usage(response.json())


def load_usage() -> dict[str, int] | None:
    try:
        return get_backend_usage(BACKEND_API_URL)
    except (requests.RequestException, ValueError) as error:
        LOGGER.warning("Backend usage is unavailable: %s", error)
    try:
        return get_deepl_usage(api_base, api_key)
    except (requests.RequestException, RuntimeError, ValueError) as error:
        LOGGER.warning("DeepL usage is unavailable: %s", error)
    return None


def format_usage_count(count: int) -> str:
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M".replace(".0M", "M")
    if count >= 1_000:
        return f"{count / 1_000:.0f}K"
    return f"{count:,}"


def record_translation(**details) -> None:
    try:
        sidebar_store.add_translation(
            user=sidebar_store.DEFAULT_USER,
            **details
        )
    except (OSError, sqlite3.Error):
        LOGGER.exception("Could not save translation history.")
        st.warning("The translation completed, but could not be saved to history.")


def start_new_translation() -> None:
    st.session_state["deepl_file_uploader_generation"] += 1
    st.session_state["deepl_source_text"] = ""
    st.session_state["deepl_text_result_display"] = ""
    for key in (
        "deepl_text_result",
        "deepl_document_file_result",
        "sidebar_opened_history_id",
    ):
        st.session_state.pop(key, None)
    st.session_state["deepl_translation_tabs"] = "↑  Upload document"


def toggle_history_collapsed() -> None:
    st.session_state["sidebar_history_collapsed"] = (
        not st.session_state["sidebar_history_collapsed"]
    )


def reopen_history_translation(
    translation_id: str,
    source_options: dict[str, str],
    target_options: dict[str, str],
) -> None:
    row = sidebar_store.get_translation(sidebar_store.DEFAULT_USER, translation_id)
    if row is None:
        st.session_state.pop("sidebar_opened_history_id", None)
        return

    st.session_state["sidebar_opened_history_id"] = translation_id
    st.session_state["deepl_file_uploader_generation"] += 1
    st.session_state.pop("deepl_document_file_result", None)
    st.session_state["deepl_translation_tabs"] = (
        "≡  Paste text" if row["kind"] == "text" else "↑  Upload document"
    )
    source_name = str(row["source_language"])
    target_name = str(row["target_language"])
    if source_name in source_options or source_name == "Detect automatically":
        st.session_state["deepl_source_language"] = source_name
    if target_name in target_options:
        st.session_state["deepl_target_language"] = target_name

    if row["kind"] == "text":
        source_text = str(row.get("source_text") or "")
        st.session_state["deepl_source_text"] = source_text
        if row["status"] == "Done" and row.get("result_text"):
            source_code = source_options.get(source_name, "AUTO")
            target_code = target_options.get(target_name)
            if target_code:
                st.session_state["deepl_text_result"] = {
                    "text": row["result_text"],
                    "signature": (source_text, target_code, source_code)
                }
        else:
            st.session_state.pop("deepl_text_result", None)
    else:
        st.session_state.pop("deepl_text_result", None)
        st.session_state["deepl_source_text"] = ""


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


def translate_text(
    api_base,
    api_key,
    text,
    target_lang,
    source_lang,
    protect_placeholders=False,
):
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
    if protect_placeholders:
        # Data shield placeholders are <x i="N"/> tags. XML tag handling makes
        # DeepL keep them intact; ignore_tags stops it touching them at all.
        data["tag_handling"] = "xml"
        data["ignore_tags"] = [data_shield.PLACEHOLDER_TAG]
        data["split_sentences"] = "1"

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


def update_progress_bar(placeholder, percent, label="PROGRESS"):
    percent = max(0, min(100, int(percent)))
    placeholder.markdown(
        f"""
        <div
            class="neumorphic-track"
            role="progressbar"
            aria-valuemin="0"
            aria-valuemax="100"
            aria-valuenow="{percent}"
            aria-label="{label}: {percent}%"
        >
            <div class="neumorphic-fill" style="width: {percent}%;"></div>
            <div class="neumorphic-text">{label}: {percent}%</div>
        </div>
        """,
        unsafe_allow_html=True
    )


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
        progress_started_at = time.monotonic()
        progress_percent = 0
        progress_placeholder = st.empty()
        update_progress_bar(progress_placeholder, progress_percent)
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
                update_progress_bar(progress_placeholder, 100, "COMPLETE")
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
            elapsed = time.monotonic() - progress_started_at
            if remaining is not None:
                remaining = max(float(remaining), 0)
                estimated_percent = int(
                    100 * elapsed / max(elapsed + remaining, 1)
                )
            else:
                estimated_percent = int(
                    100 * elapsed / 600
                )
            progress_percent = max(
                progress_percent,
                min(estimated_percent, 99)
            )
            update_progress_bar(progress_placeholder, progress_percent)
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


def get_masked_document(file_name, file_content, content_hash):
    """Mask an upload once per file and keep the result for later reruns.

    Returns (masked_document, None) or (None, reason the file is refused).
    """
    cache = st.session_state.setdefault("document_shield_cache", {})
    key = (file_name, content_hash)
    if key not in cache:
        try:
            cache.clear()
            cache[key] = (
                document_shield.mask_document(file_name, file_content),
                None,
            )
        except (
            document_shield.DocumentShieldUnsupported,
            data_shield.DataShieldError,
        ) as error:
            cache[key] = (None, str(error))
    return cache[key]


def render_file_translation(
    uploaded_file,
    file_kind,
    state_key,
    api_base,
    api_key,
    target_code,
    target_name,
    source_code,
    source_name,
):
    if uploaded_file is None:
        st.session_state.pop(state_key, None)
        return

    file_content = uploaded_file.getvalue()
    content_hash = hashlib.sha256(file_content).hexdigest()
    shield_enabled = st.session_state["data_shield_enabled"]
    signature = (
        uploaded_file.name,
        content_hash,
        target_code,
        source_code,
        DOCUMENT_OUTPUT_FORMAT,
        shield_enabled,
    )
    saved_result = st.session_state.get(state_key)
    if saved_result and saved_result["signature"] != signature:
        st.session_state.pop(state_key, None)

    st.success("✅File uploaded.")
    st.caption(
        f"Selected: **{uploaded_file.name}** · "
        f"{uploaded_file.size / (1024 * 1024):.2f} MB"
    )

    masked_document = None
    if shield_enabled:
        masked_document, refusal = get_masked_document(
            uploaded_file.name,
            file_content,
            content_hash,
        )
        if refusal:
            st.warning(
                f":material/shield: {refusal} To send this file to DeepL "
                "unmasked, turn off Data shield in the sidebar."
            )
        elif masked_document.shield.is_masked:
            st.caption(
                ":material/shield: Data shield will hide "
                f"{data_shield.summary(masked_document.shield)} "
                "from DeepL."
            )
        else:
            st.caption(
                ":material/shield: Data shield found no personal details "
                "in this file."
            )
        if masked_document is not None:
            for warning in masked_document.warnings:
                st.caption(f":material/warning: {warning}")

    if st.button(
        f"Translate {file_kind}",
        type="primary",
        icon=":material/translate:",
        disabled=shield_enabled and masked_document is None,
        key=f"{state_key}_translate"
    ):
        st.session_state.pop("sidebar_opened_history_id", None)
        try:
            with st.spinner(
                f"Translating {file_kind.lower()} into {target_name}..."
            ):
                translated_file = translate_document(
                    api_base,
                    api_key,
                    uploaded_file.name,
                    (
                        masked_document.content
                        if masked_document is not None
                        else file_content
                    ),
                    uploaded_file.type,
                    target_code,
                    source_code,
                    output_format=DOCUMENT_OUTPUT_FORMAT
                )
                if masked_document is not None:
                    translated_file = document_shield.restore_document(
                        translated_file,
                        masked_document.shield,
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
            record_translation(
                file_name=uploaded_file.name,
                source_language=source_name,
                target_language=target_name,
                status="Done",
                kind="document",
                result_data=translated_file,
                result_file_name=translated_name,
            )
        except (
            requests.RequestException,
            RuntimeError,
            TimeoutError,
            ValueError,
            data_shield.DataShieldError,
        ) as error:
            st.error(f"{file_kind} translation failed: {error}")
            record_translation(
                file_name=uploaded_file.name,
                source_language=source_name,
                target_language=target_name,
                status="Failed",
                kind="document",
                error_message=str(error),
            )

    saved_result = st.session_state.get(state_key)
    if saved_result and saved_result["signature"] == signature:
        st.success(f"Translation completed. Translated into {target_name}.")
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
    render_feedback_footer()
    st.stop()

api_base = get_api_base(api_key)
try:
    target_languages = get_languages(api_base, api_key, "translate_text")
except (requests.RequestException, RuntimeError, ValueError) as error:
    st.error(f"Could not load supported languages from DeepL: {error}")
    render_feedback_footer()
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
    render_feedback_footer()
    st.stop()


def _sidebar_label(text: str) -> None:
    st.markdown(
        f'<div class="sidebar-section-label">{text}</div>',
        unsafe_allow_html=True,
    )


def _history_group_name(created_at: datetime, today) -> str:
    if created_at.date() == today:
        return "Today"
    if (today - created_at.date()).days == 1:
        return "Yesterday"
    return created_at.strftime("%B %d, %Y")


def _render_history_list(
    source_language_options: dict[str, str],
    target_language_options: dict[str, str],
) -> None:
    search = st.text_input(
        "Search history",
        placeholder="Search file or language",
        label_visibility="collapsed",
        key="sidebar_history_search",
    )
    rows = sidebar_store.list_translations(
        sidebar_store.DEFAULT_USER,
        search=search,
        limit=100,
    )
    history_list = st.container(
        height=300,
        border=False,
        key="sidebar_history_list",
    )
    if not rows:
        history_list.caption("No translations found.")

    today = datetime.now().astimezone().date()
    current_group = None
    for row in rows:
        created_at = datetime.fromisoformat(str(row["created_at"]))
        group = _history_group_name(created_at, today)
        if group != current_group:
            current_group = group
            history_list.markdown(
                f'<div class="sidebar-history-group">{group}</div>',
                unsafe_allow_html=True,
            )

        source_text = str(row.get("source_text") or "")
        title = str(row["file_name"])
        if row["kind"] == "text" and source_text:
            title = "Pasted text · " + " ".join(source_text.split()[:6])
        if len(title) > 34:
            title = f"{title[:32]}…"

        if history_list.button(
            title,
            key=f"sidebar_history_{row['id']}",
            width="stretch",
        ):
            reopen_history_translation(
                str(row["id"]),
                source_language_options,
                target_language_options,
            )
            st.rerun()

        status = str(row["status"])
        status_class = "failed" if status == "Failed" else "done"
        display_time = created_at.strftime("%I:%M %p").lstrip("0")
        history_list.markdown(
            '<div class="sidebar-history-meta">'
            f'{html.escape(str(row["source_language"]))} → '
            f'{html.escape(str(row["target_language"]))}'
            f' · {display_time} · '
            f'<span class="sidebar-history-{status_class}">'
            f'{html.escape(status)}</span></div>',
            unsafe_allow_html=True,
        )


def render_sidebar(
    source_language_options: dict[str, str],
    target_language_options: dict[str, str],
) -> None:
    with st.sidebar:
        st.button(
            "+ New translation",
            type="primary",
            key="sidebar_new_translation",
            on_click=start_new_translation,
            width="stretch",
        )

        with st.container(border=True, key="sidebar_history_card"):
            collapsed = st.session_state["sidebar_history_collapsed"]
            with st.container(
                horizontal=True,
                horizontal_alignment="distribute",
                vertical_alignment="center",
                key="sidebar_history_header",
            ):
                _sidebar_label("History")
                st.button(
                    "",
                    icon=(
                        ":material/expand_more:"
                        if collapsed
                        else ":material/expand_less:"
                    ),
                    type="tertiary",
                    key="sidebar_history_toggle",
                    on_click=toggle_history_collapsed,
                )
            if not collapsed:
                _render_history_list(
                    source_language_options,
                    target_language_options,
                )

        with st.container(border=True, key="sidebar_data_shield_card"):
            st.toggle(
                "Data shield",
                key="data_shield_enabled",
            )
            st.markdown(
                '<div class="sidebar-muted">Hides phone, email, PAN, Aadhaar '
                'and policy numbers from DeepL in pasted text and in PDF, '
                'Word, PowerPoint and text files. Images and scanned pages '
                'are blocked while it is on.</div>',
                unsafe_allow_html=True,
            )

        with st.container(border=True, key="sidebar_usage"):
            _sidebar_label("DeepL usage")
            usage = load_usage()
            if usage is None:
                st.markdown(
                    '<div class="sidebar-muted">Usage unavailable</div>',
                    unsafe_allow_html=True,
                )
            else:
                count = usage["character_count"]
                limit = usage["character_limit"]
                percent = min(100, round(count * 100 / limit)) if limit else 0
                st.progress(percent / 100)
                st.markdown(
                    f'<div class="sidebar-muted">'
                    f'{format_usage_count(count)} of '
                    f'{format_usage_count(limit)} used ({percent}%)</div>',
                    unsafe_allow_html=True,
                )


render_sidebar(source_options, target_options)


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
            "Choose Your Language",
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
opened_history_id = st.session_state.get("sidebar_opened_history_id")
opened_history = (
    sidebar_store.get_translation(
        sidebar_store.DEFAULT_USER,
        opened_history_id,
    )
    if opened_history_id
    else None
)
if opened_history and (
    opened_history["kind"] == "document"
    or opened_history["status"] == "Failed"
):
    with st.container(border=True):
        st.subheader(str(opened_history["file_name"]))
        st.caption(
            f"{opened_history['source_language']} → "
            f"{opened_history['target_language']} · "
            f"{opened_history['status']}"
        )
        if opened_history["status"] == "Failed":
            st.error(
                str(opened_history.get("error_message")
                    or "This translation failed.")
            )
        elif opened_history["kind"] == "document":
            try:
                result_data = sidebar_store.read_result_file(
                    str(opened_history["result_path"])
                )
            except (OSError, ValueError) as error:
                LOGGER.exception("Could not reopen a document result.")
                st.error(f"Stored translation unavailable: {error}")
            else:
                st.download_button(
                    "Download translated document",
                    data=result_data,
                    file_name=str(opened_history["result_file_name"]),
                    mime="application/pdf",
                    type="primary",
                    icon=":material/download:",
                    key=f"sidebar_history_download_{opened_history_id}",
                )

with st.container(horizontal=True, horizontal_alignment="left"):
    st.badge(
        f"{len(target_options)} target languages",
        icon=":material/language:",
        color="green"
    )
    st.badge("Text, PDF & documents", icon=":material/folder_open:")

upload_tab, text_tab = st.tabs(
    ["↑  Upload document", "≡  Paste text"],
    default="↑  Upload document",
    key="deepl_translation_tabs",
    on_change="rerun",
)

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
                st.session_state.pop("sidebar_opened_history_id", None)
                shield = (
                    data_shield.mask(source_text)
                    if st.session_state["data_shield_enabled"]
                    else data_shield.ShieldResult(text=source_text)
                )
                try:
                    with st.spinner(f"Translating into {target_name}..."):
                        translated_text = translate_text(
                            api_base,
                            api_key,
                            shield.text,
                            target_code,
                            source_code,
                            protect_placeholders=shield.is_masked,
                        )
                    translated_text = data_shield.restore(
                        translated_text,
                        shield,
                    )
                    st.session_state["deepl_text_result"] = {
                        "text": translated_text,
                        "signature": (source_text, target_code, source_code),
                        "shield_summary": data_shield.summary(shield),
                    }
                    text_excerpt = " ".join(source_text.split()[:6])
                    record_translation(
                        file_name=f"Pasted text: {text_excerpt}",
                        source_language=source_name,
                        target_language=target_name,
                        status="Done",
                        kind="text",
                        source_text=source_text,
                        result_text=translated_text,
                    )
                except (
                    requests.RequestException,
                    RuntimeError,
                    ValueError,
                    data_shield.DataShieldError,
                ) as error:
                    st.error(f"Text translation failed: {error}")
                    text_excerpt = " ".join(source_text.split()[:6])
                    record_translation(
                        file_name=f"Pasted text: {text_excerpt}",
                        source_language=source_name,
                        target_language=target_name,
                        status="Failed",
                        kind="text",
                        source_text=source_text,
                        error_message=str(error),
                    )

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
            if translated_text:
                st.success("Translation completed.")
                if result.get("shield_summary"):
                    st.caption(
                        ":material/shield: Data shield kept "
                        f"{result['shield_summary']} away from DeepL."
                    )
            st.session_state["deepl_text_result_display"] = translated_text
            st.text_area(
                "Translation",
                height=130,
                key="deepl_text_result_display",
                disabled=True,
                placeholder="Your translation will appear here."
            )
            _COPY_BUTTON(
                key="deepl_translation_copy",
                data={"text": translated_text},
                width="stretch",
                height=52
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
            key=(
                "deepl_document_file_"
                f"{st.session_state['deepl_file_uploader_generation']}"
            )
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
            source_code,
            source_name,
        )

render_feedback_footer()
