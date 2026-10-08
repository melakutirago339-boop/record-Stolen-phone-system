from flask import Flask, render_template, request, redirect, session, url_for
import os
import psycopg2
from functools import wraps

app = Flask(__name__)

# -------------------------------------------------
# APP CONFIGURATION
# -------------------------------------------------

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "stolen-phone-demo-secret-key"
)


# -------------------------------------------------
# DATABASE CONNECTION
# -------------------------------------------------

def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise Exception("DATABASE_URL is not configured.")

    return psycopg2.connect(database_url)


# -------------------------------------------------
# CREATE DATABASE TABLES
# -------------------------------------------------

def create_tables():

    conn = get_db_connection()
    cur = conn.cursor()

    # Registered phones
    cur.execute("""
        CREATE TABLE IF NOT EXISTS registered_phones (
            id SERIAL PRIMARY KEY,
            owner_name VARCHAR(150) NOT NULL,
            phone_number VARCHAR(50),
            imei VARCHAR(100) UNIQUE NOT NULL,
            phone_model VARCHAR(150),
            color VARCHAR(50),
            registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Stolen phones
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stolen_phones (
            id SERIAL PRIMARY KEY,
            owner_name VARCHAR(150) NOT NULL,
            phone_number VARCHAR(50),
            imei VARCHAR(100) NOT NULL,
            phone_model VARCHAR(150),
            last_location VARCHAR(255),
            report_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status VARCHAR(50) DEFAULT 'Stolen'
        )
    """)

    # Cases
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id SERIAL PRIMARY KEY,
            case_number VARCHAR(100) UNIQUE NOT NULL,
            imei VARCHAR(100),
            owner_name VARCHAR(150),
            officer_name VARCHAR(150),
            case_status VARCHAR(50) DEFAULT 'Open',
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Authorized locations
    cur.execute("""
        CREATE TABLE IF NOT EXISTS authorized_locations (
            id SERIAL PRIMARY KEY,
            location_name VARCHAR(150) NOT NULL,
            city VARCHAR(100),
            latitude VARCHAR(50),
            longitude VARCHAR(50),
            location_type VARCHAR(100),
            address TEXT,
            status VARCHAR(50) DEFAULT 'Authorized',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()

    cur.close()
    conn.close()

    print("Database tables ready")


# -------------------------------------------------
# LOGIN REQUIRED DECORATOR
# -------------------------------------------------

def login_required(func):

    @wraps(func)
    def wrapper(*args, **kwargs):

        if "username" not in session:
            return redirect("/login")

        return func(*args, **kwargs)

    return wrapper


# -------------------------------------------------
# HOME
# -------------------------------------------------

@app.route("/")
def home():
    return redirect("/login")


# -------------------------------------------------
# LOGIN
# -------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "admin").strip()

        if username == "admin" and password == "admin123":

            session["username"] = username
            session["role"] = role

            return redirect("/dashboard")

        return render_template(
            "login.html",
            error="Invalid username or password"
        )

    return render_template("login.html")


# -------------------------------------------------
# DASHBOARD
# -------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():

    return render_template(
        "dashboard.html",
        username=session.get("username"),
        role=session.get("role")
    )


# -------------------------------------------------
# DATABASE TEST
# -------------------------------------------------

@app.route("/db-test")
@login_required
def db_test():

    try:

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT NOW()")
        result = cur.fetchone()

        cur.close()
        conn.close()

        return f"""
        <h2>Database Connected Successfully</h2>
        <p>Database time: {result[0]}</p>
        <a href="/dashboard">Back to Dashboard</a>
        """

    except Exception as e:

        return f"""
        <h2>Database Error</h2>
        <p>{e}</p>
        <a href="/dashboard">Back to Dashboard</a>
        """


# =================================================
# REGISTER PHONE
# =================================================

@app.route("/register_phone", methods=["GET", "POST"])
@app.route("/register", methods=["GET", "POST"])
@login_required
def register_phone():

    if request.method == "POST":

        owner_name = request.form.get(
            "owner_name", ""
        ).strip()

        phone_number = request.form.get(
            "phone_number", ""
        ).strip()

        imei = request.form.get(
            "imei", ""
        ).strip()

        phone_model = request.form.get(
            "phone_model", ""
        ).strip()

        color = request.form.get(
            "color", ""
        ).strip()

        if not owner_name or not imei:

            return render_template(
                "register_phone.html",
                error="Owner name and IMEI are required."
            )

        conn = None
        cur = None

        try:

            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO registered_phones
                (
                    owner_name,
                    phone_number,
                    imei,
                    phone_model,
                    color
                )
                VALUES (%s, %s, %s, %s, %s)
            """, (
                owner_name,
                phone_number,
                imei,
                phone_model,
                color
            ))

            conn.commit()

            return render_template(
                "register_phone.html",
                success="Phone registered successfully"
            )

        except Exception as e:

            if conn:
                conn.rollback()

            return render_template(
                "register_phone.html",
                error=f"Registration failed: {e}"
            )

        finally:

            if cur:
                cur.close()

            if conn:
                conn.close()

    return render_template("register_phone.html")


