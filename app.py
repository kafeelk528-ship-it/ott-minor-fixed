# app.py - Final stable version
import os
import json
from datetime import datetime
from flask import (
    Flask, render_template, redirect, url_for, request,
    session, flash, abort
)
import requests
from dotenv import load_dotenv
from reportlab.pdfgen import canvas

# Load .env (local dev)
load_dotenv()

# --------------------------
# Config / Env
# --------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "12345")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

DATA_FILE = "data.json"
INVOICE_DIR = os.path.join("static", "invoices")
QR_STATIC = os.path.join("static", "img", "qr.png")

# --------------------------
# Flask app (must be defined BEFORE routes)
# --------------------------
app = Flask(__name__)
app.secret_key = SECRET_KEY

# --------------------------
# Default data
# --------------------------
DEFAULT_PLANS = [
    {"id": 1, "name": "Netflix Premium", "price": 199, "logo": "netflix.png", "desc": "4K UHD • 4 Screens • 30 Days", "available": True},
    {"id": 2, "name": "Amazon Prime Video", "price": 149, "logo": "prime.png", "desc": "Full HD • All Devices • 30 Days", "available": True},
    {"id": 3, "name": "Disney+ Hotstar Premium", "price": 299, "logo": "hotstar.png", "desc": "Sports + Movies", "available": True},
    {"id": 4, "name": "Sony LIV Premium", "price": 129, "logo": "sonyliv.png", "desc": "Full HD • Originals", "available": True},
    {"id": 5, "name": "Zee5 Premium", "price": 99, "logo": "zee5.png", "desc": "Regional Content", "available": True},
]

# --------------------------
# Data helpers
# --------------------------
def init_data():
    if not os.path.exists(DATA_FILE):
        data = {"plans": DEFAULT_PLANS}
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    # ensure invoice dir exists
    if not os.path.exists(INVOICE_DIR):
        os.makedirs(INVOICE_DIR, exist_ok=True)

def load_data():
    init_data()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def get_plans():
    return load_data().get("plans", [])

def get_plan_by_id(pid):
    for p in get_plans():
        if int(p.get("id")) == int(pid):
            return p
    return None

# --------------------------
# Telegram notify helper
# --------------------------
def notify_owner_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        app.logger.info("Telegram not configured (missing env vars).")
        return False, "telegram-not-configured"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code == 200:
            return True, r.json()
        return False, r.text
    except Exception as e:
        app.logger.exception("Telegram notify failed")
        return False, str(e)

