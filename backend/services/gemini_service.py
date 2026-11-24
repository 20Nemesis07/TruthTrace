import json
import re
import httpx
from ..config import ROOT, provider


class ModelUnavailable(Exception):
    pass


def provider_error(response, key):
    try:
        error = response.json().get("error", {})
    except (ValueError, AttributeError):
        return ""
    if not isinstance(error, dict):
        return ""
    detail = " ".join(str(error.get(k) or "") for k in ("code", "message")).strip()
    detail = detail.replace(key, "[redacted]") if key else detail
    return re.sub(r"gsk_[A-Za-z0-9_-]+", "[redacted]", detail)[:400]


async def interpret(prompt, data, schema):
    name, model, key = provider()
    if not key:
        raise ModelUnavailable("No configured " + name + " key.")
    if (
        not re.fullmatch(r"[\w./-]+", model)
        or ".." in model
        or (name == "gemini" and "/" in model)
    ):
        raise ModelUnavailable("Invalid model name.")
    instructions = (
        prompt + "\nOutput JSON schema:\n" + json.dumps(schema.model_json_schema())
    )
    user = json.dumps(data, ensure_ascii=False)
    if name == "gemini":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {"x-goog-api-key": key}
        body = {
            "systemInstruction": {"parts": [{"text": instructions}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0,
            },
        }
    else:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": "Bearer " + key}
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }
    if name == "groq" and model in {"openai/gpt-oss-20b","openai/gpt-oss-120b"}:
        shape = schema.model_json_schema()
        for obj in [shape, *shape.get("$defs", {}).values()]:
            if obj.get("type") == "object":
                obj["additionalProperties"] = False
        body["response_format"] = {"type":"json_schema","json_schema":{
            "name":schema.__name__, "strict":True, "schema":shape}}
    try:
        async with httpx.AsyncClient(timeout=35, follow_redirects=False) as client:
            response = await client.post(url, headers=headers, json=body)
            if name == "groq" and response.status_code == 400:
                detail = provider_error(response, key).lower()
                format_error = any(term in detail for term in ("json_validate_failed", "json schema", "response_format", "failed to generate json", "json_schema"))
                if format_error:
                    # Retry once using prompt-guided JSON. The same local schema and evidence checks still apply.
                    body.pop("response_format", None)
                    response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
        payload = response.json()
        text = (
            "".join(
                x.get("text", "")
                for x in payload["candidates"][0]["content"]["parts"]
                if not x.get("thought")
            )
            if name == "gemini"
            else payload["choices"][0]["message"]["content"]
        )
        return schema.model_validate_json(text)
    except httpx.HTTPStatusError as exc:
        code=exc.response.status_code
        advice={400:"The provider rejected the request format or model configuration.",
                401:"Check the API key in .env and restart the backend.",
                403:"Check project permissions for the configured model.",
                404:"Check the model name and availability in your provider console.",
                413:"The request is too large for the provider.",
                429:"The project reached a rate or quota limit. Check its usage limits before retrying."}
        detail = provider_error(exc.response, key)
        raise ModelUnavailable(f"{name} HTTP {code}. " + (detail or advice.get(code,"Check the provider status and retry."))) from exc
    except httpx.TimeoutException as exc:
        raise ModelUnavailable(f"{name} timed out. Retry the verification.") from exc
    except httpx.RequestError as exc:
        raise ModelUnavailable(f"Could not connect to {name}. Check internet and proxy settings.") from exc
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        raise ModelUnavailable(f"{name} responded, but the response did not match the required assessment format.") from exc


def prompt(stage):
    return (ROOT / "backend/prompts" / (stage + ".txt")).read_text(encoding="utf-8")
