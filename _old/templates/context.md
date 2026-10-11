Project Context: Spec-Based Laptop Price Tracker
1. Project Overview
The Laptop Price Tracker is a local Python-based automation tool designed to hunt for the lowest-priced laptops across Indian e-commerce platforms (Amazon, Flipkart, Croma, Vijay Sales).

Unlike traditional trackers that monitor a static URL, this tool operates as a Spec-Based Hunter. The user inputs granular constraints (e.g., RTX 5080, >= 32GB RAM, <= 1TB SSD), and the scraper dynamically searches the storefronts, validates the results against the constraints, and alerts the user when a matching device hits an all-time low price.

2. Tech Stack (100% Free & Local)
Backend / Web Server: Flask (Python)

Database: SQLite (tracker.db)

Frontend UI: HTML5, Tailwind CSS (via CDN), Jinja2 Templating

Web Scraper: Playwright (Python) + playwright-stealth (to bypass Cloudflare/Akamai bot detection)

Alerts & Notifications:

CallMeBot API (Free WhatsApp messaging to personal numbers)

smtplib (Email via Gmail App Passwords)

Environment Management: python-dotenv for keeping API keys secure.

3. Architecture & File Structure
Plaintext
laptop_tracker/
│
├── app.py                 # Flask server, DB initialization, and input parsing
├── scraper.py             # Playwright automation engine (In Progress)
├── requirements.txt       # Dependencies list
├── .env                   # Secrets (DO NOT COMMIT)
├── .env.example           # Template for secrets
├── .gitignore             # Hides .env, DB, and cache
└── templates/
    └── index.html         # Tailwind CSS frontend dashboard
4. Core Features & Implementation Status
✅ Completed: Database Design
To handle an exhaustive list of potential specifications without creating a 50-column table, specs are stored dynamically.

Table: spec_trackers

Columns: id, search_name, specs_json (stores all specs and logical operators), notification_email, notification_whatsapp.

✅ Completed: User Interface (index.html)
Flexible Inputs: Uses <input list="..."> and <datalist> to create "comboboxes." This allows users to select standard options from a dropdown OR type custom text.

Expandable Sections: Utilizes native HTML <details> tags to hide exhaustive advanced specs (Connectivity, Display, Item Dimensions) while keeping Primary Specs (GPU, CPU, RAM) visible.

Logical Operators: Users can select >=, <=, or == for numeric fields like RAM, VRAM, and Storage.

✅ Completed: Backend Data Sanitation (app.py)
Extracts logical operators and prepends them to the data (e.g., >= 32 GB).

Uses Regex to auto-format lazy inputs (e.g., converts 16 to 16 GB for RAM; converts 1tb to 1 TB for storage).

Saves the sanitized payload as a JSON object in SQLite.

🔄 In Progress: The Scraper Engine (scraper.py)
Implemented: Reads the SQLite DB, parses the JSON, and builds an optimized e-commerce search query prioritizing Highly Identifying Specs (Brand, CPU Model, GPU Brand, GPU Model, GPU VRAM, RAM).

Implemented: Basic headless Playwright navigation to Amazon India.

Pending (Hand-off Task): The matching logic.

5. Next Steps / Hand-off Tasks for the Next LLM
Task 1: Build the Strict Validation Engine in scraper.py
Currently, the scraper navigates to Amazon and grabs the top 3 results. The next step is to write a validation function that takes the scraped product title/description and strictly compares it against the specs_json.

Challenge: It must evaluate the logical operators. If the JSON says RAM: ">= 32 GB", the scraper must parse the found laptop's RAM and ensure it is 32GB or higher before considering it a match.

Task 2: Expand to Flipkart
Replicate the Amazon scraping logic for Flipkart.

Challenge: Flipkart's DOM structure is highly dynamic. The CSS selectors for title and price (div._30jeq3 or similar) need to be accurately mapped.

Task 3: Integrate Historical Pricing & DB Logging
Once a valid laptop is found, the scraper needs to check the price_logs table (needs to be created) to determine if the current price is the new "All-Time Low".

Task 4: Notification Dispatch
Write the final function that triggers the requests.get() call to the CallMeBot WhatsApp API and the smtplib email dispatch if a new lowest price is logged.

Note to developer/LLM: Ensure you reference the existing project documentation log within the "Laptop Price Tracker" file to maintain continuity regarding UI decisions and formatting rules.