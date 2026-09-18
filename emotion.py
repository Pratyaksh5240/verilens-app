"""Emotion classification using HuggingFace Transformers with robust fallback and audit logging.

Features:
- Loads 'j-hartmann/emotion-english-distilroberta-base' with top_k=None (replacing deprecated return_all_scores).
- Cached model loading via functools.lru_cache.
- Detailed Python logging for model loading errors and inference exceptions.
- Heuristic keyword fallback when Transformers/PyTorch is unavailable.
- Structured diagnostics output informing the UI and scoring engine of the active mode.
"""

import logging
from functools import lru_cache
from typing import Dict, Optional, Tuple

logger = logging.getLogger("verilens.emotion")

# Track the reason why the ML model is not in use (if any)
_MODEL_LOAD_ERROR: Optional[str] = None


@lru_cache(maxsize=1)
def load_emotion_pipeline():
    """Load the HuggingFace text-classification pipeline with top_k=None.

    Returns:
        Optional[pipeline]: Loaded pipeline, or None if unavailable.
    """
    global _MODEL_LOAD_ERROR
    try:
        from transformers import pipeline

        logger.info("Initializing HuggingFace emotion classification pipeline...")
        nlp = pipeline(
            "text-classification",
            model="j-hartmann/emotion-english-distilroberta-base",
            top_k=None,
            truncation=True,
            max_length=512,
        )
        _MODEL_LOAD_ERROR = None
        logger.info("Emotion classification pipeline loaded successfully.")
        return nlp
    except ImportError as exc:
        _MODEL_LOAD_ERROR = f"Transformers or PyTorch is not installed ({exc})."
        logger.warning("ML emotion model unavailable: %s", _MODEL_LOAD_ERROR)
        return None
    except Exception as exc:
        _MODEL_LOAD_ERROR = f"Model load failure: {exc}"
        logger.error("Failed to load emotion model from HuggingFace hub: %s", exc, exc_info=True)
        return None


def detect_emotion_fallback(text: str) -> Tuple[str, float]:
    """Analyze emotional tone via heuristic keyword matching when ML pipeline is unavailable.

    Returns:
        Tuple[str, float]: (dominant_emotion_label, confidence_score).
    """
    text_lower = (text or "").lower()

    lexicon = {
        "fear": [
            "panic", "danger", "fear", "terrified", "scared", "threat", "warning",
            "crisis", "collapse", "alarming", "deadly", "fatal", "horror"
        ],
        "anger": [
            "outrage", "angry", "rage", "corrupt", "fraud", "shocking", "furious",
            "scandal", "treason", "disgrace", "shameful", "betrayal"
        ],
        "joy": [
            "happy", "celebrate", "win", "success", "hope", "joy", "triumph",
            "breakthrough", "achievement", "delight", "proud"
        ],
        "sadness": [
            "sad", "tragic", "death", "grief", "loss", "cry", "mourn",
            "heartbroken", "casualty", "devastation", "sorrow"
        ],
        "surprise": [
            "unexpected", "astonishing", "shock", "unbelievable", "stunned",
            "staggering", "unprecedented"
        ],
    }

    scores = {label: sum(word in text_lower for word in words) for label, words in lexicon.items()}
    top_label = max(scores, key=scores.get)
    hit_count = scores[top_label]

    if hit_count == 0:
        return "neutral", 0.50

    confidence = min(0.92, 0.50 + hit_count * 0.08)
    return top_label, round(confidence, 2)


def get_emotion_intensity(label: str, score: float) -> str:
    """Determine the emotional intensity level based on label and confidence."""
    if label == "neutral":
        return "Low"
    if score >= 0.75:
        return "High"
    if score >= 0.55:
        return "Moderate"
    return "Low"


def analyze_emotion(text: str) -> Dict[str, object]:
    """Perform emotion detection with ML pipeline first, falling back to heuristic keyword analysis.

    Returns:
        Dict[str, object] containing:
            - label: Dominant emotion (e.g. 'fear', 'anger', 'neutral')
            - score: Confidence score (0.0 - 1.0)
            - is_ml: True if HuggingFace transformer was used, False if fallback
            - mode_description: Human-readable string for the active model
            - fallback_reason: Explanation if fallback was used, otherwise None
            - intensity: 'High', 'Moderate', or 'Low'
            - diagnostics_note: Explanatory note emphasizing that emotion is a rhetorical signal, not proof of falsity.
    """
    if not text or not text.strip():
        return {
            "label": "neutral",
            "score": 0.50,
            "is_ml": False,
            "mode_description": "None (empty text)",
            "fallback_reason": "No text provided for analysis.",
            "intensity": "Low",
            "diagnostics_note": "No text available.",
        }

    pipeline_model = load_emotion_pipeline()

    if pipeline_model is None:
        label, score = detect_emotion_fallback(text)
        intensity = get_emotion_intensity(label, score)
        return {
            "label": label,
            "score": score,
            "is_ml": False,
            "mode_description": "Keyword Heuristic Fallback",
            "fallback_reason": _MODEL_LOAD_ERROR or "ML model pipeline not loaded.",
            "intensity": intensity,
            "diagnostics_note": (
                "Emotional intensity is an editorial framing diagnostic. High emotion (such as fear during a disaster) "
                "reflects narrative tone, not necessarily factual unreliability."
            ),
        }

    try:
        # Evaluate up to 512 tokens (~2000 chars)
        clipped_text = text[:2048]
        output = pipeline_model(clipped_text)

        # In modern transformers with top_k=None, output is List[List[Dict[str, Any]]] or List[Dict[str, Any]]
        if output and isinstance(output[0], list):
            predictions = output[0]
        elif isinstance(output, list):
            predictions = output
        else:
            predictions = [output]

        top_pred = max(predictions, key=lambda item: item.get("score", 0.0))
        label = str(top_pred.get("label", "neutral")).lower()
        score = float(top_pred.get("score", 0.50))
        intensity = get_emotion_intensity(label, score)

        return {
            "label": label,
            "score": round(score, 3),
            "is_ml": True,
            "mode_description": "HuggingFace DistilRoBERTa (j-hartmann)",
            "fallback_reason": None,
            "intensity": intensity,
            "diagnostics_note": (
                "Emotional intensity is an editorial framing diagnostic. High emotion (such as fear during a disaster) "
                "reflects narrative tone, not necessarily factual unreliability."
            ),
        }
    except Exception as exc:
        logger.error("Transformer inference failed: %s; falling back to heuristic", exc, exc_info=True)
        label, score = detect_emotion_fallback(text)
        intensity = get_emotion_intensity(label, score)
        return {
            "label": label,
            "score": score,
            "is_ml": False,
            "mode_description": "Keyword Heuristic Fallback",
            "fallback_reason": f"Inference failure: {exc}",
            "intensity": intensity,
            "diagnostics_note": (
                "Emotional intensity is an editorial framing diagnostic. High emotion (such as fear during a disaster) "
                "reflects narrative tone, not necessarily factual unreliability."
            ),
        }
