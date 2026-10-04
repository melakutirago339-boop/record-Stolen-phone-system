import os
from datetime import datetime

import psycopg2
from flask import Flask, render_template, request, redirect, session, url_for

app = Flask(__name__)

# IMPORTANT:
# Change this in Render Environment Variables.
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise Exception("DATABASE_URL is not configured in Render.")

    return psycopg2.connect(database_url)


# =========================================================
# CREATE DATABASE TABLES
# =========================================================

def create_tables():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Registered phones
        cur.execute("""
            CREATE TABLE IF NOT EXISTS registered_phones (
                id SERIAL PRIMARY KEY,
                owner_name VARCHAR(100) NOT NULL,
                phone_number VARCHAR(50),
                phone_model VARCHAR(100),
                imei VARCHAR(50) UNIQUE NOT NULL,
                date_registered DATE,
                description TEXT,
                status VARCHAR(30) DEFAULT 'Registered',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Stolen phones
        cur.execute("""
            CREATE TABLE IF NOT EXISTS stolen_phones (
                id SERIAL PRIMARY KEY,
                owner_name VARCHAR(100) NOT NULL,
                phone_number VARCHAR(50),
                phone_model VARCHAR(100),
                imei VARCHAR(50) NOT NULL,
                stolen_date DATE,
                stolen_location TEXT,
                description TEXT,
                status VARCHAR(30) DEFAULT 'Stolen',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Cases
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                id SERIAL PRIMARY KEY,
                imei VARCHAR(50) NOT NULL,
                owner_name VARCHAR(100),
                case_number VARCHAR(100),
                case_status VARCHAR(30) DEFAULT 'Open',
                officer_name VARCHAR(100),
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        cur.close()
        conn.close()

        print("Database tables created successfully.")

    except Exception as e:
        print("Database table creation error:", e)


# =========================================================
# LOGIN
# =========================================================

@app.route("/")
def home():
    if "username" in session:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "Administrator").strip()

        # Admin login
        if username == "admin" and password == "admin":

            session["username"] = username
            session["role"] = role

            return redirect(url_for("dashboard"))

        return render_template(
            "login.html",
            error="Invalid username or password ❌"
        )

    return render_template("login.html")


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if "username" not in session:
        return redirect(url_for("login"))

    return render_template(
        "dashboard.html",
        username=session.get("username"),
        role=session.get("role")
    )


# =========================================================
# REGISTER PHONE
# =========================================================

@app.route("/register-phone", methods=["GET", "POST"])
def register_phone():

    if "username" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        owner_name = request.form.get("owner_name", "").strip()
        phone_number = request.form.get("phone_number", "").strip()
        phone_model = request.form.get("phone_model", "").strip()
        imei = request.form.get("imei", "").strip()
        date_registered = request.form.get("date_registered") or None
        description = request.form.get("description", "").strip()

        if not owner_name or not phone_model or not imei:
            return render_template(
                "register_phone.html",
                error="Owner name, phone model and IMEI are required ❌"
            )

        try:

            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO registered_phones
                (
                    owner_name,
                    phone_number,
                    phone_model,
                    imei,
                    date_registered,
                    description
                )
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                owner_name,
                phone_number,
                phone_model,
                imei,
                date_registered,
                description
            ))

            conn.commit()

            cur.close()
            conn.close()

            return render_template(
                "register_phone.html",
                success="Phone registered successfully ✅"
            )

        except psycopg2.errors.UniqueViolation:

            return render_template(
                "register_phone.html",
                error="This IMEI is already registered ❌"
            )

        except Exception as e:

            return render_template(
                "register_phone.html",
                error=f"Database error ❌: {e}"
            )

    return render_template("register_phone.html")


# =========================================================
# REPORT STOLEN PHONE
# =========================================================

