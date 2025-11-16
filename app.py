from flask import Flask, render_template, redirect, url_for, session, request
import sqlite3
import os
import requests

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "testsecret")

# ==============================
# DATABASE INITIALIZATION
# ==============================
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price INTEGER,
            description TEXT,
            img TEXT
        )
    """)

    conn.commit()
    conn.close()


init_db()


# ==============================
# HOME PAGE
# ==============================
@app.route("/")
def home():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT * FROM products")
    products = c.fetchall()
    conn.close()

    return render_template("index.html", products=products)


# ==============================
# PRODUCT DETAILS PAGE
# ==============================
@app.route("/plan/<int:pid>")
def plan(pid):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE id=?", (pid,))
    product = c.fetchone()
    conn.close()

    return render_template("plan.html", product=product)


# ==============================
# ADD TO CART
# ==============================
@app.route("/add-to-cart/<int:pid>")
def add_to_cart(pid):
    if "cart" not in session:
        session["cart"] = []

    session["cart"].append(pid)
    session.modified = True

    return redirect(url_for("cart"))


# ==============================
# BUY NOW
# ==============================
@app.route("/buy-now/<int:pid>")
def buy_now(pid):
    session["cart"] = [pid]
    return redirect(url_for("checkout"))


# ==============================
# CART PAGE
# ==============================
@app.route("/cart")
def cart():
    cart_items = []
    total = 0

    if "cart" in session:
        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        for pid in session["cart"]:
            c.execute("SELECT * FROM products WHERE id=?", (pid,))
            item = c.fetchone()
            if item:
                cart_items.append(item)
                total += item[2]

        conn.close()

    return render_template("cart.html", cart_items=cart_items, total=total)


# ==============================
# CHECKOUT PAGE
# ==============================
@app.route("/checkout")
def checkout():
    qr_image = "/static/img/qr.png"
    total = 0

    if "cart" in session:
        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        for pid in session["cart"]:
            c.execute("SELECT price FROM products WHERE id=?", (pid,))
            price = c.fetchone()
            if price:
                total += price[0]

        conn.close()

    return render_template("checkout.html", total=total, qr_image=qr_image)


# ==============================
# SUBMIT UTR + TELEGRAM NOTIFICATION
# ==============================
@app.route("/submit_utr", methods=["POST"])
def submit_utr():
    utr = request.form.get("utr")
    email = request.form.get("email")

    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    message = f"🟢 NEW PAYMENT\n\nUTR: {utr}\nEmail: {email}"

    # Send Telegram message
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": message}
        )
    except Exception as e:
        print("Telegram error:", e)

    return render_template("payment_success.html")


# ==============================
# ADMIN LOGIN
# ==============================
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        user = request.form["username"]
        pwd = request.form["password"]

        if (user == os.getenv("ADMIN_USER")) and (pwd == os.getenv("ADMIN_PASS")):
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            return render_template("admin_login.html", error="Invalid Credentials")

    return render_template("admin_login.html")


# ==============================
# ADMIN DASHBOARD
# ==============================
@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT * FROM products")
    products = c.fetchall()
    conn.close()

    return render_template("dashboard.html", products=products)


# ==============================
# EDIT PRODUCT
# ==============================
@app.route("/admin/edit/<int:pid>", methods=["GET", "POST"])
def edit_product(pid):
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    if request.method == "POST":
        name = request.form["name"]
        price = request.form["price"]
        desc = request.form["description"]
        img = request.form["img"]

        c.execute(
            "UPDATE products SET name=?, price=?, description=?, img=? WHERE id=?",
            (name, price, desc, img, pid)
        )
        conn.commit()
        conn.close()

        return redirect(url_for("admin_dashboard"))

    c.execute("SELECT * OF products WHERE id=?", (pid,))
    product = c.fetchone()
    conn.close()

    return render_template("edit_product.html", product=product)


# ==============================
# RUN FLASK
# ==============================
if __name__ == "__main__":
    app.run(debug=True)
