import openai

# Capture original ChatCompletion.acreate
ORIG_ACREATE = openai.ChatCompletion.acreate

import json
import hashlib
from cachetools import LRUCache

# In-memory LRU cache for quick lookups
# MongoDB persistent cache for cross-restart persistence
import os
from motor.motor_asyncio import AsyncIOMotorClient

# Setup MongoDB persistent cache if URL is provided and reachable
_mongo_url = os.getenv("MONGO_URL")
_db_name = os.getenv("DB_NAME", "openhands_cache")
MONGO_ENABLED = False
if _mongo_url:
    try:
        # Allow invalid certs if needed (e.g., self-signed or Atlas SSL issues)
        _mongo_client = AsyncIOMotorClient(
            _mongo_url,
            tls=True,
            tlsAllowInvalidCertificates=True
        )
        _mongo_db = _mongo_client[_db_name]
        _mongo_cache = _mongo_db.get_collection("openai_cache")
        MONGO_ENABLED = True
    except Exception:
        # Could not connect to Mongo, disable persistent cache
        MONGO_ENABLED = False

# Ensure index on _id for quick lookups
# (Optionally you could add TTL indexes against a timestamp field)
async def _ensure_indexes():
    try:
        await _mongo_cache.create_index("_id", unique=True)
    except Exception:
        pass

# Schedule index creation if MongoDB persistence is enabled
import asyncio
if MONGO_ENABLED:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_ensure_indexes())
    except Exception:
        try:
            asyncio.run(_ensure_indexes())
        except Exception:
            pass

from cachetools import LRUCache

target_cache = LRUCache(maxsize=256)

# Summarization settings
MAX_HISTORY = 6
SUMMARY_MODEL = "gpt-3.5-turbo"


def _make_cache_key(model: str, messages: list, **kwargs) -> str:
    payload = {"model": model, "messages": messages, **kwargs}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


from types import SimpleNamespace


def _dict_to_obj(data):
    """
    Recursively convert a dict/list structure into SimpleNamespace objects.
    """
    if isinstance(data, dict):
        return SimpleNamespace(**{k: _dict_to_obj(v) for k, v in data.items()})
    if isinstance(data, list):
        return [_dict_to_obj(item) for item in data]
    return data


async def acreate_cached(model: str, messages: list, **kwargs):
    """
    Call OpenAI ChatCompletion.acreate with both in-memory and MongoDB persistence.
    """
    key = _make_cache_key(model, messages, **kwargs)
    # First check in-memory cache
    if key in target_cache:
        return target_cache[key]
    # Next check persistent Mongo cache
    try:
        doc = await _mongo_cache.find_one({"_id": key})
        if doc:
            cached_obj = _dict_to_obj(doc["response"])
            target_cache[key] = cached_obj
            return cached_obj
    except Exception:
        pass
    # Not cached: perform actual API call
    response = await ORIG_ACREATE(model=model, messages=messages, **kwargs)
    # Persist to Mongo
    try:
        data = response.to_dict() if hasattr(response, 'to_dict') else dict(response)
        await _mongo_cache.insert_one({"_id": key, "response": data})
    except Exception:
        pass
    # Store in-memory
    target_cache[key] = response
    return response


import hashlib

_aux_sent = set()
DEFAULT_SYS_PROMPT = "You are a helpful AI assistant."

def build_payload(user_content: str, include_aux: bool = False, aux_prompt: str = None) -> list:
    """
    Build message payload with optional auxiliary injection.
    Inserts DEFAULT_SYS_PROMPT as the base system message.
    Only injects aux_prompt once per unique content.
    """
    payload = [{"role": "system", "content": DEFAULT_SYS_PROMPT}]
    if include_aux and aux_prompt:
        key = hashlib.sha256(aux_prompt.encode()).hexdigest()
        if key not in _aux_sent:
            payload.append({"role": "system", "content": aux_prompt})
            _aux_sent.add(key)
    payload.append({"role": "user", "content": user_content})
    return payload

async def acreate_with_summary_and_cache(model: str, messages: list, **kwargs):
    """
    Summarize long histories and then cache the result persistently.
    """
    msgs = await summarize_messages(messages)
    return await acreate_cached(model, msgs, **kwargs)

# Apply global monkey-patch so all ChatCompletion.acreate calls use our wrapper
openai.ChatCompletion.acreate = acreate_with_summary_and_cache



                  


async def summarize_messages(messages: list) -> list:
    """
    If messages exceed MAX_HISTORY, summarize older turns into one summary message.
    """
    if len(messages) <= MAX_HISTORY:
        return messages
    # Summarize older messages
    old = messages[:-MAX_HISTORY]
    summary_prompt = [{"role": "system", "content": f"Summarize the following in <=50 tokens:"}]
    summary_prompt.extend(old)
    summary_resp = await acreate_cached(SUMMARY_MODEL, summary_prompt, temperature=0.3)
    summary_text = summary_resp.choices[0].message.content.strip()
    # Compose new message list
    return [{"role": "system", "content": f"SUMMARY: {summary_text}"}] + messages[-MAX_HISTORY:]
