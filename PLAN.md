# PC Tracker: Rebuild Plan

Oct 10, 2026 · Surya Giri

> **For Claude Code:** this is the agreed plan for rebuilding this project. Read it fully before changing code. Build in the phase order under "Build order", one phase at a time, and stop for review after each phase. Answered decisions are at the end. The old `templates/context.md` is inaccurate (it claims scraper work that doesn't exist) and should not be trusted.

## Summary

Keep the stack (Flask, SQLite, Tailwind, Playwright), rebuild almost everything on top of it. The current build is a long spec form that saves text; nothing ever searches, tracks a price or sends an alert, because `scraper.py` is empty (0 bytes) even though the hand-off notes say parts of it are done.

The rebuild turns it into a four-step loop: **describe the laptop you want, preview what the stores have, pick the listings to track, get told when one hits a new low.** Every spec gets its own field with a fixed list of choices, every tracked item links to its real product page, and anything you track can be paused, removed or cleared.

## Keep vs redo

What exists today is about 3 KB of Flask, a 23 KB form template, an empty scraper and a database holding two saved searches (both "Legion", RTX 5080). Verdict per piece:

| Piece | Today | Verdict |
| --- | --- | --- |
| Stack: Flask, SQLite, Jinja, Tailwind, Playwright | Sensible, free, runs locally | **Keep** |
| `app.py` | One file; single table; specs saved as text like `">= 32 GB"`; no edit or delete; hard-coded secret key | **Rewrite** into a small package (routes, models, scraper, notifier) |
| Database schema | One table, specs as a JSON blob of strings | **Replace** with typed tables (next section); migrate the 2 saved searches |
| `index.html` | ~70 free-text inputs copied from an Amazon spec sheet; duplicates (Brand vs Brand Name, RAM vs RAM Installed, GPU VRAM vs Graphics RAM Size); a "Scanner Resolution" field; storage type and interface merged into one box | **Redo** as a multi-page UI with a short, deduplicated filter set |
| `scraper.py` | Empty | **Build from scratch** |
| `context.md` hand-off notes | Claims scraper work that does not exist | **Replace** with an accurate README |
| Ideas worth keeping | Min/max comparisons on RAM, VRAM, storage; dropdown-or-type inputs; Indian retailers; email + WhatsApp alerts | **Keep**, done properly |

## Filters and data model

Every attribute is its own field, stored as a typed value, never as a sentence. Brand-dependent lists cascade: pick a CPU brand and the model list shows only that brand's chips; same for GPUs. Every field defaults to "Any", and each dropdown still accepts a typed value for something new.

| Group | Field | Input | Example choices |
| --- | --- | --- | --- |
| Laptop | Brand | Multi-select | Lenovo, ASUS, HP, Dell, MSI, Acer, Apple |
| Laptop | Series / model line | Text, suggested per brand | Legion Pro 7, ROG Strix G16 |
| CPU | CPU brand | Dropdown | Intel, AMD, Apple, Qualcomm |
| CPU | CPU family | Dropdown, filtered by brand | Core Ultra 9, Core i7, Ryzen 9, M4 Pro |
| CPU | CPU model | Text, optional | 275HX, 9955HX |
| GPU | GPU brand | Dropdown | NVIDIA, AMD, Intel, Apple (integrated) |
| GPU | GPU model | Multi-select, filtered by brand | RTX 5090, RTX 5080, RTX 5070 Ti |
| GPU | VRAM | Minimum | 8, 12, 16, 24 GB |
| Memory | RAM size | Minimum | 16, 32, 64 GB |
| Memory | RAM type | Dropdown | DDR5, LPDDR5X, DDR4 |
| Storage | Storage type | Dropdown | SSD, HDD, SSD + HDD |
| Storage | Storage interface | Dropdown, optional | NVMe PCIe 4.0, NVMe PCIe 5.0 |
| Storage | Storage size | Minimum | 512 GB, 1 TB, 2 TB |
| Display | Screen size | Min and max | 14 to 18 inches |
| Display | Resolution | Minimum | FHD, QHD+, 4K |
| Display | Refresh rate | Minimum | 120, 165, 240 Hz |
| Display | Panel | Multi-select | IPS, OLED, Mini-LED |
| Other | Max weight | Maximum | 2.5 kg |
| Price | Budget | Max, in ₹ | 2,50,000 |
| Where | Retailers | Checkboxes | Amazon, Flipkart, Croma, Vijay Sales, Reliance Digital |

Min/max fields replace the current `>=`/`<=`/`==` selectors: "RAM at least 32 GB" reads better and covers every real case. The ~50 rarely used fields (ports, Bluetooth version, webcam) are dropped from the form; the scraper still saves every raw spec it finds, so they can come back later as filters without re-scraping.

The database grows from one table to five:

- **hunts**: a saved search; one column per filter above, plus name, status (active, paused) and created date.
- **listings**: one product page found at one retailer: URL, title, image, retailer, parsed specs, raw spec table, and state (new, tracked, ignored).
- **price_points**: listing, price, MRP, in stock or not, time checked. One row per check.
- **alerts**: what was sent, on which channel, for which price, when. Prevents repeats.
- **settings**: notification channels, check frequency, quiet hours.

## How you use it

Yes, you will see every found item before anything is tracked, with a button to its real product page. Nothing is tracked automatically.

1. **Create a hunt.** Fill only the filters you care about, name it, save. You can also skip filters and paste a product URL to track that one page directly.
2. **Search now.** The scraper searches each chosen retailer, opens each result's product page, and reads its spec table (more reliable than reading titles).
3. **Review results.** A grid of cards, each with photo, title, retailer, current price, MRP, and spec chips. Chips are green when they match a filter, red when they don't, grey when the page didn't say. Results split into **Matches** and **Near misses** (one filter failed or unknown), so a listing with a vague spec sheet isn't silently lost. Each card has **View on Amazon/Flipkart/…** (opens the real page in a new tab) and a **Track** checkbox.
4. **Track selected.** Ticked cards move to the hunt's tracked list; unticked ones are hidden as ignored and won't be shown again on the next search. New listings that appear later land in a "New since last visit" tray for the same review.
5. **Watch.** Tracked listings are re-checked on a schedule. The same laptop at several stores is grouped by model number so you see one row with the cheapest store highlighted.

Clearing tracking, at every level:

- **One listing:** Untrack (keeps its price history) or Delete (removes it).
- **One hunt:** Pause (stops checks and alerts), Edit filters, or Delete with its listings.
- **Everything:** "Clear all tracking" in Settings, behind a confirm dialog, with an option to keep or wipe price history.
- Every delete shows a 10-second Undo.

## Prices, lows and alerts

Every check writes a price point, so "lowest price" is computed from your own history, not guessed. Default schedule: every 6 hours while the app runs, adjustable in Settings, with a random delay between pages so stores don't block it.

Each tracked listing shows:

- Current price, MRP and discount, in ₹ with Indian grouping (₹1,89,990).
- All-time low and 30-day low since tracking began, with the date each was seen.
- A price-history chart, one line per store when the same model is sold in several.
- Stock status; out-of-stock checks are recorded but never count as a low.

Alert rules, set per hunt (any combination):

| Rule | Fires when |
| --- | --- |
| New all-time low | Price is below every earlier price point for that listing |
| Target price | Price drops to or below a number you set |
| Drop by % | Price falls at least X% below the previous check |
| Back in stock | An out-of-stock listing becomes buyable |
| New match | A new listing matching the hunt appears (goes to the review tray) |

Channels: in-app alert feed (always on), email via Gmail app password, and WhatsApp via CallMeBot, both already in your plan. Telegram is a recommended extra: free, instant, and more dependable than CallMeBot's shared service. Each alert carries the laptop name, old and new price, the store and a direct link. A per-listing cooldown (default 24 h) and quiet hours stop repeat pings, and Settings has a **Send test alert** button for each channel.

Prices tracked are the listed selling price. Bank-card and exchange offers vary per buyer, so they are shown as a note when the page lists them, not used in the low.

## Visual design

The one long form becomes a small app with a left sidebar and five pages, built like a shopping dashboard rather than a settings screen.

| Page | What it shows |
| --- | --- |
| Dashboard | Biggest drops this week, tracked items at their all-time low, recent alerts, next check time |
| Hunts | One card per hunt: filter summary as chips, matches found, cheapest match, Pause / Edit / Delete |
| Hunt detail | Filters panel on the left, results grid on the right with Matches / Near misses / Tracked tabs |
| Tracked | Table of every tracked laptop, grouped by model, sortable by price, drop %, distance from low |
| Settings | Notification channels with test buttons, check schedule, clear all tracking |

Look and feel:

- **Theme:** light and dark, following the system setting. Dark is a deep slate background with one accent colour (emerald for price drops, red for increases); no gradients or glow.
- **Type:** Inter for text, tabular figures so prices line up; prices are the largest text on every card.
- **Cards:** product photo on a white tile (store photos have white backgrounds), retailer logo badge, spec chips, a small sparkline of the last 30 days.
- **Filter form:** grouped into collapsible panels (Laptop, CPU, GPU, Memory, Storage, Display, Budget and stores), with a live "active filters" chip bar at the top you can click to remove.
- **Feedback:** a progress panel while a search runs ("Amazon: 24 found, checking specs 9/24"), toasts for saves and undos, clear empty states.
- **Interactivity:** HTMX for in-place updates (track, untrack, filter, search progress) so it feels like an app without a JavaScript framework; Chart.js for price history.
- Works on a phone browser on the same Wi-Fi, so alerts can be followed up from the phone.

![Hunt results page mock-up](docs/results-page-mockup.png)

You tick the listings you want, open any of them on the store's own page first, and only ticked ones are tracked. Mock-up uses sample data.

## Build order

Five phases, each ending in something you can open and use. Phase 2 is the riskiest, so it comes early.

1. **Foundation.** New project layout, new database with the 2 saved Legion hunts migrated, the sidebar layout and design system, the new filter form with cascading dropdowns, edit/pause/delete for hunts.
2. **Search and preview (Amazon + Flipkart).** One scraper module per store behind a common interface (search, read product page), a spec normaliser that turns "16 GB DDR5 5600MHz" into size 16, type DDR5, the results grid with Matches / Near misses, View-on-store links, and Track selected.
3. **Price history.** Background scheduler, price points, all-time and 30-day lows, charts, the Tracked page, grouping the same model across stores.
4. **Alerts.** Alert rules per hunt, email and WhatsApp (plus Telegram if you want it), cooldowns, quiet hours, test buttons, alert feed.
5. **More stores and polish.** Croma, Vijay Sales, Reliance Digital; add-by-URL; dashboard; mobile layout pass.

Known risk: Amazon and Flipkart actively block bots and change their page layouts. The plan copes by checking slowly, using a real (non-headless) browser profile, keeping each store's parsing in one small file that is quick to fix, and showing a "store check failed" badge instead of failing silently.

## Decisions (answered)

- [x] Stores for phase 2: Amazon + Flipkart (**default**), or all five from the start? → **Amazon + Flipkart**
- [x] Alert channels: email + WhatsApp as planned (**default**), add Telegram, or swap WhatsApp for Telegram? → **Email + WhatsApp**
- [x] Check frequency: every 6 hours (**default**), or another interval? → **Every 6 hours**
- [ ] Where it runs: on your PC for now. Later, some kind of cloud service, maybe Amazon (AWS); which AWS service is still undecided. → **Build to run locally now, but keep it cloud-ready** (config via `.env`, no hard-coded paths, database path configurable).
- [x] Existing code: rebuild in place in the laptop_tracker folder (**default**, old files moved to an `_old/` folder), or start a fresh folder? → **Rebuild in place, old files to `_old/`**
- [x] Delivery check (added Oct 11, during phase 2): an optional delivery PIN code in Settings; each search records whether a listing can be delivered there. → **One PIN code for the whole app, blank = no check**
- [x] More stores (asked for Oct 11, ahead of phase 5): Croma, Vijay Sales and Reliance Digital switched on, plus the brands' own Indian stores. → **Added Lenovo, ASUS, Dell, Acer, Apple and Samsung. HP's store blocks automated browsers; MSI and Gigabyte have no Indian online store of their own.**
- [x] Check frequency (changed Oct 11): a choice in Settings instead of a fixed 6 hours. → **1, 3, 6, 12 or 24 hours; default 6**
- [x] Phases 3 and 4 built together on Oct 11 at the user's request. Left out: the "new match" alert, the Chart.js history chart (a sparkline instead), per-listing delete, "Clear all tracking".
