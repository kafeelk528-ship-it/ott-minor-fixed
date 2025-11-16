# app.py
import os
import json
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, session, flash, abort
import requests
from dotenv import load_dotenv

# load local .env in dev
load_dotenv()

# Config from env
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "12345")
YOUR_DOMAIN = os.getenv("YOUR_DOMAIN", "http://localhost:5000")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or 587)
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER or "noreply@example.com")

DATA_FILE = "data.json"

app = Flask(__name__)
app.secret_key = SECRET_KEY

# --------------------------
# Data persistence (data.json)
# --------------------------
DEFAULT_PLANS = [
    {"id": 1, "name": "Netflix Premium", "price": 199, "logo": "netflix.png", "desc": "4K UHD • 4 Screens • 30 Days", "available": True},
    {"id": 2, "name": "Amazon Prime Video", "price": 149, "logo": "prime.png", "desc": "Full HD • All Devices • 30 Days", "available": True},
    {"id": 3, "name": "Disney+ Hotstar Premium", "price": 299, "logo": "hotstar.png", "desc": "Sports + Movies", "available": True},
    {"id": 4, "name": "Sony LIV Premium", "price": 129, "logo": "sonyliv.png", "desc": "Full HD • Originals", "available": True},
    {"id": 5, "name": "Zee5 Premium", "price": 99, "logo": "zee5.png", "desc": "Regional Content", "available": True},
]

DEFAULT_COUPONS = [
    # example: {"code": "DEMO10", "type":"percent", "amount":10, "expires_at": None}
]

def init_data():
    if not os.path.exists(DATA_FILE):
        data = {"plans": DEFAULT_PLANS, "coupons": DEFAULT_COUPONS}
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

def load_data():
    init_data()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# --------------------------
# Helpers
# --------------------------
def get_plans():
    data = load_data()
    return data.get("plans", [])

def get_plan_by_id(pid):
    for p in get_plans():
        if p["id"] == int(pid):
            return p
    return None

def apply_coupon_to_amount(code, amount):
    if not code:
        return amount, None
    data = load_data()
    for c in data.get("coupons", []):
        if c.get("code","").upper() == code.upper():
            # expiry
            if c.get("expires_at"):
                expires = datetime.fromisoformat(c["expires_at"])
                if datetime.utcnow() > expires:
                    return amount, "EXPIRED"
            if c["type"] == "flat":
                new = max(0, amount - c["amount"])
            else:
                new = max(0, int(amount * (100 - c["amount"]) / 100))
            return new, None
    return amount, "INVALID"

def notify_owner_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        app.logger.info("Telegram not configured.")
        return False, "telegram-not-configured"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code == 200:
            return True, r.json()
        else:
            return False, r.text
    except Exception as e:
        return False, str(e)

# --------------------------
# Routes - Public
# --------------------------
@app.route("/")
def home():
    plans = get_plans()
    return render_template("index.html", plans=plans)

@app.route("/plans")
def plans_page():
    plans = get_plans()
    return render_template("plans.html", plans=plans)

@app.route("/plan/<int:plan_id>")
def plan_details(plan_id):
    p = get_plan_by_id(plan_id)
    if not p:
        abort(404)
    return render_template("plan-details.html", plan=p)

# Cart & Buy
@app.route("/add-to-cart/<int:plan_id>")
def add_to_cart(plan_id):
    p = get_plan_by_id(plan_id)
    if not p:
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
    # set cart to only this plan and go to checkout
    p = get_plan_by_id(plan_id)
    if not p:
        flash("Plan not found.", "error")
        return redirect(url_for("plans_page"))
    session["cart"] = [plan_id]
    session.modified = True
    return redirect(url_for("checkout"))

@app.route("/cart")
def cart_page():
    cart_ids = session.get("cart", [])
    cart_items = [get_plan_by_id(pid) for pid in cart_ids if get_plan_by_id(pid)]
    total = sum(item["price"] for item in cart_items)
    return render_template("cart.html", cart=cart_items, total=total)

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
    cart_items = [get_plan_by_id(pid) for pid in cart_ids if get_plan_by_id(pid)]
    total = sum(item["price"] for item in cart_items)
    # Sample QR shown from static/img/qr.png
    return render_template("checkout.html", cart=cart_items, total=total, qr_url=url_for("static", filename="img/qr.png"))

