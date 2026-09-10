"""Seferim — ilçe minibüs yer ayırma uygulaması."""

from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)

from schedule import (
    AUTO_NOTE,
    DEFAULT_ROUTE,
    SEED_DRIVERS,
    VEHICLE_TYPE,
    build_auto_trips,
    departure_time_for,
    drivers_with_group_index,
    group_for_day,
    weekly_plan_for,
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "seferim.db"

ROUTES = [
    ("ilce-merkez", "Refahiye → Erzincan"),
    ("merkez-ilce", "Erzincan → Refahiye"),
]

VEHICLE_TYPES = [
    "14 kişilik minibüs",
    "16 kişilik minibüs",
    "18 kişilik minibüs",
    "Diğer",
]

app = Flask(__name__)
app.secret_key = os.environ.get("SEFERIM_SECRET", "seferim-dev-secret-change-me")
DRIVER_REGISTER_CODE = os.environ.get("SEFERIM_DRIVER_CODE", "refahiye2026")
ADMIN_USERNAME = os.environ.get("SEFERIM_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("SEFERIM_ADMIN_PASS", "refahiye2026")


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_: object | None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS drivers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL UNIQUE,
            plate TEXT NOT NULL,
            vehicle_type TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_id INTEGER NOT NULL,
            route_code TEXT NOT NULL,
            depart_date TEXT NOT NULL,
            depart_time TEXT NOT NULL,
            seats_total INTEGER NOT NULL,
            driver_name TEXT NOT NULL,
            driver_phone TEXT NOT NULL,
            plate TEXT NOT NULL,
            vehicle_type TEXT NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (driver_id) REFERENCES drivers(id)
        );

        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id INTEGER NOT NULL,
            passenger_name TEXT NOT NULL,
            passenger_phone TEXT NOT NULL,
            seats INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE
        );
        """
    )
    db.commit()
    db.close()


def ensure_seed_drivers(db: sqlite3.Connection) -> list[dict]:
    """10 örnek şoförü kaydeder / günceller; A/B grup sırasını korur."""
    now = datetime.now().isoformat(timespec="seconds")
    drivers: list[dict] = []
    for seed in drivers_with_group_index():
        row = db.execute(
            "SELECT * FROM drivers WHERE phone = ?", (seed["phone"],)
        ).fetchone()
        if row:
            db.execute(
                """
                UPDATE drivers
                SET name = ?, plate = ?, vehicle_type = ?
                WHERE id = ?
                """,
                (seed["name"], seed["plate"], VEHICLE_TYPE, row["id"]),
            )
            driver_id = row["id"]
        else:
            cur = db.execute(
                """
                INSERT INTO drivers (name, phone, plate, vehicle_type, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (seed["name"], seed["phone"], seed["plate"], VEHICLE_TYPE, now),
            )
            driver_id = cur.lastrowid
        drivers.append(
            {
                "id": driver_id,
                "name": seed["name"],
                "phone": seed["phone"],
                "plate": seed["plate"],
                "vehicle_type": VEHICLE_TYPE,
                "group": seed["group"],
                "group_index": seed["group_index"],
            }
        )
    db.commit()
    return drivers


