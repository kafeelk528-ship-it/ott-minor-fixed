from flask import Flask, render_template, request, redirect, send_file, url_for
import json
import io
from reportlab.pdfgen import canvas
import requests
import os

app = Flask(__name__)


# ============================================================
# LOAD MOVIE / PRODUCT DATA
# ============================================================
def load_data():
    with open("data.json", "r") as f:
        return json.load(f)


def save_data(data):
    with open("data.json", "w") as f:
        json.dump(data, f, indent=4)


# ============================================================
# HOME PAGE
# ============================================================
@app.route("/")
def index():
    data = load_data()
    return render_template("index.html", data=data)


# ============================================================
# PLANS PAGE (Fix for your BASE.HTML error)
# ============================================================
@app.route("/plans")
def plans():
    return render_template("plans.html")


@app.route("/plan-details")
def plan_details():
    return render_template("plan-details.html")


# ============================================================
# CART PAGE
# ============================================================
@app.route("/cart")
def cart():
    return render_template("cart.html")


# ============================================================
# CHECKOUT PAGE
# ============================================================
@app.route("/checkout")
def checkout():
    return render_template("checkout.html")


# ============================================================
# SUBMIT UTR PAGE (form)
# ============================================================
@app.route("/submit_utr", methods=["GET", "POST"])
def submit_utr():
    if request.method == "POST":
        utr = request.form.get("utr")

        # TELEGRAM NOTIFICATION
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

        if telegram_token and chat_id:
            message = f"New Payment Received!\nUTR: {utr}"
            url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
            requests.post(url, data={"chat_id": chat_id, "text": message})

        return render_template("success.html", utr=utr)

    return render_template("submit_utr.html")


# ============================================================
# PDF INVOICE GENERATION
# ============================================================
@app.route("/invoice")
def invoice():
    utr = request.args.get("utr")

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)

    p.setTitle("Invoice")

    # Heading
    p.drawString(100, 780, "INVOICE")

    # Invoice Details
    p.drawString(100, 740, f"UTR Number: {utr}")
    p.drawString(100, 720, "Payment Status: RECEIVED")
    p.drawString(100, 700, "Service: OTT Subscription / Movie Purchase")
    p.drawString(100, 660, "Thank you for your payment!")

    p.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"invoice_{utr}.pdf",
        mimetype="application/pdf"
    )


# ============================================================
# ADMIN LOGIN PAGE
# ============================================================
@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        user = request.form.get("username")
        pwd = request.form.get("password")

        if user == "admin" and pwd == "admin":
            return redirect("/admin_dashboard")

    return render_template("admin_login.html")


# ============================================================
# ADMIN DASHBOARD
# ============================================================
@app.route("/admin_dashboard")
def admin_dashboard():
    data = load_data()
    return render_template("admin_dashboard.html", data=data)


# ============================================================
# ADMIN – ADD PRODUCT
# ============================================================
@app.route("/admin_add", methods=["GET", "POST"])
def admin_add():
    if request.method == "POST":
        name = request.form.get("name")
        price = request.form.get("price")
        image = request.form.get("image")

        data = load_data()
        new_id = data[-1]["id"] + 1 if data else 1

        data.append({
            "id": new_id,
            "name": name,
            "price": price,
            "image": image
        })

        save_data(data)

        return redirect("/admin_dashboard")

    return render_template("admin-add.html")


# ============================================================
# ADMIN – EDIT PRODUCT
# ============================================================
@app.route("/admin_edit/<int:id>", methods=["GET", "POST"])
def admin_edit(id):
    data = load_data()
    product = next((x for x in data if x["id"] == id), None)

    if request.method == "POST":
        product["name"] = request.form.get("name")
        product["price"] = request.form.get("price")
        product["image"] = request.form.get("image")

        save_data(data)
        return redirect("/admin_dashboard")

    return render_template("admin_edit.html", product=product)


# ============================================================
# ADMIN – DELETE PRODUCT
# ============================================================
@app.route("/admin_delete/<int:id>")
def admin_delete(id):
    data = load_data()
    data = [x for x in data if x["id"] != id]
    save_data(data)
    return redirect("/admin_dashboard")


# ============================================================
# CONTACT PAGE
# ============================================================
@app.route("/contact")
def contact():
    return render_template("contact.html")


# ============================================================
# RUN APP
# ============================================================
if __name__ == "__main__":
    app.run(debug=True)
