"""Key pool management with automatic failover, cooldowns, and hot-reloading.

Supports multi-key environment variables:
  GROQ_API_KEYS=key1,key2,...
  OPENROUTER_API_KEYS=key1,key2,...
  GEMINI_API_KEYS=key1,key2,...
While maintaining backward compatibility with single-key variables:
  GROQ_API_KEY, OPENROUTER_API_KEY, PLATFORM_API_KEY, GEMINI_API_KEY.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("copilot.key_pool")


@dataclass
class ManagedKey:
    key: str
    provider: str
    masked_id: str
    exhausted: bool = False
    cooldown_until: float = 0.0
    failure_count: int = 0
    last_reason: Optional[str] = None


class KeyPool:
    """Manages API keys per provider with failover, 429 cooldowns, and hot-reload."""

    def __init__(self, env_path: Optional[Path | str] = None):
        self.env_path = Path(env_path) if env_path else Path(__file__).resolve().parents[2] / ".env"
        self._keys_by_provider: Dict[str, List[ManagedKey]] = {
            "groq": [],
            "openrouter": [],
            "gemini": [],
            "openai": [],
            "anthropic": [],
        }
        self.reload_from_env()

    def reload_from_env(self) -> None:
        """Re-read .env and update key pool, preserving status of existing keys."""
        if not self.env_path.exists():
            return

        env_vars: Dict[str, str] = {}
        try:
            for line in self.env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip().strip("'\"")
        except Exception as e:
            logger.warning("Failed to read .env file for key pool: %s", e)

        provider_mappings = {
            "groq": ["GROQ_API_KEYS", "GROQ_API_KEY"],
            "openrouter": ["OPENROUTER_API_KEYS", "OPENROUTER_API_KEY", "PLATFORM_API_KEY"],
            "gemini": ["GEMINI_API_KEYS", "GEMINI_API_KEY", "GOOGLE_API_KEY"],
            "openai": ["OPENAI_API_KEYS", "OPENAI_API_KEY"],
            "anthropic": ["ANTHROPIC_API_KEYS", "ANTHROPIC_API_KEY"],
        }

        for provider, var_names in provider_mappings.items():
            discovered_keys: List[str] = []
            for var_name in var_names:
                raw_val = env_vars.get(var_name) or os.getenv(var_name, "")
                if raw_val:
                    for k in raw_val.split(","):
                        k_clean = k.strip()
                        if k_clean and k_clean not in discovered_keys:
                            discovered_keys.append(k_clean)

            existing_map = {mk.key: mk for mk in self._keys_by_provider.get(provider, [])}
            updated_list: List[ManagedKey] = []
            for k in discovered_keys:
                if k in existing_map:
                    updated_list.append(existing_map[k])
                else:
                    masked = f"...{k[-4:]}" if len(k) >= 4 else "..."
                    updated_list.append(ManagedKey(key=k, provider=provider, masked_id=masked))

            self._keys_by_provider[provider] = updated_list

    def get_active_key(self, provider: str) -> Optional[ManagedKey]:
        """Get the first active (non-exhausted, non-cooldown) key for a provider."""
        now = time.time()
        keys = self._keys_by_provider.get(provider, [])

        # 1. Try to find a ready key
        for mk in keys:
            if not mk.exhausted and now >= mk.cooldown_until:
                return mk

        # 2. If all exhausted or cooling down, try reloading .env in case user added a key
        self.reload_from_env()
        keys = self._keys_by_provider.get(provider, [])
        for mk in keys:
            if not mk.exhausted and now >= mk.cooldown_until:
                return mk

        return None

    def mark_key_exhausted(
        self,
        provider: str,
        key: str,
        reason: str,
        cooldown_s: Optional[float] = None,
    ) -> None:
        """Mark a key exhausted or under cooldown. Logs ONLY provider and masked key id."""
        keys = self._keys_by_provider.get(provider, [])
        for mk in keys:
            if mk.key == key:
                mk.failure_count += 1
                mk.last_reason = reason
                if cooldown_s is not None:
                    mk.cooldown_until = time.time() + cooldown_s
                    logger.warning(
                        "Key %s for provider %s hit rate limit (%s). In cooldown for %.1fs",
                        mk.masked_id,
                        provider,
                        reason,
                        cooldown_s,
                    )
                else:
                    mk.exhausted = True
                    logger.warning(
                        "Key %s for provider %s marked exhausted (reason: %s). Switching to next key/provider.",
                        mk.masked_id,
                        provider,
                        reason,
                    )
                break

    def reload_keys(self) -> Dict[str, int]:
        """Explicit hot reload command: resets exhausted flags and re-reads .env."""
        self.reload_from_env()
        for provider, keys in self._keys_by_provider.items():
            for mk in keys:
                mk.exhausted = False
                mk.cooldown_until = 0.0
                mk.failure_count = 0
        return {p: len([k for k in keys if not k.exhausted]) for p, keys in self._keys_by_provider.items()}
