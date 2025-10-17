import global_settings
import aiohttp
import asyncio

# Use Claude Sonnet 4
MODEL_ID = "claude-sonnet-4-20250514"


async def ask_claude(message: str) -> str:
    """
    Send a message to Claude Sonnet 4 API and return the response text.
    Args:
        message (str): The user's question or prompt.
    Returns:
        str: The response from Claude.
    """
    api_key = getattr(global_settings, "ANTHROPIC_API_KEY", None)
    if not api_key:
        raise RuntimeError(
            "Anthropic API key not found in global_settings.ANTHROPIC_API_KEY"
        )

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL_ID,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": message}],
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Claude API error: {resp.status} {text}")
            data = await resp.json()
            return data["content"][0]["text"].strip()
