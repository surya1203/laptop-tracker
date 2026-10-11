"""One-time import of saved searches from the pre-rebuild database.

The old app stored each search as a JSON blob of display strings such as
{"ram": ">= 16 GB", "storage_type": "SSD PCIe 5.0"}. This turns them into typed hunts.
"""
import json
import re
import sqlite3
from pathlib import Path

from . import catalog, hunts


def _gb(text):
    """'>= 16 GB' -> 16, '1 TB' -> 1024, anything else -> None."""
    match = re.search(r"(\d+(?:\.\d+)?)\s*(tb|gb)?", text.lower())
    if not match:
        return None
    value = float(match.group(1)) * (1024 if match.group(2) == "tb" else 1)
    return int(value) or None


def _gpu_brand(model):
    model = model.lower()
    if re.search(r"\b(rtx|gtx|geforce)\b", model):
        return "NVIDIA"
    if re.search(r"\b(rx|radeon)\b", model):
        return "AMD"
    if re.search(r"\b(arc|iris)\b", model):
        return "Intel"
    return None


def convert(specs):
    """Map one old specs blob to hunt fields. Returns (fields, keys that had no home)."""
    specs = {k: v.strip() for k, v in specs.items() if isinstance(v, str) and v.strip()}
    hunt = hunts.blank()

    def take(*keys):
        for key in keys:
            if key in specs:
                return specs.pop(key)
        return None

    if brand := take("brand", "brand_name"):
        hunt["brands"] = [hunts._canonical(brand, catalog.BRANDS)]
    hunt["series"] = take("model_name")
    hunt["cpu_brand"] = take("cpu_brand")
    hunt["cpu_family"] = take("cpu_model")  # the old "CPU Model" box held the family, e.g. "Core Ultra 9"
    hunt["cpu_model"] = take("cpu_model_number")

    hunt["gpu_brand"] = take("gpu_brand")
    if gpu := take("gpu_model", "gpu", "graphics_coprocessor"):
        hunt["gpu_models"] = [gpu]
        hunt["gpu_brand"] = hunt["gpu_brand"] or _gpu_brand(gpu)

    # Old ">=", "<=" and "==" selectors all become a minimum; the new form only has minimums here.
    for field, keys in (
        ("vram_min_gb", ("gpu_vram", "graphics_ram_size")),
        ("ram_min_gb", ("ram", "ram_memory_installed")),
        ("storage_min_gb", ("storage_capacity", "hard_drive_size")),
    ):
        if value := take(*keys):
            hunt[field] = _gb(value)

    hunt["ram_type"] = take("ram_type", "ram_memory_technology", "system_ram_type")

    # "SSD PCIe 5.0" held both the drive type and its interface.
    storage = " ".join(filter(None, [take("storage_type"), take("hard_drive_interface")]))
    if storage:
        low = storage.lower()
        if "ssd" in low and "hdd" in low:
            hunt["storage_type"] = "SSD + HDD"
        elif "hdd" in low:
            hunt["storage_type"] = "HDD"
        elif "ssd" in low or "nvme" in low or "pcie" in low:
            hunt["storage_type"] = "SSD"
        if version := re.search(r"pcie\s*(\d(?:\.\d)?)", low):
            number = version.group(1) if "." in version.group(1) else f"{version.group(1)}.0"
            hunt["storage_interface"] = f"NVMe PCIe {number}"
        elif "sata" in low:
            hunt["storage_interface"] = "SATA"

    if screen := take("screen_size"):
        if match := re.search(r"\d+(?:\.\d+)?", screen):
            hunt["screen_min_in"] = hunt["screen_max_in"] = float(match.group())
    if panel := take("display_type"):
        hunt["panels"] = [hunts._canonical(panel, catalog.PANELS)]

    return hunt, sorted(specs)


def import_legacy(conn, legacy_path):
    """Copy old saved searches into `conn` (caller commits). Returns log lines."""
    if not Path(legacy_path).is_file():
        return []
    old = sqlite3.connect(f"file:{Path(legacy_path).as_posix()}?mode=ro", uri=True)
    try:
        rows = old.execute(
            "SELECT search_name, specs_json, notification_email, notification_whatsapp "
            "FROM spec_trackers ORDER BY id"
        ).fetchall()
    except sqlite3.Error:
        return [f"Legacy import skipped: {legacy_path} has no spec_trackers table."]
    finally:
        old.close()

    log = []
    for name, specs_json, email, whatsapp in rows:
        hunt, dropped = convert(json.loads(specs_json or "{}"))
        hunt["name"] = name
        hunts.insert(conn, hunt)
        note = f" (not carried over: {', '.join(dropped)})" if dropped else ""
        log.append(f"Imported saved search “{name}” as a hunt{note}.")
        # Alerts are global now; keep the first contact details found.
        for key, value in (("notify_email", email), ("notify_whatsapp", whatsapp)):
            if value and value.strip():
                conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value.strip()))
    return log
