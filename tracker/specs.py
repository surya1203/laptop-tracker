"""Spec normaliser: a store's spec table plus the listing title -> typed values.

Stores label the same thing differently ("RAM Memory Installed Size", "RAM"), and
leave things out of the table that the title states, so every field reads the
table first and falls back to the title.
"""
import re

from . import catalog

_RESOLUTION_PIXELS = {
    "HD": 1366 * 768, "FHD": 1920 * 1080, "FHD+": 1920 * 1200,
    "QHD": 2560 * 1440, "QHD+": 2560 * 1600, "4K": 3840 * 2160,
}
# Marketing names, most specific first.
_RESOLUTION_NAMES = [
    (r"4k|uhd|3840", "4K"),
    (r"wqxga|qhd\s*\+|2\.5k|2\.8k|3k|3\.2k", "QHD+"),
    (r"wqhd|qhd|2k", "QHD"),
    (r"wuxga|fhd\s*\+|full hd\s*\+", "FHD+"),
    (r"fhd|full hd|1080p", "FHD"),
]
_RAM_TYPES = ["LPDDR5X", "LPDDR5", "LPDDR4X", "DDR5", "DDR4", "DDR3"]


def _loose(text):
    """A pattern for `text` that ignores case-irrelevant spacing: 'RTX 5070 Ti' also finds 'RTX5070Ti'."""
    return r"[\s-]*".join(re.escape(part) for part in text.split())


def squash(text):
    """Lowercase letters and digits only, for forgiving 'does this mention that' checks."""
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def _plain(text):
    """Without the trademark signs brands scatter through names ("GeForce RTX™ 5070")."""
    return re.sub(r"[®™©]|\((?:R|TM)\)", "", str(text)).strip()


def _number(text):
    match = re.search(r"\d+(?:\.\d+)?", (text or "").replace(",", ""))
    return float(match.group()) if match else None


def _gb(text):
    """'1 TB' -> 1024, '512 GB' -> 512, '16GB' -> 16."""
    match = re.search(r"(\d+(?:\.\d+)?)\s*(tb|gb|mb)\b", (text or "").lower())
    if not match:
        return None
    value = float(match.group(1)) * {"tb": 1024, "gb": 1, "mb": 1 / 1024}[match.group(2)]
    return int(value) if value >= 1 else None


def resolution_class(width, height):
    """The highest catalog resolution this pixel count reaches, e.g. 2880x1800 -> 'QHD+'."""
    pixels = width * height
    best = None
    for name in catalog.RESOLUTIONS:
        if pixels >= _RESOLUTION_PIXELS[name]:
            best = name
    return best


class _Table:
    """Case-insensitive lookup over a store's spec table."""

    def __init__(self, raw):
        self.rows = {squash(key): _plain(value) for key, value in (raw or {}).items() if value}

    def get(self, *labels):
        for label in labels:
            value = self.rows.get(squash(label))
            if value and squash(value) not in ("na", "no", "none", "notavailable", "notapplicable"):
                return value
        return None

    def join(self, *labels):
        return " ".join(v for v in (self.rows.get(squash(label)) for label in labels) if v)

    def like(self, wanted, unwanted=None):
        """The values of every row whose label mentions `wanted`: stores word the same row many ways."""
        return " ".join(value for key, value in self.rows.items()
                        if re.search(wanted, key) and not (unwanted and re.search(unwanted, key)))


def _cpu(table, title):
    text = table.join("Processor Brand", "Processor Name", "Processor Variant", "Processor Type",
                      "CPU Model", "CPU Model Number") + " " + title
    text = f"{table.like(r'^(processor|cpu|coretype|processorfamily|processormodel(number)?)$')} {text}"
    low = text.lower()
    brand = None
    for name, pattern in (("Apple", r"\bapple\b|\bm[1-5]\b(?! ?\.)"), ("Qualcomm", r"snapdragon|qualcomm"),
                          ("AMD", r"ryzen|\bamd\b"), ("Intel", r"\bintel\b|core\s*(ultra|i[3579])|\bi[3579][- ]\d")):
        if re.search(pattern, low):
            brand = name
            break
    family = None
    families = sorted((f for fs in catalog.CPU_FAMILIES.values() for f in fs), key=len, reverse=True)
    for name in families:
        if re.search(rf"(?<![a-z0-9]){_loose(name)}(?![a-z0-9])", low, re.I):
            family = name
            break
    if not family:
        bare = re.search(r"\bi([3579])[- ]\d{4,5}", low)  # "i7-13650HX" with no "Core"
        if bare:
            family = f"Core i{bare.group(1)}"
    # "Ryzen 7 260" / "Core Ultra 9 275HX" first, then a bare "13650HX" elsewhere in the text.
    model = (re.search(r"(?:ultra\s*[3579]|\bi[3579]|ryzen\s*(?:ai\s*)?[3579])\s*(?:processor\s*)?-?\s*(\d{3,5}[a-z]{0,2})\b(?!\s*(?:gb|tb|hz))", text, re.I)
             or re.search(r"\b(\d{3,5}(?:HX|HS|HK|H|U|P|V|K))\b", text, re.I))
    return brand, family, model.group(1).upper() if model else None, text


