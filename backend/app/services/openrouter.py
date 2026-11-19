import httpx


class OpenRouterError(RuntimeError):
    pass


async def generate_answer(api_key: str, models: list[str], base_url: str, timeout: int,
                          message: str, history: list[dict], context: list[dict]) -> tuple[str, str]:
    if not api_key:
        raise OpenRouterError("OPENROUTER_API_KEY is not configured")

    source_text = "\n\n".join(
        f"[Source {i + 1}: {item.get('title', 'Untitled')} - {item.get('url', '')}]\n{item.get('text', item.get('excerpt', ''))}"
        for i, item in enumerate(context)
    )
    system = (
        "You are PropertyIQ, a grounded real estate assistant. Use only the supplied source context. "
        "Never invent prices, availability, amenities, locations, or project specifications. "
        "If the context does not answer the question, say that the publicly available information does not contain it. "
        "Use concise answers and refer to sources by title and URL."
    )
    messages = [{"role": "system", "content": system + "\n\nSOURCE CONTEXT:\n" + (source_text or "No relevant documents retrieved.")}]
    for item in history[-12:]:
        role = item.get("role")
        content = item.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})

    async with httpx.AsyncClient(timeout=timeout) as client:
        last_error = None
        errors = []
        for model in models:
            try:
                response = await client.post(
                    base_url.rstrip("/") + "/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "HTTP-Referer": "http://localhost",
                             "X-Title": "PropertyIQ"},
                    json={"model": model, "messages": messages, "temperature": 0.2},
                )
                if response.status_code >= 400:
                    raise OpenRouterError(f"OpenRouter returned HTTP {response.status_code}: {response.text[:300]}")
                data = response.json()
                answer = data["choices"][0]["message"]["content"]
                return answer, model
            except (httpx.HTTPError, KeyError, IndexError, OpenRouterError) as exc:
                last_error = exc
                errors.append(f"{model}: {exc}")
        details = "; ".join(errors)
        raise OpenRouterError(f"OpenRouter request failed for all configured models: {details or last_error}")
