"""
Clinical Logic Module for MedEcho
Handles differential diagnosis generation, structured encounter extraction,
and EHR context integration using MedGemma 27B (text) or 4B.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Prompt templates ───────────────────────────────────────────────────────────

_DIFF_DX_PROMPT = """You are a senior clinician. Based on the following transcribed clinical encounter, generate a structured differential diagnosis.

ENCOUNTER TRANSCRIPT:
{transcript}

{ehr_context}

Provide your response as a JSON object with the following structure:
{{
  "primary_diagnosis": {{
    "condition": "...",
    "confidence": "high|medium|low",
    "reasoning": "..."
  }},
  "differential_diagnoses": [
    {{
      "condition": "...",
      "confidence": "high|medium|low",
      "key_features": ["...", "..."],
      "ruling_out": "..."
    }}
  ],
  "red_flags": ["...", "..."],
  "urgent_workup": ["...", "..."]
}}

Return ONLY valid JSON."""

_EXTRACTION_PROMPT = """You are a clinical documentation specialist. Extract structured clinical information from this encounter transcript.

ENCOUNTER TRANSCRIPT:
{transcript}

Extract and return a JSON object with EXACTLY this structure:
{{
  "symptoms": [],
  "radiology_findings": [],
  "suggested_medications": [],
  "follow_up_date": "",
  "vital_signs": {{}},
  "allergies": [],
  "procedures_ordered": [],
  "diagnoses": [],
  "physician_notes": ""
}}

Rules:
- symptoms: list of symptom strings as mentioned
- radiology_findings: any imaging findings mentioned
- suggested_medications: drug names with dose/frequency if mentioned
- follow_up_date: ISO date string or "" if not mentioned
- vital_signs: dict of {{metric: value}} (e.g. {{"BP": "120/80", "HR": "72"}})
- allergies: drug/substance allergies mentioned
- procedures_ordered: any procedures or tests ordered
- diagnoses: working diagnoses mentioned
- physician_notes: free-text summary of key clinical notes

Return ONLY valid JSON."""

_EHR_SUMMARY_PROMPT = """Summarize the following patient history for clinical context. Be concise and highlight:
1. Relevant past diagnoses
2. Current medications
3. Known allergies
4. Relevant surgical history
5. Key risk factors

PATIENT HISTORY:
{ehr_text}

