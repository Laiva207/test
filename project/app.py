from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
import requests
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "super_secret_key_123"  # sesiju atslēga


# ===== oficiālās vietas =====
OFFICIAL_LOCATIONS = [
    "Venta",
    "Abava",
    "Daugava",
    "Lielupe",
    "Usmas ezers",
    "Engures ezers",
    "Burtnieku ezers",
    "Lubāna ezers"
]


# ===== DB savienojums =====
def get_db_connection():
    conn = sqlite3.connect("fishing.db")  # pieslēgums DB
    conn.row_factory = sqlite3.Row  # kolonnas pēc nosaukuma
    return conn


# ===== laikapstākļu koda tulkojums =====
def weather_code_to_text(code):
    weather_codes = {
        0: "Skaidrs",
        1: "Pārsvarā skaidrs",
        2: "Daļēji mākoņains",
        3: "Apmācies",
        45: "Migla",
        48: "Sarima",
        51: "Neliels smidzeklis",
        53: "Smidzeklis",
        55: "Spēcīgs smidzeklis",
        61: "Neliels lietus",
        63: "Lietus",
        65: "Spēcīgs lietus",
        71: "Neliels sniegs",
        73: "Sniegs",
        75: "Spēcīgs sniegs",
        80: "Lietusgāzes",
        81: "Stiprākas lietusgāzes",
        82: "Ļoti stipras lietusgāzes",
        95: "Negaiss",
    }
    return weather_codes.get(code, "Nezināmi laikapstākļi")


# ===== koordinātas pēc vietas =====
def get_coordinates(location_name):
    try:
        url = "https://geocoding-api.open-meteo.com/v1/search"
        params = {
            "name": location_name,
            "count": 1,
            "language": "en",
            "format": "json"
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if "results" in data and data["results"]:
            result = data["results"][0]
            return result["latitude"], result["longitude"], result["name"]
    except Exception:
        return None

    return None


# ===== laikapstākļi pēc vietas =====
def get_weather_for_location(location_name):
    coords = get_coordinates(location_name)
    if not coords:
        return None

    latitude, longitude, resolved_name = coords

    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,wind_speed_10m,weather_code",
            "timezone": "auto"
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        current = data.get("current")

        if not current:
            return None

        return {
            "location": resolved_name,
            "temperature": current.get("temperature_2m"),
            "wind_speed": current.get("wind_speed_10m"),
            "weather_text": weather_code_to_text(current.get("weather_code")),
        }
    except Exception:
        return None


# ===== iespējamās zivis pēc vietas =====
def get_possible_fish_by_location(location_name):
    fish_map = {
        "Venta": ["Līdaka", "Asaris", "Zandarts", "Sapals", "Vimba", "Sams"],
        "Abava": ["Forele", "Alata", "Asaris", "Līdaka"],
        "Daugava": ["Līdaka", "Zandarts", "Sams", "Asaris", "Plaudis"],
        "Lielupe": ["Līdaka", "Zandarts", "Asaris", "Karūsa"],
        "Usmas ezers": ["Līdaka", "Asaris", "Zandarts", "Līnis"],
        "Engures ezers": ["Līdaka", "Asaris", "Līnis", "Karūsa"],
        "Burtnieku ezers": ["Līdaka", "Asaris", "Zandarts", "Plaudis"],
        "Lubāna ezers": ["Līdaka", "Asaris", "Karūsa", "Līnis"]
    }
    return fish_map.get(location_name, ["Līdaka", "Asaris", "Zandarts"])


# ===== admin pārbaude =====
def is_admin():
    return session.get("role") == "admin"


# ===== DB izveide =====
def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    # lietotāji
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user'
    )
    """)

    # ieraksti
    c.execute("""
    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        location TEXT NOT NULL,
        date TEXT NOT NULL,
        season TEXT NOT NULL,
        weather TEXT NOT NULL,
        notes TEXT,
        user_id INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # zivis
    c.execute("""
    CREATE TABLE IF NOT EXISTS fish (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )
    """)

    # saite note ↔ fish
    c.execute("""
    CREATE TABLE IF NOT EXISTS note_fish (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        note_id INTEGER NOT NULL,
        fish_id INTEGER NOT NULL,
        FOREIGN KEY (note_id) REFERENCES notes(id),
        FOREIGN KEY (fish_id) REFERENCES fish(id)
    )
    """)

    # pievieno role kolonnu vecai DB, ja vajag
    try:
        c.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
    except sqlite3.OperationalError:
        pass

    # sākuma zivis
    default_fish = [
        "Līdaka", "Asaris", "Zandarts", "Rauda", "Karūsa",
        "Līnis", "Sapals", "Vimba", "Sams", "Forele",
        "Alata", "Plaudis"
    ]

    for fish_name in default_fish:
        c.execute("INSERT OR IGNORE INTO fish (name) VALUES (?)", (fish_name,))

    # admin lietotājs
    admin_username = "admin"
    admin_password = "Admin123"

    admin_user = c.execute(
        "SELECT * FROM users WHERE username = ?",
        (admin_username,)
    ).fetchone()

    if not admin_user:
        hashed_admin_password = generate_password_hash(admin_password)
        c.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (admin_username, hashed_admin_password, "admin")
        )

    conn.commit()
    conn.close()


