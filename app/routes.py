
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    abort
)

from datetime import date
from functools import wraps
import secrets

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from app.models import get_db


main = Blueprint("main", __name__)


# LOGIN REQUIRED DECORATOR
def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if "customer_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("main.login"))

        return view(**kwargs)

    return wrapped_view


# HOMEPAGE
@main.route("/")
def home():
    return render_template(
        "index.html",
        today=date.today().isoformat()
    )


# FLIGHT SEARCH
@main.route("/search")
def search_flights():

    origin = request.args.get("origin", "").strip()
    destination = request.args.get("destination", "").strip()
    travel_date = request.args.get("travel_date", "").strip()

    try:
        passengers = int(request.args.get("passengers", 1))
    except (ValueError, TypeError):
        passengers = 1

    if not origin or not destination or not travel_date:
        return "Please provide all flight search details.", 400

    if origin.casefold() == destination.casefold():
        return "Departure and arrival cities must be different.", 400

    if passengers < 1 or passengers > 5:
        return "Passenger count must be between 1 and 5.", 400

    db = get_db()

    flights = db.execute("""
        SELECT *
        FROM journeys
        WHERE LOWER(departure_city) = LOWER(?)
          AND LOWER(arrival_city) = LOWER(?)
          AND journey_date = ?
          AND available_seats >= ?
        ORDER BY departure_time
    """, (
        origin,
        destination,
        travel_date,
        passengers
    )).fetchall()

    return render_template(
        "search_results.html",
        flights=flights,
        origin=origin,
        destination=destination,
        travel_date=travel_date,
        passengers=passengers
    )


# CUSTOMER REGISTRATION
@main.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not password:
            flash("Please complete all required fields.", "error")
            return redirect(url_for("main.register"))

        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
            return redirect(url_for("main.register"))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("main.register"))

        db = get_db()

        existing_customer = db.execute(
            "SELECT customer_id FROM customers WHERE email = ?",
            (email,)
        ).fetchone()

        if existing_customer:
            flash(
                "An account with this email already exists.",
                "error"
            )
            return redirect(url_for("main.register"))

        password_hash = generate_password_hash(password)

        db.execute("""
            INSERT INTO customers (
                name,
                email,
                password_hash
            )
            VALUES (?, ?, ?)
        """, (
            name,
            email,
            password_hash
        ))

        db.commit()

        flash(
            "Registration successful. Please log in.",
            "success"
        )

        return redirect(url_for("main.login"))

    return render_template("register.html")


# CUSTOMER LOGIN
@main.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db()

        customer = db.execute("""
            SELECT *
            FROM customers
            WHERE email = ?
        """, (email,)).fetchone()

        if customer and check_password_hash(
            customer["password_hash"],
            password
        ):

            session.clear()

            session["customer_id"] = customer["customer_id"]
            session["customer_name"] = customer["name"]

            flash(
                "Welcome back, " + customer["name"] + "!",
                "success"
            )

            return redirect(url_for("main.home"))

        flash("Invalid email or password.", "error")
        return redirect(url_for("main.login"))

    return render_template("login.html")


# CUSTOMER LOGOUT
@main.route("/logout")
def logout():

    session.clear()

    flash("You have been logged out.", "success")

    return redirect(url_for("main.home"))


# BOOKING DETAILS
@main.route("/book/<int:journey_id>", methods=["GET", "POST"])
@login_required
def book_flight(journey_id):

    db = get_db()

    flight = db.execute("""
        SELECT *
        FROM journeys
        WHERE journey_id = ?
    """, (journey_id,)).fetchone()

    if flight is None:
        abort(404)

    try:
        passengers = int(request.values.get("passengers", 1))
    except (ValueError, TypeError):
        passengers = 1

    if passengers < 1 or passengers > 5:
        abort(400)

    if request.method == "POST":

        passenger_name = request.form.get(
            "passenger_name", ""
        ).strip()

        passenger_phone = request.form.get(
            "passenger_phone", ""
        ).strip()

        if not passenger_name or not passenger_phone:
            flash(
                "Please complete all passenger details.",
                "error"
            )

            return redirect(url_for(
                "main.book_flight",
                journey_id=journey_id,
                passengers=passengers
            ))

        if (
            not passenger_phone.isdigit()
            or len(passenger_phone) != 10
        ):
            flash(
                "Enter a valid 10-digit phone number.",
                "error"
            )

            return redirect(url_for(
                "main.book_flight",
                journey_id=journey_id,
                passengers=passengers
            ))

        amount = flight["ticket_price"] * passengers
        booking_code = "SKY" + secrets.token_hex(4).upper()

        try:
            cursor = db.execute("""
                UPDATE journeys
                SET available_seats = available_seats - ?
                WHERE journey_id = ?
                  AND available_seats >= ?
            """, (
                passengers,
                journey_id,
                passengers
            ))

            if cursor.rowcount == 0:
                db.rollback()

                flash(
                    "Sorry, not enough seats are available.",
                    "error"
                )

                return redirect(url_for("main.home"))

            db.execute("""
                INSERT INTO reservations (
                    booking_code,
                    customer_id,
                    journey_id,
                    passenger_name,
                    passenger_phone,
                    passenger_count,
                    amount,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'CONFIRMED')
            """, (
                booking_code,
                session["customer_id"],
                journey_id,
                passenger_name,
                passenger_phone,
                passengers,
                amount
            ))

            db.commit()

        except Exception:
            db.rollback()
            raise

        return redirect(url_for(
            "main.booking_confirmation",
            booking_code=booking_code
        ))

    return render_template(
        "booking.html",
        flight=flight,
        passengers=passengers
    )


