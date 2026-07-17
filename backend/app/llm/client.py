"""Wrapper Anthropic : prompt caching, retry, appel JSON structuré."""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from anthropic import AsyncAnthropic
from anthropic.types import TextBlock
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL

logger = logging.getLogger(__name__)

_client: Optional[AsyncAnthropic] = None


def client() -> AsyncAnthropic:
    global _client
    if _client is None:
        if not ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY non défini. Ajoute-le dans .env")
        # Timeout explicite : le défaut du SDK est de 10 MINUTES — une requête qui
        # traîne bloquait un slot du scoring pendant tout ce temps (scoring qui rampe).
        # 90 s suffisent largement (le plus gros appel = génération CV ~8k tokens).
        _client = AsyncAnthropic(
            api_key=ANTHROPIC_API_KEY,
            timeout=90.0,
            max_retries=2,
        )
    return _client


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
async def complete(
    system: str | list[dict[str, Any]],
    user: str,
    max_tokens: int = 2000,
    temperature: float = 0.3,
    model: Optional[str] = None,
) -> str:
    """Appel simple, renvoie le texte concaténé."""
    sys_param = system if isinstance(system, list) else [{"type": "text", "text": system}]
    resp = await client().messages.create(
        model=model or ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        system=sys_param,
        messages=[{"role": "user", "content": user}],
    )
    parts: list[str] = []
    for block in resp.content:
        if isinstance(block, TextBlock):
            parts.append(block.text)
    return "".join(parts)


async def complete_json(
    system: str | list[dict[str, Any]],
    user: str,
    max_tokens: int = 2000,
    model: Optional[str] = None,
) -> dict[str, Any]:
    """Appel avec prompt 'répond en JSON uniquement'. Extrait le JSON du texte."""
    json_rule = "Tu dois répondre UNIQUEMENT avec du JSON valide, sans texte avant ni après, sans ```json."
    if isinstance(system, str):
        full_system: str | list[dict[str, Any]] = system + "\n\n" + json_rule
    else:
        # Ajoute la consigne en dernier bloc (non-caché → pas de pénalité).
        full_system = list(system) + [{"type": "text", "text": json_rule}]
    text = await complete(full_system, user, max_tokens=max_tokens, temperature=0.2, model=model)
    text = text.strip()
    # Strip markdown fences si le modèle en ajoute malgré tout
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error("LLM JSON invalide: %s", text[:500])
        # Dernier recours : chercher le premier { et le dernier }
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start : end + 1])
        raise


def cached_system(parts: list[str]) -> list[dict[str, Any]]:
    """Construit un system prompt avec un cache breakpoint sur CHAQUE bloc.

    Tout ce qui est en `system` est stable d'un appel à l'autre, donc cacheable.
    Un breakpoint en fin de chaque bloc permet à Anthropic de cacher tout ce qui
    précède. Max 4 breakpoints par requête — on garde au plus 4 blocs.
    """
    parts = [p for p in parts if p and p.strip()]
    if len(parts) > 4:
        # Fusionne les blocs en trop dans le 1er (le moins susceptible de changer)
        parts = ["\n\n".join(parts[: len(parts) - 3]), *parts[len(parts) - 3 :]]
    blocks: list[dict[str, Any]] = []
    for p in parts:
        blocks.append({"type": "text", "text": p, "cache_control": {"type": "ephemeral"}})
    return blocks
