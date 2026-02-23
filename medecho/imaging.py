"""
Medical Imaging Module for MedEcho
Handles MedSigLIP zero-shot classification and MedGemma 4B multimodal analysis.
"""

import io
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# ── Default label sets ─────────────────────────────────────────────────────────

CHEST_XRAY_LABELS = [
    "Pneumonia",
    "Cardiomegaly",
    "Pleural Effusion",
    "Pneumothorax",
    "Atelectasis",
    "Fracture",
    "Consolidation",
    "Edema",
    "Nodule",
    "Normal",
]

PATHOLOGY_LABELS = [
    "Benign tissue",
    "Malignant tumor",
    "Adenocarcinoma",
    "Squamous cell carcinoma",
    "Normal tissue",
    "Inflammatory infiltrate",
    "Necrosis",
]

DERMATOLOGY_LABELS = [
    "Melanoma",
    "Basal cell carcinoma",
    "Squamous cell carcinoma",
    "Benign nevus",
    "Seborrheic keratosis",
    "Actinic keratosis",
    "Normal skin",
]

LABEL_SETS: Dict[str, List[str]] = {
    "Chest X-Ray": CHEST_XRAY_LABELS,
    "Pathology Slide": PATHOLOGY_LABELS,
    "Dermatology": DERMATOLOGY_LABELS,
}


# ── Image loading helper ───────────────────────────────────────────────────────


def load_image(image_input: Union[str, Path, bytes, "PIL.Image.Image"]) -> "PIL.Image.Image":  # type: ignore[name-defined]
    """Load an image from a file path, bytes buffer, or PIL Image."""
    from PIL import Image  # type: ignore

    if isinstance(image_input, Image.Image):
        return image_input.convert("RGB")
    if isinstance(image_input, (str, Path)):
        return Image.open(str(image_input)).convert("RGB")
    if isinstance(image_input, (bytes, bytearray)):
        return Image.open(io.BytesIO(image_input)).convert("RGB")
    raise TypeError(f"Unsupported image type: {type(image_input)}")


# ── MedSigLIP Zero-Shot Classifier ────────────────────────────────────────────


class MedSigLIPAnalyzer:
    """
    Zero-shot image classification using MedSigLIP
    (google/medsiglip-base-patch16-224) from the HAI-DEF suite.

    Computes cosine similarity between the image embedding and a set
    of label text embeddings, returning confidence scores for each label.
    """

    MODEL_ID = "google/medsiglip-base-patch16-224"

    def __init__(self, device: str = "cpu"):
        self._device = device
        self._model = None
        self._processor = None

    # ------------------------------------------------------------------
    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            from transformers import AutoProcessor, AutoModel  # type: ignore
            import torch  # type: ignore

            logger.info("Loading MedSigLIP model…")
            self._processor = AutoProcessor.from_pretrained(self.MODEL_ID)
            self._model = AutoModel.from_pretrained(self.MODEL_ID).to(self._device)
            self._model.eval()
            self._torch = torch
            logger.info("MedSigLIP ready on %s", self._device)
        except Exception as exc:
            logger.error("Failed to load MedSigLIP: %s", exc)
            raise

    # ------------------------------------------------------------------
    def classify(
        self,
        image: Union[str, Path, bytes, "PIL.Image.Image"],  # type: ignore[name-defined]
        labels: Optional[List[str]] = None,
        modality: str = "Chest X-Ray",
        top_k: int = 5,
    ) -> List[Dict[str, float]]:
        """
        Run zero-shot classification.

        Returns a sorted list of {label: str, score: float} dicts,
        highest confidence first.
        """
        import torch  # type: ignore
        import torch.nn.functional as F  # type: ignore

        self._load()

        if labels is None:
            labels = LABEL_SETS.get(modality, CHEST_XRAY_LABELS)

        pil_img = load_image(image)

        # Encode image
        img_inputs = self._processor(images=pil_img, return_tensors="pt").to(
            self._device
        )
        with torch.no_grad():
            img_features = self._model.get_image_features(**img_inputs)
            img_features = F.normalize(img_features, dim=-1)

        # Encode labels
        text_inputs = self._processor(
            text=labels, return_tensors="pt", padding=True
        ).to(self._device)
        with torch.no_grad():
            text_features = self._model.get_text_features(**text_inputs)
            text_features = F.normalize(text_features, dim=-1)

        # Cosine similarities → softmax probabilities
        logits = (img_features @ text_features.T).squeeze(0)
        probs = F.softmax(logits * 100, dim=-1).cpu().tolist()

        results = sorted(
            [{"label": lbl, "score": float(sc)} for lbl, sc in zip(labels, probs)],
            key=lambda x: x["score"],
            reverse=True,
        )
        return results[:top_k]


# ── MedGemma 4B Multimodal Analyzer ───────────────────────────────────────────