init_db()


# ===== login =====
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        conn.close()

        # paroles pārbaude
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]

            if user["role"] == "admin":
                return redirect(url_for("admin_panel"))

            return redirect(url_for("dashboard"))

        return render_template("login.html", error="Nepareizs lietotājvārds vai parole")

    return render_template("login.html")


# ===== reģistrācija =====
@app.route("/register", methods=["POST"])
def register():
    username = request.form["username"].strip()
    password = request.form["password"]

    # lietotājvārda pārbaude
    if len(username) < 3:
        return render_template("login.html", error="Lietotājvārdam jābūt vismaz 3 simboliem")

    # paroles pārbaude
    if len(password) < 6:
        return render_template("login.html", error="Parolei jābūt vismaz 6 simboliem")

    if not any(ch.isdigit() for ch in password):
        return render_template("login.html", error="Parolei jāsatur vismaz viens cipars")

    hashed_password = generate_password_hash(password)  # hash parole

    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (username, hashed_password, "user")
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return render_template("login.html", error="Šāds lietotājs jau eksistē")

    conn.close()
    return redirect(url_for("login"))


# ===== lietotāja panelis =====
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    notes = conn.execute(
        "SELECT * FROM notes WHERE user_id = ? ORDER BY date DESC, id DESC",
        (session["user_id"],)
    ).fetchall()

    notes_with_fish = []
    for note in notes:
        fish_rows = conn.execute("""
            SELECT fish.name
            FROM fish
            JOIN note_fish ON fish.id = note_fish.fish_id
            WHERE note_fish.note_id = ?
        """, (note["id"],)).fetchall()

        fish_names = [row["name"] for row in fish_rows]
        notes_with_fish.append({
            "id": note["id"],
            "location": note["location"],
            "date": note["date"],
            "season": note["season"],
            "weather": note["weather"],
            "notes": note["notes"],
            "fish": fish_names
        })

    conn.close()

    weather_data = get_weather_for_location("Kuldīga")

    return render_template(
        "dashboard.html",
        notes=notes_with_fish,
        weather_data=weather_data
    )


# ===== admin panelis =====
@app.route("/admin")
def admin_panel():
    if "user_id" not in session or not is_admin():
        return redirect(url_for("login"))

    conn = get_db_connection()
    rows = conn.execute("""
        SELECT notes.id, notes.location, notes.date, notes.season, notes.weather, notes.notes,
               users.username
        FROM notes
        JOIN users ON notes.user_id = users.id
        ORDER BY notes.date DESC, notes.id DESC
    """).fetchall()

    all_notes = []
    for row in rows:
        fish_rows = conn.execute("""
            SELECT fish.name
            FROM fish
            JOIN note_fish ON fish.id = note_fish.fish_id
            WHERE note_fish.note_id = ?
        """, (row["id"],)).fetchall()

        fish_names = [f["name"] for f in fish_rows]

        all_notes.append({
            "id": row["id"],
            "username": row["username"],
            "location": row["location"],
            "date": row["date"],
            "season": row["season"],
            "weather": row["weather"],
            "notes": row["notes"],
            "fish": fish_names
        })

    conn.close()
    return render_template("admin.html", notes=all_notes)


