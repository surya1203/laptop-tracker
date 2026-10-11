import sqlite3
import json
import re
from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = 'super_secret_local_key'
DB_NAME = "tracker.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS spec_trackers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_name TEXT NOT NULL,
            specs_json TEXT NOT NULL,
            notification_email TEXT,
            notification_whatsapp TEXT
        )
    ''')
    conn.commit()
    conn.close()

def format_storage(val):
    match = re.match(r'^(\d+)\s*([a-zA-Z]+)$', val.strip())
    if match:
        num, unit = match.groups()
        return f"{num} {unit.upper()}"
    return val.strip()

def format_ram(val):
    val = val.strip()
    if val.isdigit():
        return f"{val} GB"
    match = re.match(r'^(\d+)\s*([a-zA-Z]+)$', val)
    if match:
        num, unit = match.groups()
        return f"{num} {unit.upper()}"
    return val

@app.route('/')
def index():
    conn = sqlite3.connect(DB_NAME)
    trackers = conn.execute('SELECT id, search_name, specs_json FROM spec_trackers').fetchall()
    conn.close()
    
    parsed_trackers = []
    for t in trackers:
        parsed_trackers.append({
            'id': t[0],
            'name': t[1],
            'specs': json.loads(t[2])
        })
        
    return render_template('index.html', trackers=parsed_trackers)

@app.route('/add', methods=['POST'])
def add_tracker():
    form_data = dict(request.form)
    search_name = form_data.pop('search_name', '').strip()
    email = form_data.pop('notification_email', '').strip()
    whatsapp = form_data.pop('notification_whatsapp', '').strip()

    active_specs = {}
    
    # Process regular fields and modifiers
    for key, value in form_data.items():
        if value.strip() and not key.endswith('_mod'):
            # Check if this field has a modifier (>=, <=, ==)
            modifier = form_data.get(f"{key}_mod", "").strip()
            prefix = f"{modifier} " if modifier else ""
            
            if key == 'storage_capacity' or key == 'hard_drive_size':
                active_specs[key] = f"{prefix}{format_storage(value)}"
            elif key in ['ram', 'gpu_vram', 'graphics_ram_size', 'ram_memory_installed']:
                active_specs[key] = f"{prefix}{format_ram(value)}"
            else:
                active_specs[key] = value.strip()

    if not active_specs and not search_name:
        flash("You must fill out at least one specification or a Search Name.")
        return redirect(url_for('index'))

    if not search_name:
        search_name = "Detailed Spec Search"

    conn = sqlite3.connect(DB_NAME)
    conn.execute('''
        INSERT INTO spec_trackers (search_name, specs_json, notification_email, notification_whatsapp)
        VALUES (?, ?, ?, ?)
    ''', (search_name, json.dumps(active_specs), email, whatsapp))
    conn.commit()
    conn.close()
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)