def _gpu(table, title):
    text = table.join("Graphics Co Processor", "Graphic Processor", "Graphics Coprocessor",
                      "Graphics Card Description", "Video Processor", "Graphics Description") + " " + title
    text = f"{table.like(r'graphic|gpu', r'memory|ram|size|capacity|type$')} {text}"
    low = text.lower()
    model = None
    for name in sorted((m for ms in catalog.GPU_MODELS.values() for m in ms), key=len, reverse=True):
        if "integrated" in name.lower():
            continue
        if re.search(rf"(?<![a-z0-9]){_loose(name)}(?![a-z0-9])", low, re.I):
            model = name
            break
    if not model:
        other = re.search(r"\b(rtx|gtx|rx|arc)\s*-?\s*([a-z]?\d{3,4}[a-z]?)(\s*ti|\s*super|\s*xt)?", low)
        if other:
            model = f"{other.group(1).upper()} {other.group(2).upper()}{(other.group(3) or '').title()}"
    brand = None
    for name, pattern in (("NVIDIA", r"nvidia|geforce|\brtx\b|\bgtx\b"), ("AMD", r"radeon|\brx\s*\d"),
                          ("Intel", r"\barc\b|iris|intel (uhd|hd|graphics)"), ("Apple", r"\bapple\b")):
        if re.search(pattern, low):
            brand = name
            break
    return brand, model, text


def _resolution(table, title):
    for value in (table.get("Screen Resolution"), table.get("Native Resolution"),
                  table.get("Maximum Display Resolution"), table.get("Display Maximum Resolution"),
                  table.get("Resolution"), table.like(r"^(display|screen|displaytype|screentype)$"), title):
        match = re.search(r"(\d{3,4})\s*[x×]\s*(\d{3,4})", value or "", re.I)
        if match:
            width, height = sorted((int(match.group(1)), int(match.group(2))), reverse=True)
            return resolution_class(width, height), f"{width} × {height}"
    text = (table.join("Screen Resolution Type", "Screen Type", "Display Type", "Display") + " " + title).lower()
    for pattern, name in _RESOLUTION_NAMES:
        if re.search(rf"(?<![a-z0-9])(?:{pattern})(?![a-z0-9+])", text):
            return name, None
    return None, None