# =================================================
# REPORT STOLEN PHONE
# =================================================

@app.route("/report_stolen", methods=["GET", "POST"])
@app.route("/report", methods=["GET", "POST"])
@login_required
def report_stolen():

    if request.method == "POST":

        owner_name = request.form.get(
            "owner_name", ""
        ).strip()

        phone_number = request.form.get(
            "phone_number", ""
        ).strip()

        imei = request.form.get(
            "imei", ""
        ).strip()

        phone_model = request.form.get(
            "phone_model", ""
        ).strip()

        last_location = request.form.get(
            "last_location", ""
        ).strip()

        if not owner_name or not imei:

            return render_template(
                "report_stolen.html",
                error="Owner name and IMEI are required."
            )

        conn = None
        cur = None

        try:

            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO stolen_phones
                (
                    owner_name,
                    phone_number,
                    imei,
                    phone_model,
                    last_location,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                owner_name,
                phone_number,
                imei,
                phone_model,
                last_location,
                "Stolen"
            ))

            conn.commit()

            return render_template(
                "report_stolen.html",
                success="Stolen phone report saved successfully"
            )

        except Exception as e:

            if conn:
                conn.rollback()

            return render_template(
                "report_stolen.html",
                error=f"Report failed: {e}"
            )

        finally:

            if cur:
                cur.close()

            if conn:
                conn.close()

    return render_template("report_stolen.html")


# =================================================
# SEARCH PHONE BY IMEI
# =================================================

@app.route("/search_imei", methods=["GET", "POST"])
@app.route("/search", methods=["GET", "POST"])
@login_required
def search_imei():

    results = []
    searched_imei = ""

    if request.method == "POST":

        searched_imei = request.form.get(
            "imei", ""
        ).strip()

        conn = None
        cur = None

        try:

            conn = get_db_connection()
            cur = conn.cursor()

            # Search stolen phones
            cur.execute("""
                SELECT
                    id,
                    owner_name,
                    phone_number,
                    imei,
                    phone_model,
                    last_location,
                    report_date,
                    status
                FROM stolen_phones
                WHERE imei = %s
                ORDER BY report_date DESC
            """, (searched_imei,))

            stolen_results = cur.fetchall()

            for row in stolen_results:

                results.append({
                    "type": "Stolen Phone",
                    "id": row[0],
                    "owner_name": row[1],
                    "phone_number": row[2],
                    "imei": row[3],
                    "phone_model": row[4],
                    "location": row[5],
                    "date": row[6],
                    "status": row[7]
                })

            # Search registered phones
            cur.execute("""
                SELECT
                    id,
                    owner_name,
                    phone_number,
                    imei,
                    phone_model,
                    color,
                    registration_date
                FROM registered_phones
                WHERE imei = %s
                ORDER BY registration_date DESC
            """, (searched_imei,))

            registered_results = cur.fetchall()

            for row in registered_results:

                results.append({
                    "type": "Registered Phone",
                    "id": row[0],
                    "owner_name": row[1],
                    "phone_number": row[2],
                    "imei": row[3],
                    "phone_model": row[4],
                    "location": row[5],
                    "date": row[6],
                    "status": "Registered"
                })

        except Exception as e:

            return render_template(
                "search_imei.html",
                error=f"Search failed: {e}",
                results=[],
                searched_imei=searched_imei
            )

        finally:

            if cur:
                cur.close()

            if conn:
                conn.close()

    return render_template(
        "search_imei.html",
        results=results,
        searched_imei=searched_imei
    )


# =================================================
# CASE MANAGEMENT
# =================================================

@app.route("/cases", methods=["GET", "POST"])
@login_required
def cases():

    message = None
    error = None

    if request.method == "POST":

        case_number = request.form.get(
            "case_number", ""
        ).strip()

        imei = request.form.get(
            "imei", ""
        ).strip()

        owner_name = request.form.get(
            "owner_name", ""
        ).strip()

        officer_name = request.form.get(
            "officer_name", ""
        ).strip()

        case_status = request.form.get(
            "case_status", "Open"
        ).strip()

        description = request.form.get(
            "description", ""
        ).strip()

        if not case_number or not imei:

            error = "Case number and IMEI are required."

        else:

            conn = None
            cur = None

            try:

                conn = get_db_connection()
                cur = conn.cursor()

                cur.execute("""
                    INSERT INTO cases
                    (
                        case_number,
                        imei,
                        owner_name,
                        officer_name,
                        case_status,
                        description
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    case_number,
                    imei,
                    owner_name,
                    officer_name,
                    case_status,
                    description
                ))

                conn.commit()

                message = "Case created successfully"

            except Exception as e:

                if conn:
                    conn.rollback()

                error = f"Case creation failed: {e}"

            finally:

                if cur:
                    cur.close()

                if conn:
                    conn.close()

    # Get cases
    case_list = []

    conn = None
    cur = None

    try:

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                id,
                case_number,
                imei,
                owner_name,
                officer_name,
                case_status,
                description,
                created_at
            FROM cases
            ORDER BY created_at DESC
        """)

        rows = cur.fetchall()

        for row in rows:

            case_list.append({
                "id": row[0],
                "case_number": row[1],
                "imei": row[2],
                "owner_name": row[3],
                "officer_name": row[4],
                "case_status": row[5],
                "description": row[6],
                "created_at": row[7]
            })

    except Exception as e:

        error = str(e)

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()

    return render_template(
        "cases.html",
        cases=case_list,
        success=message,
        error=error
    )


