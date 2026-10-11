"""The parts of the store modules that work without a browser, and the spec sheets the newer stores publish."""
from tracker import hunts, search, specs
from tracker.stores import STORES, acer, apple, asus, sells, vijaysales
from tracker.stores.base import ld_offer, relevant, without_brand

CROMA_TABLE = {
    "Brand": "Lenovo", "Model Series": "Legion 5 15IAX10", "Model Number": "83F000BSIN", "Product Weight": "1.9 Kg",
    "Display Size (In Inches)": "15.1 Inches", "Display Type": "OLED", "Screen Resolution": "2560 x 1600 pixels",
    "Refresh Rate": "165 Hz", "Processor Brand": "Intel", "Processor Type": "Core Ultra 9", "Processor Variant": "275HX",
    "Type of RAM": "DDR5", "RAM": "16GB",
}
LENOVO_TABLE = {
    "Brand": "Lenovo", "Part Number": "83F5CTO1WWIN2",
    "Processor": "Intel Core Ultra 9 275HX Processor (E-cores up to 4.60 GHz P-cores up to 5.40 GHz)",
    "Graphic Card": "NVIDIA GeForce RTX 5070 Ti Laptop GPU 12GB GDDR7", "Memory": "32 GB DDR5-6400MT/s (CSODIMM) - (2 x 16 GB)",
    "Storage": "1 TB SSD M.2 2280 PCIe Gen4 TLC",
    "Display": "40.64cms (16) WQXGA (2560 x 1600), OLED, Glare, Non-Touch, HDR 1000 True Black, 500 nits, 240Hz",
}
DELL_TABLE = {
    "Brand": "Dell", "Processor": "Intel® Core™ 9 processor 270H (24MB cache, 14 cores, 20 threads, up to 5.8 GHz)",
    "Graphics Card": "NVIDIA® GeForce RTX™ 5070, 8 GB GDDR7", "Memory": "16GB DDR5, 2x8GB, 5600MT/s",
    "Storage": "1TB M.2 PCIe NVMe Solid State Drive",
    "Display": "16.0-inch 16:10 2.5K(2560x1600) Anti-Glare Non-Touch 300nits WVA/IPS Display with ComfortView Plus",
}
RELIANCE_TABLE = {
    "Brand": "Lenovo", "Series": "Legion 5 Pro 16IRX10", "Screen Resolution": "2560 x 1600 px",
    "Screen Size (Diagonal)": "40.64 cm - 16 inch", "Graphic Card Memory": "8 GB", "Memory (RAM)": "32 GB",
    "Memory Details": "2x 16GB SO-DIMM DDR5-5600", "Processor": "Intel Core i7-14650HX, 16C (8P + 8E) / 24T",
    "Storage Type Capacity": "1TB SSD M.2 2242 PCIe 4.0x4 NVMe", "Storage Capacity": "1 TB",
    "Graphics Card Model": "NVIDIA GeForce RTX 5060 8GB GDDR7, Boost Clock 2497MHz, TGP 115W",
}


def test_croma_sheet():
    found = specs.normalise("Lenovo Legion 5 15IAX10 Intel Core Ultra 9 Gaming Laptop (16GB, 512GB SSD, 8GB Graphics, "
                            "NVIDIA GeForce RTX 5070)", CROMA_TABLE)
    assert (found["cpu_family"], found["cpu_model"], found["gpu_model"]) == ("Core Ultra 9", "275HX", "RTX 5070")
    assert (found["ram_gb"], found["ram_type"], found["storage_gb"], found["weight_kg"]) == (16, "DDR5", 512, 1.9)
    assert (found["screen_in"], found["resolution"], found["refresh_hz"], found["panel"]) == (15.1, "QHD+", 165, "OLED")
    assert (found["series"], found["model_number"]) == ("Legion 5 15IAX10", "83F000BSIN")


def test_a_brand_store_sheet_with_one_row_per_part():
    found = specs.normalise("Lenovo Legion Pro 7 Intel, 40.64cms - Core Ultra (customisable, 83F5CTO1WWIN2)", LENOVO_TABLE)
    assert (found["cpu_family"], found["cpu_model"], found["gpu_model"], found["vram_gb"]) == ("Core Ultra 9", "275HX", "RTX 5070 Ti", 12)
    assert (found["ram_gb"], found["ram_type"], found["storage_gb"], found["storage_interface"]) == (32, "DDR5", 1024, "NVMe PCIe 4.0")
    assert (found["screen_in"], found["resolution"], found["refresh_hz"], found["panel"]) == (16.0, "QHD+", 240, "OLED")


