"""Fixed server-side allowlist. Plugin manifests cannot select Python modules."""

import importlib


ADAPTERS = {
    "hermes": "HermesAdapter",
    "codex": "CodexAdapter",
    "claude": "ClaudeAdapter",
    "pi": "PiAdapter",
    "deepseek": "DeepSeekAdapter",
}


def factories():
    registered = {}
    for agent_id, class_name in ADAPTERS.items():
        module_name = f"agent_runner.adapters.{agent_id}"
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as error:
            if error.name == module_name:
                continue  # A leaf not delivered/installed is honestly unavailable.
            raise  # A broken installed adapter must not disappear silently.
        registered[agent_id] = getattr(module, class_name)
    return registered
