"""Compare one listing's specs with a hunt's filters.

Each spec becomes a chip: "match" (meets a filter), "miss" (fails it), "unknown"
(a filter is set but the page did not say) or "plain" (no filter on that spec).
"""
from . import catalog
from .hunts import inr, num, size
from .specs import squash

MATCH, MISS, UNKNOWN, PLAIN = "match", "miss", "unknown", "plain"


def _state(wanted, known, ok):
    """No filter -> plain; filter but no value -> unknown; otherwise match or miss."""
    if not wanted:
        return PLAIN
    if not known:
        return UNKNOWN
    return MATCH if ok else MISS


def _worst(*states):
    for state in (MISS, UNKNOWN, MATCH):
        if state in states:
            return state
    return PLAIN


def _mentions(haystack, needle):
    return squash(needle) in squash(haystack)


def evaluate(hunt, listing):
    """Returns (verdict, chips). verdict is 'match', 'near' or 'miss'; chips is [(text, state), ...]."""
    specs = listing["specs"]
    chips = []

    def chip(text, state, missing):
        """Show the spec; if the page did not give it, say which filter could not be checked."""
        if text:
            chips.append((text, state))
        elif state == UNKNOWN:
            chips.append((f"{missing}?", UNKNOWN))

    brand = specs.get("brand")
    wanted = [b.lower() for b in hunt["brands"]]
    chip(brand, _state(wanted, brand, (brand or "").lower() in wanted), "Brand")

    if hunt["series"]:
        name = f"{listing['title']} {specs.get('series') or ''}"
        chips.append((hunt["series"], MATCH if _mentions(name, hunt["series"]) else MISS))

    cpu_text = specs.get("cpu_text") or ""
    cpu = _worst(
        _state(hunt["cpu_brand"], specs.get("cpu_brand"),
               (specs.get("cpu_brand") or "").lower() == (hunt["cpu_brand"] or "").lower()),
        _state(hunt["cpu_family"], specs.get("cpu_family") or cpu_text.strip(),
               (specs.get("cpu_family") or "").lower() == (hunt["cpu_family"] or "").lower()
               or _mentions(cpu_text, hunt["cpu_family"] or "")),
        _state(hunt["cpu_model"], cpu_text.strip(), _mentions(cpu_text, hunt["cpu_model"] or "")),
    )
    chip(" ".join(p for p in (specs.get("cpu_family") or specs.get("cpu_brand"), specs.get("cpu_model")) if p), cpu, "CPU")

    gpu_model, gpu_text = specs.get("gpu_model"), specs.get("gpu_text") or ""
    known_models = {m.lower() for models in catalog.GPU_MODELS.values() for m in models}
    wanted_models = hunt["gpu_models"]
    model_ok = any(
        (gpu_model or "").lower() == m.lower() if m.lower() in known_models else _mentions(gpu_text, m)
        for m in wanted_models
    )
    gpu = _worst(
        _state(hunt["gpu_brand"], specs.get("gpu_brand"),
               (specs.get("gpu_brand") or "").lower() == (hunt["gpu_brand"] or "").lower()),
        _state(wanted_models, gpu_model or gpu_text.strip(), model_ok),
    )
    chip(gpu_model or specs.get("gpu_brand"), gpu, "GPU")

    def at_least(field, wanted_value, text, missing):
        value = specs.get(field)
        chip(text(value) if value else None, _state(wanted_value, value, value and value >= (wanted_value or 0)), missing)

    at_least("vram_gb", hunt["vram_min_gb"], lambda v: f"{v} GB VRAM", "VRAM")
    at_least("ram_gb", hunt["ram_min_gb"], lambda v: f"{v} GB RAM", "RAM")

    ram_type = specs.get("ram_type")
    chip(ram_type, _state(hunt["ram_type"], ram_type, (ram_type or "").lower() == (hunt["ram_type"] or "").lower()), "RAM type")

    storage_type = specs.get("storage_type")
    storage_gb = specs.get("storage_gb")
    storage = _worst(
        _state(hunt["storage_type"], storage_type, storage_type == hunt["storage_type"]),
        _state(hunt["storage_min_gb"], storage_gb, storage_gb and storage_gb >= (hunt["storage_min_gb"] or 0)),
    )
    chip(" ".join(p for p in (size(storage_gb) if storage_gb else None, storage_type) if p), storage, "Storage")

    interface = specs.get("storage_interface")
    # A bare "NVMe" does not say which PCIe generation, so it cannot confirm or rule out a specific one.
    exact = interface if interface != "NVMe" or hunt["storage_interface"] == "NVMe" else None
    state = _state(hunt["storage_interface"], exact, exact == hunt["storage_interface"])
    if hunt["storage_interface"] or interface:
        chip(interface if state != UNKNOWN else None, state, hunt["storage_interface"] or "Interface")

    screen = specs.get("screen_in")
    low, high = hunt["screen_min_in"], hunt["screen_max_in"]
    chip(f'{num(screen)}"' if screen else None,
         _state(low or high, screen, screen and (not low or screen >= low) and (not high or screen <= high)), "Screen")

    resolution = specs.get("resolution")
    order = catalog.RESOLUTIONS
    chip(resolution, _state(hunt["resolution_min"], resolution,
                            resolution in order and hunt["resolution_min"] in order
                            and order.index(resolution) >= order.index(hunt["resolution_min"])), "Resolution")

    at_least("refresh_hz", hunt["refresh_min_hz"], lambda v: f"{v} Hz", "Refresh rate")

    panel = specs.get("panel")
    wanted = [p.lower() for p in hunt["panels"]]
    chip(panel, _state(wanted, panel, (panel or "").lower() in wanted), "Panel")

    weight = specs.get("weight_kg")
    chip(f"{num(weight)} kg" if weight else None,
         _state(hunt["weight_max_kg"], weight, weight and weight <= (hunt["weight_max_kg"] or 0)), "Weight")

    price = listing.get("price_inr")
    if hunt["budget_max_inr"]:
        state = _state(True, price, price and price <= hunt["budget_max_inr"])
        chips.append((f"Budget {inr(hunt['budget_max_inr'])}" if price else "Price?", state))

    misses = sum(1 for _, state in chips if state == MISS)
    unknowns = sum(1 for _, state in chips if state == UNKNOWN)
    verdict = "match" if not misses and not unknowns else "near" if misses <= 1 else "miss"
    return verdict, chips
