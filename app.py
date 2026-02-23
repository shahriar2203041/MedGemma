"""
MedEcho: AI Radiology & Clinical Scribe
=========================================
Streamlit application entry point.

Run with:
    streamlit run app.py
"""

import io
import json
import logging
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import streamlit as st

# ── Page configuration (must be first Streamlit call) ─────────────────────────
st.set_page_config(
    page_title="MedEcho – AI Clinical Scribe",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("medecho.app")

# ── Custom CSS ─────────────────────────────────────────────────────────────────
CUSTOM_CSS = """
<style>
/* ---- Global ---- */
:root {
    --med-navy:    #0D1B2A;
    --med-blue:    #1B4F72;
    --med-teal:    #1ABC9C;
    --med-teal2:   #17A589;
    --med-white:   #F0F4F8;
    --med-gray:    #BDC3C7;
    --med-danger:  #E74C3C;
    --med-warn:    #F39C12;
    --med-success: #27AE60;
    --card-bg:     #152536;
    --border:      #1F3A52;
}

body, .stApp {
    background-color: var(--med-navy);
    color: var(--med-white);
    font-family: 'Inter', 'Segoe UI', sans-serif;
}

/* ---- Sidebar ---- */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0a1628 0%, #0D1B2A 100%);
    border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] * {
    color: var(--med-white) !important;
}

/* ---- Header / Logo ---- */
.medecho-header {
    background: linear-gradient(135deg, #0D1B2A 0%, #1B4F72 60%, #1ABC9C 100%);
    border-radius: 16px;
    padding: 24px 32px;
    margin-bottom: 24px;
    border: 1px solid var(--border);
    box-shadow: 0 8px 32px rgba(26,188,156,0.15);
}
.medecho-title {
    font-size: 2.4rem;
    font-weight: 800;
    letter-spacing: -0.5px;
    color: #ffffff;
    margin: 0;
}
.medecho-subtitle {
    font-size: 1rem;
    color: var(--med-teal);
    margin-top: 4px;
    letter-spacing: 0.5px;
}
.medecho-badge {
    display: inline-block;
    background: rgba(26,188,156,0.2);
    border: 1px solid var(--med-teal);
    border-radius: 20px;
    padding: 2px 12px;
    font-size: 0.75rem;
    color: var(--med-teal);
    margin-right: 8px;
    margin-top: 8px;
}

/* ---- Cards ---- */
.med-card {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
}
.med-card-title {
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--med-teal);
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* ---- Status indicators ---- */
.status-online  { color: var(--med-success); font-weight: 600; }
.status-offline { color: var(--med-danger);  font-weight: 600; }
.status-warn    { color: var(--med-warn);    font-weight: 600; }

/* ---- Metric tiles ---- */
.metric-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
.metric-tile {
    flex: 1; min-width: 120px;
    background: rgba(26,188,156,0.08);
    border: 1px solid rgba(26,188,156,0.25);
    border-radius: 10px;
    padding: 14px;
    text-align: center;
}
.metric-tile .val { font-size: 1.8rem; font-weight: 800; color: var(--med-teal); }
.metric-tile .lbl { font-size: 0.75rem; color: var(--med-gray); margin-top: 2px; }

/* ---- Score bars ---- */
.score-bar-wrap { margin-bottom: 8px; }
.score-label    { font-size: 0.85rem; color: var(--med-white); display: flex; justify-content: space-between; }
.score-bar-bg   { background: var(--border); border-radius: 4px; height: 8px; margin-top: 4px; }
.score-bar-fill { height: 8px; border-radius: 4px; background: linear-gradient(90deg, #1ABC9C, #2ECC71); }

/* ---- Redaction pills ---- */
.redact-pill {
    display: inline-block;
    background: rgba(231,76,60,0.2);
    border: 1px solid var(--med-danger);
    border-radius: 12px;
    padding: 2px 10px;
    font-size: 0.75rem;
    color: var(--med-danger);
    margin: 2px;
}

/* ---- Tabs ---- */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: var(--card-bg);
    border-radius: 10px;
    padding: 4px;
    gap: 2px;
    border: 1px solid var(--border);
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    color: var(--med-gray) !important;
    border-radius: 8px;
    padding: 8px 20px;
}
[data-testid="stTabs"] [aria-selected="true"] {
    background: var(--med-teal) !important;
    color: white !important;
}

/* ---- Buttons ---- */
.stButton > button {
    background: linear-gradient(135deg, var(--med-teal), var(--med-teal2));
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    padding: 8px 20px;
    transition: all 0.2s;
}
.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 15px rgba(26,188,156,0.4);
}

/* ---- Text areas / inputs ---- */
.stTextArea textarea, .stTextInput input {
    background: var(--card-bg) !important;
    color: var(--med-white) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
}
.stSelectbox select, div[data-baseweb="select"] {
    background: var(--card-bg) !important;
    color: var(--med-white) !important;
}

/* ---- VAD pulse animation ---- */
@keyframes vad-pulse {
    0%   { box-shadow: 0 0 0 0 rgba(26,188,156, 0.7); }
    70%  { box-shadow: 0 0 0 10px rgba(26,188,156, 0); }
    100% { box-shadow: 0 0 0 0 rgba(26,188,156, 0); }
}
.vad-active {
    display: inline-block;
    width: 12px; height: 12px;
    background: var(--med-teal);
    border-radius: 50%;
    animation: vad-pulse 1.5s infinite;
}

/* ---- Diff Dx confidence badges ---- */
.badge-high   { background: rgba(39,174,96,0.2);  color: #2ECC71; border: 1px solid #27AE60; }
.badge-medium { background: rgba(243,156,18,0.2); color: #F39C12; border: 1px solid #D68910; }
.badge-low    { background: rgba(231,76,60,0.2);  color: #E74C3C; border: 1px solid #C0392B; }
.badge-conf {
    display: inline-block;
    border-radius: 20px;
    padding: 1px 10px;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
}

/* ---- QR box ---- */
.qr-container {
    background: white;
    border-radius: 12px;
    padding: 16px;
    display: inline-block;
    box-shadow: 0 4px 24px rgba(0,0,0,0.3);
}

/* ---- Scrollable transcript ---- */
.transcript-box {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
    min-height: 120px;
    max-height: 280px;
    overflow-y: auto;
    font-size: 0.95rem;
    line-height: 1.7;
    white-space: pre-wrap;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ── Session state initialisation ───────────────────────────────────────────────

def _init_state() -> None:
    defaults = {
        "encounter_id": str(uuid.uuid4())[:8].upper(),
        "transcript": "",
        "redacted_transcript": "",
        "pii_labels": [],
        "structured_data": {},
        "diff_dx": {},
        "image_analysis": {},
        "siglip_scores": [],
        "encounter_data": {},
        "qr_bytes": b"",
        "export_bytes": b"",
        "export_key": "",
        "ehr_summary": "",
        "offline_mode": False,
        "connectivity_checked": False,
        "audio_bytes": b"",
        "recording": False,
        "model_loaded": False,
        "prior_report": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ── Connectivity check ─────────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def _check_connectivity() -> bool:
    from medecho.offline import is_online
    return is_online()


# ── Lazy-loaded modules ────────────────────────────────────────────────────────

@st.cache_resource(show_spinner="Initialising PII redactor…")
def get_redactor():
    from medecho.voice import redact_pii
    return redact_pii

@st.cache_resource(show_spinner="Setting up clinical engine…")
def get_clinical_engine(gemini_key: str, model_size: str):
    from medecho.clinical import ClinicalEngine, MedGemmaTextClient
    llm = MedGemmaTextClient(
        model_size=model_size,
        gemini_api_key=gemini_key or None,
    )
    return ClinicalEngine(llm=llm)

@st.cache_resource(show_spinner="Setting up image analyser…")
def get_image_analyzer(hf_token: str, gemini_key: str):
    # Returns (MedGemmaImageAnalyzer, MedSigLIPAnalyzer)
    from medecho.imaging import MedGemmaImageAnalyzer, MedSigLIPAnalyzer
    return (
        MedGemmaImageAnalyzer(hf_token=hf_token or None),
        MedSigLIPAnalyzer(),
    )

@st.cache_resource(show_spinner="Setting up output modules…")
def get_exporters():
    from medecho.output import EncryptedJSONExporter, QRCodeGenerator
    exp = EncryptedJSONExporter()
    qr = QRCodeGenerator()
    return exp, qr


# ── Sidebar ────────────────────────────────────────────────────────────────────

def render_sidebar() -> Dict:
    """Render sidebar and return configuration dict."""
    with st.sidebar:
        st.markdown(
            """
            <div style='text-align:center; padding: 12px 0 20px 0;'>
              <span style='font-size:2.5rem'>🩺</span><br>
              <strong style='font-size:1.2rem; color:#1ABC9C;'>MedEcho</strong><br>
              <span style='font-size:0.75rem; color:#BDC3C7;'>AI Clinical Scribe v1.0</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Connectivity status
        online = _check_connectivity()
        st.session_state.offline_mode = not online
        icon = "🟢" if online else "🔴"
        status = "Online" if online else "Offline Mode"
        css = "status-online" if online else "status-offline"
        st.markdown(f"<p class='{css}'>{icon} {status}</p>", unsafe_allow_html=True)

        st.divider()

        # ── API Keys ────────────────────────────────────────────────
        st.subheader("🔑 API Configuration")
        gemini_key = st.text_input(
            "Gemini API Key",
            type="password",
            value=os.environ.get("GEMINI_API_KEY", ""),
            help="Required for cloud inference. Get yours at aistudio.google.com",
        )
        hf_token = st.text_input(
            "HuggingFace Token",
            type="password",
            value=os.environ.get("HF_TOKEN", ""),
            help="Required to download MedGemma / MedSigLIP weights.",
        )
        medasr_key = st.text_input(
            "MedASR / Google Cloud Key",
            type="password",
            value=os.environ.get("GOOGLE_CLOUD_API_KEY", ""),
            help="For MedASR medical transcription (optional – falls back to Whisper).",
        )

        st.divider()

        # ── Model Selection ─────────────────────────────────────────
        st.subheader("🤖 Model Settings")
        _LLM_OPTIONS = ["MedGemma 4B (local)", "MedGemma 27B (local)", "Gemini 2.0 Flash (cloud)"]
        _LLM_DEFAULT = "Gemini 2.0 Flash (cloud)"
        llm_choice = st.selectbox(
            "Clinical Reasoning Model",
            _LLM_OPTIONS,
            index=_LLM_OPTIONS.index(_LLM_DEFAULT),
            help="Select the LLM for differential diagnosis and structured extraction.",
        )
        model_size = "4b" if "4B" in llm_choice else "27b"

        _IMG_OPTIONS = ["MedGemma 4B (local)", "Gemini Vision (cloud)"]
        _IMG_DEFAULT = "Gemini Vision (cloud)"
        img_backend = st.selectbox(
            "Image Analysis Backend",
            _IMG_OPTIONS,
            index=_IMG_OPTIONS.index(_IMG_DEFAULT),
        )
        use_siglip = st.toggle("Enable MedSigLIP Zero-Shot", value=True)
        use_vad = st.toggle("Enable VAD (Voice Activity Detection)", value=True)

        st.divider()

        # ── Patient Info ────────────────────────────────────────────
        st.subheader("👤 Patient & Encounter")
        patient_name = st.text_input("Patient Name", placeholder="(will be redacted in output)")
        physician = st.text_input("Attending Physician", placeholder="Dr. Smith")
        encounter_date = st.date_input("Encounter Date", value=datetime.today())

        st.divider()

        # ── Security ────────────────────────────────────────────────
        st.subheader("🔒 Security")
        encrypt_output = st.toggle("Encrypt Export", value=True)
        generate_qr = st.toggle("Generate QR Code", value=True)

        # ── Encounter ID ────────────────────────────────────────────
        st.markdown(
            f"<p style='font-size:0.8rem; color:#BDC3C7;'>Encounter ID: "
            f"<code style='color:#1ABC9C;'>{st.session_state.encounter_id}</code></p>",
            unsafe_allow_html=True,
        )

        if st.button("🔄 New Encounter"):
            # Reset encounter-specific state
            for k in [
                "transcript", "redacted_transcript", "pii_labels", "structured_data",
                "diff_dx", "image_analysis", "siglip_scores", "encounter_data",
                "qr_bytes", "export_bytes", "export_key", "audio_bytes",
            ]:
                st.session_state[k] = type(st.session_state[k])()
            st.session_state.encounter_id = str(uuid.uuid4())[:8].upper()
            st.rerun()

    return {
        "gemini_key": gemini_key,
        "hf_token": hf_token,
        "medasr_key": medasr_key,
        "model_size": model_size,
        "llm_choice": llm_choice,
        "img_backend": img_backend,
        "use_siglip": use_siglip,
        "use_vad": use_vad,
        "patient_name": patient_name,
        "physician": physician,
        "encounter_date": str(encounter_date),
        "encrypt_output": encrypt_output,
        "generate_qr": generate_qr,
    }


# ── Header ─────────────────────────────────────────────────────────────────────

def render_header(cfg: Dict) -> None:
    online_badge = (
        '<span class="medecho-badge">🟢 Online</span>'
        if not st.session_state.offline_mode
        else '<span class="medecho-badge" style="border-color:#E74C3C;color:#E74C3C;">🔴 Offline</span>'
    )
    st.markdown(
        f"""
        <div class="medecho-header">
          <h1 class="medecho-title">🩺 MedEcho</h1>
          <p class="medecho-subtitle">AI Radiology &amp; Clinical Scribe — Powered by HAI-DEF Suite</p>
          <div>
            <span class="medecho-badge">MedGemma 4B</span>
            <span class="medecho-badge">MedSigLIP</span>
            <span class="medecho-badge">MedASR</span>
            <span class="medecho-badge">VAD</span>
            {online_badge}
            <span class="medecho-badge">EID: {st.session_state.encounter_id}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Tab 1: Voice Interface ─────────────────────────────────────────────────────

def render_voice_tab(cfg: Dict) -> None:
    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown('<div class="med-card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="med-card-title">🎙️ Voice Capture</div>', unsafe_allow_html=True
        )

        # VAD status
        vad_html = (
            '<span class="vad-active"></span> <span style="color:#1ABC9C; font-size:0.85rem;">VAD Active</span>'
            if cfg["use_vad"]
            else '<span style="color:#BDC3C7; font-size:0.85rem;">VAD Disabled</span>'
        )
        st.markdown(vad_html, unsafe_allow_html=True)

        # File upload (browser microphone not available in base Streamlit)
        audio_file = st.file_uploader(
            "Upload audio recording (WAV / MP3 / M4A)",
            type=["wav", "mp3", "m4a", "ogg", "flac"],
            help="Record your clinical encounter and upload here. "
                 "In a deployed app this connects to the live microphone via WebRTC.",
        )

        if audio_file:
            st.audio(audio_file)
            st.session_state.audio_bytes = audio_file.read()

        # Or type/paste transcript directly
        st.markdown("**— or —**")
        manual_text = st.text_area(
            "Paste / type encounter transcript",
            height=160,
            placeholder=(
                "Patient presents with persistent cough for 3 weeks, "
                "fever 38.5°C, shortness of breath on exertion. "
                "BP 130/85, HR 92. History of type 2 diabetes. "
                "Chest X-ray shows right lower lobe infiltrate…"
            ),
        )

        transcribe_btn = st.button("🔬 Transcribe & Analyse", use_container_width=True)

        if transcribe_btn:
            text_to_process = manual_text.strip()

            if not text_to_process and st.session_state.audio_bytes:
                with st.spinner("Transcribing audio with MedASR…"):
                    from medecho.voice import MedASRClient, VoiceActivityDetector, pcm_frames

                    vad = VoiceActivityDetector() if cfg["use_vad"] else None
                    asr = MedASRClient(
                        api_key=cfg["medasr_key"] or None,
                        use_local_fallback=True,
                    )

                    audio_data = st.session_state.audio_bytes
                    if vad and vad.available:
                        audio_data = vad.filter_speech(audio_data)

                    result = asr.transcribe(audio_data)
                    text_to_process = result["text"]
                    st.info(
                        f"Transcription source: **{result['source']}** | "
                        f"Confidence: **{result['confidence']:.0%}**"
                    )

            if text_to_process:
                # PII redaction
                redact_fn = get_redactor()
                redacted, labels = redact_fn(text_to_process)
                st.session_state.transcript = text_to_process
                st.session_state.redacted_transcript = redacted
                st.session_state.pii_labels = labels
            elif st.session_state.offline_mode:
                st.warning("Offline: Audio saved locally for later processing.")
                if st.session_state.audio_bytes:
                    from medecho.offline import OfflineStore
                    from medecho.voice import bytes_to_wav
                    store = OfflineStore()
                    store.save_audio(
                        bytes_to_wav(st.session_state.audio_bytes),
                        encounter_id=st.session_state.encounter_id,
                    )
            else:
                st.warning("Please provide audio or type a transcript.")

        st.markdown("</div>", unsafe_allow_html=True)

    with col_right:
        st.markdown('<div class="med-card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="med-card-title">📝 Transcript (Privacy-Protected)</div>',
            unsafe_allow_html=True,
        )

        if st.session_state.redacted_transcript:
            st.markdown(
                f'<div class="transcript-box">{st.session_state.redacted_transcript}</div>',
                unsafe_allow_html=True,
            )

            if st.session_state.pii_labels:
                st.markdown("**PII Redacted:**")
                pills = " ".join(
                    f'<span class="redact-pill">{lbl}</span>'
                    for lbl in set(st.session_state.pii_labels)
                )
                st.markdown(pills, unsafe_allow_html=True)
            else:
                st.success("✅ No PII detected")
        else:
            st.markdown(
                '<p style="color:#BDC3C7; font-style:italic;">Transcript will appear here after processing…</p>',
                unsafe_allow_html=True,
            )

        # EHR Context
        st.markdown("---")
        st.markdown(
            '<div class="med-card-title">📋 EHR Context (Optional)</div>',
            unsafe_allow_html=True,
        )
        ehr_input = st.text_area(
            "Paste past patient history / EHR notes",
            height=100,
            placeholder="Include past diagnoses, medications, allergies, surgical history…",
        )
        if ehr_input and st.button("📖 Summarise EHR"):
            with st.spinner("Summarising patient history…"):
                engine = get_clinical_engine(cfg["gemini_key"], cfg["model_size"])
                st.session_state.ehr_summary = engine.summarize_ehr(ehr_input)
            st.success("EHR summarised!")

        if st.session_state.ehr_summary:
            st.markdown(
                f'<div class="transcript-box">{st.session_state.ehr_summary}</div>',
                unsafe_allow_html=True,
            )

        st.markdown("</div>", unsafe_allow_html=True)


# ── Tab 2: Imaging ─────────────────────────────────────────────────────────────

def render_imaging_tab(cfg: Dict) -> None:
    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown('<div class="med-card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="med-card-title">🔬 Image Upload</div>', unsafe_allow_html=True
        )

        modality = st.selectbox(
            "Imaging Modality",
            ["Chest X-Ray", "Pathology Slide", "Dermatology", "CT Slice", "MRI Slice"],
        )

        uploaded_img = st.file_uploader(
            "Upload medical image",
            type=["jpg", "jpeg", "png", "bmp", "tiff", "dcm"],
            help="Supports JPEG, PNG, TIFF, and DICOM images.",
        )

        if uploaded_img:
            try:
                from PIL import Image
                img_bytes = uploaded_img.read()
                pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                st.image(pil_img, caption=f"{modality} — {uploaded_img.name}", use_container_width=True)
            except Exception as e:
                st.error(f"Could not load image: {e}")
                img_bytes = None
                pil_img = None
        else:
            img_bytes = None
            pil_img = None

        # Prior report for comparison
        st.markdown("**Prior Report (for longitudinal comparison)**")
        prior = st.text_area(
            "Paste prior radiology report",
            height=80,
            key="prior_report_input",
            placeholder="Previous findings for comparison…",
        )
        st.session_state.prior_report = prior

        # Analysis buttons
        col_a, col_b = st.columns(2)
        with col_a:
            analyse_btn = st.button(
                "🧠 Describe Image", use_container_width=True, disabled=pil_img is None
            )
        with col_b:
            compare_btn = st.button(
                "🔄 Compare with Prior",
                use_container_width=True,
                disabled=(pil_img is None or not prior.strip()),
            )

        classify_btn = None
        if cfg["use_siglip"]:
            classify_btn = st.button(
                "🎯 Zero-Shot Classify (MedSigLIP)",
                use_container_width=True,
                disabled=pil_img is None,
            )

        # Run analyses
        if analyse_btn and pil_img:
            with st.spinner("Analysing image with MedGemma 4B…"):
                if cfg["img_backend"] == "Gemini Vision (cloud)" and cfg["gemini_key"]:
                    from medecho.imaging import GeminiVisionClient
                    client = GeminiVisionClient(api_key=cfg["gemini_key"])
                    result = client.analyze(
                        img_bytes,
                        f"This is a {modality}. Provide a detailed radiological report: "
                        "(1) Image quality, (2) Key findings, (3) Pertinent negatives, "
                        "(4) Impression, (5) Recommendations.",
                    )
                else:
                    analyzer, _ = get_image_analyzer(cfg["hf_token"], cfg["gemini_key"])
                    result = analyzer.describe(pil_img, modality=modality)
                st.session_state.image_analysis = {"description": result, "modality": modality}
            st.success("Analysis complete!")

        if compare_btn and pil_img and prior.strip():
            with st.spinner("Comparing with prior report…"):
                if cfg["img_backend"] == "Gemini Vision (cloud)" and cfg["gemini_key"]:
                    from medecho.imaging import GeminiVisionClient
                    client = GeminiVisionClient(api_key=cfg["gemini_key"])
                    result = client.analyze(
                        img_bytes,
                        f"This is a current {modality}. Prior report: {prior}\n"
                        "Compare: (1) Interval changes, (2) Stable findings, "
                        "(3) New findings, (4) Resolved, (5) Impression.",
                    )
                else:
                    analyzer, _ = get_image_analyzer(cfg["hf_token"], cfg["gemini_key"])
                    result = analyzer.compare_with_prior(pil_img, prior, modality)
                st.session_state.image_analysis = {
                    "comparison": result,
                    "modality": modality,
                    "prior": prior,
                }
            st.success("Comparison complete!")

        if classify_btn and pil_img and cfg["use_siglip"]:
            with st.spinner("Running MedSigLIP zero-shot classification…"):
                try:
                    _, siglip = get_image_analyzer(cfg["hf_token"], cfg["gemini_key"])
                    scores = siglip.classify(pil_img, modality=modality)
                    st.session_state.siglip_scores = scores
                except Exception as exc:
                    st.error(f"MedSigLIP unavailable (weights not downloaded): {exc}")

        st.markdown("</div>", unsafe_allow_html=True)

    with col_right:
        # ── MedSigLIP scores ────────────────────────────────────────
        if st.session_state.siglip_scores:
            st.markdown('<div class="med-card">', unsafe_allow_html=True)
            st.markdown(
                '<div class="med-card-title">🎯 MedSigLIP Classification</div>',
                unsafe_allow_html=True,
            )
            for item in st.session_state.siglip_scores:
                score = item["score"]
                pct = int(score * 100)
                st.markdown(
                    f"""
                    <div class="score-bar-wrap">
                      <div class="score-label">
                        <span>{item['label']}</span>
                        <span style='color:#1ABC9C; font-weight:700;'>{pct}%</span>
                      </div>
                      <div class="score-bar-bg">
                        <div class="score-bar-fill" style="width:{pct}%;"></div>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            st.markdown("</div>", unsafe_allow_html=True)

        # ── Image Analysis Result ───────────────────────────────────
        if st.session_state.image_analysis:
            st.markdown('<div class="med-card">', unsafe_allow_html=True)
            st.markdown(
                '<div class="med-card-title">📊 Radiology Report</div>',
                unsafe_allow_html=True,
            )
            analysis = st.session_state.image_analysis
            if "description" in analysis:
                st.markdown(analysis["description"])
            elif "comparison" in analysis:
                st.markdown("**Longitudinal Comparison:**")
                st.markdown(analysis["comparison"])
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.markdown(
                """
                <div class="med-card" style="text-align:center; padding:48px;">
                  <p style="font-size:3rem;">🔬</p>
                  <p style="color:#BDC3C7;">Upload an image and click Analyse<br>to see the AI report here.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ── Tab 3: Clinical Summary ────────────────────────────────────────────────────

def render_clinical_tab(cfg: Dict) -> None:
    if not st.session_state.redacted_transcript:
        st.info("💡 Complete the Voice tab first to generate a transcript for clinical analysis.")
        return

    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown('<div class="med-card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="med-card-title">🧠 Differential Diagnosis</div>',
            unsafe_allow_html=True,
        )

        if st.button("🔍 Generate Differential Diagnosis", use_container_width=True):
            with st.spinner("Consulting MedGemma for differential diagnosis…"):
                engine = get_clinical_engine(cfg["gemini_key"], cfg["model_size"])
                st.session_state.diff_dx = engine.differential_diagnosis(
                    st.session_state.redacted_transcript,
                    ehr_summary=st.session_state.ehr_summary or None,
                )
            st.success("Differential diagnosis generated!")

        if st.session_state.diff_dx:
            dx = st.session_state.diff_dx
            primary = dx.get("primary_diagnosis", {})
            if primary:
                conf = primary.get("confidence", "low")
                badge_class = f"badge-{conf}"
                st.markdown(
                    f"""
                    <div style="background:rgba(26,188,156,0.08); border:1px solid #1ABC9C;
                                border-radius:10px; padding:16px; margin-bottom:12px;">
                      <strong style="font-size:1rem;">Primary: {primary.get('condition','—')}</strong>
                      <span class="badge-conf {badge_class}" style="margin-left:8px;">{conf}</span>
                      <p style="color:#BDC3C7; margin-top:8px; font-size:0.88rem;">
                        {primary.get('reasoning','—')}
                      </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            ddx = dx.get("differential_diagnoses", [])
            if ddx:
                st.markdown("**Differential Diagnoses:**")
                for item in ddx:
                    conf = item.get("confidence", "low")
                    badge_class = f"badge-{conf}"
                    features = ", ".join(item.get("key_features", []))
                    st.markdown(
                        f"""
                        <div style="border-left:3px solid #1B4F72; padding:8px 12px; margin-bottom:8px;
                                    background:rgba(27,79,114,0.15); border-radius:0 8px 8px 0;">
                          <strong>{item.get('condition','—')}</strong>
                          <span class="badge-conf {badge_class}" style="margin-left:8px;">{conf}</span>
                          <p style="color:#BDC3C7; font-size:0.82rem; margin:4px 0 0 0;">{features}</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            red_flags = dx.get("red_flags", [])
            if red_flags:
                st.markdown("**🚨 Red Flags:**")
                for flag in red_flags:
                    st.markdown(f"- {flag}")

            workup = dx.get("urgent_workup", [])
            if workup:
                st.markdown("**🔬 Urgent Workup:**")
                for item in workup:
                    st.markdown(f"- {item}")

        st.markdown("</div>", unsafe_allow_html=True)

    with col_right:
        st.markdown('<div class="med-card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="med-card-title">📋 Structured Encounter Extraction</div>',
            unsafe_allow_html=True,
        )

        if st.button("⚙️ Extract Structured Data", use_container_width=True):
            with st.spinner("Extracting structured clinical data…"):
                engine = get_clinical_engine(cfg["gemini_key"], cfg["model_size"])
                st.session_state.structured_data = engine.extract_structured(
                    st.session_state.redacted_transcript
                )
            st.success("Structured data extracted!")

        if st.session_state.structured_data:
            sd = st.session_state.structured_data

            def _list_block(title: str, key: str, icon: str) -> None:
                items = sd.get(key, [])
                if items:
                    st.markdown(f"**{icon} {title}**")
                    for item in items:
                        st.markdown(f"  - {item}")

            _list_block("Symptoms", "symptoms", "🤒")
            _list_block("Radiology Findings", "radiology_findings", "🩻")
            _list_block("Suggested Medications", "suggested_medications", "💊")
            _list_block("Procedures Ordered", "procedures_ordered", "🔬")
            _list_block("Diagnoses", "diagnoses", "📌")

            vs = sd.get("vital_signs", {})
            if vs:
                st.markdown("**❤️ Vital Signs**")
                vitals_html = " ".join(
                    f'<span class="medecho-badge">{k}: {v}</span>'
                    for k, v in vs.items()
                )
                st.markdown(vitals_html, unsafe_allow_html=True)

            fu = sd.get("follow_up_date", "")
            if fu:
                st.markdown(f"**📅 Follow-up:** {fu}")

            notes = sd.get("physician_notes", "")
            if notes:
                st.markdown("**📝 Physician Notes**")
                st.markdown(
                    f'<div class="transcript-box">{notes}</div>',
                    unsafe_allow_html=True,
                )

            # Show raw JSON
            with st.expander("🗂️ Raw JSON"):
                st.json(sd)

        st.markdown("</div>", unsafe_allow_html=True)

    # Context-aware synthesis
    if st.session_state.redacted_transcript and (
        st.session_state.ehr_summary or st.session_state.image_analysis
    ):
        st.markdown('<div class="med-card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="med-card-title">🌐 Context-Aware Clinical Synthesis</div>',
            unsafe_allow_html=True,
        )
        if st.button("💡 Generate Holistic Recommendations", use_container_width=True):
            with st.spinner("Synthesising all available clinical data…"):
                engine = get_clinical_engine(cfg["gemini_key"], cfg["model_size"])
                img_text = (
                    st.session_state.image_analysis.get("description")
                    or st.session_state.image_analysis.get("comparison")
                    or ""
                )
                synthesis = engine.context_aware_suggestion(
                    st.session_state.redacted_transcript,
                    st.session_state.ehr_summary or "Not provided.",
                    image_findings=img_text or None,
                )
            st.markdown(synthesis)
        st.markdown("</div>", unsafe_allow_html=True)


# ── Tab 4: Output & Export ─────────────────────────────────────────────────────

def render_output_tab(cfg: Dict) -> None:
    exp, qr_gen = get_exporters()

    # ── Build encounter package ─────────────────────────────────────
    encounter = {
        "encounter_id": st.session_state.encounter_id,
        "date": cfg["encounter_date"],
        "patient_name": cfg["patient_name"] or "[REDACTED]",
        "physician": cfg["physician"],
        "transcript_raw": st.session_state.transcript,
        "transcript_redacted": st.session_state.redacted_transcript,
        "pii_redacted_labels": st.session_state.pii_labels,
        "ehr_summary": st.session_state.ehr_summary,
        "structured": st.session_state.structured_data,
        "differential_diagnosis": st.session_state.diff_dx,
        "imaging": st.session_state.image_analysis,
        "siglip_scores": st.session_state.siglip_scores,
    }

    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown('<div class="med-card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="med-card-title">💾 Export Encounter</div>',
            unsafe_allow_html=True,
        )

        # Metrics
        num_symptoms = len(st.session_state.structured_data.get("symptoms", []))
        num_dx = len(
            st.session_state.diff_dx.get("differential_diagnoses", [])
        )
        has_imaging = bool(st.session_state.image_analysis)
        transcript_words = len(st.session_state.redacted_transcript.split())

        st.markdown(
            f"""
            <div class="metric-row">
              <div class="metric-tile">
                <div class="val">{transcript_words}</div>
                <div class="lbl">Transcript Words</div>
              </div>
              <div class="metric-tile">
                <div class="val">{num_symptoms}</div>
                <div class="lbl">Symptoms</div>
              </div>
              <div class="metric-tile">
                <div class="val">{num_dx}</div>
                <div class="lbl">Differentials</div>
              </div>
              <div class="metric-tile">
                <div class="val">{'✅' if has_imaging else '—'}</div>
                <div class="lbl">Imaging</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("🔒 Generate Encrypted Export", use_container_width=True):
            with st.spinner("Encrypting encounter data…"):
                data = exp.export(encounter, encrypt=cfg["encrypt_output"])
                st.session_state.export_bytes = data
                st.session_state.export_key = exp.key_b64
            st.success(
                "Export ready! "
                + ("🔒 Encrypted." if cfg["encrypt_output"] and exp.encryption_available else "📄 Plain JSON.")
            )

        if st.session_state.export_bytes:
            fname = f"encounter_{st.session_state.encounter_id}.{'enc' if cfg['encrypt_output'] else 'json'}"
            st.download_button(
                "⬇️ Download Encounter File",
                data=st.session_state.export_bytes,
                file_name=fname,
                mime="application/octet-stream",
                use_container_width=True,
            )

            if cfg["encrypt_output"] and st.session_state.export_key:
                st.markdown("**🔑 Decryption Key** (store securely):")
                st.code(st.session_state.export_key, language="text")

        # Raw JSON preview
        with st.expander("🗂️ Preview Full Encounter JSON"):
            st.json(encounter)

        st.markdown("</div>", unsafe_allow_html=True)

    with col_right:
        st.markdown('<div class="med-card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="med-card-title">📱 Patient QR Code</div>',
            unsafe_allow_html=True,
        )

        if cfg["generate_qr"] and qr_gen.available:
            if st.button("📲 Generate QR Code", use_container_width=True):
                with st.spinner("Generating QR code…"):
                    qr_bytes = qr_gen.generate_bytes(encounter)
                    st.session_state.qr_bytes = qr_bytes
                st.success("QR code generated!")

            if st.session_state.qr_bytes:
                st.markdown(
                    '<div class="qr-container" style="text-align:center; margin:0 auto; display:block; width:fit-content;">',
                    unsafe_allow_html=True,
                )
                st.image(
                    st.session_state.qr_bytes,
                    caption="Scan to access encounter summary",
                    width=250,
                )
                st.markdown("</div>", unsafe_allow_html=True)
                st.download_button(
                    "⬇️ Download QR Code",
                    data=st.session_state.qr_bytes,
                    file_name=f"qr_{st.session_state.encounter_id}.png",
                    mime="image/png",
                    use_container_width=True,
                )
        else:
            msg = (
                "QR generation disabled in settings."
                if not cfg["generate_qr"]
                else "Install `qrcode[pil]` to enable QR generation."
            )
            st.info(msg)

        # Offline status
        st.markdown("---")
        st.markdown(
            '<div class="med-card-title">📡 Offline Status</div>',
            unsafe_allow_html=True,
        )
        from medecho.offline import OfflineStore, is_online
        store = OfflineStore()
        stats = store.get_stats()
        st.markdown(
            f"""
            <div class="metric-row">
              <div class="metric-tile">
                <div class="val">{stats['pending_encounters']}</div>
                <div class="lbl">Pending</div>
              </div>
              <div class="metric-tile">
                <div class="val">{stats['offline_audio_files']}</div>
                <div class="lbl">Audio Files</div>
              </div>
              <div class="metric-tile">
                <div class="val">{stats['total_size_mb']} MB</div>
                <div class="lbl">Storage Used</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        connectivity = "🟢 Online" if is_online() else "🔴 Offline"
        st.markdown(f"**Connectivity:** {connectivity}")

        st.markdown("</div>", unsafe_allow_html=True)


# ── Tab 5: About / Model Info ──────────────────────────────────────────────────

def render_about_tab() -> None:
    st.markdown(
        """
        <div class="med-card">
          <div class="med-card-title">ℹ️ About MedEcho</div>
          <p>
            <strong>MedEcho</strong> is an open-source AI Clinical Scribe and Radiology Assistant
            built on Google's <strong>Health AI Developer Foundations (HAI-DEF)</strong> model suite.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
            <div class="med-card">
              <div class="med-card-title">🤖 HAI-DEF Models Used</div>
              <ul>
                <li><strong>MedGemma 4B Multimodal</strong> – radiology image description,
                    anatomical localization, longitudinal comparison</li>
                <li><strong>MedGemma 27B Text</strong> – differential diagnosis,
                    structured extraction, clinical reasoning</li>
                <li><strong>MedSigLIP</strong> – zero-shot medical image classification
                    (Chest X-ray, pathology, dermatology)</li>
                <li><strong>MedASR</strong> – radiology-specialised speech recognition
                    (with Whisper local fallback)</li>
              </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            """
            <div class="med-card">
              <div class="med-card-title">🛡️ Privacy & Security Features</div>
              <ul>
                <li>🔍 <strong>PII Redaction</strong> – regex-based removal of names,
                    phone numbers, SSNs, MRNs before display</li>
                <li>🔒 <strong>AES-256-GCM Encryption</strong> – encounter files encrypted
                    with the <code>cryptography</code> (Fernet) library</li>
                <li>📱 <strong>QR Code Export</strong> – compact encounter summary as
                    patient-portable QR</li>
                <li>📡 <strong>Offline Mode</strong> – full local save when internet
                    is unavailable; auto-sync on reconnect</li>
                <li>🎙️ <strong>VAD Gating</strong> – records only when human voice
                    is detected (webrtcvad)</li>
              </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div class="med-card">
          <div class="med-card-title">⚙️ Architecture</div>
          <pre style="color:#1ABC9C; font-size:0.82rem; background:#0D1B2A; padding:12px; border-radius:8px;">
🎙️  Microphone / Audio Upload
        │
        ▼  webrtcvad (VAD gating)
        ▼  MedASR / Whisper (transcription)
        ▼  Regex PII redactor
        │
        ├──► MedGemma 27B ─► Differential Diagnosis
        │                   ─► Structured Extraction (JSON)
        │                   ─► Context-Aware Synthesis (+ EHR)
        │
🖼️  Image Upload
        │
        ▼  MedSigLIP (zero-shot classification)
        ▼  MedGemma 4B (image description / comparison)
        │
        ▼  EncryptedJSONExporter (AES-256-GCM via cryptography)
        ▼  QRCodeGenerator (patient handoff)
        ▼  OfflineStore (local fallback)
          </pre>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Main entry point ───────────────────────────────────────────────────────────

def main() -> None:
    cfg = render_sidebar()
    render_header(cfg)

    tab_ear, tab_eye, tab_brain, tab_output, tab_about = st.tabs(
        ["🎙️ Ear (Voice)", "🔬 Eye (Imaging)", "🧠 Brain (Clinical)", "📤 Output", "ℹ️ About"]
    )

    with tab_ear:
        render_voice_tab(cfg)

    with tab_eye:
        render_imaging_tab(cfg)

    with tab_brain:
        render_clinical_tab(cfg)

    with tab_output:
        render_output_tab(cfg)

    with tab_about:
        render_about_tab()


if __name__ == "__main__":
    main()
