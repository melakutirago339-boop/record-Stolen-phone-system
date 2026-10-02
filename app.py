
```python
from flask import Flask, render_template, request, redirect, url_for, session
import os

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "stolen-phone-system-secret-key"
)


@app.route("/")
def home():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")
        role = request.form.get("role")

        if username == "admin" and password == "admin123":

            session["username"] = username
            session["role"] = role or "admin"

            return redirect(url_for("dashboard"))

        return render_template(
            "login.html",
            error="Invalid username or password"
        )

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():

    if "username" not in session:
        return redirect(url_for("login"))

    return render_template(
        "dashboard.html",
        username=session.get("username"),
        role=session.get("role")
    )


@app.route("/register-phone", methods=["GET", "POST"])
def register_phone():

    if "username" not in session:
        return redirect(url_for("login"))

    message = None

    if request.method == "POST":

        owner_name = request.form.get("owner_name")
        phone_number = request.form.get("phone_number")
        imei1 = request.form.get("imei1")
        imei2 = request.form.get("imei2")
        brand = request.form.get("brand")
        model = request.form.get("model")
        color = request.form.get("color")
        registration_date = request.form.get("registration_date")
        description = request.form.get("description")

        print("PHONE REGISTRATION")
        print("Owner:", owner_name)
        print("Phone:", phone_number)
        print("IMEI 1:", imei1)
        print("IMEI 2:", imei2)
        print("Brand:", brand)
        print("Model:", model)
        print("Color:", color)
        print("Registration Date:", registration_date)
        print("Description:", description)

        message = "Phone information received successfully."

    return render_template(
        "register_phone.html",
        message=message
    )


@app.route("/report-stolen", methods=["GET", "POST"])
def report_stolen():

    if "username" not in session:
        return redirect(url_for("login"))

    message = None

    if request.method == "POST":

        owner_name = request.form.get("owner_name")
        phone_number = request.form.get("phone_number")
        imei = request.form.get("imei")
        brand = request.form.get("brand")
        model = request.form.get("model")
        incident_date = request.form.get("incident_date")
        location = request.form.get("location")
        status = request.form.get("status")
        description = request.form.get("description")

        print("STOLEN PHONE REPORT")
        print("Owner:", owner_name)
        print("Phone:", phone_number)
        print("IMEI:", imei)
        print("Brand:", brand)
        print("Model:", model)
        print("Date:", incident_date)
        print("Location:", location)
        print("Status:", status)
        print("Description:", description)

        message = "Stolen phone report received successfully."

    return render_template(
        "report_stolen.html",
        message=message
    )


@app.route("/search-imei", methods=["GET", "POST"])
def search_imei():

    if "username" not in session:
        return redirect(url_for("login"))

    result = None

    if request.method == "POST":

        imei = request.form.get("imei")

        result = {
            "imei": imei,
            "status": "Not checked yet"
        }

    return render_template(
        "search_imei.html",
        result=result
    )


@app.route("/cases")
def cases():

    if "username" not in session:
        return redirect(url_for("login"))

    return render_template("cases.html")


@app.route("/reports")
def reports():

    if "username" not in session:
        return redirect(url_for("login"))

    return render_template("reports.html")


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
```