@app.route("/submit_utr", methods=["POST"])
def submit_utr():
    # Form fields: name, phone, utr, email (optional)
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    utr = request.form.get("utr", "").strip()
    email = request.form.get("email", "").strip()
    cart_ids = session.get("cart", [])
    cart_items = [get_plan_by_id(pid) for pid in cart_ids if get_plan_by_id(pid)]
    total = sum(item["price"] for item in cart_items)

    if not utr or not phone:
        flash("Please provide UTR and phone number.", "error")
        return redirect(url_for("checkout"))

    # Build message
    products = ", ".join([p["name"] for p in cart_items]) or "No items"
    message = f"New UTR Submission\nName: {name}\nPhone: {phone}\nEmail: {email}\nUTR: {utr}\nAmount: ₹{total}\nProducts: {products}\nTime: {datetime.utcnow().isoformat()}"

    ok, resp = notify_owner_telegram(message)
    app.logger.info("Telegram notify: %s %s", ok, resp)

    # Optionally send email (if SMTP configured) - minimal attempt using smtplib
    email_sent = False
    email_err = None
    if SMTP_HOST and SMTP_USER and SMTP_PASS and email:
        try:
            import smtplib
            from email.message import EmailMessage
            em = EmailMessage()
            em["From"] = FROM_EMAIL
            em["To"] = email
            em["Subject"] = "Payment received - pending verification"
            em.set_content(f"Hi {name},\n\nWe received your payment UTR: {utr} for amount ₹{total}.\nWe will verify and activate your plan.\n\nThanks.")
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
                smtp.starttls()
                smtp.login(SMTP_USER, SMTP_PASS)
                smtp.send_message(em)
                email_sent = True
        except Exception as e:
            email_err = str(e)
            app.logger.exception("Sending mail failed")

    # Clear cart for demo. In real system keep until admin verifies.
    session.pop("cart", None)

    return render_template("submit_utr_result.html",
                           ok=ok, telegram_resp=resp, email_sent=email_sent, email_err=email_err)

# Coupons
@app.route("/apply_coupon", methods=["POST"])
def apply_coupon():
    code = request.form.get("coupon", "").strip()
    cart_ids = session.get("cart", [])
    cart_items = [get_plan_by_id(pid) for pid in cart_ids if get_plan_by_id(pid)]
    total = sum(item["price"] for item in cart_items)
    new_total, err = apply_coupon_to_amount(code, total)
    if err:
        flash(f"Coupon: {err}", "error")
    else:
        session["applied_coupon"] = code.upper()
        flash(f"Coupon applied. New total: ₹{new_total}", "success")
    return redirect(url_for("cart_page"))

@app.route("/contact")
def contact_page():
    return render_template("contact.html")

# --------------------------
# Admin (simple session-based)
# --------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USER and password == ADMIN_PASS:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        else:
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
    plans = get_plans()
    return render_template("admin_dashboard.html", plans=plans)

@app.route("/admin/edit/<int:plan_id>", methods=["GET", "POST"])
@admin_required
def admin_edit(plan_id):
    data = load_data()
    plans = data.get("plans", [])
    plan = None
    for p in plans:
        if p["id"] == plan_id:
            plan = p
            break
    if not plan:
        abort(404)
    if request.method == "POST":
        # update values
        plan["name"] = request.form.get("name", plan["name"]).strip()
        plan["price"] = int(request.form.get("price", plan["price"]))
        plan["desc"] = request.form.get("desc", plan.get("desc",""))
        plan["logo"] = request.form.get("logo", plan.get("logo",""))
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
# Static file for health
# --------------------------
@app.route("/_debug/telegram-test")
def debug_telegram():
    ok, resp = notify_owner_telegram("Test message from your app at " + datetime.utcnow().isoformat())
    return {"ok": ok, "resp": str(resp)}

# --------------------------
# Start
# --------------------------
if __name__ == "__main__":
    init_data()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=(os.getenv("FLASK_ENV","development")!="production"))