# --------------------------
# PDF invoice generator
# --------------------------
def generate_invoice(name, phone, utr, total, products):
    # safe file name
    safe_utr = "".join(ch for ch in (utr or "no_utr") if ch.isalnum() or ch in "-_")
    filename = f"invoice_{safe_utr}_{int(datetime.utcnow().timestamp())}.pdf"
    out_path = os.path.join(INVOICE_DIR, filename)

    c = canvas.Canvas(out_path)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 800, "OTT STORE — PAYMENT INVOICE")
    c.setFont("Helvetica", 12)
    c.drawString(50, 770, f"Name: {name or '—'}")
    c.drawString(50, 750, f"Phone: {phone or '—'}")
    c.drawString(50, 730, f"UTR: {utr or '—'}")
    c.drawString(50, 710, f"Amount: ₹{total}")
    c.drawString(50, 690, f"Products: {products}")
    c.drawString(50, 670, f"Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    c.line(45, 660, 550, 660)
    c.drawString(50, 640, "Thank you for your purchase.")
    c.showPage()
    c.save()

    return filename

# --------------------------
# Routes - Public
# --------------------------
@app.route("/")
def home():
    return render_template("index.html", plans=get_plans())

@app.route("/plans")
def plans_page():
    return render_template("plans.html", plans=get_plans())

@app.route("/plan/<int:plan_id>")
def plan_details(plan_id):
    p = get_plan_by_id(plan_id)
    if not p:
        abort(404)
    return render_template("plan-details.html", plan=p)

# --------------------------
# Cart & checkout flows
# --------------------------
@app.route("/add-to-cart/<int:plan_id>")
def add_to_cart(plan_id):
    plan = get_plan_by_id(plan_id)
    if not plan:
        flash("Plan not found.", "error")
        return redirect(url_for("plans_page"))

    cart = session.get("cart", [])
    if plan_id not in cart:
        cart.append(plan_id)
    session["cart"] = cart
    session.modified = True
    return redirect(url_for("cart_page"))

@app.route("/buy-now/<int:plan_id>")
def buy_now(plan_id):
    plan = get_plan_by_id(plan_id)
    if not plan:
        flash("Plan not found.", "error")
        return redirect(url_for("plans_page"))
    session["cart"] = [plan_id]
    session.modified = True
    return redirect(url_for("checkout"))

@app.route("/cart")
def cart_page():
    cart_ids = session.get("cart", [])
    items = [get_plan_by_id(pid) for pid in cart_ids if get_plan_by_id(pid)]
    total = sum(item["price"] for item in items if item)
    return render_template("cart.html", cart=items, total=total)

@app.route("/cart/remove/<int:plan_id>")
def remove_cart(plan_id):
    cart = session.get("cart", [])
    if plan_id in cart:
        cart.remove(plan_id)
    session["cart"] = cart
    session.modified = True
    return redirect(url_for("cart_page"))

@app.route("/checkout")
def checkout():
    cart_ids = session.get("cart", [])
    items = [get_plan_by_id(pid) for pid in cart_ids if get_plan_by_id(pid)]
    total = sum(i["price"] for i in items if i)
    qr_url = url_for("static", filename="img/qr.png")
    return render_template("checkout.html", cart=items, total=total, qr_url=qr_url)

@app.route("/submit_utr", methods=["POST"])
def submit_utr():
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    utr = request.form.get("utr", "").strip()
    email = request.form.get("email", "").strip()

    cart_ids = session.get("cart", [])
    items = [get_plan_by_id(pid) for pid in cart_ids if get_plan_by_id(pid)]
    total = sum(i["price"] for i in items if i)
    products = ", ".join(i["name"] for i in items if i) or "No items"

    if not utr or not phone:
        flash("Please provide UTR and phone.", "error")
        return redirect(url_for("checkout"))

    # Notify via Telegram
    message = (
        f"New UTR Submission\n"
        f"Name: {name}\nPhone: {phone}\nEmail: {email}\nUTR: {utr}\n"
        f"Amount: ₹{total}\nProducts: {products}\nTime: {datetime.utcnow().isoformat()}"
    )
    ok, resp = notify_owner_telegram(message)
    app.logger.info("Telegram notify result: %s %s", ok, resp)

    # Generate invoice PDF
    invoice_filename = generate_invoice(name, phone, utr, total, products)
    invoice_url = url_for("static", filename=f"invoices/{invoice_filename}")

    # For demo: clear cart after UTR submit (you can change behavior)
    session.pop("cart", None)

    return render_template("submit_utr_result.html", invoice_url=invoice_url, telegram_ok=ok, telegram_resp=resp)

# --------------------------
# Admin (session-based, simple)
# --------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("username") == ADMIN_USER and request.form.get("password") == ADMIN_PASS:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Invalid credentials", "error")
    return render_template("admin_login.html")

def admin_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return fn(*a, **kw)
    return wrapper

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    return render_template("admin_dashboard.html", plans=get_plans())

@app.route("/admin/edit/<int:plan_id>", methods=["GET", "POST"])
@admin_required
def admin_edit(plan_id):
    data = load_data()
    plans = data.get("plans", [])
    plan = next((p for p in plans if int(p["id"]) == int(plan_id)), None)
    if not plan:
        abort(404)

    if request.method == "POST":
        # update fields (simple)
        plan["name"] = request.form.get("name", plan["name"])
        plan["price"] = int(request.form.get("price", plan["price"]))
        plan["desc"] = request.form.get("desc", plan.get("desc", ""))
        plan["logo"] = request.form.get("logo", plan.get("logo", ""))
        plan["available"] = True if request.form.get("available") == "on" else False
        save_data(data)
        flash("Plan updated", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("admin_edit.html", plan=plan)

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("home"))

# --------------------------
# Debug endpoint to test telegram
# --------------------------
@app.route("/_debug/telegram-test")
def debug_telegram():
    ok, resp = notify_owner_telegram("Test message from app at " + datetime.utcnow().isoformat())
    return {"ok": ok, "resp": str(resp)}

# --------------------------
# App start
# --------------------------
if __name__ == "__main__":
    init_data()
    # port from env if provided
    port = int(os.getenv("PORT", "5000"))
    debug_flag = os.getenv("FLASK_ENV", "development") != "production"
    app.run(host="0.0.0.0", port=port, debug=debug_flag)