# =================================================
# AUTHORIZED LOCATION
# =================================================

@app.route("/location", methods=["GET", "POST"])
@login_required
def location():

    message = None
    error = None

    if request.method == "POST":

        location_name = request.form.get(
            "location_name", ""
        ).strip()

        city = request.form.get(
            "city", ""
        ).strip()

        latitude = request.form.get(
            "latitude", ""
        ).strip()

        longitude = request.form.get(
            "longitude", ""
        ).strip()

        location_type = request.form.get(
            "location_type", "Other"
        ).strip()

        address = request.form.get(
            "address", ""
        ).strip()

        status = request.form.get(
            "status", "Authorized"
        ).strip()

        if not location_name:

            error = "Location name is required."

        else:

            conn = None
            cur = None

            try:

                conn = get_db_connection()
                cur = conn.cursor()

                cur.execute("""
                    INSERT INTO authorized_locations
                    (
                        location_name,
                        city,
                        latitude,
                        longitude,
                        location_type,
                        address,
                        status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    location_name,
                    city,
                    latitude,
                    longitude,
                    location_type,
                    address,
                    status
                ))

                conn.commit()

                message = "Authorized location saved successfully"

            except Exception as e:

                if conn:
                    conn.rollback()

                error = f"Location save failed: {e}"

            finally:

                if cur:
                    cur.close()

                if conn:
                    conn.close()

    # Get locations
    locations = []

    conn = None
    cur = None

    try:

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                id,
                location_name,
                city,
                latitude,
                longitude,
                location_type,
                address,
                status,
                created_at
            FROM authorized_locations
            ORDER BY created_at DESC
        """)

        rows = cur.fetchall()

        for row in rows:

            locations.append({
                "id": row[0],
                "location_name": row[1],
                "city": row[2],
                "latitude": row[3],
                "longitude": row[4],
                "location_type": row[5],
                "address": row[6],
                "status": row[7],
                "created_at": row[8]
            })

    except Exception as e:

        error = str(e)

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()

    return render_template(
        "location.html",
        locations=locations,
        success=message,
        error=error
    )


# =================================================
# REPORTS
# =================================================

@app.route("/reports")
@login_required
def reports():

    stolen_count = 0
    registered_count = 0
    cases_count = 0
    locations_count = 0

    recent_stolen = []

    conn = None
    cur = None

    try:

        conn = get_db_connection()
        cur = conn.cursor()

        # Total stolen phones
        cur.execute("""
            SELECT COUNT(*)
            FROM stolen_phones
        """)

        stolen_count = cur.fetchone()[0]

        # Total registered phones
        cur.execute("""
            SELECT COUNT(*)
            FROM registered_phones
        """)

        registered_count = cur.fetchone()[0]

        # Total cases
        cur.execute("""
            SELECT COUNT(*)
            FROM cases
        """)

        cases_count = cur.fetchone()[0]

        # Total authorized locations
        cur.execute("""
            SELECT COUNT(*)
            FROM authorized_locations
        """)

        locations_count = cur.fetchone()[0]

        # Recent stolen phone reports
        cur.execute("""
            SELECT
                id,
                owner_name,
                phone_number,
                imei,
                phone_model,
                last_location,
                report_date,
                status
            FROM stolen_phones
            ORDER BY report_date DESC
            LIMIT 20
        """)

        rows = cur.fetchall()

        for row in rows:

            recent_stolen.append({
                "id": row[0],
                "owner_name": row[1],
                "phone_number": row[2],
                "imei": row[3],
                "phone_model": row[4],
                "location": row[5],
                "date": row[6],
                "status": row[7]
            })

    except Exception as e:

        return render_template(
            "reports.html",
            error=f"Reports error: {e}",
            stolen_count=stolen_count,
            registered_count=registered_count,
            cases_count=cases_count,
            locations_count=locations_count,
            recent_stolen=recent_stolen
        )

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()

    return render_template(
        "reports.html",
        stolen_count=stolen_count,
        registered_count=registered_count,
        cases_count=cases_count,
        locations_count=locations_count,
        recent_stolen=recent_stolen
    )


# =================================================
# LOGOUT
# =================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# =================================================
# START APPLICATION
# =================================================

try:

    create_tables()

except Exception as e:

    print("Database initialization error:", e)


if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