class MedGemmaImageAnalyzer:
    """
    Multimodal image analysis using MedGemma 4B (google/medgemma-4b-it).

    Supports:
      - Detailed image description
      - Anatomical localization (finding features in X-rays)
      - Longitudinal comparison (current scan vs. prior report)
      - 3-D volume interpretation (CT / MRI narrative)
    """

    MODEL_ID = "google/medgemma-4b-it"

    # System prompt that situates the model in a radiology workflow
    _SYSTEM_PROMPT = (
        "You are an expert radiologist and clinical image analyst. "
        "Provide accurate, structured, clinically relevant interpretations. "
        "Always note key findings, pertinent negatives, and suggest follow-up "
        "if appropriate. Use standard radiological terminology."
    )

    def __init__(self, hf_token: Optional[str] = None, device: str = "cpu"):
        self._hf_token = hf_token
        self._device = device
        self._model = None
        self._processor = None

    # ------------------------------------------------------------------
    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            from transformers import AutoProcessor, AutoModelForImageTextToText  # type: ignore
            import torch  # type: ignore

            logger.info("Loading MedGemma 4B model…")
            kwargs: Dict = {
                "trust_remote_code": True,
                "torch_dtype": "auto",
            }
            if self._hf_token:
                kwargs["token"] = self._hf_token

            self._processor = AutoProcessor.from_pretrained(
                self.MODEL_ID, **{"token": self._hf_token} if self._hf_token else {}
            )
            self._model = AutoModelForImageTextToText.from_pretrained(
                self.MODEL_ID, **kwargs
            ).to(self._device)
            self._torch = torch
            logger.info("MedGemma 4B ready on %s", self._device)
        except Exception as exc:
            logger.error("Failed to load MedGemma 4B: %s", exc)
            raise

    # ------------------------------------------------------------------
    def _generate(self, messages: List[Dict], max_new_tokens: int = 512) -> str:
        """Run the model and return the generated text."""
        import torch  # type: ignore

        self._load()

        formatted = self._processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._processor(
            text=formatted,
            images=[m["image"] for m in messages if "image" in m],
            return_tensors="pt",
        ).to(self._device)

        with torch.no_grad():
            output_ids = self._model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
            )

        new_tokens = output_ids[0][inputs["input_ids"].shape[-1] :]
        return self._processor.decode(new_tokens, skip_special_tokens=True).strip()

    # ------------------------------------------------------------------
    def describe(
        self,
        image: Union[str, Path, bytes, "PIL.Image.Image"],  # type: ignore[name-defined]
        modality: str = "Chest X-Ray",
    ) -> str:
        """Generate a detailed radiological description of the image."""
        pil_img = load_image(image)
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": pil_img},
                    {
                        "type": "text",
                        "text": (
                            f"This is a {modality}. "
                            "Please provide a detailed, structured radiological report "
                            "including: (1) Image quality assessment, (2) Key findings, "
                            "(3) Pertinent negatives, (4) Impression, (5) Recommendations."
                        ),
                    },
                ],
            }
        ]
        return self._generate(messages)

    # ------------------------------------------------------------------
    def localize(
        self,
        image: Union[str, Path, bytes, "PIL.Image.Image"],  # type: ignore[name-defined]
        finding: str,
    ) -> str:
        """Anatomical localization – describe *where* a finding is in the image."""
        pil_img = load_image(image)
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": pil_img},
                    {
                        "type": "text",
                        "text": (
                            f"Please identify and describe the anatomical location of "
                            f'"{finding}" in this image. Be specific about lobe, zone, '
                            "laterality, and relationship to adjacent structures."
                        ),
                    },
                ],
            }
        ]
        return self._generate(messages)

    # ------------------------------------------------------------------
    def compare_with_prior(
        self,
        current_image: Union[str, Path, bytes, "PIL.Image.Image"],  # type: ignore[name-defined]
        prior_report_text: str,
        modality: str = "Chest X-Ray",
    ) -> str:
        """
        Longitudinal comparison: analyse the current scan in the context
        of a prior radiology report.
        """
        pil_img = load_image(current_image)
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": pil_img},
                    {
                        "type": "text",
                        "text": (
                            f"This is a current {modality}. "
                            f"The prior report states:\n\n{prior_report_text}\n\n"
                            "Please compare the current image with the prior report. "
                            "Describe: (1) Interval changes, (2) Stable findings, "
                            "(3) New findings, (4) Resolved findings, (5) Overall impression."
                        ),
                    },
                ],
            }
        ]
        return self._generate(messages)

    # ------------------------------------------------------------------
    def interpret_volume(
        self,
        image: Union[str, Path, bytes, "PIL.Image.Image"],  # type: ignore[name-defined]
        volume_type: str = "CT",
    ) -> str:
        """High-level narrative interpretation of a CT or MRI slice."""
        pil_img = load_image(image)
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": pil_img},
                    {
                        "type": "text",
                        "text": (
                            f"This is a {volume_type} image slice. "
                            "Provide a systematic interpretation including: "
                            "window/level assessment, organ/structure evaluation, "
                            "pathological findings, and clinical significance."
                        ),
                    },
                ],
            }
        ]
        return self._generate(messages)


# ── Gemini API fallback (for demo / when local models not available) ───────────


class GeminiVisionClient:
    """
    Lightweight wrapper around the Gemini API for image analysis.
    Used as a demo fallback when local MedGemma weights are not loaded.
    """

    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        self._api_key = api_key
        self._model_name = model_name

    def analyze(self, image_bytes: bytes, prompt: str) -> str:
        """Send an image + prompt to Gemini and return the response."""
        try:
            import google.generativeai as genai  # type: ignore

            genai.configure(api_key=self._api_key)
            model = genai.GenerativeModel(self._model_name)

            from PIL import Image  # type: ignore

            pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            response = model.generate_content([prompt, pil_img])
            return response.text.strip()
        except Exception as exc:
            logger.error("Gemini API call failed: %s", exc)
            return f"[Analysis unavailable: {exc}]"
