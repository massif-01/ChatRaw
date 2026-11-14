"""Install complete trusted market bundles without a network request."""

import json
import shutil
import tempfile
from pathlib import Path


class BundledPluginError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def install(plugin_id, bundled_root, installed_root, config, save_config):
    # This is deliberately an ID lookup, never a browser-controlled source path.
    if (
        not isinstance(plugin_id, str)
        or not plugin_id
        or len(plugin_id) > 100
        or any(not (c.isascii() and (c.isalnum() or c in "-_")) for c in plugin_id)
    ):
        raise BundledPluginError("Invalid plugin ID")
    bundled_root = Path(bundled_root).resolve()
    installed_root = Path(installed_root).resolve()
    index = json.loads((bundled_root / "index.json").read_text(encoding="utf-8"))
    entry = next(
        (item for item in index.get("plugins", []) if item.get("id") == plugin_id), None
    )
    if not entry:
        raise BundledPluginError("Plugin is not bundled with this image", 404)
    folder = entry.get("folder", plugin_id)
    source = bundled_root / folder
    if (
        source.resolve().parent != bundled_root
        or source.is_symlink()
        or not source.is_dir()
    ):
        raise BundledPluginError("Bundled plugin directory is invalid", 500)
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("id") != plugin_id:
        raise BundledPluginError(
            "Bundled manifest does not match the requested plugin", 500
        )
    # Bundled assets are image-owned. Refuse links rather than following one
    # outside the bundle and copying unrelated host files into public static UI.
    if any(path.is_symlink() for path in source.rglob("*")):
        raise BundledPluginError("Bundled plugin contains a symbolic link", 500)
    installed_root.mkdir(parents=True, exist_ok=True)
    target = installed_root / plugin_id
    if target.is_symlink():
        raise BundledPluginError("Installed plugin target is a symbolic link", 409)
    with tempfile.TemporaryDirectory(
        prefix=".bundle-", dir=installed_root.parent
    ) as staging:
        replacement = Path(staging) / "replacement"
        previous = Path(staging) / "previous"
        shutil.copytree(source, replacement)
        existed = target.exists()
        if existed:
            target.rename(previous)
        try:
            replacement.rename(target)
            plugins = config.setdefault("plugins", {})
            plugins.setdefault(plugin_id, {"enabled": True, "settings_values": {}})
            save_config(config)
        except BaseException:
            if target.exists():
                shutil.rmtree(target)
            if existed:
                previous.rename(target)
            raise
    return {"success": True, "plugin_id": plugin_id, "manifest": manifest}
