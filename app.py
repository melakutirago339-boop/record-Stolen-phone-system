from flask import Flask, render_template, request, redirect, url_for, session
import os
import psycopg2

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")

# =========================

# DATABASE CONNECTION

# =========================

def get_db_connection():
database_url = os.environ.get("DATABASE_URL")


if not database_url:
    raise RuntimeError("DATABASE_URL is not configured.")

return psycopg2.connect(database_url)


# =========================

# CREATE DATABASE TABLES

# =========================

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
            owner_name VARCHAR(100) NOT NULL,
            phone_number VARCHAR(50),
            phone_brand VARCHAR(100),
            phone_model VARCHAR(100),
            phone_color VARCHAR(50),
            imei VARCHAR(50) UNIQUE NOT NULL,
            imei2 VARCHAR(50),
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
    print("Database tables created successfully.")

except Exception as e:
    print("Database table creation error:", e)

finally:
    if cur:
        cur.close()
    if conn:
        conn.close()


# =========================

# LOGIN

# =========================

@app.route("/", methods=["GET", "POST"])
def login():


if request.method == "POST":

    username = request.form.get("username")
    password = request.form.get("password")
    role = request.form.get("role", "officer")

    # Test login
    if username == "admin" and password == "admin123":

        session["username"] = username
        session["role"] = role

        return redirect(url_for("dashboard"))

    return render_template(
        "login.html",
        error="Invalid username or password."
    )

return render_template("login.html")


# =========================

# DASHBOARD

# =========================

@app.route("/dashboard")
def dashboard():


if "username" not in session:
    return redirect(url_for("login"))

registered_count = 0
stolen_count = 0
recovered_count = 0
active_cases = 0

conn = None
cur = None

try:

    conn = get_db_connection()
    cur = conn.cursor()

    # Registered phones
    cur.execute("""
        SELECT COUNT(*)
        FROM registered_phones
    """)

    registered_count = cur.fetchone()[0]

    # Stolen phones
    cur.execute("""
        SELECT COUNT(*)
        FROM stolen_phones
    """)

    stolen_count = cur.fetchone()[0]

    # Recovered phones
    cur.execute("""
        SELECT COUNT(*)
        FROM stolen_phones
        WHERE status = 'Recovered'
    """)

    recovered_count = cur.fetchone()[0]

    # Active cases
    cur.execute("""
        SELECT COUNT(*)
        FROM cases
        WHERE case_status = 'Open'
    """)

    active_cases = cur.fetchone()[0]

except Exception as e:

    print("Dashboard database error:", e)

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


# =========================

# REGISTER PHONE

# =========================

@app.route("/register-phone", methods=["GET", "POST"])
def register_phone():


if "username" not in session:
    return redirect(url_for("login"))

if request.method == "POST":

    owner_name = request.form.get("owner_name")
    phone_number = request.form.get("phone_number")
    imei = request.form.get("imei")
    imei2 = request.form.get("imei2")
    phone_brand = request.form.get("phone_brand")
    phone_model = request.form.get("phone_model")
    phone_color = request.form.get("phone_color")
    date_registered = request.form.get("date_registered")
    description = request.form.get("description")

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
                phone_brand,
                phone_model,
                phone_color,
                imei,
                imei2,
                date_registered,
                description
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            owner_name,
            phone_number,
            phone_brand,
            phone_model,
            phone_color,
            imei,
            imei2,
            date_registered,
            description
        ))

        conn.commit()

        return redirect(url_for("dashboard"))

    except Exception as e:

        print("Register phone error:", e)

        if conn:
            conn.rollback()

        return render_template(
            "register_phone.html",
            error="Could not register the phone. Please check the IMEI and try again."
        )

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()

return render_template("register_phone.html")


# =========================

# LOGOUT

# =========================

@app.route("/logout")
def logout():


session.clear()

return redirect(url_for("login"))


# =========================

# STARTUP

# =========================

try:
create_tables()
except Exception as e:
print("Startup database error:", e)

# =========================

# LOCAL DEVELOPMENT

# =========================

if **name** == "**main**":


port = int(os.environ.get("PORT", 5000))

app.run(
    host="0.0.0.0",
    port=port
)