def test_trademark_signs_do_not_hide_a_model():
    found = specs.normalise("Dell Alienware 16 Aurora Gaming Laptop (OAN1625001301MINO)", DELL_TABLE)
    assert (found["cpu_brand"], found["cpu_family"], found["cpu_model"]) == ("Intel", "Core 9", "270H")
    assert (found["gpu_brand"], found["gpu_model"], found["vram_gb"]) == ("NVIDIA", "RTX 5070", 8)
    assert (found["ram_gb"], found["storage_gb"], found["resolution"], found["panel"]) == (16, 1024, "QHD+", "IPS")


def test_reliance_sheet():
    found = specs.normalise("Lenovo Legion 5 Pro 16IRX10 83NN0046IN Gaming Laptop", RELIANCE_TABLE)
    assert (found["cpu_family"], found["cpu_model"], found["gpu_model"], found["vram_gb"]) == ("Core i7", "14650HX", "RTX 5060", 8)
    assert (found["ram_gb"], found["ram_type"], found["storage_gb"], found["screen_in"]) == (32, "DDR5", 1024, 16.0)


def test_vijay_sales_description_becomes_a_spec_sheet():
    markup = ("<b>Processor:</b> Intel Core Ultra 7 255HX (20 Cores) – Flagship-level performance.<br>\r\n "
              "<b>Graphics:</b> NVIDIA GeForce RTX 5060 (8GB GDDR7, 115W TGP)<br><strong>Memory</strong>: 32GB DDR5-5600")
    sheet = vijaysales.description_specs(markup)
    assert sheet["Processor"].startswith("Intel Core Ultra 7 255HX") and sheet["Memory"] == "32GB DDR5-5600"
    found = specs.normalise("Lenovo Legion Pro 5 AI Powered Gaming Laptop", sheet)
    assert (found["cpu_model"], found["gpu_model"], found["vram_gb"], found["ram_gb"]) == ("255HX", "RTX 5060", 8, 32)


def test_unrelated_results_are_dropped():
    assert relevant("Lenovo Legion Pro 5 Gaming Laptop (RTX 5070)", "Lenovo Legion RTX 5080 laptop")
    assert not relevant("HP 15 Laptop Backpack", "Lenovo Legion RTX 5080 laptop")


def test_brand_stores_are_not_asked_for_their_own_name():
    assert without_brand("Dell Alienware RTX 5080 laptop", "Dell") == "Alienware RTX 5080"
    assert without_brand("ASUS laptop", "ASUS") == "laptop"


def test_a_brand_store_is_skipped_for_other_brands():
    assert sells(STORES["lenovo"], ["Lenovo", "ASUS"]) and sells(STORES["lenovo"], [])
    assert not sells(STORES["lenovo"], ["ASUS"])
    assert sells(STORES["croma"], ["ASUS"])


def test_a_brand_store_only_gets_phrases_for_its_brand():
    hunt = hunts.blank()
    hunt.update(brands=["Lenovo", "ASUS"], gpu_models=["RTX 5080"])
    assert search.queries(hunt) == ["Lenovo RTX 5080 laptop", "ASUS RTX 5080 laptop"]
    assert search.queries(hunt, ("ASUS",)) == ["ASUS RTX 5080 laptop"]
    hunt.update(brands=[])
    assert search.queries(hunt, ("Dell",)) == ["Dell RTX 5080 laptop"]


def test_every_store_follows_the_interface():
    for key, store in STORES.items():
        assert store.KEY == key and store.LABEL
        assert callable(store.prepare) and callable(store.search) and callable(store.read)


def test_names_made_from_page_addresses():
    assert asus._name("https://in.store.asus.com/gaming-laptop-rog-strix-g16-g614p.html?config=90NR0KW7-M00B60") == "ASUS ROG Strix G16 G614P"
    assert apple._name("https://www.apple.com/in/shop/buy-mac/macbook-pro/14-inch-silver-standard-display-apple-m5-chip-"
                       "10-core-cpu-10-core-gpu-16gb-memory-1tb-storage").startswith("Apple MacBook Pro 14 inch, silver")
    assert acer._phrase("https://store.acer.com/en-in/acer-predator-helios-neo-16-gaming-laptop-windows-11-home-"
                        "nvidia-geforce-rtx-5070-laptop-gpu") == "predator helios neo 16 rtx 5070"


def test_price_from_a_schema_block():
    block = {"offers": [{"price": 239900.00, "priceCurrency": "INR"}]}
    assert ld_offer(block) == (239900, True)
    assert ld_offer({"offers": {"price": "219990", "availability": "https://schema.org/OutOfStock"}}) == (219990, False)
