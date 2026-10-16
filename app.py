
from flask import Flask, render_template, request, redirect, session, url_for
import os
import psycopg2
from functools import wraps
from werkzeug.security import check_password_hash

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

                    # Add missing columns without deleting existing records
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

        # Ensure required columns exist in an older cases table
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
        
        # Case history table
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
                source VARCHAR(150),
                notes TEXT,
                permission_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
                recorded_by VARCHAR(150),
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        password = request.form.get("password", "")

        admin_username = os.environ.get(
            "ADMIN_USERNAME", "admin"
        ).strip()

        admin_password_hash = os.environ.get(
            "ADMIN_PASSWORD_HASH", ""
        ).strip()

        # Remove accidental whitespace around the hash
        admin_password_hash = "".join(
            admin_password_hash.split()
        )

        if admin_username and admin_password_hash:
            try:
                if (
                    username == admin_username
                    and check_password_hash(
                        admin_password_hash, password
                    )
                ):
                    session.clear()
                    session["username"] = username
                    session["role"] = "admin"
                    return redirect(url_for("dashboard"))

            except (ValueError, TypeError) as error:
                app.logger.error(
                    "ADMIN_PASSWORD_HASH is invalid: %s",
                    error
                )

        return render_template(
            "login.html",
            error="Invalid username or password. Check admin settings."
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

        # Open cases from both tables, avoiding duplicate IMEIs
        cur.execute("""
            SELECT
                (
                    SELECT COUNT(*)
                    FROM cases
                    WHERE LOWER(TRIM(COALESCE(case_status, 'reported')))
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
                    WHERE LOWER(TRIM(COALESCE(s.case_status, 'reported')))
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
    conn = None
    cur = None

    if request.method == "POST":
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

        status = request.form.get("case_status", "Reported").strip()
        description = request.form.get("description", "").strip()

        allowed_statuses = [
            "Reported",
            "Under Investigation",
            "Recovered",
            "Closed"
        ]

        if status not in allowed_statuses:
            status = "Reported"

        if not owner_name or not imei:
            return render_template(
                "report_stolen.html",
                error="Owner name and IMEI are required."
            )

        try:
                
            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO stolen_phones (
                    owner_name,
                    phone_number,
                    imei,
                    phone_model,
                    last_location,
                    date_stolen,
                    status,
                    case_status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                owner_name,
                phone_number,
                imei,
                (brand + " " + phone_model).strip(),
                location,
                date_stolen or None,
                status,
                status
            ))

            conn.commit()

            return redirect(url_for("dashboard"))

        except Exception as e:
            if conn:
                conn.rollback()

            print("Stolen phone report error:", repr(e))

            return render_template(
                "report_stolen.html",
                error="Report failed. Check the IMEI and database logs."
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
    conn = None
    cur = None
    case_list = []
    selected_case = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

     
        if request.method == "POST":
            action = request.form.get("action", "").strip()

         
            # Update an existing case or stolen-phone report
            if action == "update_case":
                source = request.form.get("source", "").strip()
                record_id = request.form.get("record_id", "").strip()
                case_status = request.form.get(
                    "case_status", "Reported"
                ).strip()
                officer_name = request.form.get(
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

                    if source == "case":
                        cur.execute("""
                            SELECT case_number, imei, case_status
                            FROM cases
                            WHERE id = %s
                        """, (record_id,))
                    else:
                        cur.execute("""
                            SELECT
                                'STOLEN-' || id::text,
                                imei,
                                case_status
                            FROM stolen_phones
                            WHERE id = %s
                        """, (record_id,))

                    old_record = cur.fetchone()

                    if not old_record:
                        error = "Case or stolen-phone report not found."

                    else:
                        case_number = old_record[0]
                        imei = old_record[1]
                        previous_status = old_record[2] or "Reported"

                        if source == "case":
                            cur.execute("""
                                UPDATE cases
                                SET case_status = %s,
                                    officer_name = %s
                                WHERE id = %s
                            """, (
                                case_status, officer_name, record_id
                            ))
                        else:
                            cur.execute("""
                                UPDATE stolen_phones
                                SET case_status = %s,
                                    officer_name = %s
                                WHERE id = %s
                            """, (
                                case_status, officer_name, record_id
                            ))

                       
                        # Save history only when the status changes
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
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT DO NOTHING
                                RETURNING id
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

                            history_row = cur.fetchone()

                        conn.commit()
                        message = "Case updated successfully."

 

            # Create a new case
            elif action == "create_case":
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
            case_list.append({
                "id": row[0],
                "case_number": row[1],
                "imei": row[2],
                "owner_name": row[3] or "",
                "officer_name": row[4] or "",
                "case_status": row[5] or "Reported",
                "description": row[6] or "",
                "created_at": row[7],
                "phone_model": "",
                "last_location": "",
                "source": "case"
            })

        # Load stolen-phone reports not yet linked to a case
        cur.execute("""
            SELECT s.id, s.imei, s.owner_name,
                   s.phone_model, s.last_location,
                   s.report_date, s.case_status, s.officer_name
            FROM stolen_phones AS s
            WHERE NOT EXISTS (
                SELECT 1
                FROM cases AS c
                WHERE c.imei = s.imei
            )
            ORDER BY s.report_date DESC
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
# AUTHORIZED LOCATION
# =================================================

@app.route("/phone_locations", methods=["GET", "POST"])
@login_required
def phone_locations():
    message = None
    error = None
    locations = []

    if request.method == "POST":
        imei = request.form.get("imei", "").strip()
        location = request.form.get("location", "").strip()
        source = request.form.get("source", "").strip()
        notes = request.form.get("notes", "").strip()
        permission = request.form.get("permission_confirmed") == "yes"

        if not imei or not location:
            error = "IMEI and location are required."
        elif not permission:
            error = "Confirm legal authorization before saving."
        else:
            conn = None
            cur = None

            try:
                conn = get_db_connection()
                cur = conn.cursor()

                cur.execute("""
                    INSERT INTO phone_location_history
                    (imei, location, source, notes,
                     permission_confirmed, recorded_by)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    imei,
                    location,
                    source or None,
                    notes or None,
                    True,
                    str(session.get("username", "admin"))
                ))

                conn.commit()
                message = "Phone location record saved successfully."

            except Exception as e:
                if conn:
                    conn.rollback()
                error = f"Save failed: {e}"

            finally:
                if cur:
                    cur.close()
                if conn:
                    conn.close()

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, imei, location, source, notes,
                   permission_confirmed, recorded_by, recorded_at
            FROM phone_location_history
            ORDER BY recorded_at DESC
        """)

        rows = cur.fetchall()

        for row in rows:
            locations.append({
                "id": row[0],
                "imei": row[1],
                "location": row[2],
                "source": row[3],
                "notes": row[4],
                "permission_confirmed": row[5],
                "recorded_by": row[6],
                "recorded_at": row[7]
            })

    except Exception as e:
        error = error or f"Could not load location history: {e}"

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return render_template(
        "phone_locations.html",
        locations=locations,
        success=message,
        error=error
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

               # 3. Count cases and unlinked stolen-phone reports
        # without counting the same IMEI twice.
        cur.execute("""
            WITH all_cases AS (
                SELECT
                    case_status,
                    imei
                FROM cases

                UNION ALL

                SELECT
                    CASE
                        WHEN LOWER(TRIM(COALESCE(s.case_status, '')))
                             IN (
                                 'recovered',
                                 'closed',
                                 'investigation',
                                 'under investigation',
                                 'in progress'
                             )
                        THEN s.case_status

                        WHEN LOWER(TRIM(COALESCE(s.status, '')))
                             IN (
                                 'reported',
                                 'recovered',
                                 'closed',
                                 'investigation',
                                 'under investigation',
                                 'in progress'
                             )
                        THEN s.status

                        ELSE 'Reported'
                    END AS case_status,
                    s.imei
                FROM stolen_phones AS s
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM cases AS c
                    WHERE c.imei = s.imei
                )
            )
            SELECT
                COUNT(*),

                COUNT(*) FILTER (
                    WHERE LOWER(TRIM(COALESCE(case_status, '')))
                          = 'reported'
                ),

                COUNT(*) FILTER (
                    WHERE LOWER(TRIM(COALESCE(case_status, '')))
                          IN (
                              'investigation',
                              'under investigation',
                              'in progress'
                          )
                ),

                COUNT(*) FILTER (
                    WHERE LOWER(TRIM(COALESCE(case_status, '')))
                          = 'recovered'
                ),

                COUNT(*) FILTER (
                    WHERE LOWER(TRIM(COALESCE(case_status, '')))
                          = 'closed'
                )

            FROM all_cases
        """)

        row = cur.fetchone()

        cases_count = row[0]
        reported_count = row[1]
        investigation_count = row[2]
        recovered_cases_count = row[3]
        closed_count = row[4]

        recovered_count = recovered_cases_count

        active_cases_count = (
            reported_count + investigation_count
        )

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