# ===== pievienot ierakstu =====
@app.route("/add", methods=["GET", "POST"])
def add_note():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    if request.method == "POST":
        location = request.form["location"]
        date = request.form["date"]
        season = request.form["season"]
        weather = request.form["weather"].strip()
        notes_text = request.form.get("notes", "").strip()
        selected_fish = request.form.getlist("fish")

        # minimāla pārbaude
        if not location or not date or not season or not weather:
            fish_rows = conn.execute("SELECT * FROM fish ORDER BY name").fetchall()
            conn.close()
            return render_template(
                "add_note.html",
                fish=fish_rows,
                locations=OFFICIAL_LOCATIONS,
                suggested_fish=get_possible_fish_by_location(location if location else "Venta"),
                error="Aizpildi visus obligātos laukus"
            )

        # saglabā note
        cursor = conn.execute("""
            INSERT INTO notes (location, date, season, weather, notes, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (location, date, season, weather, notes_text, session["user_id"]))

        note_id = cursor.lastrowid

        # saglabā zivis
        for fish_id in selected_fish:
            conn.execute(
                "INSERT INTO note_fish (note_id, fish_id) VALUES (?, ?)",
                (note_id, fish_id)
            )

        conn.commit()
        conn.close()
        return redirect(url_for("dashboard"))

    fish_rows = conn.execute("SELECT * FROM fish ORDER BY name").fetchall()
    conn.close()

    return render_template(
        "add_note.html",
        fish=fish_rows,
        locations=OFFICIAL_LOCATIONS,
        suggested_fish=get_possible_fish_by_location("Venta"),
        error=None
    )


# ===== rediģēt ierakstu =====
@app.route("/edit/<int:note_id>", methods=["GET", "POST"])
def edit_note(note_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    note = conn.execute(
        "SELECT * FROM notes WHERE id = ? AND user_id = ?",
        (note_id, session["user_id"])
    ).fetchone()

    if not note:
        conn.close()
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        location = request.form["location"]
        date = request.form["date"]
        season = request.form["season"]
        weather = request.form["weather"].strip()
        notes_text = request.form["notes"].strip()
        selected_fish = request.form.getlist("fish")

        conn.execute("""
            UPDATE notes
            SET location = ?, date = ?, season = ?, weather = ?, notes = ?
            WHERE id = ? AND user_id = ?
        """, (location, date, season, weather, notes_text, note_id, session["user_id"]))

        conn.execute("DELETE FROM note_fish WHERE note_id = ?", (note_id,))

        for fish_id in selected_fish:
            conn.execute(
                "INSERT INTO note_fish (note_id, fish_id) VALUES (?, ?)",
                (note_id, fish_id)
            )

        conn.commit()
        conn.close()
        return redirect(url_for("dashboard"))

    fish_rows = conn.execute("SELECT * FROM fish ORDER BY name").fetchall()
    selected_rows = conn.execute(
        "SELECT fish_id FROM note_fish WHERE note_id = ?",
        (note_id,)
    ).fetchall()
    selected_ids = [row["fish_id"] for row in selected_rows]

    conn.close()

    return render_template(
        "edit_note.html",
        note=note,
        fish=fish_rows,
        selected_ids=selected_ids,
        locations=OFFICIAL_LOCATIONS,
        suggested_fish=get_possible_fish_by_location(note["location"])
    )


# ===== dzēst ierakstu =====
@app.route("/delete/<int:note_id>")
def delete_note(note_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    conn.execute("DELETE FROM note_fish WHERE note_id = ?", (note_id,))
    conn.execute(
        "DELETE FROM notes WHERE id = ? AND user_id = ?",
        (note_id, session["user_id"])
    )
    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))


# ===== logout =====
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)