def regenerate_auto_schedule(weeks: int = 4) -> int:
    """Otomatik vardiya seferlerini silip yeniden üretir. Dönüş: eklenen sefer sayısı."""
    db = get_db()
    drivers = ensure_seed_drivers(db)

    old = db.execute(
        "SELECT id FROM trips WHERE note = ?", (AUTO_NOTE,)
    ).fetchall()
    for trip in old:
        db.execute("DELETE FROM reservations WHERE trip_id = ?", (trip["id"],))
    db.execute("DELETE FROM trips WHERE note = ?", (AUTO_NOTE,))

    now = datetime.now().isoformat(timespec="seconds")
    trips = build_auto_trips(drivers, start=date.today(), weeks=weeks, route_code=DEFAULT_ROUTE)
    for trip in trips:
        db.execute(
            """
            INSERT INTO trips (
                driver_id, route_code, depart_date, depart_time,
                seats_total, driver_name, driver_phone, plate,
                vehicle_type, note, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trip["driver_id"],
                trip["route_code"],
                trip["depart_date"],
                trip["depart_time"],
                trip["seats_total"],
                trip["driver_name"],
                trip["driver_phone"],
                trip["plate"],
                trip["vehicle_type"],
                trip["note"],
                now,
            ),
        )
    db.commit()
    return len(trips)


def bootstrap_schedule_if_needed() -> None:
    """İlk açılışta veya eski (tek grup) programdaysa A/B vardiyayı kur."""
    with app.app_context():
        db = get_db()
        seed_phones = tuple(d["phone"] for d in SEED_DRIVERS)
        placeholders = ",".join("?" * len(seed_phones))
        count = db.execute(
            f"SELECT COUNT(*) AS c FROM drivers WHERE phone IN ({placeholders})",
            seed_phones,
        ).fetchone()["c"]
        # Salı = B grubu; ayrıca son sefer 18:00 olmalı
        tuesday_auto = db.execute(
            """
            SELECT COUNT(*) AS c FROM trips
            WHERE note = ?
              AND depart_date >= ?
              AND CAST(strftime('%w', depart_date) AS INTEGER) = 2
            """,
            (AUTO_NOTE, date.today().isoformat()),
        ).fetchone()["c"]
        has_1800 = db.execute(
            """
            SELECT COUNT(*) AS c FROM trips
            WHERE note = ?
              AND depart_date >= ?
              AND depart_time = '18:00'
            """,
            (AUTO_NOTE, date.today().isoformat()),
        ).fetchone()["c"]
        if count < len(SEED_DRIVERS) or tuesday_auto == 0 or has_1800 == 0:
            regenerate_auto_schedule(weeks=4)


def route_label(code: str) -> str:
    for value, label in ROUTES:
        if value == code:
            return label
    return code


def seats_taken(trip_id: int) -> int:
    row = get_db().execute(
        "SELECT COALESCE(SUM(seats), 0) AS taken FROM reservations WHERE trip_id = ?",
        (trip_id,),
    ).fetchone()
    return int(row["taken"])


def enrich_trip(row: sqlite3.Row) -> dict:
    trip = dict(row)
    taken = seats_taken(trip["id"])
    trip["seats_taken"] = taken
    trip["seats_left"] = max(trip["seats_total"] - taken, 0)
    trip["route_label"] = route_label(trip["route_code"])
    trip["full"] = trip["seats_left"] <= 0
    return trip


def current_driver() -> sqlite3.Row | None:
    driver_id = session.get("driver_id")
    if not driver_id:
        return None
    return get_db().execute(
        "SELECT * FROM drivers WHERE id = ?", (driver_id,)
    ).fetchone()


def current_admin() -> bool:
    return bool(session.get("is_admin"))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_driver():
            flash("Şoför paneli için giriş yapın.", "error")
            return redirect(url_for("driver_login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_admin():
            flash("Yönetici girişi gerekli.", "error")
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)

    return wrapped


@app.context_processor
def inject_globals():
    return {
        "current_driver": current_driver(),
        "current_admin": current_admin(),
        "routes": ROUTES,
        "vehicle_types": VEHICLE_TYPES,
        "today": date.today().isoformat(),
    }


@app.route("/google97e294fc82905f9f.html")
def google_site_verification():
    return send_from_directory(BASE_DIR, "google97e294fc82905f9f.html")


@app.route("/")
def index():
    route_code = request.args.get("route", "")
    today = date.today()
    raw_day = request.args.get("date", today.isoformat())
    try:
        selected = date.fromisoformat(raw_day)
    except ValueError:
        selected = today
    day = selected.isoformat()
    is_today = day == today.isoformat()

    query = """
        SELECT * FROM trips
        WHERE depart_date = ?
    """
    params: list[str] = [day]

    if route_code:
        query += " AND route_code = ?"
        params.append(route_code)

    query += " ORDER BY depart_time ASC"

    trips = [enrich_trip(row) for row in get_db().execute(query, params).fetchall()]

    day_names = [
        "Pazartesi",
        "Salı",
        "Çarşamba",
        "Perşembe",
        "Cuma",
        "Cumartesi",
        "Pazar",
    ]
    day_options = []
    for offset in range(14):
        d = today + timedelta(days=offset)
        label = f"{day_names[d.weekday()]} · {d.strftime('%d.%m.%Y')}"
        if offset == 0:
            label = f"Bugün · {label}"
        day_options.append({"value": d.isoformat(), "label": label})

    heading = (
        f"Bugün · {day_names[selected.weekday()]}"
        if is_today
        else f"{day_names[selected.weekday()]} · {selected.strftime('%d.%m.%Y')}"
    )

    return render_template(
        "index.html",
        trips=trips,
        selected_route=route_code,
        selected_date=day,
        is_today=is_today,
        day_options=day_options,
        heading=heading,
    )


@app.route("/sefer/<int:trip_id>", methods=["GET", "POST"])
def trip_detail(trip_id: int):
    db = get_db()
    row = db.execute("SELECT * FROM trips WHERE id = ?", (trip_id,)).fetchone()
    if not row:
        flash("Sefer bulunamadı.", "error")
        return redirect(url_for("index"))

    trip = enrich_trip(row)

    if request.method == "POST":
        name = request.form.get("passenger_name", "").strip()
        phone = request.form.get("passenger_phone", "").strip()
        try:
            seats = int(request.form.get("seats", "1"))
        except ValueError:
            seats = 0

        if not name or not phone:
            flash("Ad ve telefon zorunludur.", "error")
        elif seats < 1:
            flash("En az 1 koltuk seçin.", "error")
        elif seats > trip["seats_left"]:
            flash(f"Yetersiz koltuk. Kalan: {trip['seats_left']}", "error")
        else:
            db.execute(
                """
                INSERT INTO reservations
                (trip_id, passenger_name, passenger_phone, seats, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (trip_id, name, phone, seats, datetime.now().isoformat(timespec="seconds")),
            )
            db.commit()
            flash("Yeriniz ayrıldı. Şoför sizi listede görecek.", "success")
            return redirect(url_for("trip_detail", trip_id=trip_id))

        trip = enrich_trip(
            db.execute("SELECT * FROM trips WHERE id = ?", (trip_id,)).fetchone()
        )

    reservations = db.execute(
        """
        SELECT * FROM reservations
        WHERE trip_id = ?
        ORDER BY created_at ASC
        """,
        (trip_id,),
    ).fetchall()

    return render_template(
        "trip_detail.html",
        trip=trip,
        reservations=reservations,
    )


@app.route("/sofor/kayit", methods=["GET", "POST"])
def driver_register():
    flash("Şoför kaydını yalnızca yönetici yapar. Kayıtlıysanız giriş yapın.", "error")
    return redirect(url_for("driver_login"))


@app.route("/yonetici/giris", methods=["GET", "POST"])
def admin_login():
    if current_admin():
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session.pop("driver_id", None)
            session["is_admin"] = True
            flash("Yönetici girişi yapıldı.", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Kullanıcı adı veya şifre hatalı.", "error")

    return render_template("admin_login.html")


@app.route("/yonetici/cikis")
def admin_logout():
    session.pop("is_admin", None)
    flash("Yönetici çıkışı yapıldı.", "success")
    return redirect(url_for("index"))


@app.route("/yonetici")
@admin_required
def admin_dashboard():
    db = get_db()
    drivers = db.execute(
        """
        SELECT d.*,
               (SELECT COUNT(*) FROM trips t WHERE t.driver_id = d.id) AS trip_count
        FROM drivers d
        ORDER BY d.name COLLATE NOCASE ASC
        """
    ).fetchall()
    return render_template("admin_dashboard.html", drivers=drivers)


@app.route("/yonetici/sofor/yeni", methods=["GET", "POST"])
@admin_required
def admin_new_driver():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        plate = request.form.get("plate", "").strip().upper()
        vehicle_type = request.form.get("vehicle_type", "").strip()

        if not all([name, phone, plate, vehicle_type]):
            flash("Tüm alanlar zorunludur.", "error")
        else:
            db = get_db()
            existing = db.execute(
                "SELECT id FROM drivers WHERE phone = ?", (phone,)
            ).fetchone()
            if existing:
                flash("Bu telefon zaten kayıtlı.", "error")
            else:
                db.execute(
                    """
                    INSERT INTO drivers (name, phone, plate, vehicle_type, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        phone,
                        plate,
                        vehicle_type,
                        datetime.now().isoformat(timespec="seconds"),
                    ),
                )
                db.commit()
                flash(f"{name} kaydedildi. Telefonuyla giriş yapabilir.", "success")
                return redirect(url_for("admin_dashboard"))

    return render_template("admin_new_driver.html")


@app.route("/vardiya")
def schedule_page():
    rows = []
    for seed in drivers_with_group_index():
        rows.append(
            {
                "index": seed["group_index"] + 1,
                "group": seed["group"],
                "name": seed["name"],
                "phone": seed["phone"],
                "plate": seed["plate"],
                "plan": weekly_plan_for(seed["group"], seed["group_index"]),
            }
        )
    today_group = group_for_day(date.today())
    today_plan = []
    for seed in drivers_with_group_index():
        t = departure_time_for(seed["group"], seed["group_index"], date.today())
        if t:
            today_plan.append(
                {
                    "name": seed["name"],
                    "time": t,
                    "plate": seed["plate"],
                    "group": seed["group"],
                }
            )
    today_plan.sort(key=lambda x: x["time"])
    return render_template(
        "schedule.html",
        rows=rows,
        today_plan=today_plan,
        today_group=today_group,
        day_names=["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"],
    )


@app.route("/vardiya/yenile", methods=["POST"])
@admin_required
def schedule_regenerate():
    try:
        weeks = int(request.form.get("weeks", "4"))
    except ValueError:
        weeks = 4
    weeks = max(1, min(weeks, 12))
    count = regenerate_auto_schedule(weeks=weeks)
    flash(f"Vardiya programı yenilendi: {count} sefer oluşturuldu ({weeks} hafta).", "success")
    return redirect(url_for("schedule_page"))


@app.route("/soforler")
def drivers_list():
    drivers = get_db().execute(
        """
        SELECT d.*,
               (SELECT COUNT(*) FROM trips t WHERE t.driver_id = d.id) AS trip_count
        FROM drivers d
        ORDER BY d.name COLLATE NOCASE ASC
        """
    ).fetchall()
    return render_template("drivers_list.html", drivers=drivers)


@app.route("/yonetici/sofor/<int:driver_id>/sil", methods=["POST"])
@admin_required
def admin_delete_driver(driver_id: int):
    db = get_db()
    driver = db.execute(
        "SELECT id, name FROM drivers WHERE id = ?", (driver_id,)
    ).fetchone()
    if not driver:
        flash("Şoför bulunamadı.", "error")
        return redirect(url_for("admin_dashboard"))

    trip_ids = [
        row["id"]
        for row in db.execute(
            "SELECT id FROM trips WHERE driver_id = ?", (driver_id,)
        ).fetchall()
    ]
    for trip_id in trip_ids:
        db.execute("DELETE FROM reservations WHERE trip_id = ?", (trip_id,))
    db.execute("DELETE FROM trips WHERE driver_id = ?", (driver_id,))
    db.execute("DELETE FROM drivers WHERE id = ?", (driver_id,))
    db.commit()

    if session.get("driver_id") == driver_id:
        session.pop("driver_id", None)

    flash(f"{driver['name']} silindi.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/sofor/giris", methods=["GET", "POST"])
def driver_login():
    if current_driver():
        return redirect(url_for("driver_dashboard"))

    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        driver = get_db().execute(
            "SELECT * FROM drivers WHERE phone = ?", (phone,)
        ).fetchone()
        if not driver:
            flash("Bu telefonla kayıtlı şoför yok.", "error")
        else:
            session.pop("is_admin", None)
            session["driver_id"] = driver["id"]
            flash(f"Hoş geldiniz, {driver['name']}.", "success")
            return redirect(url_for("driver_dashboard"))

    return render_template("driver_login.html")


@app.route("/sofor/cikis")
def driver_logout():
    session.pop("driver_id", None)
    flash("Çıkış yapıldı.", "success")
    return redirect(url_for("index"))


@app.route("/sofor")
@login_required
def driver_dashboard():
    driver = current_driver()
    assert driver is not None
    rows = get_db().execute(
        """
        SELECT * FROM trips
        WHERE driver_id = ?
        ORDER BY depart_date DESC, depart_time DESC
        """,
        (driver["id"],),
    ).fetchall()
    trips = [enrich_trip(row) for row in rows]
    return render_template("driver_dashboard.html", trips=trips)


@app.route("/sofor/sefer/yeni", methods=["GET", "POST"])
@login_required
def driver_new_trip():
    driver = current_driver()
    assert driver is not None

    if request.method == "POST":
        route_code = request.form.get("route_code", "").strip()
        depart_date = request.form.get("depart_date", "").strip()
        depart_time = request.form.get("depart_time", "").strip()
        plate = request.form.get("plate", "").strip().upper()
        vehicle_type = request.form.get("vehicle_type", "").strip()
        note = request.form.get("note", "").strip()
        try:
            seats_total = int(request.form.get("seats_total", "0"))
        except ValueError:
            seats_total = 0

        if route_code not in {r[0] for r in ROUTES}:
            flash("Güzergâh seçin.", "error")
        elif not depart_date or not depart_time:
            flash("Tarih ve saat zorunludur.", "error")
        elif not plate or not vehicle_type:
            flash("Plaka ve araç tipi zorunludur.", "error")
        elif seats_total < 1 or seats_total > 30:
            flash("Koltuk sayısı 1–30 arasında olmalı.", "error")
        else:
            db = get_db()
            db.execute(
                """
                INSERT INTO trips (
                    driver_id, route_code, depart_date, depart_time,
                    seats_total, driver_name, driver_phone, plate,
                    vehicle_type, note, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    driver["id"],
                    route_code,
                    depart_date,
                    depart_time,
                    seats_total,
                    driver["name"],
                    driver["phone"],
                    plate,
                    vehicle_type,
                    note or None,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            db.commit()
            flash("Sefer yayınlandı.", "success")
            return redirect(url_for("driver_dashboard"))

    return render_template("driver_new_trip.html", driver=driver)


@app.route("/sofor/sefer/<int:trip_id>")
@login_required
def driver_trip(trip_id: int):
    driver = current_driver()
    assert driver is not None
    db = get_db()
    row = db.execute(
        "SELECT * FROM trips WHERE id = ? AND driver_id = ?",
        (trip_id, driver["id"]),
    ).fetchone()
    if not row:
        flash("Sefer bulunamadı.", "error")
        return redirect(url_for("driver_dashboard"))

    trip = enrich_trip(row)
    reservations = db.execute(
        """
        SELECT * FROM reservations
        WHERE trip_id = ?
        ORDER BY created_at ASC
        """,
        (trip_id,),
    ).fetchall()
    return render_template(
        "driver_trip.html",
        trip=trip,
        reservations=reservations,
    )


@app.route("/sofor/sefer/<int:trip_id>/sil", methods=["POST"])
@login_required
def driver_delete_trip(trip_id: int):
    driver = current_driver()
    assert driver is not None
    db = get_db()
    row = db.execute(
        "SELECT id FROM trips WHERE id = ? AND driver_id = ?",
        (trip_id, driver["id"]),
    ).fetchone()
    if not row:
        flash("Sefer bulunamadı.", "error")
    else:
        db.execute("DELETE FROM reservations WHERE trip_id = ?", (trip_id,))
        db.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
        db.commit()
        flash("Sefer silindi.", "success")
    return redirect(url_for("driver_dashboard"))


if __name__ == "__main__":
    init_db()
    bootstrap_schedule_if_needed()
    port = int(os.environ.get("PORT", "5050"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
else:
    init_db()
    bootstrap_schedule_if_needed()
