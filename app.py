# app.py
import os
import json
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, session, flash, abort
import requests
from dotenv import load_dotenv

# Load local .env
load_dotenv()

# Config
SECRET_KEY = os.getenv("SECRET_KEY", "dev-key")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "12345")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
DATA_FILE = "data.json"

# Flask App
app = Flask(__name__)
app.secret_key = SECRET_KEY

# ---------- INITIAL DATA ----------
DEFAULT_PLANS = [
    {"id": 1, "name": "Netflix Premium", "price": 199, "logo": "netflix.png", "desc": "4K UHD • 4 Screens • 30 Days", "available": True},
    {"id": 2, "name": "Amazon Prime Video", "price": 149, "logo": "prime.png", "desc": "Full HD • 30 Days", "available": True},
    {"id": 3, "name": "Disney+ Hotstar", "price": 299, "logo": "hotstar.png", "desc": "Sports + Entertainment", "available": True},
    {"id": 4, "name": "Sony LIV", "price": 129, "logo": "sonyliv.png", "desc": "Full HD", "available": True},
    {"id": 5, "name": "Zee5 Premium", "price": 99, "logo": "zee5.png", "desc": "Regional Content", "available": True},
]

def init_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({"plans": DEFAULT_PLANS}, f, indent=2)

def load_data():
    init_data()
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_plans():
    return load_data().get("plans", [])

def get_plan_by_id(pid):
    for p in get_plans():
        if p["id"] == pid:
            return p
    return None

# ---------- Telegram Notify ----------
def notify_owner_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False, "Telegram not configured"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=10)
        return (r.status_code == 200), r.text
    except Exception as e:
        return False, str(e)

# ---------- ROUTES ----------
@app.route("/")
def home():
    return render_template("index.html", plans=get_plans())

@app.route("/plans")
def plans_page():
    return render_template("plans.html", plans=get_plans())

@app.route("/plan/<int:pid>")
def plan_details(pid):
    p = get_plan_by_id(pid)
    if not p:
        abort(404)
    return render_template("plan-details.html", plan=p)

# ---------- CART ----------
@app.route("/add-to-cart/<int:pid>")
def add_to_cart(pid):
    plan = get_plan_by_id(pid)
    if not plan:
        flash("Plan not found", "error")
        return redirect(url_for("home"))

    cart = session.get("cart", [])
    if pid not in cart:
        cart.append(pid)
    session["cart"] = cart
    session.modified = True

    return redirect(url_for("cart_page"))

@app.route("/cart")
def cart_page():
    ids = session.get("cart", [])
    cart_items = [get_plan_by_id(i) for i in ids if get_plan_by_id(i)]
    total = sum(p["price"] for p in cart_items)
    return render_template("cart.html", cart=cart_items, total=total)

@app.route("/cart/remove/<int:pid>")
def cart_remove(pid):
    cart = session.get("cart", [])
    if pid in cart:
        cart.remove(pid)
    session["cart"] = cart
    session.modified = True
    return redirect(url_for("cart_page"))

# ---------- CHECKOUT ----------
@app.route("/checkout")
def checkout():
    cart_ids = session.get("cart", [])

    if not cart_ids:
        flash("Cart is empty.", "error")
        return redirect(url_for("home"))

    cart_items = [get_plan_by_id(pid) for pid in cart_ids if get_plan_by_id(pid)]

    if not cart_items:
        flash("Invalid cart items.", "error")
        return redirect(url_for("home"))

    total = sum(item["price"] for item in cart_items)

    return render_template(
        "checkout.html",
        cart=cart_items,
        total=total,
        qr_url=url_for("static", filename="img/qr.png")
    )

# ---------- UTR SUBMIT ----------
@app.route("/submit_utr", methods=["POST"])
def submit_utr():
    name = request.form.get("name", "")
    phone = request.form.get("phone", "")
    utr = request.form.get("utr", "")
    email = request.form.get("email", "")

    cart_ids = session.get("cart", [])
    if not cart_ids:
        flash("Cart empty", "error")
        return redirect(url_for("home"))

    cart_items = [get_plan_by_id(pid) for pid in cart_ids if get_plan_by_id(pid)]

    total = sum(item["price"] for item in cart_items)
    products = ", ".join(p["name"] for p in cart_items)

    message = (
        f"New Order\n"
        f"Name: {name}\nPhone: {phone}\nUTR: {utr}\n"
        f"Amount: ₹{total}\nProducts: {products}\n"
        f"Time: {datetime.now().isoformat()}"
    )

    notify_owner_telegram(message)

    session.pop("cart", None)

    return render_template("submit_utr_result.html", products=products, total=total)

# ---------- ADMIN ----------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")
        if u == ADMIN_USER and p == ADMIN_PASS:
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Invalid login", "error")
    return render_template("admin_login.html")

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*a, **kw):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return f(*a, **kw)
    return wrapper

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    return render_template("admin_dashboard.html", plans=get_plans())

@app.route("/admin/edit/<int:pid>", methods=["GET", "POST"])
@admin_required
def admin_edit(pid):
    data = load_data()
    plans = data["plans"]

    plan = next((p for p in plans if p["id"] == pid), None)
    if not plan:
        abort(404)

    if request.method == "POST":
        plan["name"] = request.form.get("name")
        plan["price"] = int(request.form.get("price"))
        plan["desc"] = request.form.get("desc")
        plan["logo"] = request.form.get("logo")
        plan["available"] = request.form.get("available") == "on"
        save_data(data)
        flash("Updated", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("admin_edit.html", plan=plan)

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("home"))

# ---------- START ----------
if __name__ == "__main__":
    init_data()
    app.run(debug=True)
