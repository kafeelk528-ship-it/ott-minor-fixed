import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, session, url_for, flash, send_from_directory
import requests

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

# SECRET - pick from env or fallback (change before production)
app.secret_key = os.environ.get("SECRET_KEY", "dev_secret_please_change")

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

# ---------------- DB helpers ----------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db_and_seed():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            image TEXT NOT NULL
        )
    """)
    conn.commit()

    # seed only if empty
    cur.execute("SELECT COUNT(1) as cnt FROM products")
    if cur.fetchone()["cnt"] == 0:
        defaults = [
            ("Netflix Premium", 199, "netflix.png"),
            ("Amazon Prime Video", 149, "prime.png"),
            ("Disney+ Hotstar", 299, "hotstar.png"),
            ("Sony LIV Premium", 129, "sonyliv.png"),
            ("Zee5 Premium", 99, "zee5.png"),
        ]
        cur.executemany("INSERT INTO products (name, price, image) VALUES (?,?,?)", defaults)
        conn.commit()
        app.logger.info("Seeded products into DB.")
    conn.close()

# run init at startup
init_db_and_seed()


# ---------------- Utility ----------------
def query_products():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return rows

def get_product(pid):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE id=?", (pid,))
    row = cur.fetchone()
    conn.close()
    return row

# ---------------- Routes ----------------
@app.route("/")
def index():
    try:
        products = query_products()
        return render_template("index.html", products=products)
    except Exception as e:
        app.logger.exception("Error rendering index:")
        return "Internal error", 500

@app.route("/plans")
def plans():
    products = query_products()
    return render_template("plans.html", plans=products)

@app.route("/plan/<int:pid>")
def plan_detail(pid):
    p = get_product(pid)
    if not p:
        return "Not found", 404
    return render_template("plan-details.html", plan=p)

# Cart
@app.route("/add-to-cart/<int:pid>")
def add_to_cart(pid):
    cart = session.get("cart", [])
    if pid not in cart:
        cart.append(pid)
        session["cart"] = cart
        session.modified = True
    return redirect(request.referrer or url_for("index"))

@app.route("/buy-now/<int:pid>")
def buy_now(pid):
    session["cart"] = [pid]
    session.modified = True
    return redirect(url_for("checkout"))

@app.route("/cart")
def cart_page():
    cart = session.get("cart", [])
    if not cart:
        return render_template("cart.html", products=[], total=0)
    placeholders = ",".join("?"*len(cart))
    conn = get_db()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM products WHERE id IN ({placeholders})", cart)
    products = cur.fetchall()
    conn.close()
    total = sum(p["price"] for p in products)
    return render_template("cart.html", products=products, total=total)

@app.route("/remove-from-cart/<int:pid>")
def remove_from_cart(pid):
    cart = session.get("cart", [])
    if pid in cart:
        cart.remove(pid)
        session["cart"] = cart
    return redirect(url_for("cart_page"))

# Checkout - shows QR and UTR form
@app.route("/checkout")
def checkout():
    cart = session.get("cart", [])
    if not cart:
        return redirect(url_for("index"))
    placeholders = ",".join("?"*len(cart))
    conn = get_db()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM products WHERE id IN ({placeholders})", cart)
    products = cur.fetchall()
    conn.close()
    total = sum(p["price"] for p in products)
    return render_template("checkout.html", amount=total)

# Submit UTR (POST)
@app.route("/submit_utr", methods=["POST"])
def submit_utr():
    try:
        name = request.form.get("name", "Unknown")
        email = request.form.get("email", "")
        utr = request.form.get("utr", "")
        cart = session.get("cart", [])
        placeholders = ",".join("?"*len(cart)) if cart else "0"
        conn = get_db()
        cur = conn.cursor()
        if cart:
            cur.execute(f"SELECT SUM(price) as s FROM products WHERE id IN ({placeholders})", cart)
            total = cur.fetchone()["s"] or 0
        else:
            total = 0
        conn.close()

        # Telegram notification
        bot_token = os.environ.get("BOT_TOKEN")
        chat_id = os.environ.get("CHAT_ID")
        if bot_token and chat_id:
            text = f"🔔 New payment submission\nName: {name}\nEmail: {email}\nAmount: ₹{total}\nUTR: {utr}"
            try:
                requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage",
                              json={"chat_id": chat_id, "text": text})
            except Exception:
                app.logger.exception("Telegram send failed")

        # clear cart (optional)
        session.pop("cart", None)

        return render_template("utr_submitted.html", name=name, amount=total)
    except Exception:
        app.logger.exception("Error in submit_utr")
        return "Internal server error", 500

# Admin
@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        user = request.form.get("username")
        pwd = request.form.get("password")
        if user == os.environ.get("ADMIN_USER", "admin") and pwd == os.environ.get("ADMIN_PASS", "12345"):
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid credentials", "error")
            return render_template("admin_login.html")
    return render_template("admin_login.html")

@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    products = query_products()
    return render_template("dashboard.html", products=products)

@app.route("/admin/edit/<int:pid>", methods=["GET","POST"])
def admin_edit(pid):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    p = get_product(pid)
    if not p:
        return "Product not found", 404
    if request.method == "POST":
        name = request.form.get("name")
        price = int(request.form.get("price") or 0)
        image = request.form.get("image")
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE products SET name=?, price=?, image=? WHERE id=?", (name, price, image, pid))
        conn.commit()
        conn.close()
        return redirect(url_for("admin_dashboard"))
    return render_template("edit_product.html", product=p)

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("index"))

# serve favicon (optional)
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static','img'), 'favicon.ico')

# health
@app.route("/_health")
def health():
    return "ok"

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
