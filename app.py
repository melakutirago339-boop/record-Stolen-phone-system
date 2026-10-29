
from flask import Flask, render_template, request, redirect, session, url_for
import os
import psycopg2
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

# -------------------------------------------------
# APP CONFIGURATION
# -------------------------------------------------

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "stolen-phone-demo-secret-key"
)
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
# CREATE DATABASE TABLES
# -------------------------------------------------
def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is missing."
        )

    return psycopg2.connect(
        database_url,
        sslmode="require",
        connect_timeout=15
    )

def create_tables():
    conn = None
    cur = None

    try:
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

        cur.execute("""
            ALTER TABLE registered_phones
            ADD COLUMN IF NOT EXISTS registration_date
            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                status VARCHAR(50) DEFAULT 'Stolen',
                case_status VARCHAR(50) DEFAULT 'Reported',
                officer_name VARCHAR(150)
            )
        """)

        cur.execute("""
            ALTER TABLE stolen_phones
            ADD COLUMN IF NOT EXISTS last_location VARCHAR(255)
        """)

        cur.execute("""
            ALTER TABLE stolen_phones
            ADD COLUMN IF NOT EXISTS date_stolen DATE
        """)

        cur.execute("""
            ALTER TABLE stolen_phones
            ADD COLUMN IF NOT EXISTS report_date
            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        """)

        cur.execute("""
            ALTER TABLE stolen_phones
            ADD COLUMN IF NOT EXISTS case_status
            VARCHAR(50) DEFAULT 'Reported'
        """)

        cur.execute("""
            ALTER TABLE stolen_phones
            ADD COLUMN IF NOT EXISTS officer_name VARCHAR(150)
        """)

        # Cases
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                id SERIAL PRIMARY KEY,
                case_number VARCHAR(100) UNIQUE NOT NULL,
                imei VARCHAR(100),
                owner_name VARCHAR(150),
                officer_name VARCHAR(150),
                case_status VARCHAR(50) DEFAULT 'Reported',
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            ALTER TABLE cases
            ADD COLUMN IF NOT EXISTS owner_name VARCHAR(150)
        """)

        cur.execute("""
            ALTER TABLE cases
            ADD COLUMN IF NOT EXISTS officer_name VARCHAR(150)
        """)

        cur.execute("""
            ALTER TABLE cases
            ADD COLUMN IF NOT EXISTS case_status
            VARCHAR(50) DEFAULT 'Reported'
        """)

        cur.execute("""
            ALTER TABLE cases
            ADD COLUMN IF NOT EXISTS description TEXT
        """)

        cur.execute("""
            ALTER TABLE cases
            ADD COLUMN IF NOT EXISTS created_at
            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        """)

        cur.execute("""
            ALTER TABLE cases
            ADD COLUMN IF NOT EXISTS imei VARCHAR(100)
        """)

        cur.execute("""
            ALTER TABLE cases
            ADD COLUMN IF NOT EXISTS case_number VARCHAR(100)
        """)

        # Case history
        cur.execute("""
            CREATE TABLE IF NOT EXISTS case_history (
                id SERIAL PRIMARY KEY,
                source VARCHAR(20) NOT NULL,
                record_id INTEGER NOT NULL,
                case_number VARCHAR(100),
                imei VARCHAR(100),
                previous_status VARCHAR(50),
                new_status VARCHAR(50) NOT NULL,
                officer_name VARCHAR(150),
                changed_by VARCHAR(150),
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Phone location history
        cur.execute("""
            CREATE TABLE IF NOT EXISTS phone_location_history (
                id SERIAL PRIMARY KEY,
                imei VARCHAR(100) NOT NULL,
                location VARCHAR(255) NOT NULL,
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION,
                source VARCHAR(150),
                notes TEXT,
                permission_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
                recorded_by VARCHAR(150),
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            ALTER TABLE phone_location_history
            ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION
        """)

        cur.execute("""
            ALTER TABLE phone_location_history
            ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION
        """)

        cur.execute("""
            ALTER TABLE phone_location_history
            ADD COLUMN IF NOT EXISTS permission_confirmed
            BOOLEAN NOT NULL DEFAULT FALSE
        """)

              # Authorized locations
        cur.execute("""
            ALTER TABLE authorized_locations
            ADD COLUMN IF NOT EXISTS city TEXT
        """)

        cur.execute("""
            ALTER TABLE authorized_locations
            ADD COLUMN IF NOT EXISTS address TEXT
        """)

        cur.execute("""
            ALTER TABLE authorized_locations
            ADD COLUMN IF NOT EXISTS location_type TEXT
        """)

        cur.execute("""
            ALTER TABLE authorized_locations
            ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION
        """)

        cur.execute("""
            ALTER TABLE authorized_locations
            ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION
        """)

        cur.execute("""
            ALTER TABLE authorized_locations
            ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'Active'
        """)
        # System users
        cur.execute("""
            CREATE TABLE IF NOT EXISTS system_users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role VARCHAR(20) NOT NULL
                    CHECK (role IN ('officer', 'user')),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        print("Database tables ready")

    except Exception as e:
        if conn:
            conn.rollback()

        print("Database table setup error:", repr(e))
        raise

    finally:
        if cur:
            cur.close()

        if conn:
            conn.close()


# =================================================
# AUTHORIZED LOCATIONS
# =================================================

@app.route("/location", methods=["GET", "POST"])
@login_required
def location_redirect():
    message = None
    error = None
    locations = []

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if request.method == "POST":
            action = request.form.get("action", "add_location")

            # Delete an authorized location after confirmation
            if action == "delete_location":
                location_id = request.form.get("location_id", "").strip()

                if not location_id.isdigit():
                    error = "Invalid location ID."
                elif int(location_id) not in (2, 3):
                    error = (
                        "For safety, this delete action is currently "
                        "limited to duplicate location IDs 2 and 3."
                    )
                else:
                    cur.execute("""
                        DELETE FROM authorized_locations
                        WHERE id = %s
                    """, (int(location_id),))

                    if cur.rowcount == 1:
                        conn.commit()
                        message = (
                            f"Duplicate authorized location "
                            f"ID {location_id} deleted."
                        )
                    else:
                        conn.rollback()
                        error = (
                            f"Location ID {location_id} was not found."
                        )

            # Add a new authorized location
            elif action == "add_location":
                name = request.form.get("name", "").strip()
                city = request.form.get("city", "").strip()
                address = request.form.get("address", "").strip()
                location_type = request.form.get("type", "").strip()
                status = request.form.get("status", "Active").strip()

                latitude_text = request.form.get("latitude", "").strip()
                longitude_text = request.form.get("longitude", "").strip()

                latitude = None
                longitude = None

                if not name or not city:
                    error = "Location name and city are required."

                try:
                    if latitude_text:
                        latitude = float(latitude_text)
                    if longitude_text:
                        longitude = float(longitude_text)
                except ValueError:
                    error = "Latitude and longitude must be valid numbers."

                if not error and ((latitude is None) != (longitude is None)):
                    error = "Enter both coordinates or leave both blank."

                if not error and latitude is not None and not -90 <= latitude <= 90:
                    error = "Latitude must be between -90 and 90."

                if not error and longitude is not None and not -180 <= longitude <= 180:
                    error = "Longitude must be between -180 and 180."

                if not error:
                    cur.execute("""
                        INSERT INTO authorized_locations
                            (location_name, city, latitude, longitude,
                             location_type, address, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        name,
                        city,
                        str(latitude) if latitude is not None else None,
                        str(longitude) if longitude is not None else None,
                        location_type or None,
                        address or None,
                        status or "Active"
                    ))

                    conn.commit()
                    message = "Authorized location saved successfully."

            else:
                error = "Invalid action."

        cur.execute("""
            SELECT *
            FROM authorized_locations
            ORDER BY location_name, id
        """)

        columns = [description[0] for description in cur.description]
        locations = [
            dict(zip(columns, row))
            for row in cur.fetchall()
        ]

    except Exception:
        if conn:
            conn.rollback()

        app.logger.exception("Authorized locations page failed")
        error = (
            "Could not complete the operation. "
            "Check Render logs; the record may be protected by a database constraint."
        )

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return render_template(
        "authorized_locations.html",
        locations=locations,
        message=message,
        error=error
    )


# -------------------------------------------------
# CREATE OFFICER ACCOUNT
# -------------------------------------------------

@app.route("/admin/create-officer", methods=["GET", "POST"])
@login_required
def create_officer():
    if session.get("role") != "admin":
        return "Access denied", 403

    message = None
    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if len(username) < 3:
            error = "Username must be at least 3 characters."
        elif len(password) < 10:
            error = "Password must be at least 10 characters."
        else:
            conn = None
            cur = None
            try:
                conn = get_db_connection()
                cur = conn.cursor()

                password_hash = generate_password_hash(password)

                cur.execute("""
                    INSERT INTO system_users
                        (username, password_hash, role, is_active)
                    VALUES (%s, %s, 'officer', TRUE)
                    ON CONFLICT (username) DO NOTHING
                    RETURNING id
                """, (username, password_hash))

                created = cur.fetchone()
                conn.commit()

                if created:
                    message = "Officer account created successfully."
                else:
                    error = "That username already exists."

            except Exception:
                if conn:
                    conn.rollback()
                app.logger.exception("Could not create officer account")
                error = "Could not create account. Check the server logs."

            finally:
                if cur:
                    cur.close()
                if conn:
                    conn.close()

    return render_template(
        "create_officer.html",
        message=message,
        error=error
    )
            

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
        password = request.form.get("password", "")
        selected_role = request.form.get("role", "").strip().lower()

        # Existing Administrator login
        admin_username = os.environ.get(
            "ADMIN_USERNAME", "admin"
        ).strip()

        admin_password_hash = "".join(
            os.environ.get("ADMIN_PASSWORD_HASH", "").split()
        )

        try:
            if (
                selected_role == "admin"
                and admin_username
                and admin_password_hash
                and username == admin_username
                and check_password_hash(
                    admin_password_hash, password
                )
            ):
                session.clear()
                session["username"] = username
                session["role"] = "admin"
                return redirect(url_for("dashboard"))

            # Officer and regular user login
            if selected_role in ("officer", "user"):
                conn = get_db_connection()
                cur = conn.cursor()

                try:
                    cur.execute("""
                        SELECT username, password_hash, role
                        FROM system_users
                        WHERE username = %s
                          AND is_active = TRUE
                    """, (username,))

                    account = cur.fetchone()

                    if (
                        account
                        and account[2].lower() == selected_role
                        and check_password_hash(
                            account[1], password
                        )
                    ):
                        session.clear()
                        session["username"] = account[0]
                        session["role"] = account[2].lower()
                        return redirect(url_for("dashboard"))

                finally:
                    cur.close()
                    conn.close()

        except (ValueError, TypeError) as error:
            app.logger.error("Login validation error: %s", error)

        except Exception:
            app.logger.exception("Login database error")

        return render_template(
            "login.html",
            error="Invalid username, password, or role."
        )

    return render_template("login.html")

# -------------------------------------------------
# DASHBOARD
# -------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    registered_count = 0
    stolen_count = 0
    recovered_count = 0
    active_cases = 0

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Total registered phones
        cur.execute("""
            SELECT COUNT(*)
            FROM registered_phones
        """)
        registered_count = cur.fetchone()[0]

        # Total stolen phone reports
        cur.execute("""
            SELECT COUNT(*)
            FROM stolen_phones
        """)
        stolen_count = cur.fetchone()[0]

        # Recovered stolen-phone reports
        cur.execute("""
            SELECT COUNT(*)
            FROM stolen_phones
            WHERE LOWER(TRIM(COALESCE(status, ''))) = 'recovered'
               OR LOWER(TRIM(COALESCE(case_status, ''))) = 'recovered'
        """)
        recovered_reports = cur.fetchone()[0]

        # Recovered cases not already represented by a stolen-phone report
        cur.execute("""
            SELECT COUNT(*)
            FROM cases AS c
            WHERE LOWER(TRIM(COALESCE(c.case_status, ''))) = 'recovered'
              AND NOT EXISTS (
                  SELECT 1
                  FROM stolen_phones AS s
                  WHERE s.imei = c.imei
              )
        """)
        recovered_cases = cur.fetchone()[0]

        recovered_count = recovered_reports + recovered_cases

                # Count unique open cases across both tables
        cur.execute("""
            WITH open_records AS (
                SELECT
                    NULLIF(TRIM(imei), '') AS imei,
                    LOWER(TRIM(COALESCE(case_status, 'reported'))) AS case_status
                FROM cases

                UNION ALL

                SELECT
                    NULLIF(TRIM(imei), '') AS imei,
                    LOWER(TRIM(COALESCE(case_status, 'reported'))) AS case_status
                FROM stolen_phones AS s
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM cases AS c
                    WHERE c.imei = s.imei
                )
            ),
            unique_open_cases AS (
                SELECT DISTINCT imei
                FROM open_records
                WHERE case_status IN (
                    'reported',
                    'investigation',
                    'under investigation',
                    'in progress'
                )
                  AND imei IS NOT NULL
            )
            SELECT COUNT(*)
            FROM unique_open_cases
        """)
        active_cases = cur.fetchone()[0]

    except Exception as e:
        if conn:
            conn.rollback()
        print("Dashboard database error:", repr(e))

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return render_template(
        "dashboard.html",
        username=session.get("username"),
        role=session.get("role"),
        registered_count=registered_count,
        stolen_count=stolen_count,
        recovered_count=recovered_count,
        active_cases=active_cases
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

# -------------------------------------------------
# USER REGISTRATION
# -------------------------------------------------

@app.route("/register_phone", methods=["GET", "POST"])
@app.route("/register", methods=["GET", "POST"])
@login_required
def register_phone():
    if request.method == "POST":
        owner_name = request.form.get("owner_name", "").strip()
        phone_number = request.form.get("phone_number", "").strip()

        imei = (
            request.form.get("imei", "").strip()
            or request.form.get("imei1", "").strip()
        )
        imei2 = request.form.get("imei2", "").strip()

        phone_model = (
            request.form.get("phone_model", "").strip()
            or request.form.get("model", "").strip()
        )
        brand = request.form.get("brand", "").strip()
        color = request.form.get("color", "").strip()
        description = request.form.get("description", "").strip()

        if not owner_name or not imei:
            return render_template(
                "register_phone.html",
                error="Owner name and IMEI 1 are required."
            )

        if not imei.isdigit() or len(imei) != 15:
            return render_template(
                "register_phone.html",
                error="IMEI 1 must contain exactly 15 digits."
            )

        if imei2 and (
            not imei2.isdigit() or len(imei2) != 15
        ):
            return render_template(
                "register_phone.html",
                error="IMEI 2 must contain exactly 15 digits."
            )

        conn = None
        cur = None

        try:
            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute("""
                ALTER TABLE registered_phones
                ADD COLUMN IF NOT EXISTS brand VARCHAR(100)
            """)
            cur.execute("""
                ALTER TABLE registered_phones
                ADD COLUMN IF NOT EXISTS imei2 VARCHAR(100)
            """)
            cur.execute("""
                ALTER TABLE registered_phones
                ADD COLUMN IF NOT EXISTS description TEXT
            """)

            cur.execute("""
                INSERT INTO registered_phones (
                    owner_name,
                    phone_number,
                    imei,
                    phone_model,
                    color,
                    brand,
                    imei2,
                    description
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                owner_name,
                phone_number,
                imei,
                phone_model,
                color,
                brand,
                imei2 or None,
                description
            ))

            conn.commit()

            return render_template(
                "register_phone.html",
                success="Phone registered successfully!"
            )

        except Exception as e:
            if conn:
                conn.rollback()

            print("Phone registration error:", repr(e))

            return render_template(
                "register_phone.html",
                error=(
                    "Registration failed. "
                    "Check whether this IMEI is already registered "
                    "and review the Render logs."
                )
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
    if request.method == "GET":
        return render_template("report_stolen.html")

    conn = None
    cur = None

    owner_name = request.form.get("owner_name", "").strip()
    phone_number = request.form.get("phone_number", "").strip()

    imei = (
        request.form.get("imei", "").strip()
        or request.form.get("imei1", "").strip()
    )

    brand = request.form.get("brand", "").strip()
    phone_model = (
        request.form.get("phone_model", "").strip()
        or request.form.get("model", "").strip()
    )

    date_stolen = (
        request.form.get("date_stolen", "").strip()
        or request.form.get("incident_date", "").strip()
    )

    location = (
        request.form.get("location_stolen", "").strip()
        or request.form.get("last_location", "").strip()
        or request.form.get("location", "").strip()
    )

    status_input = (
        request.form.get("case_status", "").strip()
        or request.form.get("status", "Reported").strip()
    )

    description = request.form.get("description", "").strip()
    officer_name = request.form.get("officer_name", "").strip()

    # Accept common status names and normalize them.
    status_map = {
        "reported": "Reported",
        "investigation": "Investigation",
        "under investigation": "Investigation",
        "in progress": "Investigation",
        "recovered": "Recovered",
        "closed": "Closed"
    }

    status = status_map.get(status_input.lower(), "Reported")

    # Avoid repeating the brand if it is already in the model.
    if brand and phone_model:
        if brand.casefold() in phone_model.casefold():
            full_model = phone_model
        else:
            full_model = f"{brand} {phone_model}"
    else:
        full_model = brand or phone_model

    # Validate the required fields.
    if not owner_name:
        return render_template(
            "report_stolen.html",
            error="Owner name is required."
        )

    if not imei.isdigit() or len(imei) != 15:
        return render_template(
            "report_stolen.html",
            error="Please enter a valid 15-digit IMEI number."
        )

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Check the actual database columns before inserting.
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = %s
        """, ("stolen_phones",))

        db_columns = {
            row[0] for row in cur.fetchall()
        }

        if not db_columns:
            raise RuntimeError(
                "The stolen_phones table was not found."
            )

        if not {"owner_name", "imei"}.issubset(db_columns):
            raise RuntimeError(
                "Required owner_name or imei column is missing."
            )

        # Only insert fields that actually exist in the table.
        data = {
            "owner_name": owner_name,
            "phone_number": phone_number,
            "imei": imei,
            "phone_model": full_model,
            "last_location": location,
            "status": status,
            "case_status": status,
        }

        if date_stolen and "date_stolen" in db_columns:
            data["date_stolen"] = date_stolen

        if "description" in db_columns:
            data["description"] = description

        if officer_name and "officer_name" in db_columns:
            data["officer_name"] = officer_name

        insert_columns = []
        placeholders = []
        values = []

        for column, value in data.items():
            if column in db_columns:
                insert_columns.append(column)
                placeholders.append("%s")
                values.append(value)

        # Record the submission time when these columns exist.
        for timestamp_column in ("report_date", "created_at"):
            if (
                timestamp_column in db_columns
                and timestamp_column not in insert_columns
            ):
                insert_columns.append(timestamp_column)
                placeholders.append("CURRENT_TIMESTAMP")

        if not insert_columns:
            raise RuntimeError(
                "No compatible columns found for the insert."
            )

        sql = (
            "INSERT INTO stolen_phones ("
            + ", ".join(insert_columns)
            + ") VALUES ("
            + ", ".join(placeholders)
            + ")"
        )

        cur.execute(sql, values)
        conn.commit()

        return redirect(url_for("dashboard"))

    except Exception:
        if conn:
            conn.rollback()

        app.logger.exception("Stolen phone report failed")

        return render_template(
            "report_stolen.html",
            error=(
                "Report failed. Check the Render logs "
                "for the exact database error."
            )
        )

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# =================================================
# SEARCH PHONE BY IMEI
# =================================================

@app.route("/search_imei", methods=["GET", "POST"])
@app.route("/search", methods=["GET", "POST"])
@login_required
def search_imei():
    results = []
    searched_imei = ""
    error = None
    location_history = []
    location_history_error = None

    conn = None
    cur = None

    if request.method == "POST":
        searched_imei = request.form.get("imei", "").strip()

        if not searched_imei.isdigit() or len(searched_imei) != 15:
            error = "Please enter a valid 15-digit IMEI number."
        else:
            def first_value(record, *keys):
                for key in keys:
                    value = record.get(key)
                    if value is not None and value != "":
                        return value
                return None

            try:
                conn = get_db_connection()
                cur = conn.cursor()

                # Search registered phones
                cur.execute("""
                    SELECT *
                    FROM registered_phones
                    WHERE imei = %s
                """, (searched_imei,))

                registered_columns = [
                    desc[0] for desc in cur.description
                ]

                for row in cur.fetchall():
                    phone = dict(zip(registered_columns, row))

                    results.append({
                        "type": "Registered Phone",
                        "owner_name": phone.get("owner_name"),
                        "phone_number": phone.get("phone_number"),
                        "imei": phone.get("imei"),
                        "phone_model": phone.get("phone_model"),
                        "location": first_value(
                            phone, "location", "color", "address"
                        ),
                        "date": first_value(
                            phone, "registration_date",
                            "created_at", "registered_at"
                        ),
                        "status": phone.get("status") or "Registered"
                    })

                               # Search case records
                cur.execute("""
                    SELECT *
                    FROM cases
                    WHERE imei = %s
                """, (searched_imei,))

                case_columns = [
                    desc[0] for desc in cur.description
                ]

                for row in cur.fetchall():
                    case = dict(zip(case_columns, row))

                    results.append({
                        "type": "Case Record",
                        "owner_name": case.get("owner_name"),
                        "phone_number": None,
                        "imei": case.get("imei"),
                        "phone_model": None,
                        "location": None,
                        "date": case.get("created_at"),
                        "status": case.get("case_status") or "Reported",
                        "case_number": case.get("case_number"),
                        "officer_name": case.get("officer_name")
                    })
                    
                # Load saved location history, including GPS coordinates.
                try:
                    cur.execute("""
                        SELECT location,
                               latitude,
                               longitude,
                               source,
                               notes,
                               recorded_by,
                               recorded_at
                        FROM phone_location_history
                        WHERE imei = %s
                        ORDER BY recorded_at DESC
                    """, (searched_imei,))

                    for row in cur.fetchall():
                        location_history.append({
                            "location": row[0],
                            "latitude": row[1],
                            "longitude": row[2],
                            "source": row[3],
                            "notes": row[4],
                            "recorded_by": row[5],
                            "recorded_at": row[6]
                        })

                except Exception:
                    app.logger.exception(
                        "Could not load phone location history"
                    )
                    location_history_error = (
                        "Could not load location history. "
                        "Check the Render logs for details."
                    )

            except Exception:
                if conn:
                    conn.rollback()

                app.logger.exception("IMEI search failed")
                error = (
                    "Search failed. Check the database table "
                    "and column names in app.py."
                )

            finally:
                if cur:
                    cur.close()
                if conn:
                    conn.close()

    return render_template(
        "search_imei.html",
        results=results,
        searched_imei=searched_imei,
        error=error,
        location_history=location_history,
        location_history_error=location_history_error
    )
    
# =================================================
# CASE MANAGEMENT
# =================================================

@app.route("/cases", methods=["GET", "POST"])
@login_required
def cases():
    message = None
    error = None
    conn = None
    cur = None
    case_list = []
    selected_case = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

     
        if request.method == "POST":
            action = request.form.get("action", "").strip()
            role = session.get("role", "").strip().lower()

         
            # Update an existing case or stolen-phone report
            if action == "update_case":
                role = session.get("role", "").strip().lower()

                if role not in ["admin", "officer"]:
                    error = "Access denied."

                else:
                    source = request.form.get("source", "").strip()
                    record_id = request.form.get("record_id", "").strip()
                    case_status = request.form.get(
                        "case_status", "Reported"
                    ).strip()
                    requested_officer = request.form.get(
                        "officer_name", ""
                    ).strip()

                    allowed_statuses = [
                        "Reported", "Investigation", "Recovered"
                    ]

                    if (
                        not record_id.isdigit()
                        or case_status not in allowed_statuses
                        or source not in ["case", "report"]
                    ):
                        error = "Invalid case update details."

                    else:
                        record_id = int(record_id)

                        # Lock the record while processing the update.
                        # This helps prevent simultaneous duplicate updates.
                        if source == "case":
                            cur.execute("""
                                SELECT case_number, imei,
                                       case_status, officer_name
                                FROM cases
                                WHERE id = %s
                                FOR UPDATE
                            """, (record_id,))
                        else:
                            cur.execute("""
                                SELECT
                                    'STOLEN-' || id::text,
                                    imei, case_status, officer_name
                                FROM stolen_phones
                                WHERE id = %s
                                FOR UPDATE
                            """, (record_id,))

                        old_record = cur.fetchone()

                        if not old_record:
                            error = "Case or stolen-phone report not found."

                        else:
                            case_number = old_record[0]
                            imei = old_record[1]
                            previous_status = old_record[2] or "Reported"
                            existing_officer = old_record[3] or ""

                            # Officers may change status only.
                            # Admins may also change officer assignment.
                            if role == "officer":
                                officer_name = existing_officer
                            else:
                                officer_name = requested_officer

                            if source == "case":
                                if role == "admin":
                                    cur.execute("""
                                        UPDATE cases
                                        SET case_status = %s,
                                            officer_name = %s
                                        WHERE id = %s
                                    """, (
                                        case_status,
                                        officer_name,
                                        record_id
                                    ))
                                else:
                                    cur.execute("""
                                        UPDATE cases
                                        SET case_status = %s
                                        WHERE id = %s
                                    """, (case_status, record_id))

                            else:
                                if role == "admin":
                                    cur.execute("""
                                        UPDATE stolen_phones
                                        SET case_status = %s,
                                            officer_name = %s
                                        WHERE id = %s
                                    """, (
                                        case_status,
                                        officer_name,
                                        record_id
                                    ))
                                else:
                                    cur.execute("""
                                        UPDATE stolen_phones
                                        SET case_status = %s
                                        WHERE id = %s
                                    """, (case_status, record_id))

                            # Save history only when the status changes.
                            if previous_status != case_status:
                                cur.execute("""
                                    INSERT INTO case_history (
                                        source,
                                        record_id,
                                        case_number,
                                        imei,
                                        previous_status,
                                        new_status,
                                        officer_name,
                                        changed_by
                                    )
                                    VALUES (
                                        %s, %s, %s, %s,
                                        %s, %s, %s, %s
                                    )
                                """, (
                                    source,
                                    record_id,
                                    case_number,
                                    imei,
                                    previous_status,
                                    case_status,
                                    officer_name,
                                    session.get("username", "unknown")
                                ))

                            conn.commit()
                            message = "Case updated successfully."

 
            # Create a new case - Admin only
            elif action == "create_case":
                role = session.get("role", "").strip().lower()

                if role != "admin":
                    error = "Access denied. Only admins can create cases."
                else:
                    case_number = request.form.get(
                        "case_number", ""
                    ).strip()
                    imei = request.form.get("imei", "").strip()
                    owner_name = request.form.get(
                        "owner_name", ""
                    ).strip()
                    officer_name = request.form.get(
                        "officer_name", ""
                    ).strip()
                    case_status = request.form.get(
                        "case_status", "Reported"
                    ).strip()
                    description = request.form.get(
                        "description", ""
                    ).strip()

                    allowed_statuses = [
                        "Reported", "Investigation", "Recovered"
                    ]

                    if not case_number or not imei:
                        error = "Case number and IMEI are required."
                    elif case_status not in allowed_statuses:
                        error = "Please select a valid case status."
                    else:
                        cur.execute("""
                            INSERT INTO cases (
                                case_number, imei, owner_name,
                                officer_name, case_status, description
                            )
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT DO NOTHING
                            RETURNING id
                        """, (
                            case_number, imei, owner_name,
                            officer_name, case_status, description
                        ))

                        inserted = cur.fetchone()

                        if inserted:
                            conn.commit()
                            message = "Case created successfully."
                        else:
                            conn.rollback()
                            error = "This case number already exists."

              # Load cases created in the cases table
        cur.execute("""
            SELECT id, case_number, imei, owner_name,
                   officer_name, case_status, description, created_at
            FROM cases
            ORDER BY created_at DESC
        """)
        existing_cases = cur.fetchall()

        for row in existing_cases:
            
            case_imei = row[2] or ""
            cur.execute("""
                SELECT phone_model, color
                FROM registered_phones
                WHERE imei = %s
                LIMIT 1
            """, (case_imei,))

            phone_details = cur.fetchone()

            phone_model = ""
            phone_color = ""

            if phone_details:
                phone_model = phone_details[0] or ""
                phone_color = phone_details[1] or ""

            case_list.append({
                "id": row[0],
                "case_number": row[1],
                "imei": case_imei,
                "owner_name": row[3] or "",
                "officer_name": row[4] or "",
                "case_status": row[5] or "Reported",
                "description": row[6] or "",
                "created_at": row[7],
                "phone_model": phone_model,
                "last_location": "",
                "phone_color": phone_color,
                "source": "case"
            })
        # Load stolen-phone reports into Case Management.
        # Show each report even if another case has the same IMEI.
        cur.execute("""
            SELECT s.id, s.imei, s.owner_name,
                   s.phone_model, s.last_location,
                   s.report_date, s.case_status, s.officer_name
            FROM stolen_phones AS s
            ORDER BY s.report_date DESC NULLS LAST, s.id DESC
        """)
        unlinked_reports = cur.fetchall()

        for row in unlinked_reports:
            case_list.append({
                "id": row[0],
                "case_number": "STOLEN-" + str(row[0]),
                "imei": row[1],
                "owner_name": row[2] or "",
                "phone_model": row[3] or "",
                "last_location": row[4] or "",
                "created_at": row[5],
                "case_status": row[6] or "Reported",
                "officer_name": row[7] or "",
                "description": "Stolen phone report",
                "source": "report"
            })

        case_list.sort(
            key=lambda item: str(item["created_at"] or ""),
            reverse=True
        )

        # Load one case for viewing details
        view_source = request.args.get("source", "").strip()
        view_id = request.args.get("view_id", "").strip()

        if view_id.isdigit() and view_source in ["case", "report"]:
            if view_source == "case":
                cur.execute("""
                    SELECT id, case_number, imei, owner_name,
                           officer_name, case_status,
                           description, created_at
                    FROM cases
                    WHERE id = %s
                """, (int(view_id),))
                row = cur.fetchone()

                if row:
                    selected_case = {
                        "id": row[0],
                        "case_number": row[1],
                        "imei": row[2] or "",
                        "owner_name": row[3] or "",
                        "officer_name": row[4] or "",
                        "case_status": row[5] or "Reported",
                        "description": row[6] or "",
                        "created_at": row[7],
                        "source": "case"
                    }

            else:
                cur.execute("""
                    SELECT id, imei, owner_name, phone_model,
                           last_location, report_date,
                           case_status, officer_name
                    FROM stolen_phones
                    WHERE id = %s
                """, (int(view_id),))
                row = cur.fetchone()

                if row:
                    selected_case = {
                        "id": row[0],
                        "case_number": "STOLEN-" + str(row[0]),
                        "imei": row[1] or "",
                        "owner_name": row[2] or "",
                        "phone_model": row[3] or "",
                        "last_location": row[4] or "",
                        "created_at": row[5],
                        "case_status": row[6] or "Reported",
                        "officer_name": row[7] or "",
                        "description": "Stolen phone report",
                        "source": "report"
                    }

    except Exception as e:
        if conn:
            conn.rollback()

        print("Case management error:", repr(e))
        error = "Could not process cases. Check Render Logs."

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return render_template(
        "cases.html",
        cases=case_list,
        selected_case=selected_case,
        message=message,
        error=error
    )

# =================================================
# AUTHORIZED LOCATION / PHONE GPS LOCATION HISTORY
# =================================================

@app.route("/phone_locations", methods=["GET", "POST"])
@login_required
def phone_locations():
    message = None
    error = None
    locations = []
    authorized_locations = []
    search_imei = request.args.get("search_imei", "").strip()

    if request.method == "POST":
        imei = request.form.get("imei", "").strip()
        location = request.form.get("location", "").strip()
        source = request.form.get("source", "").strip()
        notes = request.form.get("notes", "").strip()
        permission = (
            request.form.get("permission_confirmed") == "yes"
        )

        latitude_text = request.form.get("latitude", "").strip()
        longitude_text = request.form.get("longitude", "").strip()
        latitude = None
        longitude = None

        try:
            if latitude_text:
                latitude = float(latitude_text)
            if longitude_text:
                longitude = float(longitude_text)
        except ValueError:
            error = "Latitude and Longitude must be valid numbers."

        if not error and (not imei or not location):
            error = "IMEI and location are required."
        elif not error and (len(imei) != 15 or not imei.isdigit()):
            error = "IMEI must contain exactly 15 digits."
        elif not error and not permission:
            error = "Confirm legal authorization before saving."
        elif not error and ((latitude is None) != (longitude is None)):
            error = "Enter both Latitude and Longitude, or leave both empty."
        elif not error and latitude is not None and not (-90 <= latitude <= 90):
            error = "Latitude must be between -90 and 90."
        elif not error and longitude is not None and not (-180 <= longitude <= 180):
            error = "Longitude must be between -180 and 180."

        if not error:
            conn = None
            cur = None
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO phone_location_history (
                        imei, location, latitude, longitude,
                        source, notes, permission_confirmed, recorded_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    imei, location, latitude, longitude,
                    source or None, notes or None, True,
                    str(session.get("username", "unknown"))
                ))
                conn.commit()
                message = "Phone location record saved successfully."
            except Exception:
                if conn:
                    conn.rollback()
                app.logger.exception("Phone location save failed")
                error = "Save failed. Check the Render logs and database."
            finally:
                if cur:
                    cur.close()
                if conn:
                    conn.close()

    # Load phone GPS location history.
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if search_imei and (
            len(search_imei) != 15 or not search_imei.isdigit()
        ):
            error = error or "Search IMEI must contain exactly 15 digits."
        else:
            if search_imei:
                cur.execute("""
                    SELECT id, imei, location, latitude, longitude,
                           source, notes, permission_confirmed,
                           recorded_by, recorded_at
                    FROM phone_location_history
                    WHERE imei = %s
                    ORDER BY recorded_at DESC
                """, (search_imei,))
            else:
                cur.execute("""
                    SELECT id, imei, location, latitude, longitude,
                           source, notes, permission_confirmed,
                           recorded_by, recorded_at
                    FROM phone_location_history
                    ORDER BY recorded_at DESC
                """)

            for row in cur.fetchall():
                locations.append({
                    "id": row[0],
                    "imei": row[1],
                    "location": row[2],
                    "latitude": row[3],
                    "longitude": row[4],
                    "source": row[5],
                    "notes": row[6],
                    "permission_confirmed": row[7],
                    "recorded_by": row[8],
                    "recorded_at": row[9]
                })

    except Exception:
        app.logger.exception("Phone location history load failed")
        error = error or "Could not load phone location history. Check Render logs."
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    # Load authorized locations for the GPS map.
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT location_name, address, city,
                   latitude, longitude, location_type, status
            FROM authorized_locations
            WHERE latitude IS NOT NULL
              AND longitude IS NOT NULL
              AND LOWER(TRIM(COALESCE(status, ''))) = 'active'
            ORDER BY location_name
        """)
        for row in cur.fetchall():
            authorized_locations.append({
                "location_name": row[0],
                "address": row[1],
                "city": row[2],
                "latitude": row[3],
                "longitude": row[4],
                "location_type": row[5],
                "status": row[6]
            })
    except Exception:
        app.logger.exception("Authorized locations map load failed")
        error = error or "Could not load authorized locations for the map."
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
            
     # Count GPS history records.
    gps_record_count = sum(
        1 for item in locations
        if item["latitude"] is not None
        and item["longitude"] is not None
    )

    no_gps_record_count = len(locations) - gps_record_count

    return render_template(
        "phone_locations.html",
        locations=locations,
        authorized_locations=authorized_locations,
        success=message,
        error=error,
        search_imei=search_imei,
        gps_record_count=gps_record_count,
        no_gps_record_count=no_gps_record_count
    )

# =================================================
# CASE HISTORY
# =================================================

@app.route("/case_history")
@login_required
def case_history():
    
    history_list = []
    error = None
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                id,
                source,
                record_id,
                case_number,
                imei,
                previous_status,
                new_status,
                officer_name,
                changed_by,
                changed_at
            FROM case_history
            ORDER BY changed_at DESC
            LIMIT 200
        """)

        rows = cur.fetchall()

        for row in rows:
            history_list.append({
                "id": row[0],
                "source": row[1],
                "record_id": row[2],
                "case_number": row[3] or "",
                "imei": row[4] or "",
                "previous_status": row[5] or "",
                "new_status": row[6] or "",
                "officer_name": row[7] or "",
                "changed_by": row[8] or "",
                "changed_at": row[9]
            })

    except Exception as e:
        if conn:
            conn.rollback()

        print("Case history error:", repr(e))
        error = "Could not load case history. Check Render Logs."

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return render_template(
        "case_history.html",
        history_list=history_list,
        error=error
    )