@app.route("/report-stolen", methods=["GET", "POST"])
def report_stolen():

    if "username" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        owner_name = request.form.get("owner_name", "").strip()
        phone_number = request.form.get("phone_number", "").strip()
        phone_model = request.form.get("phone_model", "").strip()
        imei = request.form.get("imei", "").strip()
        stolen_date = request.form.get("stolen_date") or None
        stolen_location = request.form.get("stolen_location", "").strip()
        description = request.form.get("description", "").strip()

        if not owner_name or not imei:
            return render_template(
                "report_stolen.html",
                error="Owner name and IMEI are required ❌"
            )

        try:

            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO stolen_phones
                (
                    owner_name,
                    phone_number,
                    phone_model,
                    imei,
                    stolen_date,
                    stolen_location,
                    description
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                owner_name,
                phone_number,
                phone_model,
                imei,
                stolen_date,
                stolen_location,
                description
            ))

            conn.commit()

            cur.close()
            conn.close()

            return render_template(
                "report_stolen.html",
                success="Stolen phone report saved successfully ✅"
            )

        except Exception as e:

            return render_template(
                "report_stolen.html",
                error=f"Database error ❌: {e}"
            )

    return render_template("report_stolen.html")


# =========================================================
# SEARCH PHONE BY IMEI
# =========================================================

@app.route("/search-imei", methods=["GET", "POST"])
def search_imei():

    if "username" not in session:
        return redirect(url_for("login"))

    result = None
    error = None
    imei = ""

    if request.method == "POST":

        imei = request.form.get("imei", "").strip()

        if not imei:
            error = "Please enter an IMEI number."

        else:

            try:

                conn = get_db_connection()
                cur = conn.cursor()

                # Search registered phone
                cur.execute("""
                    SELECT
                        id,
                        owner_name,
                        phone_number,
                        phone_model,
                        imei,
                        date_registered,
                        description,
                        status
                    FROM registered_phones
                    WHERE imei = %s
                """, (imei,))

                registered = cur.fetchone()

                # Search stolen phone
                cur.execute("""
                    SELECT
                        id,
                        owner_name,
                        phone_number,
                        phone_model,
                        imei,
                        stolen_date,
                        stolen_location,
                        description,
                        status
                    FROM stolen_phones
                    WHERE imei = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (imei,))

                stolen = cur.fetchone()

                cur.close()
                conn.close()

                if registered or stolen:
                    result = {
                        "registered": registered,
                        "stolen": stolen
                    }
                else:
                    error = "No phone found with this IMEI ❌"

            except Exception as e:

                error = f"Database error ❌: {e}"

    return render_template(
        "search_imei.html",
        result=result,
        error=error,
        imei=imei
    )


# =========================================================
# CASE MANAGEMENT
# =========================================================

@app.route("/cases")
def cases():

    if "username" not in session:
        return redirect(url_for("login"))

    try:

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                id,
                imei,
                owner_name,
                case_number,
                case_status,
                officer_name,
                notes,
                created_at
            FROM cases
            ORDER BY created_at DESC
        """)

        case_list = cur.fetchall()

        cur.close()
        conn.close()

        return render_template(
            "cases.html",
            cases=case_list
        )

    except Exception as e:

        return render_template(
            "cases.html",
            cases=[],
            error=f"Database error ❌: {e}"
        )


# =========================================================
# REPORTS
# =========================================================

@app.route("/reports")
def reports():

    if "username" not in session:
        return redirect(url_for("login"))

    try:

        conn = get_db_connection()
        cur = conn.cursor()

        # Total registered phones
        cur.execute("""
            SELECT COUNT(*)
            FROM registered_phones
        """)

        total_registered = cur.fetchone()[0]

        # Total stolen phones
        cur.execute("""
            SELECT COUNT(*)
            FROM stolen_phones
        """)

        total_stolen = cur.fetchone()[0]

        # Total cases
        cur.execute("""
            SELECT COUNT(*)
            FROM cases
        """)

        total_cases = cur.fetchone()[0]

        cur.close()
        conn.close()

        return render_template(
            "reports.html",
            total_registered=total_registered,
            total_stolen=total_stolen,
            total_cases=total_cases
        )

    except Exception as e:

        return render_template(
            "reports.html",
            total_registered=0,
            total_stolen=0,
            total_cases=0,
            error=f"Database error ❌: {e}"
        )


# =========================================================
# STARTUP
# =========================================================

try:
    create_tables()
except Exception as e:
    print("Startup database error:", e)


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port
    )