Return a brief clinical summary (3-5 sentences)."""

# Maximum characters of raw LLM output to include when JSON parsing fails
_MAX_FALLBACK_REASONING_LENGTH = 500


# ── MedGemma Text Client ────────────────────────────────────────────────────────


class MedGemmaTextClient:
    """
    Text-only interface to MedGemma.

    Primary: google/medgemma-27b-text (best reasoning)
    Fallback: google/medgemma-4b-it (faster, lower memory)
    Also supports Gemini API as a cloud fallback.
    """

    MODELS = {
        "27b": "google/medgemma-27b-text",
        "4b": "google/medgemma-4b-it",
    }

    def __init__(
        self,
        model_size: str = "4b",
        hf_token: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        device: str = "cpu",
    ):
        self._model_size = model_size
        self._hf_token = hf_token
        self._gemini_api_key = gemini_api_key
        self._device = device
        self._model = None
        self._tokenizer = None

    # ------------------------------------------------------------------
    def _load_local(self) -> None:
        if self._model is not None:
            return
        from transformers import AutoTokenizer, AutoModelForCausalLM  # type: ignore
        import torch  # type: ignore

        model_id = self.MODELS.get(self._model_size, self.MODELS["4b"])
        logger.info("Loading %s…", model_id)
        kwargs: Dict[str, Any] = {"torch_dtype": "auto"}
        if self._hf_token:
            kwargs["token"] = self._hf_token

        self._tokenizer = AutoTokenizer.from_pretrained(
            model_id, **{"token": self._hf_token} if self._hf_token else {}
        )
        self._model = AutoModelForCausalLM.from_pretrained(
            model_id, **kwargs
        ).to(self._device)
        self._model.eval()
        self._torch = torch
        logger.info("%s loaded on %s", model_id, self._device)

    # ------------------------------------------------------------------
    def generate(self, prompt: str, max_new_tokens: int = 1024) -> str:
        """Generate text. Tries Gemini API first if key is available."""
        if self._gemini_api_key:
            try:
                return self._generate_gemini(prompt, max_new_tokens)
            except Exception as exc:
                logger.warning("Gemini API failed (%s); falling back to local model.", exc)

        return self._generate_local(prompt, max_new_tokens)

    # ------------------------------------------------------------------
    def _generate_gemini(self, prompt: str, max_tokens: int) -> str:
        import google.generativeai as genai  # type: ignore

        genai.configure(api_key=self._gemini_api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        resp = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(max_output_tokens=max_tokens),
        )
        return resp.text.strip()

    # ------------------------------------------------------------------
    def _generate_local(self, prompt: str, max_new_tokens: int) -> str:
        import torch  # type: ignore

        self._load_local()
        inputs = self._tokenizer(prompt, return_tensors="pt").to(self._device)
        with torch.no_grad():
            out = self._model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=self._tokenizer.eos_token_id,
            )
        new = out[0][inputs["input_ids"].shape[-1] :]
        return self._tokenizer.decode(new, skip_special_tokens=True).strip()


# ── JSON extraction helper ─────────────────────────────────────────────────────


def _extract_json(text: str) -> Optional[Dict]:
    """Extract the first JSON object found in *text*."""
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find JSON block between ```json ... ``` or { ... }
    patterns = [
        r"```json\s*([\s\S]+?)\s*```",
        r"```\s*([\s\S]+?)\s*```",
        r"(\{[\s\S]+\})",
    ]
    for pat in patterns:
        match = re.search(pat, text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
    return None


# ── Clinical Engine ────────────────────────────────────────────────────────────


class ClinicalEngine:
    """
    Orchestrates clinical NLP tasks:
      1. Differential diagnosis generation
      2. Structured encounter extraction
      3. EHR context summarization
    """

    def __init__(self, llm: Optional[MedGemmaTextClient] = None):
        self._llm = llm or MedGemmaTextClient()

    # ------------------------------------------------------------------
    def differential_diagnosis(
        self,
        transcript: str,
        ehr_summary: Optional[str] = None,
    ) -> Dict:
        """
        Generate a differential diagnosis from an encounter transcript.

        Returns a dict with primary_diagnosis and differential_diagnoses.
        """
        ehr_section = (
            f"\nPATIENT HISTORY CONTEXT:\n{ehr_summary}" if ehr_summary else ""
        )
        prompt = _DIFF_DX_PROMPT.format(
            transcript=transcript.strip(), ehr_context=ehr_section
        )
        raw = self._llm.generate(prompt)
        result = _extract_json(raw)

        if result is None:
            # Return a minimal structure so callers don't crash
            return {
                "primary_diagnosis": {
                    "condition": "Unable to parse",
                    "confidence": "low",
                    "reasoning": raw[:_MAX_FALLBACK_REASONING_LENGTH],
                },
                "differential_diagnoses": [],
                "red_flags": [],
                "urgent_workup": [],
            }
        return result

    # ------------------------------------------------------------------
    def extract_structured(self, transcript: str) -> Dict:
        """
        Convert encounter transcript to structured JSON:
          symptoms, radiology_findings, suggested_medications,
          follow_up_date, vital_signs, allergies, procedures_ordered,
          diagnoses, physician_notes.
        """
        prompt = _EXTRACTION_PROMPT.format(transcript=transcript.strip())
        raw = self._llm.generate(prompt)
        result = _extract_json(raw)

        if result is None:
            return {
                "symptoms": [],
                "radiology_findings": [],
                "suggested_medications": [],
                "follow_up_date": "",
                "vital_signs": {},
                "allergies": [],
                "procedures_ordered": [],
                "diagnoses": [],
                "physician_notes": transcript[:300],
            }
        return result

    # ------------------------------------------------------------------
    def summarize_ehr(self, ehr_text: str) -> str:
        """Produce a concise clinical summary from a raw EHR blob."""
        prompt = _EHR_SUMMARY_PROMPT.format(ehr_text=ehr_text.strip())
        return self._llm.generate(prompt, max_new_tokens=300)

    # ------------------------------------------------------------------
    def context_aware_suggestion(
        self,
        transcript: str,
        ehr_summary: str,
        image_findings: Optional[str] = None,
    ) -> str:
        """
        Combine transcript, EHR context, and imaging findings for a
        holistic clinical recommendation.
        """
        imaging_section = (
            f"\nRADIOLOGY FINDINGS:\n{image_findings}" if image_findings else ""
        )
        prompt = (
            "You are a senior clinician. Given the following information, "
            "provide concise, evidence-based clinical recommendations.\n\n"
            f"ENCOUNTER TRANSCRIPT:\n{transcript}\n\n"
            f"PATIENT HISTORY:\n{ehr_summary}"
            f"{imaging_section}\n\n"
            "Provide: (1) Top differential diagnoses, (2) Immediate management steps, "
            "(3) Investigations to order, (4) Patient counseling points."
        )
        return self._llm.generate(prompt, max_new_tokens=600)
