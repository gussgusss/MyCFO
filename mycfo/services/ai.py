from __future__ import annotations

import json
from urllib import error, request

from flask import current_app

from ..errors import APIError


def build_alert_suggestions(*, workspace_name: str, metrics: dict, alerts: list[dict]) -> dict:
    if not alerts:
        return {
            "summary": "No active alerts. The business appears stable based on the current alert rules.",
            "suggestions": [],
            "grounding": {
                "workspace_name": workspace_name,
                "alert_count": 0,
                "alerts": [],
            },
            "provider": "none",
            "model": None,
        }

    api_key = current_app.config.get("HUGGINGFACE_API_KEY")
    if not api_key:
        raise APIError(
            status_code=503,
            error_type="configuration_error",
            code="huggingface_not_configured",
            message="HUGGINGFACE_API_KEY is not configured.",
        )

    model = current_app.config["HUGGINGFACE_MODEL"]
    prompt = _build_prompt(workspace_name=workspace_name, metrics=metrics, alerts=alerts)
    body = {
        "model": model,
        "messages": [
        {
            "role": "user",
            "content": prompt,
        }
        ],
        "max_tokens": 350,
        "temperature": 0.3,
    }
    req = request.Request(
        url="https://router.huggingface.co/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "mycfo-api/1.0",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=current_app.config["HUGGINGFACE_TIMEOUT_SECONDS"]) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise APIError(
            status_code=502,
            error_type="upstream_error",
            code="huggingface_request_failed",
            message=f"Hugging Face inference request failed: {detail or exc.reason}",
        ) from exc
    except error.URLError as exc:
        raise APIError(
            status_code=502,
            error_type="upstream_error",
            code="huggingface_unreachable",
            message="Could not reach Hugging Face inference API.",
        ) from exc

    return _normalize_response(raw=raw, alerts=alerts, workspace_name=workspace_name, model=model)


def _build_prompt(*, workspace_name: str, metrics: dict, alerts: list[dict]) -> str:
    prompt_payload = {
        "workspace_name": workspace_name,
        "metrics": {
            "mrr_cents": metrics.get("mrr_cents"),
            "arr_cents": metrics.get("arr_cents"),
            "net_revenue_cents_30d": metrics.get("net_revenue_cents_30d"),
            "burn_cents_30d": metrics.get("burn_cents_30d"),
            "cash_on_hand_cents": metrics.get("cash_on_hand_cents"),
            "runway_months": metrics.get("runway_months"),
            "warnings": metrics.get("warnings", []),
        },
        "alerts": alerts,
    }
    return (
        "You are a CFO copilot. Use only the provided metrics and alerts. "
        "Do not invent facts or metrics. Return strict JSON with keys: "
        "summary (string), suggestions (array of objects with title, rationale, priority, expected_impact), "
        "and risks (array of strings).\n\n"
        f"INPUT:\n{json.dumps(prompt_payload, sort_keys=True)}"
    )


def _normalize_response(*, raw: str, alerts: list[dict], workspace_name: str, model: str) -> dict:
    parsed = json.loads(raw)
    generated_text = _extract_generated_text(parsed)

    if generated_text is None:
        raise APIError(
            status_code=502,
            error_type="upstream_error",
            code="huggingface_invalid_response",
            message="Hugging Face returned an unexpected response shape.",
        )

    json_text = _extract_json_block(generated_text)
    try:
        content = json.loads(json_text)
    except json.JSONDecodeError:
        content = {
            "summary": generated_text.strip(),
            "suggestions": [],
            "risks": [],
        }

    content.setdefault("summary", "")
    content.setdefault("suggestions", [])
    content.setdefault("risks", [])
    content["grounding"] = {
        "workspace_name": workspace_name,
        "alert_count": len(alerts),
        "alerts": alerts,
    }
    content["provider"] = "huggingface"
    content["model"] = model
    return content


def _extract_generated_text(parsed: object) -> str | None:
    if isinstance(parsed, dict):
        if "choices" in parsed and parsed["choices"]:
            return parsed["choices"][0]["message"]["content"]
        if "error" in parsed:
            raise APIError(
                status_code=502,
                error_type="upstream_error",
                code="huggingface_model_error",
                message=f"Hugging Face returned an error: {parsed['error']}",
            )
    return None


def _extract_json_block(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return text
    return text[start : end + 1]
