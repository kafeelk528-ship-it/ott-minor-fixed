from flask import Flask, render_template, request, session, redirect, send_file, url_for
import json
import io
from reportlab.pdfgen import canvas
import requests
import os

app = Flask(__name__)
app.secret_key = "ott-secret"

DATA_FILE = "data.json"


# -------------------------
# Data helpers
# -------------------------
def load_data():
    # ensure file exists and has expected structure
    if not os.path.exists(DATA_FILE):
        default = {"plans": [], "coupons": []}
        with open(DATA_FILE, "w") as f:
            json.dump(default, f, indent=4)
        return default

    with open(DATA_FILE, "r") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            data = {"plans": [], "coupons": []}
    # ensure keys exist
    if "plans" not in data:
        data["plans"] = []
    if "coupons" not in data:
        data["coupons"] = []
    return data


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


# -------------------------
# Routes
# -------------------------
@app.route("/")
def index():
    data = load_data()
    return render_template("index.html", data=data)


@app.route("/plans")
def plans():
    data = load_data()
    return render_template("plans.html", data=data)


@app.route("/plan-details")
def plan_details():
    data = load_data()
    plan_id = request.args.get("plan_id", type=int)
    plan = None
    if plan_id is not None:
        plan = next((p for p in data["plans"] if p.get("id") == plan_id), None)
    return render_template("plan-details.html", plan=plan, data=data)


@app.route("/cart")
def cart():
    cart_items = session.get("cart", [])
    total = sum(item["price"] for item in cart_items)
    return render_template("cart.html", cart=cart_items, total=total)


@app.route("/add_to_cart")
def add_to_cart():
    plan_id = request.args.get("plan_id", type=int)
    data = load_data()

    plan = next((p for p in data["plans"] if p["id"] == plan_id), None)
    if not plan:
        return redirect(url_for("index"))

    if "cart" not in session:
        session["cart"] = []

    session["cart"].append(plan)
    session.modified = True

    return redirect(url_for("cart"))


@app.route("/remove_from_cart/<int:index>")
def remove_from_cart(index):
    cart = session.get("cart", [])
    if 0 <= index < len(cart):
        cart.pop(index)
        session["cart"] = cart
        session.modified = True
    return redirect(url_for("cart"))


@app.route("/checkout")
def checkout():
    cart_items = session.get("cart", [])
    total = sum(item["price"] for item in cart_items)
    return render_template("checkout.html", total=total)


@app.route("/submit_utr", methods=["GET", "POST"])
def submit_utr():
    if request.method == "POST":
        utr = request.form.get("utr")
        plan_id = request.form.get("plan_id", type=int) or request.args.get("plan_id", type=int)

        # Telegram notification (optional) - configured via env vars on Render
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        telegram_chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        if telegram_token and telegram_chat and utr:
            try:
                msg = f"New Payment Received!\nUTR: {utr}"
                if plan_id:
                    data = load_data()
                    plan = next((p for p in data["plans"] if p.get("id") == plan_id), None)
                    if plan:
                        msg += f"\nPlan: {plan.get('name')} (₹{plan.get('price')})"
                url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
                requests.post(url, data={"chat_id": telegram_chat, "text": msg}, timeout=5)
            except Exception:
                # don't fail route if telegram fails
                pass

        return render_template("success.html", utr=utr)

    # GET
    return render_template("submit_utr.html")


@app.route("/invoice")
def invoice():
    """
    Generate PDF invoice. Accepts:
    - utr (required)
    - plan_id (optional)
    """
    utr = request.args.get("utr", "")
    plan_id = request.args.get("plan_id", type=int)

    plan = None
    if plan_id:
        data = load_data()
        plan = next((p for p in data["plans"] if p.get("id") == plan_id), None)

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)
    p.setTitle("Invoice")

    # Header
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 800, "INVOICE")

    p.setFont("Helvetica", 11)
    y = 760
    p.drawString(100, y, f"UTR: {utr}")
    y -= 20

    if plan:
        p.drawString(100, y, f"Plan: {plan.get('name')} (₹{plan.get('price')})")
        y -= 20

    p.drawString(100, y, "Payment Status: RECEIVED")
    y -= 30

    p.drawString(100, y, "Service: OTT Platform")
    y -= 20
    p.drawString(100, y, "Thank you for your payment!")
    y -= 30

    # Footer / small note
    p.setFont("Helvetica-Oblique", 9)
    p.drawString(100, y, "This is a system generated invoice. Contact support for queries.")

    p.save()
    buffer.seek(0)

    filename = f"invoice_{utr if utr else 'unknown'}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")


# -------------------------
# ADMIN (simple, file-based)
# -------------------------
@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    # Prefer env var credentials, fallback to admin/admin
    admin_user = os.getenv("ADMIN_USER", "admin")
    admin_pass = os.getenv("ADMIN_PASS", "admin")

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == admin_user and password == admin_pass:
            return redirect(url_for("admin_dashboard"))
        # on failure, re-render login (no flash to keep simple)
    return render_template("admin_login.html")


@app.route("/admin_dashboard")
def admin_dashboard():
    data = load_data()
    return render_template("admin_dashboard.html", data=data)


@app.route("/admin_add", methods=["GET", "POST"])
def admin_add():
    if request.method == "POST":
        name = request.form.get("name")
        price = request.form.get("price")
        desc = request.form.get("desc")
        logo = request.form.get("logo")

        data = load_data()
        plans = data.get("plans", [])
        new_id = max([p.get("id", 0) for p in plans], default=0) + 1

        new_plan = {
            "id": new_id,
            "name": name,
            "price": int(price) if price else price,
            "logo": logo,
            "desc": desc,
            "available": True
        }
        plans.append(new_plan)
        data["plans"] = plans
        save_data(data)
        return redirect(url_for("admin_dashboard"))

    return render_template("admin-add.html")


@app.route("/admin_edit/<int:id>", methods=["GET", "POST"])
def admin_edit(id):
    data = load_data()
    plans = data.get("plans", [])
    plan = next((p for p in plans if p.get("id") == id), None)
    if not plan:
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        plan["name"] = request.form.get("name")
        plan["price"] = int(request.form.get("price")) if request.form.get("price") else plan.get("price")
        plan["desc"] = request.form.get("desc")
        plan["logo"] = request.form.get("logo")
        save_data(data)
        return redirect(url_for("admin_dashboard"))

    # adapt template expecting 'product' variable (older templates)
    return render_template("admin_edit.html", product=plan)


@app.route("/admin_delete/<int:id>")
def admin_delete(id):
    data = load_data()
    data["plans"] = [p for p in data.get("plans", []) if p.get("id") != id]
    save_data(data)
    return redirect(url_for("admin_dashboard"))


# -------------------------
# CONTACT
# -------------------------
@app.route("/contact")
def contact():
    return render_template("contact.html")


# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    # Use host 0.0.0.0 for Render / external access
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)
