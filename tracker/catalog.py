"""The fixed choices behind every filter. Typed values outside these lists are still accepted."""

# What a hunt looks for: (key, label). A tower is a desktop PC without a screen of its own.
KINDS = [("laptop", "Laptop"), ("tower", "Tower PC")]
KIND_LABELS = dict(KINDS)

BRANDS = ["Lenovo", "ASUS", "HP", "Dell", "MSI", "Acer", "Apple", "Samsung", "Gigabyte"]

SERIES = {
    "Lenovo": ["Legion Pro 7", "Legion Pro 5", "Legion 7", "Legion 5", "Legion Slim 5", "LOQ", "Yoga Pro 7", "ThinkPad X1 Carbon"],
    "ASUS": ["ROG Strix Scar 18", "ROG Strix G16", "ROG Zephyrus G16", "ROG Zephyrus G14", "TUF Gaming A15", "TUF Gaming F16", "Zenbook", "Vivobook"],
    "HP": ["OMEN Max 16", "OMEN 16", "OMEN Transcend 14", "Victus 15", "Spectre x360", "Pavilion"],
    "Dell": ["Alienware 16 Area-51", "Alienware m16", "Alienware x16", "G15", "XPS 14", "Inspiron 16"],
    "MSI": ["Titan 18 HX", "Raider 18 HX", "Vector 16 HX", "Stealth 16", "Katana 15", "Cyborg 15"],
    "Acer": ["Predator Helios 18", "Predator Helios 16", "Predator Helios Neo 16", "Nitro V 15", "Swift"],
    "Apple": ["MacBook Pro 16", "MacBook Pro 14", "MacBook Air 15", "MacBook Air 13", "MacBook Neo"],
    "Samsung": ["Galaxy Book Ultra", "Galaxy Book Pro"],
    "Gigabyte": ["AORUS Master 16", "AORUS 16X", "AERO 16"],
}

TOWER_SERIES = {
    "Lenovo": ["Legion Tower 7", "Legion Tower 5", "LOQ Tower", "IdeaCentre Tower", "ThinkCentre"],
    "ASUS": ["ROG Strix G16CH", "ROG G700", "TUF Gaming T500"],
    "HP": ["OMEN 35L", "OMEN 16L", "Victus 15L", "Pavilion Desktop"],
    "Dell": ["Alienware Area-51", "Alienware Aurora", "Dell Pro Tower", "Dell Tower"],
    "MSI": ["MAG Infinite", "MEG Trident", "Codex"],
    "Acer": ["Predator Orion", "Nitro 50", "Aspire TC"],
    "Apple": ["Mac Studio", "Mac mini"],
}

CPU_FAMILIES = {
    "Intel": ["Core Ultra 9", "Core Ultra 7", "Core Ultra 5", "Core 9", "Core 7", "Core 5",
              "Core i9", "Core i7", "Core i5", "Core i3"],
    "AMD": ["Ryzen 9", "Ryzen 7", "Ryzen 5", "Ryzen AI 9", "Ryzen AI 7", "Ryzen AI 5"],
    "Apple": ["M6 Max", "M6 Pro", "M6", "M5 Ultra", "M5 Max", "M5 Pro", "M5", "M4 Max", "M4 Pro", "M4",
              "M3 Ultra", "M3 Max", "M3 Pro", "M3", "M2 Ultra", "M2 Max", "M2 Pro", "M2", "M1", "A18 Pro"],
    "Qualcomm": ["Snapdragon X Elite", "Snapdragon X Plus", "Snapdragon X"],
}

GPU_MODELS = {
    "NVIDIA": ["RTX 5090", "RTX 5080", "RTX 5070 Ti", "RTX 5070", "RTX 5060 Ti", "RTX 5060", "RTX 5050",
               "RTX 4090", "RTX 4080", "RTX 4070 Ti", "RTX 4070", "RTX 4060 Ti", "RTX 4060", "RTX 4050"],
    "AMD": ["RX 9070 XT", "RX 9070", "RX 9060 XT", "RX 7900M", "RX 7700S", "RX 7600M XT", "RX 7600S", "Radeon integrated"],
    "Intel": ["Arc A770M", "Arc A570M", "Arc integrated", "Iris Xe"],
    "Apple": ["Apple integrated"],
}

VRAM_GB = [4, 6, 8, 12, 16, 24]
# 18, 36, 48 and 128 GB are sizes Macs come in. "Unified" is Apple's memory, shared by the CPU and GPU.
RAM_GB = [8, 16, 18, 24, 32, 36, 48, 64, 96, 128]
RAM_TYPES = ["DDR5", "LPDDR5X", "LPDDR5", "DDR4", "Unified"]

STORAGE_TYPES = ["SSD", "HDD", "SSD + HDD"]
STORAGE_INTERFACES = ["NVMe PCIe 5.0", "NVMe PCIe 4.0", "NVMe PCIe 3.0", "SATA"]
STORAGE_GB = [256, 512, 1024, 2048, 4096, 8192]

SCREEN_INCHES = [13.3, 13.6, 14, 14.2, 15.3, 15.6, 16, 16.2, 17.3, 18]
# Ordered low to high so "at least" comparisons work by position.
RESOLUTIONS = ["HD", "FHD", "FHD+", "QHD", "QHD+", "4K"]
RESOLUTION_PIXELS = {
    "HD": "1366 × 768", "FHD": "1920 × 1080", "FHD+": "1920 × 1200",
    "QHD": "2560 × 1440", "QHD+": "2560 × 1600", "4K": "3840 × 2160",
}
REFRESH_HZ = [60, 120, 144, 165, 240, 300]
PANELS = ["IPS", "OLED", "Mini-LED"]

# Shops that sell every brand: (key, label).
MULTI_BRAND_STORES = [
    ("amazon", "Amazon"),
    ("flipkart", "Flipkart"),
    ("croma", "Croma"),
    ("vijaysales", "Vijay Sales"),
    ("reliancedigital", "Reliance Digital"),
]
# The brands' own Indian online stores: (key, label, brand, site). A hunt for other brands skips them.
# HP's store turns automated browsers away, and MSI and Gigabyte do not sell online in India themselves.
BRAND_STORES = [
    ("lenovo", "Lenovo Store", "Lenovo", "lenovo.com/in"),
    ("asus", "ASUS Store", "ASUS", "asus.com/in/store"),
    ("dell", "Dell Store", "Dell", "dellstore.com"),
    ("acer", "Acer Store", "Acer", "store.acer.com/en-in"),
    ("apple", "Apple Store", "Apple", "apple.com/in"),
    ("samsung", "Samsung Store", "Samsung", "samsung.com/in"),
]
RETAILER_LABELS = {key: label for key, label, *_ in MULTI_BRAND_STORES + BRAND_STORES}
DEFAULT_RETAILERS = list(RETAILER_LABELS)
# The stores that sell tower PCs (Apple's are the Mac mini and Mac Studio). The ASUS, Acer and Samsung stores list none.
TOWER_RETAILERS = ("amazon", "flipkart", "croma", "vijaysales", "reliancedigital", "lenovo", "dell", "apple")


def for_browser():
    """The brand-dependent lists the form needs for cascading dropdowns."""
    return {"series": SERIES, "tower_series": TOWER_SERIES, "cpu_families": CPU_FAMILIES, "gpu_models": GPU_MODELS,
            "tower_retailers": list(TOWER_RETAILERS)}