# BOOKING CONFIRMATION
@main.route("/confirmation/<booking_code>")
@login_required
def booking_confirmation(booking_code):

    db = get_db()

    booking = db.execute("""
        SELECT
            reservations.*,
            journeys.airline_name,
            journeys.flight_code,
            journeys.departure_city,
            journeys.arrival_city,
            journeys.journey_date,
            journeys.departure_time,
            journeys.arrival_time
        FROM reservations
        JOIN journeys
          ON reservations.journey_id = journeys.journey_id
        WHERE reservations.booking_code = ?
          AND reservations.customer_id = ?
    """, (
        booking_code,
        session["customer_id"]
    )).fetchone()

    if booking is None:
        abort(404)

    return render_template(
        "confirmation.html",
        booking=booking
    )


# CUSTOMER TRIPS
@main.route("/my-trips")
@login_required
def my_trips():

    db = get_db()

    bookings = db.execute("""
        SELECT
            reservations.*,
            journeys.airline_name,
            journeys.flight_code,
            journeys.departure_city,
            journeys.arrival_city,
            journeys.journey_date,
            journeys.departure_time,
            journeys.arrival_time
        FROM reservations
        JOIN journeys
          ON reservations.journey_id = journeys.journey_id
        WHERE reservations.customer_id = ?
        ORDER BY reservations.created_at DESC
    """, (session["customer_id"],)).fetchall()

    return render_template(
        "my_trips.html",
        bookings=bookings
    )


# FLIGHT RESCHEDULING
@main.route(
    "/reschedule/<booking_code>",
    methods=["GET", "POST"]
)
@login_required
def reschedule_flight(booking_code):

    db = get_db()

    booking = db.execute("""
        SELECT
            reservations.*,
            journeys.airline_name,
            journeys.flight_code,
            journeys.departure_city,
            journeys.arrival_city,
            journeys.journey_date,
            journeys.departure_time,
            journeys.arrival_time,
            journeys.ticket_price
        FROM reservations
        JOIN journeys
          ON reservations.journey_id = journeys.journey_id
        WHERE reservations.booking_code = ?
          AND reservations.customer_id = ?
    """, (
        booking_code,
        session["customer_id"]
    )).fetchone()

    if booking is None:
        abort(404)

    if booking["status"] != "CONFIRMED":
        flash(
            "Only confirmed bookings can be rescheduled.",
            "error"
        )
        return redirect(url_for("main.my_trips"))

    today = date.today().isoformat()

    if booking["journey_date"] < today:
        flash(
            "Past journeys cannot be rescheduled.",
            "error"
        )
        return redirect(url_for("main.my_trips"))

    if request.method == "POST":

        try:
            new_journey_id = int(
                request.form.get("journey_id", "")
            )
        except (ValueError, TypeError):
            abort(400)

        if new_journey_id == booking["journey_id"]:
            flash(
                "Please select a different flight.",
                "error"
            )
            return redirect(url_for(
                "main.reschedule_flight",
                booking_code=booking_code
            ))

        new_flight = db.execute("""
            SELECT *
            FROM journeys
            WHERE journey_id = ?
              AND LOWER(departure_city) = LOWER(?)
              AND LOWER(arrival_city) = LOWER(?)
              AND journey_date >= ?
              AND available_seats >= ?
        """, (
            new_journey_id,
            booking["departure_city"],
            booking["arrival_city"],
            today,
            booking["passenger_count"]
        )).fetchone()

        if new_flight is None:
            flash(
                "That flight is unavailable. Please choose another.",
                "error"
            )
            return redirect(url_for(
                "main.reschedule_flight",
                booking_code=booking_code
            ))

        try:
            # Reserve seats on the new flight first.
            cursor = db.execute("""
                UPDATE journeys
                SET available_seats = available_seats - ?
                WHERE journey_id = ?
                  AND available_seats >= ?
            """, (
                booking["passenger_count"],
                new_journey_id,
                booking["passenger_count"]
            ))

            if cursor.rowcount == 0:
                db.rollback()

                flash(
                    "Sorry, the selected flight no longer has enough seats.",
                    "error"
                )

                return redirect(url_for(
                    "main.reschedule_flight",
                    booking_code=booking_code
                ))

            # Release seats on the original flight.
            db.execute("""
                UPDATE journeys
                SET available_seats = available_seats + ?
                WHERE journey_id = ?
            """, (
                booking["passenger_count"],
                booking["journey_id"]
            ))

            # Update the existing reservation.
            new_amount = (
                new_flight["ticket_price"]
                * booking["passenger_count"]
            )

            db.execute("""
                UPDATE reservations
                SET journey_id = ?,
                    amount = ?
                WHERE reservation_id = ?
                  AND customer_id = ?
            """, (
                new_journey_id,
                new_amount,
                booking["reservation_id"],
                session["customer_id"]
            ))

            db.commit()

        except Exception:
            db.rollback()
            raise

        flash(
            "Your flight has been successfully rescheduled.",
            "success"
        )

        return redirect(url_for(
            "main.booking_confirmation",
            booking_code=booking_code
        ))

    # Find alternative flights on the same route.
    alternative_flights = db.execute("""
        SELECT *
        FROM journeys
        WHERE LOWER(departure_city) = LOWER(?)
          AND LOWER(arrival_city) = LOWER(?)
          AND journey_date >= ?
          AND journey_id != ?
          AND available_seats >= ?
        ORDER BY journey_date, departure_time
    """, (
        booking["departure_city"],
        booking["arrival_city"],
        today,
        booking["journey_id"],
        booking["passenger_count"]
    )).fetchall()

    return render_template(
        "reschedule.html",
        booking=booking,
        flights=alternative_flights
    )
