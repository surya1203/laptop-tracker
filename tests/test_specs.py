"""Spec normaliser and filter matching, checked against titles and spec tables as the stores publish them."""
from tracker import hunts, matching, specs

AMAZON_TITLE = ("Lenovo Legion 5 2025, AMD Ryzen 7 260, NVIDIA RTX 5050 8GB, 16GB RAM, 1TB SSD, WUXGA IPS, "
                "15(39.6cm), 165Hz, Windows 11, Office 2024+AI Now, Black, 2.5Kg, 83M00073IN, Gaming Laptop")
AMAZON_TABLE = {
    "Brand": "Lenovo", "Model Name": "Legion 5", "Screen Size": "15 Inches", "Hard Disk Size": "1 TB",
    "CPU Model": "AMD Ryzen 7", "RAM Memory Installed Size": "16 GB", "Graphics Co Processor": "NVIDIA RTX 5050",
    "Hard Disk Description": "SSD", "Item Weight": "2.1 Kilograms", "Graphics RAM Size": "8 GB",
    "Hard Drive Interface": "PCIE x 4", "Native Resolution": "1920 x 1200 pixels", "Display Type": "LCD",
    "Display Refresh Rate in Hertz": "165", "Processor Brand": "AMD", "CPU Model Number": "Ryzen 7 260",
    "Manufacturer Part Number": "83M00073IN", "RAM Memory Technology": "DDR5",
}
FLIPKART_TITLE = ("Lenovo Legion 5 WQXGA OLED Intel Core Ultra 9 275HX - (32 GB/1 TB SSD/Windows 11 Home/8 GB Graphics/"
                  "NVIDIA GeForce RTX 5070) 15IAX10 Gaming Laptop (15.1 inch, Eclipse Black, 1.9 kg)")
FLIPKART_TABLE = {
    "Dedicated Graphic Memory Capacity": "8 GB", "Processor Brand": "Intel", "Processor Name": "Core Ultra 9",
    "SSD": "Yes", "SSD Capacity": "1 TB", "RAM": "32 GB", "RAM Type": "DDR5", "Processor Variant": "275HX",
    "Graphic Processor": "NVIDIA GeForce RTX 5070", "Storage Type": "SSD", "Brand": "Lenovo",
    "Part Number": "83F0005VIN", "Screen Size": "38.35 cm (15.1 inch)", "Screen Resolution": "2560x1600 pixels",
    "Screen Type": "15.1 inch WQXGA (2560x1600) OLED 1000nits (peak), 165Hz, Dolby Vision", "Weight": "1.9 kg",
}


def test_amazon_table():
    found = specs.normalise(AMAZON_TITLE, AMAZON_TABLE)
    assert (found["brand"], found["cpu_brand"], found["cpu_family"], found["cpu_model"]) == ("Lenovo", "AMD", "Ryzen 7", "260")
    assert (found["gpu_brand"], found["gpu_model"], found["vram_gb"]) == ("NVIDIA", "RTX 5050", 8)
    assert (found["ram_gb"], found["ram_type"], found["storage_gb"], found["storage_type"]) == (16, "DDR5", 1024, "SSD")
    assert (found["resolution"], found["refresh_hz"], found["panel"], found["weight_kg"]) == ("FHD+", 165, "IPS", 2.1)
    assert found["storage_interface"] == "NVMe"  # "PCIE x 4" is lane count, not a PCIe generation
    assert found["model_number"] == "83M00073IN"


def test_flipkart_table():
    found = specs.normalise(FLIPKART_TITLE, FLIPKART_TABLE)
    assert (found["cpu_family"], found["cpu_model"], found["gpu_model"]) == ("Core Ultra 9", "275HX", "RTX 5070")
    assert (found["screen_in"], found["resolution"], found["refresh_hz"], found["panel"]) == (15.1, "QHD+", 165, "OLED")
    assert (found["ram_gb"], found["storage_gb"], found["vram_gb"], found["weight_kg"]) == (32, 1024, 8, 1.9)


def test_title_alone_is_enough_for_the_basics():
    found = specs.normalise(
        "ASUS ROG Strix G16 (2025) Intel Core Ultra 9 275HX - (32 GB/1 TB SSD/Windows 11 Home/12 GB Graphics/"
        "NVIDIA GeForce RTX 5070 Ti/240 Hz) G615LR Gaming Laptop (16 Inch, Eclipse Gray, 2.65 Kg)", {})
    assert (found["brand"], found["gpu_model"], found["vram_gb"], found["ram_gb"]) == ("ASUS", "RTX 5070 Ti", 12, 32)
    assert (found["storage_gb"], found["refresh_hz"], found["screen_in"], found["weight_kg"]) == (1024, 240, 16.0, 2.65)
    assert found["resolution"] is None and found["panel"] is None


def test_refresh_rate_is_not_read_as_a_cpu_model():
    assert specs.normalise("Some Laptop Ryzen 7, 165Hz, 16GB RAM", {})["cpu_model"] is None


def _hunt(**filters):
    hunt = hunts.blank()
    hunt.update(filters)
    return hunt


def _listing(title, table, price=150000):
    return {"title": title, "specs": specs.normalise(title, table), "price_inr": price}


def test_match_when_every_filter_is_met():
    hunt = _hunt(brands=["Lenovo"], gpu_models=["RTX 5070"], ram_min_gb=32, panels=["OLED"], budget_max_inr=350000)
    verdict, chips = matching.evaluate(hunt, _listing(FLIPKART_TITLE, FLIPKART_TABLE, 310590))
    assert verdict == "match"
    assert ("RTX 5070", "match") in chips and ("32 GB RAM", "match") in chips
    assert ("DDR5", "plain") in chips  # shown, but no filter on it


def test_one_failed_filter_is_a_near_miss_and_two_are_not():
    listing = _listing(FLIPKART_TITLE, FLIPKART_TABLE, 310590)
    assert matching.evaluate(_hunt(brands=["Lenovo"], budget_max_inr=300000), listing)[0] == "near"
    assert matching.evaluate(_hunt(brands=["ASUS"], budget_max_inr=300000), listing)[0] == "miss"


def test_rtx_5070_filter_does_not_accept_a_5070_ti():
    listing = _listing("ASUS ROG Strix G16 Ryzen 9 8940HX, RTX 5070 Ti, 16GB RAM, 1TB SSD", {})
    assert ("RTX 5070 Ti", "miss") in matching.evaluate(_hunt(gpu_models=["RTX 5070"]), listing)[1]
    assert ("RTX 5070 Ti", "match") in matching.evaluate(_hunt(gpu_models=["RTX 5070 Ti"]), listing)[1]


def test_a_spec_the_page_left_out_is_unknown_not_failed():
    listing = _listing("ASUS ROG Strix G16 Ryzen 9 8940HX, RTX 5070 Ti, 16GB RAM, 1TB SSD", {})
    verdict, chips = matching.evaluate(_hunt(panels=["OLED"], refresh_min_hz=165), listing)
    assert verdict == "near"
    assert ("Panel?", "unknown") in chips and ("Refresh rate?", "unknown") in chips