# =================================================
# REPORTS
# =================================================

@app.route("/reports")
@login_required
def reports():
    conn = None
    cur = None

    registered_count = 0
    stolen_count = 0
    recovered_count = 0
    cases_count = 0
    active_cases_count = 0
    reported_count = 0
    investigation_count = 0
    recovered_cases_count = 0
    closed_count = 0
    locations_count = 0
    recent_stolen = []
    error = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # 1. Registered phones
        cur.execute("""
            SELECT COUNT(*)
            FROM registered_phones
        """)
        registered_count = cur.fetchone()[0]

        # 2. Total stolen phone reports
        cur.execute("""
            SELECT COUNT(*)
            FROM stolen_phones
        """)
        stolen_count = cur.fetchone()[0]

        
                     # 3. Case Status summary — count unique IMEIs.
        cur.execute("""
            WITH all_case_records AS (
                SELECT
                    NULLIF(TRIM(imei), '') AS imei,
                    COALESCE(
                        NULLIF(LOWER(TRIM(case_status)), ''),
                        'reported'
                    ) AS status,
                    1 AS source_priority
                FROM cases

                UNION ALL

                SELECT
                    NULLIF(TRIM(imei), '') AS imei,
                    COALESCE(
                        NULLIF(LOWER(TRIM(case_status)), ''),
                        'reported'
                    ) AS status,
                    2 AS source_priority
                FROM stolen_phones AS s
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM cases AS c
                    WHERE c.imei = s.imei
                )
            ),
            unique_cases AS (
                SELECT DISTINCT ON (imei)
                    imei,
                    status
                FROM all_case_records
                WHERE imei IS NOT NULL
                ORDER BY imei, source_priority
            )
            SELECT
                COUNT(*),
                COUNT(*) FILTER (
                    WHERE status = 'reported'
                ),
                COUNT(*) FILTER (
                    WHERE status IN (
                        'investigation',
                        'under investigation',
                        'in progress'
                    )
                ),
                COUNT(*) FILTER (
                    WHERE status = 'recovered'
                ),
                COUNT(*) FILTER (
                    WHERE status = 'closed'
                )
            FROM unique_cases
        """)
        row = cur.fetchone()

        cases_count = row[0]
        reported_count = row[1]
        investigation_count = row[2]
        recovered_cases_count = row[3]
        closed_count = row[4]
       
        # 4. Recovered phones - use the same counting rule as Dashboard.
        cur.execute("""
            SELECT COUNT(*)
            FROM stolen_phones
            WHERE LOWER(TRIM(COALESCE(status, ''))) = 'recovered'
               OR LOWER(TRIM(COALESCE(case_status, ''))) = 'recovered'
        """)
        recovered_reports = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*)
            FROM cases AS c
            WHERE LOWER(TRIM(COALESCE(c.case_status, ''))) = 'recovered'
              AND NOT EXISTS (
                  SELECT 1
                  FROM stolen_phones AS s
                  WHERE s.imei = c.imei
              )
        """)
        recovered_cases = cur.fetchone()[0]
        recovered_count = recovered_reports + recovered_cases

        # 5. Active cases - use the same counting rule as Dashboard.
        cur.execute("""
            SELECT
                (
                    SELECT COUNT(*)
                    FROM cases
                    WHERE LOWER(TRIM(COALESCE(case_status, '')))
                        IN (
                            'reported',
                            'investigation',
                            'under investigation',
                            'in progress'
                        )
                )
                +
                (
                    SELECT COUNT(*)
                    FROM stolen_phones AS s
                    WHERE LOWER(TRIM(COALESCE(s.case_status, '')))
                        IN (
                            'reported',
                            'investigation',
                            'under investigation',
                            'in progress'
                        )
                      AND NOT EXISTS (
                          SELECT 1
                          FROM cases AS c
                          WHERE c.imei = s.imei
                      )
                )
        """)
        active_cases_count = cur.fetchone()[0]

        # 4. Authorized locations
        cur.execute("""
            SELECT COUNT(*)
            FROM authorized_locations
        """)
        locations_count = cur.fetchone()[0]

        # 5. Recent stolen phone reports
        cur.execute("""
            SELECT
                id,
                owner_name,
                phone_number,
                imei,
                phone_model,
                last_location,
                report_date,
                case_status
            FROM stolen_phones
            ORDER BY report_date DESC
            LIMIT 20
        """)

        for row in cur.fetchall():
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
        if conn:
            conn.rollback()

        print("Reports error:", repr(e))
        error = f"Reports error: {e}"

    finally:
        if cur:
            cur.close()

        if conn:
            conn.close()

    return render_template(
        "reports.html",
        registered_count=registered_count,
        stolen_count=stolen_count,
        recovered_count=recovered_count,
        cases_count=cases_count,
        active_cases_count=active_cases_count,
        reported_count=reported_count,
        investigation_count=investigation_count,
        recovered_cases_count=recovered_cases_count,
        closed_count=closed_count,
        locations_count=locations_count,
        recent_stolen=recent_stolen,
        error=error
    )


def excel_safe_text(value):
    """Prepare text safely for spreadsheet export."""
    text = "" if value is None else str(value)

    if text.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + text

    return text


@app.route("/reports/export")
@login_required
def export_reports():
    import csv
    import io
    from flask import Response

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                owner_name,
                phone_number,
                imei,
                phone_model,
                last_location,
                report_date,
                COALESCE(
                    NULLIF(case_status, ''),
                    status,
                    'Reported'
                ) AS report_status
            FROM stolen_phones
            ORDER BY report_date DESC NULLS LAST
        """)

        rows = cur.fetchall()

        output = io.StringIO(newline="")
        output.write("\ufeff")
        writer = csv.writer(output, lineterminator="\r\n")

        writer.writerow([
            "Owner Name",
            "Phone Number",
            "IMEI",
            "Phone Model",
            "Last Location",
            "Report Date",
            "Status"
        ])

        for row in rows:
            owner_name = row[0]
            phone_number = row[1]
            imei = row[2]
            phone_model = row[3]
            last_location = row[4]
            report_date = row[5]
            status = row[6]

            # Keep IMEI and phone number as text in Excel.
            imei_text = str(imei or "").strip()
            phone_text = str(phone_number or "").strip()

            imei_cell = (
                '="' + imei_text + '"'
                if imei_text.isdigit()
                else excel_safe_text(imei_text)
            )

            if phone_text.isdigit() or (
                phone_text.startswith("+")
                and phone_text[1:].isdigit()
            ):
                phone_cell = '="' + phone_text + '"'
            else:
                phone_cell = excel_safe_text(phone_text)

            # Keep date and time together.
            if report_date is not None and hasattr(
                report_date, "strftime"
            ):
                date_cell = report_date.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            else:
                date_cell = str(report_date or "")

            writer.writerow([
                excel_safe_text(owner_name),
                phone_cell,
                imei_cell,
                excel_safe_text(phone_model),
                excel_safe_text(last_location),
                date_cell,
                excel_safe_text(status)
            ])

        return Response(
            output.getvalue(),
            mimetype="text/csv; charset=utf-8",
            headers={
                "Content-Disposition":
                    'attachment; filename="stolen_phone_reports.csv"'
            }
        )

    except Exception:
        app.logger.exception("Report export failed")
        return "Report export failed. Check server logs.", 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# =================================================
