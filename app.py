from flask import Flask, render_template, request, redirect, url_for, session
import os

app = Flask(__name__)

# Secret key
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "change-this-secret-key"
)


# =========================
# HOME
# =========================
@app.route("/")
def home():
    return redirect(url_for("login"))


# =========================
# LOGIN
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")
        role = request.form.get("role")

        # Temporary login
        # We will connect this to PostgreSQL later.
        if username and password and role:

            session["username"] = username
            session["role"] = role

            return redirect(url_for("dashboard"))

        return render_template(
            "login.html",
            error="Please enter all required information."
        )

    return render_template("login.html")


# =========================
# DASHBOARD
# =========================
@app.route("/dashboard")
def dashboard():

    if "username" not in session:
        return redirect(url_for("login"))

    return render_template(
        "dashboard.html",
        username=session.get("username"),
        role=session.get("role")
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
        imei1 = request.form.get("imei1")
        imei2 = request.form.get("imei2")
        brand = request.form.get("brand")
        model = request.form.get("model")
        color = request.form.get("color")

        # Database saving will be added next.
        print("Phone Registration:")
        print(owner_name, phone_number, imei1, imei2, brand, model, color)

        return redirect(url_for("dashboard"))

    return render_template("register_phone.html")


# =========================
# REPORT STOLEN PHONE
# =========================
@app.route("/report-stolen", methods=["GET", "POST"])
def report_stolen():

    if "username" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        imei = request.form.get("imei")
        owner_name = request.form.get("owner_name")
        phone_number = request.form.get("phone_number")
        location = request.form.get("location")
        description = request.form.get("description")

        # Database saving will be added next.
        print("Stolen Phone Report:")
        print(imei, owner_name, phone_number, location, description)

        return redirect(url_for("dashboard"))

    return render_template("report_stolen.html")


# =========================
# SEARCH IMEI
# =========================
@app.route("/search-imei", methods=["GET", "POST"])
def search_imei():

    if "username" not in session:
        return redirect(url_for("login"))

    result = None

    if request.method == "POST":

        imei = request.form.get("imei")

        # PostgreSQL search will be added next.
        result = {
            "imei": imei,
            "status": "Not Found"
        }

    return render_template(
        "search_imei.html",
        result=result
    )


# =========================
# CASE MANAGEMENT
# =========================
@app.route("/cases")
def cases():

    if "username" not in session:
        return redirect(url_for("login"))

    return render_template("cases.html")


# =========================
# REPORTS
# =========================
@app.route("/reports")
def reports():

    if "username" not in session:
        return redirect(url_for("login"))

    return render_template("reports.html")


# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# =========================
# RUN APPLICATION
# =========================
if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
