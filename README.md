<div align="center">

# 🩺 MedEcho — AI Radiology & Clinical Scribe

**Powered by Google's Health AI Developer Foundations (HAI-DEF)**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35%2B-red.svg)](https://streamlit.io)
[![MedGemma](https://img.shields.io/badge/Model-MedGemma%204B%2F27B-orange.svg)](https://huggingface.co/models?other=medgemma)

*A privacy-first, hands-free AI assistant for clinical encounter documentation and medical image analysis.*

</div>

---

## Table of Contents

1. [Overview](#overview)
2. [Key Features](#key-features)
3. [Architecture](#architecture)
4. [Quick Start — One-Click Install](#quick-start--one-click-install)
5. [Manual Installation](#manual-installation)
6. [API Key Setup](#api-key-setup)
7. [Running the Application](#running-the-application)
8. [Usage Guide](#usage-guide)
9. [Configuration Reference](#configuration-reference)
10. [Model Details](#model-details)
11. [Security & Privacy](#security--privacy)
12. [Notebooks](#notebooks)
13. [Technical Paper](#technical-paper)
14. [Contributing](#contributing)
15. [License](#license)

---

## Overview

MedEcho is a full-stack clinical AI assistant built on Google's [Health AI Developer Foundations (HAI-DEF)](https://developers.google.com/health-ai-developer-foundations) suite. It combines four HAI-DEF models into a single, cohesive pipeline that:

- **Transcribes** clinical encounters with medical-specialist accuracy (MedASR)
- **Analyses** medical images — chest X-rays, pathology slides, dermatology photos (MedSigLIP + MedGemma 4B)
- **Generates** structured differential diagnoses and encounter summaries (MedGemma 27B)
- **Exports** encrypted, QR-coded patient records that work completely offline

> **Intended Use**: MedEcho is a decision-support tool. All AI outputs are clearly labelled as suggestions for qualified clinicians to review. It does not replace professional medical judgment.

---

## Key Features

| Feature | Description |
|---|---|
| 🎙️ **Voice-to-SOAP** | Hands-free dictation → structured clinical note in seconds |
| 🔬 **Zero-Shot Image Classification** | MedSigLIP classifies X-rays, pathology, derm without fine-tuning |
| 🧠 **Differential Diagnosis** | MedGemma 27B generates primary + differential diagnoses with confidence levels |
| 🔒 **PII Redaction** | 8 regex patterns strip names, phone numbers, SSNs, MRNs before any API call |
| 📱 **QR Code Export** | Patient-portable encounter summary encoded as a scannable QR code |
| 📡 **Offline Mode** | Auto-detects connectivity loss; queues data locally for later upload |
| 🔑 **In-App API Keys** | Enter API keys directly in the Streamlit sidebar — no terminal required |
| 🏥 **EHR Integration** | Paste patient history for context-aware AI suggestions |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Browser / Streamlit UI  (app.py)                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  ┌────────┐ │
│  │  🎙️  Ear     │  │  🔬  Eye     │  │  🧠  Brain    │  │ 📤 Out │ │
│  │  voice.py    │  │  imaging.py  │  │  clinical.py  │  │ put.py │ │
│  └──────────────┘  └──────────────┘  └───────────────┘  └────────┘ │
└─────────────────────────────────────────────────────────────────────┘
        │                  │                   │
   MedASR API         MedSigLIP           MedGemma API
   + Whisper        google/medsiglip-      Gemini cloud
   local fallback   base-patch16-224       or local HF
```

**Data flow:**
```
Audio  → MedASR → PII-redacted text → MedGemma 27B → DDx + structured JSON
Image  → MedSigLIP → top-5 labels → MedGemma 4B → radiology report
Both   → MedGemma 27B (EHR-aware synthesis)  → encrypted export + QR
```

**File structure:**
```
MedGemma/
├── app.py                  # Streamlit entry point
├── requirements.txt        # Python dependencies
├── install.sh              # One-click installer (Linux / macOS)
├── install.bat             # One-click installer (Windows)
├── run.sh                  # Launch script (Linux / macOS)
├── run.bat                 # Launch script (Windows)
├── .env                    # API keys (created by installer, git-ignored)
├── TECHNICAL_PAPER.md      # Academic-style technical paper
├── WRITEUP.md              # Hackathon write-up
├── medecho/
│   ├── __init__.py
│   ├── voice.py            # VAD, MedASR, PII redaction
│   ├── imaging.py          # MedSigLIP + MedGemma 4B image analysis
│   ├── clinical.py         # MedGemma 27B clinical logic
│   ├── output.py           # Encrypted JSON export, QR code generation
│   └── offline.py          # Offline fallback & connectivity monitoring
└── *.ipynb                 # Research notebooks
```

---

## Quick Start — One-Click Install

### Linux / macOS

```bash
# 1. Clone the repository
git clone https://github.com/shahriar2203041/MedGemma.git
cd MedGemma

# 2. Run the installer (creates .venv, installs deps, generates .env template)
chmod +x install.sh
./install.sh

# 3. Launch MedEcho
./run.sh
```

### Windows

```bat
REM 1. Clone the repository
git clone https://github.com/shahriar2203041/MedGemma.git
cd MedGemma

REM 2. Double-click install.bat  OR  run from Command Prompt:
install.bat

REM 3. Double-click run.bat  OR  run from Command Prompt:
run.bat
```

The installer automatically:
- Checks for Python 3.10+
- Creates an isolated virtual environment (`.venv`)
- Installs all dependencies from `requirements.txt`
- Creates a `.env` template for API keys
- Generates a one-click `run.sh` / `run.bat` launch script

---

## Manual Installation

If you prefer to set up manually:

```bash
# Prerequisites: Python 3.10+, git

# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate      # Linux/macOS
# .venv\Scripts\activate       # Windows

# 2. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 3. Create .env (optional — keys can also be entered in the app)
cp .env.example .env           # then edit .env with your keys
```

---

## API Key Setup

MedEcho needs up to three API keys depending on which features you use:

| Key | Required For | Where to Get It |
|---|---|---|
| **Gemini API Key** | Cloud AI (DDx, image analysis) — required for cloud mode | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) |
| **HuggingFace Token** | Downloading local model weights (MedGemma, MedSigLIP) | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) |
| **Google Cloud API Key** | MedASR cloud transcription (optional) | [console.cloud.google.com/apis/credentials](https://console.cloud.google.com/apis/credentials) |

### Option A — Enter keys in the Streamlit sidebar (recommended for demos)

1. Launch MedEcho (`./run.sh` or `run.bat`)
2. Open the sidebar (☰ icon, top-left)
3. Scroll to **🔑 API Configuration**
4. Enter your keys in the text fields — they are used for the current session only and are never stored to disk

### Option B — Store keys in `.env` (recommended for persistent deployments)

Edit the `.env` file created by the installer:

```dotenv
GEMINI_API_KEY=AIza...
HF_TOKEN=hf_...
GOOGLE_CLOUD_API_KEY=AIza...   # optional
```

Keys in `.env` are automatically loaded at startup. The `.env` file is listed in `.gitignore` and will never be committed.

> **Security note:** Never share your `.env` file or paste keys into public repositories.

---

## Running the Application

```bash
# Standard launch
./run.sh           # Linux/macOS
run.bat            # Windows

# Manual launch (with venv activated)
streamlit run app.py

# Specify a custom port
streamlit run app.py --server.port 8502
```

The app opens automatically in your default browser at `http://localhost:8501`.

---

## Usage Guide

### 1. Voice Transcription (The Ear)

1. Select **🎙️ Voice & Transcript** tab
2. Upload an audio file (WAV, MP3, M4A) **or** type / paste text directly
3. Click **🔬 Transcribe & Analyse**
4. MedEcho transcribes the audio using MedASR (cloud) or Whisper (offline)
5. PII is automatically redacted before display or storage
6. The transcript feeds into the Clinical Brain for diagnosis generation

### 2. Medical Image Analysis (The Eye)

1. Select **🔬 Medical Imaging** tab
2. Upload one or more images (JPEG, PNG, DICOM-derived PNG)
3. Choose analysis mode:
   - **Describe** — full structured radiology report
   - **Localize** — anatomical localization of a named finding
   - **Compare with Prior** — longitudinal change detection
   - **CT/MRI Volume** — slice-by-slice narrative
4. Toggle **MedSigLIP Zero-Shot** for automatic image classification

### 3. Clinical Analysis (The Brain)

1. Select **🧠 Clinical Analysis** tab
2. Optionally paste a patient EHR summary for context-aware suggestions
3. Click **Generate Differential Diagnosis** to get primary + differential diagnoses with confidence levels and red flags
4. Click **Extract Structured Data** to convert the transcript into a validated JSON object

### 4. Export & Output

1. Select **📤 Export** tab
2. Results are assembled into a structured encounter record
3. Click **Export** to download:
   - **Encrypted JSON** — AES-128 encrypted encounter record
   - **QR Code** — patient-portable scan containing diagnoses, medications, and follow-up date
4. The encryption key is shown once; store it safely to decrypt the file later

### 5. Offline Mode

When connectivity is lost, MedEcho automatically:
- Switches to local Whisper ASR
- Stores audio and images locally in `offline_data/`
- Queues encounters for upload when connectivity returns
- A banner in the header shows the current connectivity status

---

## Configuration Reference

All settings are accessible from the **sidebar** without restarting the app:

| Setting | Options | Description |
|---|---|---|
| **LLM Backend** | `gemini-2.0-flash` / `gemini-1.5-pro` / `MedGemma 27B (local)` / `MedGemma 4B (local)` | Text generation model |
| **Image Backend** | `MedGemma 4B (local)` / `Gemini Vision (cloud)` | Image analysis model |
| **MedSigLIP** | On / Off | Zero-shot image classification |
| **VAD** | On / Off | Voice Activity Detection (reduces noise/cost) |
| **Encrypt Export** | On / Off | AES-128 encryption of exported records |
| **Generate QR** | On / Off | Patient QR code generation |

---

## Model Details

### MedGemma 4B (Multimodal)

- **Architecture:** Gemma 3 4B + SigLIP image encoder
- **Image encoder pre-trained on:** chest X-rays, dermatology, ophthalmology, histopathology
- **Supports:** radiology report generation, anatomical localization, longitudinal comparison, 3D CT/MRI narrative
- **HuggingFace:** [`google/medgemma-4b-it`](https://huggingface.co/google/medgemma-4b-it)

### MedGemma 27B (Text-Only)

- **Architecture:** Gemma 3 27B
- **Pre-trained on:** diverse medical literature, clinical notes, medical Q&A
- **Supports:** differential diagnosis, structured extraction, EHR synthesis
- **HuggingFace:** [`google/medgemma-27b-text-it`](https://huggingface.co/google/medgemma-27b-text-it)

### MedSigLIP

- **Architecture:** SigLIP base patch16-224
- **Pre-trained on:** de-identified medical image-text pairs
- **Supports:** zero-shot classification of chest X-rays, pathology, dermatology
- **HuggingFace:** [`google/medsiglip-base-patch16-224`](https://huggingface.co/google/medsiglip-base-patch16-224)

---

## Security & Privacy

MedEcho is designed with a privacy-first architecture:

- **PII Redaction** — 8 compiled regex patterns remove names, phone numbers, SSNs, MRNs, emails, dates of birth, and ZIP codes *before* any text is sent to an API or written to disk
- **Encrypted Export** — encounter records are wrapped in a Fernet envelope (AES-128-CBC + HMAC-SHA256) using the `cryptography` library; a unique key is generated per session
- **No persistent key storage** — API keys entered in the sidebar are held only in Streamlit session state and are never written to disk
- **Local-first offline mode** — audio and images can be stored and processed entirely on-device, with no data leaving the local network

> MedEcho is intended for use in HIPAA-sensitive environments. Clinical deployments must comply with all applicable regulations, including BAA agreements with cloud providers.

---

## Notebooks

This repository includes research and tutorial notebooks:

| Notebook | Description |
|---|---|
| `quick_start_with_hugging_face.ipynb` | Load and run MedGemma via the HuggingFace Transformers library |
| `quick_start_with_model_garden.ipynb` | Use MedGemma via Google Cloud Vertex AI Model Garden |
| `quick_start_with_dicom.ipynb` | Process DICOM medical images with MedGemma |
| `fine_tune_with_hugging_face.ipynb` | Fine-tune MedGemma on a custom clinical dataset |
| `cxr_anatomy_localization_with_hugging_face.ipynb` | Chest X-ray anatomical localization |
| `cxr_longitudinal_comparison_with_hugging_face.ipynb` | Longitudinal CXR comparison |
| `high_dimensional_ct_hugging_face.ipynb` | High-dimensional CT analysis |
| `high_dimensional_pathology_hugging_face.ipynb` | Pathology slide analysis |
| `ehr_navigator_agent.ipynb` | EHR navigation with an agentic workflow |
| `reinforcement_learning_with_hugging_face.ipynb` | RL fine-tuning of MedGemma |

---

## Technical Paper

For a detailed academic-style description of the architecture, methodology, and evaluation, see [TECHNICAL_PAPER.md](TECHNICAL_PAPER.md).

---

## Contributing

We welcome bug reports, feature requests, and pull requests.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes and add tests where appropriate
4. Submit a pull request with a clear description

Please read [CONTRIBUTING.md](CONTRIBUTING.md) and our [community guidelines](https://developers.google.com/health-ai-developer-foundations/community-guidelines) before contributing.

---

## License

The **MedEcho application code** in this repository is licensed under the [Apache 2.0 License](LICENSE).

The **MedGemma and MedSigLIP model weights** are licensed under the [Health AI Developer Foundations License](https://developers.google.com/health-ai-developer-foundations/terms). Please review the model license terms before commercial use.

---

<div align="center">
Built with ❤️ by <strong>Sanjid Hasan & Sakib Hassan</strong> for the MedGemma Impact Challenge
</div>
