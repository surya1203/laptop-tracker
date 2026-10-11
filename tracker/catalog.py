"""The fixed choices behind every filter. Typed values outside these lists are still accepted."""

BRANDS = ["Lenovo", "ASUS", "HP", "Dell", "MSI", "Acer", "Apple", "Samsung", "Gigabyte"]

SERIES = {
    "Lenovo": ["Legion Pro 7", "Legion Pro 5", "Legion 7", "Legion 5", "Legion Slim 5", "LOQ", "Yoga Pro 7", "ThinkPad X1 Carbon"],
    "ASUS": ["ROG Strix Scar 18", "ROG Strix G16", "ROG Zephyrus G16", "ROG Zephyrus G14", "TUF Gaming A15", "TUF Gaming F16", "Zenbook", "Vivobook"],
    "HP": ["OMEN Max 16", "OMEN 16", "OMEN Transcend 14", "Victus 15", "Spectre x360", "Pavilion"],
    "Dell": ["Alienware 16 Area-51", "Alienware m16", "Alienware x16", "G15", "XPS 14", "Inspiron 16"],
    "MSI": ["Titan 18 HX", "Raider 18 HX", "Vector 16 HX", "Stealth 16", "Katana 15", "Cyborg 15"],
    "Acer": ["Predator Helios 18", "Predator Helios 16", "Predator Helios Neo 16", "Nitro V 15", "Swift"],
    "Apple": ["MacBook Pro 16", "MacBook Pro 14", "MacBook Air 15", "MacBook Air 13"],
    "Samsung": ["Galaxy Book Ultra", "Galaxy Book Pro"],
    "Gigabyte": ["AORUS Master 16", "AORUS 16X", "AERO 16"],
}

CPU_FAMILIES = {
    "Intel": ["Core Ultra 9", "Core Ultra 7", "Core Ultra 5", "Core i9", "Core i7", "Core i5", "Core i3"],
    "AMD": ["Ryzen 9", "Ryzen 7", "Ryzen 5", "Ryzen AI 9", "Ryzen AI 7", "Ryzen AI 5"],
    "Apple": ["M4 Max", "M4 Pro", "M4", "M3 Max", "M3 Pro", "M3"],
    "Qualcomm": ["Snapdragon X Elite", "Snapdragon X Plus", "Snapdragon X"],
}

GPU_MODELS = {
    "NVIDIA": ["RTX 5090", "RTX 5080", "RTX 5070 Ti", "RTX 5070", "RTX 5060", "RTX 5050",
               "RTX 4090", "RTX 4080", "RTX 4070", "RTX 4060", "RTX 4050"],
    "AMD": ["RX 7900M", "RX 7700S", "RX 7600M XT", "RX 7600S", "Radeon integrated"],
    "Intel": ["Arc A770M", "Arc A570M", "Arc integrated", "Iris Xe"],
    "Apple": ["Apple integrated"],
}

VRAM_GB = [4, 6, 8, 12, 16, 24]
RAM_GB = [8, 16, 24, 32, 64, 96]
RAM_TYPES = ["DDR5", "LPDDR5X", "LPDDR5", "DDR4"]

STORAGE_TYPES = ["SSD", "HDD", "SSD + HDD"]
STORAGE_INTERFACES = ["NVMe PCIe 5.0", "NVMe PCIe 4.0", "NVMe PCIe 3.0", "SATA"]
STORAGE_GB = [256, 512, 1024, 2048, 4096]

SCREEN_INCHES = [13.3, 14, 15.6, 16, 17.3, 18]
# Ordered low to high so "at least" comparisons work by position.
RESOLUTIONS = ["HD", "FHD", "FHD+", "QHD", "QHD+", "4K"]
RESOLUTION_PIXELS = {
    "HD": "1366 × 768", "FHD": "1920 × 1080", "FHD+": "1920 × 1200",
    "QHD": "2560 × 1440", "QHD+": "2560 × 1600", "4K": "3840 × 2160",
}
REFRESH_HZ = [60, 120, 144, 165, 240, 300]
PANELS = ["IPS", "OLED", "Mini-LED"]

# (key, label, searchable yet?) Croma, Vijay Sales and Reliance Digital arrive in phase 5.
RETAILERS = [
    ("amazon", "Amazon", True),
    ("flipkart", "Flipkart", True),
    ("croma", "Croma", False),
    ("vijaysales", "Vijay Sales", False),
    ("reliancedigital", "Reliance Digital", False),
]
RETAILER_LABELS = {key: label for key, label, _ in RETAILERS}
DEFAULT_RETAILERS = [key for key, _, available in RETAILERS if available]


def for_browser():
    """The brand-dependent lists the form needs for cascading dropdowns."""
    return {"series": SERIES, "cpu_families": CPU_FAMILIES, "gpu_models": GPU_MODELS}