def normalise(title, raw):
    """Typed specs for one listing. A value is None when the page did not say."""
    title = _plain(title or "")
    table = _Table(raw)
    specs = {}

    brand = table.get("Brand", "Brand Name")
    if not brand:
        first = title.split(" ", 1)[0]
        brand = next((b for b in catalog.BRANDS if b.lower() == first.lower()), None)
    specs["brand"] = next((b for b in catalog.BRANDS if brand and b.lower() == brand.lower()), brand)
    specs["series"] = table.get("Series", "Model Name", "Model Series")

    specs["cpu_brand"], specs["cpu_family"], specs["cpu_model"], specs["cpu_text"] = _cpu(table, title)
    specs["gpu_brand"], specs["gpu_model"], specs["gpu_text"] = _gpu(table, title)

    vram = _gb(table.get("Graphics RAM Size", "Dedicated Graphic Memory Capacity", "Graphics Card Ram Size",
                         "Graphic Card Memory", "Graphics Memory", "Dedicated Graphics Memory", "Graphics Card Memory"))
    if not vram:
        match = re.search(r"(\d{1,2})\s*GB\s*(?:of\s*)?GDDR", specs["gpu_text"], re.I)
        vram = int(match.group(1)) if match else None
    if not vram:
        match = re.search(r"(\d{1,2})\s*GB\s*Graphics|(?:RTX|GTX|RX)\s*\w?\d{3,4}\w?(?:\s*Ti)?[\s,/-]*(\d{1,2})\s*GB", title, re.I)
        vram = int(match.group(1) or match.group(2)) if match else None
    specs["vram_gb"] = vram

    ram = _gb(table.get("RAM Size", "RAM Memory Installed Size", "RAM Memory Installed", "RAM", "Memory (RAM)",
                        "Memory", "System Memory", "Installed RAM", "RAM Capacity"))
    if not ram:
        match = re.search(r"(\d{1,3})\s*GB\s*(?:(?:LP)?DDR\w*\s*)?RAM|\(\s*(\d{1,3})\s*GB\s*/", title, re.I)
        ram = int(match.group(1) or match.group(2)) if match else None
    specs["ram_gb"] = ram

    ram_text = (table.join("RAM Type", "RAM Memory Technology", "System RAM Type", "Memory Technology", "Type of RAM",
                           "Memory", "Memory Details", "RAM") + " " + title).upper()
    specs["ram_type"] = next((t for t in _RAM_TYPES if re.search(rf"(?<![A-Z]){t}(?![A-Z0-9])", ram_text)), None)

    ssd = _gb(table.get("SSD Capacity"))
    hdd = _gb(table.get("HDD Capacity"))
    storage = (ssd or 0) + (hdd or 0) or _gb(table.get(
        "Hard Disk Size", "Hard Drive Size", "Flash Memory Installed Size", "Storage Capacity", "Storage",
        "Storage Type Capacity", "Total Storage", "Internal Storage", "Hard Drive", "SSD"))
    if not storage:
        match = re.search(r"(\d+(?:\.\d+)?)\s*(TB|GB)\s*(?:NVMe\s*|PCIe\s*|M\.2\s*)*(?:SSD|HDD)", title, re.I)
        storage = _gb(match.group(0)) if match else None
    specs["storage_gb"] = storage

    storage_text = (table.join("Storage Type", "Hard Disk Description", "Hard Drive Interface", "Storage",
                               "Storage Type Capacity", "Hard Drive", "SSD Type") + " " + title).lower()
    has_ssd = bool(ssd) or bool(re.search(r"\bssd\b|nvme|solid state", storage_text))
    has_hdd = bool(hdd) or bool(re.search(r"\bhdd\b|mechanical hard", storage_text))
    specs["storage_type"] = "SSD + HDD" if has_ssd and has_hdd else "SSD" if has_ssd else "HDD" if has_hdd else None

    interface = None
    generation = re.search(r"(?:pcie|gen)\s*\.?\s*([345])(?:\.0)?(?![\dx])", storage_text)
    if generation:
        interface = f"NVMe PCIe {generation.group(1)}.0"
    elif re.search(r"nvme|pcie", storage_text):
        interface = "NVMe"
    elif "sata" in storage_text:
        interface = "SATA"
    specs["storage_interface"] = interface

    screen = None
    for value in (table.get("Screen Size", "Standing screen display size", "Display Size (In Inches)", "Screen Size (Diagonal)",
                            "Display Size", "Display"), title):
        match = re.search(r"(\d{2}(?:\.\d+)?)\s*(?:-\s*)?(?:inch|inches|in\b|\"|”)", value or "", re.I)
        if match and 10 <= float(match.group(1)) <= 21:
            screen = float(match.group(1))
            break
        match = re.search(r"(\d{2}(?:\.\d+)?)\s*cm", value or "", re.I)
        if match and 25 <= float(match.group(1)) <= 54:
            screen = round(float(match.group(1)) / 2.54, 1)
            break
    specs["screen_in"] = screen

    specs["resolution"], specs["resolution_px"] = _resolution(table, title)

    refresh = _number(table.get("Display Refresh Rate in Hertz", "Refresh Rate"))
    if not refresh:
        match = re.search(r"(\d{2,3})\s*Hz", f"{table.join('Screen Type', 'Display Type', 'Display')} {title}", re.I)
        refresh = float(match.group(1)) if match else None
    specs["refresh_hz"] = int(refresh) if refresh and 30 <= refresh <= 600 else None

    panel_text = (table.join("Screen Type", "Display Type", "Display Technology", "Display", "Panel Type", "Panel") + " " + title).lower()
    specs["panel"] = ("OLED" if "oled" in panel_text else
                      "Mini-LED" if re.search(r"mini[\s-]*led", panel_text) else
                      "IPS" if re.search(r"\bips\b", panel_text) else None)

    weight = None
    weight_text = table.get("Item Weight", "Weight", "Product Weight") or ""
    match = re.search(r"(\d+(?:\.\d+)?)\s*(kg|kilograms?|g|grams?)\b", weight_text, re.I)
    if match:
        weight = float(match.group(1)) / (1000 if match.group(2).lower().startswith("g") else 1)
        extra = re.search(r"kg\s*(\d+)\s*g\b", weight_text, re.I)  # "2 kg 100 g"
        if extra:
            weight += int(extra.group(1)) / 1000
    elif _number(table.get("Weight (kg)")):
        weight = _number(table.get("Weight (kg)"))
    else:
        match = re.search(r"(\d(?:\.\d+)?)\s*kg\b", title, re.I)
        weight = float(match.group(1)) if match else None
    specs["weight_kg"] = round(weight, 2) if weight and 0.5 <= weight <= 6 else None

    specs["model_number"] = table.get("Manufacturer Part Number", "Part Number", "Item model number", "Model Number", "MPN")
    return specs
