"""LiteLLM Configuration Loader.

Ingests standard LiteLLM configuration files (proxy_server_config.yaml, config.yaml, or dictionary),
resolves environment variables (os.environ/KEY and ${KEY}), manages litellm.Router instances,
and applies global LiteLLM runtime settings.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import yaml

import litellm

logger = logging.getLogger(__name__)

ENV_VAR_PATTERN = re.compile(r"\$\{([^}^{]+)\}")


def resolve_env_references(val: Any) -> Any:
    """Recursively resolves environment variable placeholders in config values.
    
    Supports:
    - 'os.environ/VAR_NAME' (LiteLLM native syntax)
    - '${VAR_NAME}' (standard environment expansion)
    """
    if isinstance(val, str):
        # LiteLLM native os.environ/ syntax
        if val.startswith("os.environ/"):
            env_key = val.split("os.environ/", 1)[1]
            return os.environ.get(env_key, "")
        # ${VAR_NAME} syntax
        if "${" in val:
            def _replace(match: re.Match) -> str:
                var_name = match.group(1)
                default_val = ""
                if ":-" in var_name:
                    var_name, default_val = var_name.split(":-", 1)
                return os.environ.get(var_name, default_val)
            return ENV_VAR_PATTERN.sub(_replace, val)
        return val
    elif isinstance(val, dict):
        return {k: resolve_env_references(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [resolve_env_references(item) for item in val]
    return val


class LiteLLMConfig:
    """Parsed and structured LiteLLM configuration container."""

    def __init__(self, raw_config: Dict[str, Any]):
        self.raw = resolve_env_references(raw_config)
        self.model_list: List[Dict[str, Any]] = self.raw.get("model_list", [])
        self.router_settings: Dict[str, Any] = self.raw.get("router_settings", {})
        self.litellm_settings: Dict[str, Any] = self.raw.get("litellm_settings", {})
        self.general_settings: Dict[str, Any] = self.raw.get("general_settings", {})
        self.environment_variables: Dict[str, Any] = self.raw.get("environment_variables", {})
        self.mcp_servers: Dict[str, Any] = self.raw.get("mcp_servers", {})

        # Apply environment variables defined in config
        for k, v in self.environment_variables.items():
            if k not in os.environ and v is not None:
                os.environ[k] = str(v)

    def apply_global_settings(self) -> None:
        """Applies litellm_settings to the global litellm module."""
        s = self.litellm_settings
        if "drop_params" in s:
            litellm.drop_params = bool(s["drop_params"])
        if "set_verbose" in s:
            litellm.set_verbose = bool(s["set_verbose"])
        if "telemetry" in s:
            litellm.telemetry = bool(s["telemetry"])
        if "request_timeout" in s:
            litellm.request_timeout = float(s["request_timeout"])
        if "num_retries" in s:
            litellm.num_retries = int(s["num_retries"])
        if "success_callback" in s and isinstance(s["success_callback"], list):
            litellm.success_callback = list(s["success_callback"])
        if "failure_callback" in s and isinstance(s["failure_callback"], list):
            litellm.failure_callback = list(s["failure_callback"])
        if "callbacks" in s and isinstance(s["callbacks"], list):
            litellm.callbacks = list(s["callbacks"])

        # Caching configuration
        if s.get("cache") is True:
            cache_params = s.get("cache_params", {})
            try:
                from litellm.caching.caching import Cache
                litellm.cache = Cache(**cache_params)
            except Exception as e:
                logger.warning(f"Could not initialize LiteLLM cache: {e}")

        logger.info("Applied global LiteLLM settings successfully.")

    def create_router(self) -> Optional[litellm.Router]:
        """Creates a litellm.Router from the configured model_list and router_settings."""
        if not self.model_list:
            return None

        router_kwargs: Dict[str, Any] = {
            "model_list": self.model_list,
        }

        # Transfer router settings
        rs = self.router_settings
        if "routing_strategy" in rs:
            router_kwargs["routing_strategy"] = rs["routing_strategy"]
        if "redis_host" in rs and rs["redis_host"]:
            router_kwargs["redis_host"] = rs["redis_host"]
        if "redis_port" in rs and rs["redis_port"]:
            router_kwargs["redis_port"] = int(rs["redis_port"])
        if "redis_password" in rs and rs["redis_password"]:
            router_kwargs["redis_password"] = rs["redis_password"]
        if "enable_pre_call_checks" in rs:
            router_kwargs["enable_pre_call_checks"] = bool(rs["enable_pre_call_checks"])
        if "model_group_alias" in rs:
            router_kwargs["model_group_alias"] = rs["model_group_alias"]
        if "num_retries" in self.litellm_settings:
            router_kwargs["num_retries"] = int(self.litellm_settings["num_retries"])
        if "context_window_fallbacks" in self.litellm_settings:
            router_kwargs["context_window_fallbacks"] = self.litellm_settings["context_window_fallbacks"]
        if "fallbacks" in rs:
            router_kwargs["fallbacks"] = rs["fallbacks"]

        try:
            router = litellm.Router(**router_kwargs)
            logger.info(f"Initialized litellm.Router with {len(self.model_list)} models using strategy '{router_kwargs.get('routing_strategy', 'simple-shuffle')}'.")
            return router
        except Exception as e:
            logger.error(f"Failed to initialize litellm.Router: {e}")
            raise


# Global singleton cache
_GLOBAL_CONFIG: Optional[LiteLLMConfig] = None
_GLOBAL_ROUTER: Optional[litellm.Router] = None


def load_config(
    config_source: Optional[Union[str, Path, Dict[str, Any]]] = None,
    apply_globals: bool = True,
) -> Optional[LiteLLMConfig]:
    """Loads LiteLLM configuration from a file path, YAML string, or dictionary."""
    global _GLOBAL_CONFIG, _GLOBAL_ROUTER

    data: Optional[Dict[str, Any]] = None

    if isinstance(config_source, dict):
        data = config_source
    elif isinstance(config_source, (str, Path)):
        p = Path(config_source)
        if p.is_file():
            with open(p, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        elif isinstance(config_source, str) and ("\n" in config_source or ":" in config_source):
            data = yaml.safe_load(config_source)
    elif config_source is None:
        candidates = [
            os.environ.get("LITELLM_CONFIG_PATH"),
            "proxy_server_config.yaml",
            "config.yaml",
            "../proxy_server_config.yaml",
        ]
        for c in candidates:
            if c and Path(c).is_file():
                with open(c, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    logger.info(f"Discovered and loaded LiteLLM config from: {c}")
                    break

    if data is None:
        return None

    cfg = LiteLLMConfig(data)
    _GLOBAL_CONFIG = cfg

    if apply_globals:
        cfg.apply_global_settings()

    if cfg.model_list:
        try:
            _GLOBAL_ROUTER = cfg.create_router()
        except Exception as e:
            logger.warning(f"Router creation skipped or failed: {e}")
            _GLOBAL_ROUTER = None
    else:
        _GLOBAL_ROUTER = None

    return cfg


def get_global_config() -> Optional[LiteLLMConfig]:
    """Returns currently loaded global LiteLLM configuration, if any."""
    return _GLOBAL_CONFIG


def get_global_router() -> Optional[litellm.Router]:
    """Returns the globally configured litellm.Router, if initialized."""
    return _GLOBAL_ROUTER


def set_global_router(router: Optional[litellm.Router]) -> None:
    """Sets or overrides the global litellm.Router instance."""
    global _GLOBAL_ROUTER
    _GLOBAL_ROUTER = router


# Backward-compatible and descriptive aliases
load_litellm_config = load_config


def create_litellm_router(
    model_list: List[Dict[str, Any]],
    routing_strategy: Optional[str] = None,
    **kwargs: Any,
) -> litellm.Router:
    """Convenience helper to create a litellm.Router directly."""
    router_kwargs: Dict[str, Any] = {"model_list": model_list, **kwargs}
    if routing_strategy:
        router_kwargs["routing_strategy"] = routing_strategy
    return litellm.Router(**router_kwargs)
