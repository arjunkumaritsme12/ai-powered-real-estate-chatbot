import httpx


class AIProviderError(RuntimeError):
    pass


OpenRouterError = AIProviderError


def _build_messages(message: str, history: list[dict], context: list[dict]) -> list[dict[str, str]]:
    source_text = "\n\n".join(
        f"[Source {i + 1}: {item.get('title', 'Untitled')} - {item.get('url', '')}]\n"
        f"{item.get('text', item.get('excerpt', ''))}"
        for i, item in enumerate(context)
    )
    system = (
        "You are PropertyIQ, a friendly, professional real-estate assistant. "
        "Reply in the user's language and keep answers clear and useful. "
        "For current listings, prices, availability, and specific developer or project facts, "
        "use only the supplied source context. Never guess or present outdated model knowledge as current. "
        "If sources do not verify a requested current property fact, say so plainly and do not invent it. "
        "For general questions unrelated to current listing facts, answer helpfully using general knowledge. "
        "Cite source URLs for property facts taken from the supplied context."
    )
    messages = [{
        "role": "system",
        "content": f"{system}\n\nSOURCE CONTEXT:\n{source_text or 'No relevant property sources were retrieved.'}",
    }]
    for item in history[-12:]:
        role = item.get("role")
        content = item.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})
    return messages


async def _generate_from_models(
    api_key: str,
    models: list[str],
    base_url: str,
    timeout: int,
    messages: list[dict[str, str]],
    provider: str,
) -> tuple[str, str]:
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if provider == "openrouter":
        headers.update({"HTTP-Referer": "https://propertyiq.onrender.com", "X-Title": "PropertyIQ"})

    errors = []
    async with httpx.AsyncClient(timeout=timeout) as client:
        for model in models:
            payload = {"model": model, "messages": messages, "temperature": 0.2, "max_tokens": 900}
            if provider == "gemini":
                payload["reasoning_effort"] = "low"
            try:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code >= 400:
                    errors.append(f"{model}: HTTP {response.status_code}: {response.text[:250]}")
                    continue
                data = response.json()
                answer = data["choices"][0]["message"]["content"]
                if not isinstance(answer, str) or not answer.strip():
                    errors.append(f"{model}: provider returned an empty text response")
                    continue
                return answer.strip(), model
            except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
                errors.append(f"{model}: {exc}")

    raise AIProviderError(f"{provider} models failed: {'; '.join(errors)}")


async def generate_answer(
    message: str,
    history: list[dict],
    context: list[dict],
    *,
    preferred_provider: str,
    gemini_api_key: str,
    gemini_models: list[str],
    gemini_base_url: str,
    openrouter_api_key: str,
    openrouter_models: list[str],
    openrouter_base_url: str,
    timeout: int,
) -> tuple[str, str]:
    messages = _build_messages(message, history, context)
    credentials = {
        "gemini": (gemini_api_key, gemini_models, gemini_base_url),
        "openrouter": (openrouter_api_key, openrouter_models, openrouter_base_url),
    }
    configured = [
        provider for provider in [preferred_provider, "openrouter" if preferred_provider == "gemini" else "gemini"]
        if credentials[provider][0]
    ]
    if not configured:
        raise AIProviderError("Configure GEMINI_API_KEY or OPENROUTER_API_KEY to enable AI answers.")

    errors = []
    for provider in configured:
        api_key, models, base_url = credentials[provider]
        try:
            return await _generate_from_models(api_key, models, base_url, timeout, messages, provider)
        except AIProviderError as exc:
            errors.append(str(exc))

    raise AIProviderError("All configured AI providers failed: " + "; ".join(errors))
