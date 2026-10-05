from flask import Flask, render_template, request, redirect, session, url_for
import os
import psycopg2

app = Flask(**name**)

app.secret_key = os.environ.get(
"SECRET_KEY",
"change-this-secret-key"
)

# =========================================================

# DATABASE CONNECTION

# =========================================================

def get_db_connection():
database_url = os.environ.get("DATABASE_URL")

```
if not database_url:
    raise RuntimeError("DATABASE_URL is not configured")

return psycopg2.connect(database_url)
```

# =========================================================

# CREATE DATABASE TABLES

# =========================================================

def create_tables():
conn = None
cur = None

```
try:
    conn = get_db_connection()
    cur = conn.cursor()

    # Registered phones
    cur.execute("""
        CREATE TABLE IF NOT EXISTS registered_phones (
            id SERIAL PRIMARY KEY,
            owner_name VARCHAR(100) NOT NULL,
            phone_number VARCHAR(50),
            imei VARCHAR(50) UNIQUE NOT NULL,
            imei2 VARCHAR(50),
            phone_brand VARCHAR(50),
            phone_model VARCHAR(100),
            phone_color VARCHAR(50),
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
```

# =========================================================

# HOME

# =========================================================

@app.route("/")
def home():
return redirect(url_for("login"))

# =========================================================

# LOGIN

# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

```
if request.method == "POST":

    username = request.form.get(
        "username",
        ""
    ).strip()

    password = request.form.get(
        "password",
        ""
    ).strip()

    role = request.form.get(
        "role",
        "admin"
    ).strip()

    if username == "admin" and password == "admin":

        session["username"] = username
        session["role"] = role

        return redirect(
            url_for("dashboard")
        )

    return render_template(
        "login.html",
        error="Invalid username or password ❌"
    )

return render_template("login.html")
```

# =========================================================

# DASHBOARD

# =========================================================

@app.route("/dashboard")
def dashboard():

```
if "username" not in session:
    return redirect(
        url_for("login")
    )

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

    print(
        "Dashboard database error:",
        e
    )

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

# =========================================================

# REGISTER PHONE

# =========================================================

@app.route(
"/register-phone",
methods=["GET", "POST"]
)
def register_phone():

```
if "username" not in session:
    return redirect(
        url_for("login")
    )

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

    imei2 = request.form.get(
        "imei2",
        ""
    ).strip()

    phone_brand = request.form.get(
        "phone_brand",
        ""
    ).strip()

    phone_model = request.form.get(
        "phone_model",
        ""
    ).strip()

    phone_color = request.form.get(
        "phone_color",
        ""
    ).strip()

    date_registered = request.form.get(
        "date_registered",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

    if not owner_name or not imei:
        return render_template(
            "register_phone.html",
            error="Owner name and IMEI are required ❌"
        )

    if len(imei) != 15 or not imei.isdigit():
        return render_template(
            "register_phone.html",
            error="IMEI 1 must contain exactly 15 digits ❌"
        )

    if imei2:
        if len(imei2) != 15 or not imei2.isdigit():
            return render_template(
                "register_phone.html",
                error="IMEI 2 must contain exactly 15 digits ❌"
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
                imei2,
                phone_brand,
                phone_model,
                phone_color,
                date_registered,
                description
            )
            VALUES
            (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
        """, (
            owner_name,
            phone_number,
            imei,
            imei2 or None,
            phone_brand,
            phone_model,
            phone_color,
            date_registered or None,
            description
        ))

        conn.commit()

        return render_template(
            "register_phone.html",
            success="Phone registered successfully ✅"
        )

    except psycopg2.errors.UniqueViolation:

        if conn:
            conn.rollback()

        return render_template(
            "register_phone.html",
            error="This IMEI is already registered ❌"
        )

    except Exception as e:

        if conn:
            conn.rollback()

        print(
            "Register phone error:",
            e
        )

        return render_template(
            "register_phone.html",
            error="Database error ❌"
        )

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()

return render_template(
    "register_phone.html"
)
```

# =========================================================

# REPORT STOLEN PHONE

# =========================================================

@app.route(
"/report-stolen",
methods=["GET", "POST"]
)
def report_stolen():

```
if "username" not in session:
    return redirect(
        url_for("login")
    )

if request.method == "POST":

    owner_name = request.form.get(
        "owner_name",
        ""
    ).strip()

    phone_number = request.form.get(
        "phone_number",
        ""
    ).strip()

    phone_model = request.form.get(
        "phone_model",
        ""
    ).strip()

    imei = request.form.get(
        "imei",
        ""
    ).strip()

    stolen_date = request.form.get(
        "stolen_date",
        ""
    ).strip()

    stolen_location = request.form.get(
        "stolen_location",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

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
                phone_model,
                imei,
                stolen_date,
                stolen_location,
                description
            )
            VALUES
            (
                %s, %s, %s, %s,
                %s, %s, %s
            )
        """, (
            owner_name,
            phone_number,
            phone_model,
            imei,
            stolen_date or None,
            stolen_location,
            description
        ))

        conn.commit()

        return render_template(
            "report_stolen.html",
            success="Stolen phone report saved successfully ✅"
        )

    except Exception as e:

        if conn:
            conn.rollback()

        print(
            "Report stolen error:",
            e
        )

        return render_template(
            "report_stolen.html",
            error="Database error ❌"
        )

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()

return render_template(
    "report_stolen.html"
)
```

# =========================================================

# SEARCH IMEI

# =========================================================

@app.route(
"/search-imei",
methods=["GET", "POST"]
)
def search_imei():

```
if "username" not in session:
    return redirect(
        url_for("login")
    )

phone = None
error = None

if request.method == "POST":

    imei = request.form.get(
        "imei",
        ""
    ).strip()

    conn = None
    cur = None

    try:

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                id,
                owner_name,
                phone_number,
                imei,
                phone_model,
                phone_brand,
                phone_color,
                date_registered,
                status,
                description
            FROM registered_phones
            WHERE imei = %s
        """, (imei,))

        phone = cur.fetchone()

        if phone is None:
            error = "No registered phone found with this IMEI ❌"

    except Exception as e:

        print(
            "Search IMEI error:",
            e
        )

        error = "Database error ❌"

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()

return render_template(
    "search_imei.html",
    phone=phone,
    error=error
)
```

# =========================================================

# CASE MANAGEMENT

# =========================================================

@app.route("/cases")
def cases():

```
if "username" not in session:
    return redirect(
        url_for("login")
    )

cases_data = []

conn = None
cur = None

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
        ORDER BY id DESC
    """)

    cases_data = cur.fetchall()

except Exception as e:

    print(
        "Cases database error:",
        e
    )

finally:

    if cur:
        cur.close()

    if conn:
        conn.close()

return render_template(
    "cases.html",
    cases=cases_data
)
```

# =========================================================

# REPORTS

# =========================================================

@app.route("/reports")
def reports():

```
if "username" not in session:
    return redirect(
        url_for("login")
    )

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

    print(
        "Reports database error:",
        e
    )

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
    active_cases=active_cases
)
```

# =========================================================

# LOGOUT

# =========================================================

@app.route("/logout")
def logout():

```
session.clear()

return redirect(
    url_for("login")
)
```

# =========================================================

# DATABASE INITIALIZATION

# =========================================================

try:

```
create_tables()
```

except Exception as e:

```
print(
    "Startup database error:",
    e
)
```

# =========================================================

# START APP

# =========================================================

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
```