# LOGOUT
# =================================================

@app.route("/logout", methods=["GET"])
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))
    
# =================================================
# SAFEDEVICE PAGE AND IMEI API
# =================================================

from flask import jsonify
from datetime import datetime
@app.route("/safedevice")
@login_required
def safedevice():
    conn = None
    cur = None

    registered_count = 0
    stolen_count = 0
    location_count = 0
    locations = []

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM registered_phones")
        registered_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM stolen_phones")
        stolen_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM phone_location_history")
        location_count = cur.fetchone()[0]

        cur.execute("""
            SELECT imei, location, latitude, longitude,
                   source, recorded_at
            FROM phone_location_history
            ORDER BY recorded_at DESC
            LIMIT 20
        """)

        for row in cur.fetchall():
            locations.append({
                "imei": row[0],
                "location": row[1],
                "latitude": row[2],
                "longitude": row[3],
                "source": row[4],
                "recorded_at": row[5]
            })

    except Exception:
        app.logger.exception("SafeDevice page database error")

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return render_template(
        "safedevice.html",
        registered_count=registered_count,
        stolen_count=stolen_count,
        location_count=location_count,
        locations=locations,
        current_year=datetime.now().year
    )


@app.route("/api/safedevice/imei", methods=["POST"])
@login_required
def safedevice_imei_api():
    data = request.get_json(silent=True) or {}
    imei = str(data.get("imei", "")).strip()

    if not imei.isdigit() or len(imei) != 15:
        return jsonify({
            "error": "IMEI must contain exactly 15 digits."
        }), 400

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM registered_phones
                WHERE imei = %s
            )
        """, (imei,))
        registered = cur.fetchone()[0]

        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM stolen_phones
                WHERE imei = %s
            )
        """, (imei,))
        stolen_report = cur.fetchone()[0]

        if stolen_report:
            status = "Stolen report found"
        elif registered:
            status = "Registered; no stolen report found"
        else:
            status = "No matching record"

        return jsonify({
            "registered": registered,
            "stolen_report": stolen_report,
            "status": status
        })

    except Exception:
        app.logger.exception("SafeDevice IMEI API error")
        return jsonify({
            "error": "Database search failed. Check Render logs."
        }), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


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
