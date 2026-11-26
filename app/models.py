
import sqlite3
from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")

    return g.db


def close_db(error=None):
    db = g.pop("db", None)

    if db is not None:
        db.close()


def init_db():
    db = get_db()

    db.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS journeys (
            journey_id INTEGER PRIMARY KEY AUTOINCREMENT,
            airline_name TEXT NOT NULL,
            flight_code TEXT NOT NULL,
            departure_city TEXT NOT NULL,
            arrival_city TEXT NOT NULL,
            journey_date TEXT NOT NULL,
            departure_time TEXT NOT NULL,
            arrival_time TEXT NOT NULL,
            ticket_price REAL NOT NULL,
            available_seats INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reservations (
            reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_code TEXT NOT NULL UNIQUE,
            customer_id INTEGER NOT NULL,
            journey_id INTEGER NOT NULL,
            passenger_name TEXT NOT NULL,
            passenger_phone TEXT NOT NULL,
            passenger_count INTEGER NOT NULL,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'CONFIRMED',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(customer_id) REFERENCES customers(customer_id),
            FOREIGN KEY(journey_id) REFERENCES journeys(journey_id)
        );
    """)

    # Initial sample journeys.
    initial_journeys = [
        (
            "IndiGo", "6E-214", "Bengaluru", "Mumbai",
            "2026-12-10", "06:45", "08:20", 4650, 40
        ),
        (
            "Air India", "AI-502", "Bengaluru", "Delhi",
            "2026-12-10", "09:15", "12:00", 6200, 35
        ),
        (
            "Akasa Air", "QP-145", "Mumbai", "Goa",
            "2026-12-11", "11:30", "12:45", 3800, 28
        ),
        (
            "IndiGo", "6E-332", "Delhi", "Bengaluru",
            "2026-12-12", "17:20", "20:05", 5900, 32
        )
    ]

    # Additional flights for rescheduling demonstrations.
    additional_journeys = [
        (
            "Air India", "AI-610", "Bengaluru", "Mumbai",
            "2026-12-15", "08:00", "09:35", 5100, 35
        ),
        (
            "Akasa Air", "QP-162", "Bengaluru", "Mumbai",
            "2026-12-18", "14:20", "15:55", 4300, 30
        ),
        (
            "IndiGo", "6E-418", "Bengaluru", "Mumbai",
            "2026-12-20", "19:10", "20:45", 4800, 42
        ),
        (
            "Air India", "AI-721", "Bengaluru", "Delhi",
            "2026-12-16", "07:30", "10:15", 6400, 30
        ),
        (
            "IndiGo", "6E-519", "Delhi", "Bengaluru",
            "2026-12-17", "16:00", "18:45", 5700, 35
        )
    ]

    all_journeys = initial_journeys + additional_journeys

    for journey in all_journeys:
        db.execute("""
            INSERT INTO journeys (
                airline_name,
                flight_code,
                departure_city,
                arrival_city,
                journey_date,
                departure_time,
                arrival_time,
                ticket_price,
                available_seats
            )
            SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?
            WHERE NOT EXISTS (
                SELECT 1
                FROM journeys
                WHERE flight_code = ?
            )
        """, journey + (journey[1],))

    db.commit()


def init_app(app):
    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db()
