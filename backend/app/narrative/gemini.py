"""Optional Gemini narrative polish (CLAUDE.md §8) — multi-model × multi-key cascade.

Off by default (ENABLE_LLM_NARRATIVE=false). When enabled, tries to polish the
deterministic template into more fluent prose, in this order:

    for each API key (primary, then GEMINI_API_KEY_FALLBACK):
        for each model in GEMINI_MODEL_CASCADE (newest/most-capable first):
            try one generate_content call

The first candidate that returns usable text wins. Any failure — quota exhaustion,
a model name that doesn't exist on this account, a transient error — just moves to
the next (model, key) pair. Only once EVERY model has failed on EVERY key does it
fall back to the deterministic template. A single SQLite-persisted counter
(usage_store.py) hard-caps the whole cascade at gemini_max_calls raw API calls,
surviving process restarts; once exhausted, this function is a no-op that returns
the template immediately.

Only computed aggregates (band, sub-scores, reason codes, cross-validation flags,
limit) are ever sent to the model — never raw GST/UPI/bank/EPFO rows (§8).
"""

from __future__ import annotations

from backend.app.config import GEMINI_MODEL_CASCADE, settings
from backend.app.narrative.usage_store import GeminiUsageStore

try:
    from google import genai
    from google.genai import errors as genai_errors
    from google.genai import types as genai_types
except ImportError:  # pragma: no cover - google-genai is a required dep, but stay
    genai = None      # graceful if a dev environment hasn't installed it yet.
    genai_errors = None
    genai_types = None


def _build_prompt(payload: dict, base_text: str) -> str:
    cross = payload["cross_validation"]
    limit = payload["limit_recommendation"]
    reasons = payload.get("reason_codes", [])
    reason_lines = "\n".join(f"- {r['direction']}: {r['evidence']}" for r in reasons)
    flag_lines = "\n".join(f"- {f['code']}: {f['evidence']}" for f in cross["flags"])

    return (
        "You are polishing a credit officer's summary for an MSME loan applicant. "
        "Rewrite the DRAFT below into 3-4 fluent, professional sentences for a bank "
        "credit officer. Use ONLY the figures given — never invent, adjust, or "
        "estimate any number. Do not add caveats not present in the data below.\n\n"
        f"SETU score: {payload['setu_score']} ({payload['band']})\n"
        f"Sub-scores: {payload['sub_scores']}\n"
        f"Reason codes:\n{reason_lines}\n"
        f"Cross-validation consistency: {cross['consistency_score']}/100\n"
        f"Cross-validation flags:\n{flag_lines or '- none'}\n"
        f"Limit recommendation: INR {limit['amount_inr']} over {limit['tenor_months']} months "
        f"({limit['basis']})\n"
        f"Recommendation: {payload['recommendation']}\n\n"
        f"DRAFT:\n{base_text}\n\n"
        "Rewritten summary:"
    )


def _api_keys() -> list[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    if settings.gemini_api_key:
        keys.append(("primary", settings.gemini_api_key))
    if settings.gemini_api_key_fallback:
        keys.append(("fallback", settings.gemini_api_key_fallback))
    return keys


def estimate_worst_case_cost_note() -> str:
    """One line for the startup log (§8): the cap makes the worst case bounded and
    tiny even on paid rates."""
    n = settings.gemini_max_calls
    return (
        f"Gemini narrative ENABLED — hard cap {n} raw calls (SQLite-persisted, "
        f"survives restarts), max {settings.gemini_max_output_tokens} output tokens/call, "
        f"cascading over {len(GEMINI_MODEL_CASCADE)} models x "
        f"{len(_api_keys())} key(s). Worst case at free-tier AI Studio rates: Rs.0. "
        f"Even at paid rates this stays well under the Rs.300 POC budget cap."
    )


def polish_narrative(payload: dict, base_text: str) -> tuple[str, str]:
    """Returns (text, source) where source is 'gemini' or 'template'."""
    if not settings.enable_llm_narrative or genai is None:
        return base_text, "template"

    keys = _api_keys()
    if not keys:
        return base_text, "template"

    usage = GeminiUsageStore()
    if usage.remaining(settings.gemini_max_calls) <= 0:
        return base_text, "template"

    prompt = _build_prompt(payload, base_text)
    config = genai_types.GenerateContentConfig(
        max_output_tokens=settings.gemini_max_output_tokens,
        temperature=0.4,
        # Several current Gemini models "think" before answering, silently spending
        # part of max_output_tokens on invisible reasoning tokens and truncating the
        # visible answer. We want the whole budget to go to the officer-facing text,
        # so thinking is switched off wherever the model supports it; models that
        # don't recognise this field just ignore it or error (caught, cascade moves on).
        thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
    )

    for key_label, api_key in keys:
        try:
            client = genai.Client(api_key=api_key)
        except Exception:
            continue

        for model_name in GEMINI_MODEL_CASCADE:
            if usage.remaining(settings.gemini_max_calls) <= 0:
                return base_text, "template"
            try:
                response = client.models.generate_content(
                    model=model_name, contents=prompt, config=config,
                )
                usage.record(key_label, model_name, "success")
                text = (response.text or "").strip()
                if text:
                    return text, "gemini"
                # empty completion — treat like a failure, try the next candidate
            except genai_errors.APIError:
                # server responded (quota exhausted, model not found/retired,
                # permission denied, etc.) — a real round trip, so it counts.
                usage.record(key_label, model_name, "error")
            except Exception:
                # transport/connection failure before reaching the server — don't
                # burn budget on it, just try the next candidate.
                pass

    return base_text, "template"
