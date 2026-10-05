from flask import Flask, render_template, request, redirect, url_for, session
import os
import psycopg2

app = Flask(**name**)

app.secret_key = os.environ.get(
"SECRET_KEY",
"stolen-phone-system-secret-key"
)

def get_db_connection():
database_url = os.environ.get("DATABASE_URL")

```
if not database_url:
    raise Exception("DATABASE_URL is not configured")

return psycopg2.connect(database_url)
```

def create_tables():
conn = None
cur = None

```
try:
    conn = get_db_connection()
    cur = conn.cursor()

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
```

@app.route("/")
def home():
return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():

```
if request.method == "POST":

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    role = request.form.get("role", "admin").strip()

    if username == "admin" and password == "admin":

        session["username"] = username
        session["role"] = role

        return redirect(url_for("dashboard"))

    return render_template(
        "login.html",
        error="Invalid username or password ❌"
    )

return render_template("login.html")
```

@app.route("/dashboard")
def dashboard():

```
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

    cur.execute("""
        SELECT COUNT(*)
        FROM registered_phones
    """)

    registered_count = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM stolen_phones
    """)

    stolen_count = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM stolen_phones
        WHERE status = 'Recovered'
    """)

    recovered_count = cur.fetchone()[0]

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
```

@app.route("/register-phone", methods=["GET", "POST"])
def register_phone():

```
if "username" not in session:
    return redirect(url_for("login"))

if request.method == "POST":

    owner_name = request.form.get(
        "owner_name",
        ""
    ).strip()

    phone_number = request.form.get(
        "phone_number",
        ""
    ).strip()

    imei = request.form.get(
        "imei",
        ""
    ).strip()

    phone_model = request.form.get(
        "phone_model",
        ""
    ).strip()

    date_registered = request.form.get(
        "date_registered"
    ) or None

    description = request.form.get(
        "description",
        ""
    ).strip()

    if not owner_name or not imei:

        return render_template(
            "register_phone.html",
            error="Owner name and IMEI are required."
        )

    if len(imei) != 15 or not imei.isdigit():

        return render_template(
            "register_phone.html",
            error="IMEI must contain exactly 15 digits."
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

        return redirect(url_for("dashboard"))

    except Exception as e:

        print("Register phone error:", e)

        if conn:
            conn.rollback()

        return render_template(
            "register_phone.html",
            error="Could not register phone. IMEI may already exist."
        )

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()

return render_template("register_phone.html")
```

@app.route("/logout")
def logout():

```
session.clear()

return redirect(url_for("login"))
```

try:
create_tables()

except Exception as e:
print("Startup database error:", e)

if **name** == "**main**":

```
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

