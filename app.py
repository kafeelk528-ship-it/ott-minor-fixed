import os
import sqlite3
from flask import Flask, render_template, request, redirect, session
import requests

app = Flask(__name__)
app.secret_key = "supersecret"

# ---------------- DB INIT ----------------
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price INTEGER,
            image TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- HOME ----------------
@app.route("/")
def home():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT * FROM products")
    products = c.fetchall()

    conn.close()
    return render_template("index.html", products=products)


# ---------------- ADD TO CART ----------------
@app.route("/add-to-cart/<int:pid>")
def add_to_cart(pid):
    cart = session.get("cart", [])
    cart.append(pid)
    session["cart"] = cart
    return redirect("/")


# ---------------- BUY NOW ----------------
@app.route("/buy-now/<int:pid>")
def buy_now(pid):
    session["cart"] = [pid]
    return redirect("/checkout")


# ---------------- CART PAGE ----------------
@app.route("/cart")
def cart_page():
    cart = session.get("cart", [])
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    if len(cart) == 0:
        products = []
        total = 0
    else:
        placeholders = ",".join("?" * len(cart))
        c.execute(f"SELECT * FROM products WHERE id IN ({placeholders})", cart)
        products = c.fetchall()
        total = sum(p[2] for p in products)

    conn.close()
    return render_template("cart.html", products=products, total=total)


# ---------------- CHECKOUT ----------------
@app.route("/checkout")
def checkout():
    cart = session.get("cart", [])
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    if len(cart) == 0:
        return redirect("/")

    placeholders = ",".join("?" * len(cart))
    c.execute(f"SELECT * FROM products WHERE id IN ({placeholders})", cart)
    products = c.fetchall()
    total = sum(p[2] for p in products)
    conn.close()

    return render_template("checkout.html", amount=total)


# ---------------- SUBMIT UTR ----------------
@app.route("/submit_utr", methods=["POST"])
def submit_UTR():
    name = request.form.get("name")
    email = request.form.get("email")
    utr = request.form.get("utr")

    cart = session.get("cart", [])
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    placeholders = ",".join("?" * len(cart))
    c.execute(f"SELECT SUM(price) FROM products WHERE id IN ({placeholders})", cart)
    amount = c.fetchone()[0]
    conn.close()

    # Telegram Notification
    bot_token = "8162787624:AAGlBqWs32zSKFd76PNXjBT-e66Y9mh0nY4"
    chat_id = "1857783746"

    message = f"""
🟢 PAYMENT REQUEST

👤 Name: {name}
📧 Email: {email}
💰 Amount: ₹{amount}
🔢 UTR: {utr}
"""

    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": message},
        )
    except:
        pass

    return render_template("utr_submitted.html", name=name, amount=amount)


# ---------------- ADMIN LOGIN ----------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        user = request.form["username"]
        pwd = request.form["password"]

        if user == "admin" and pwd == "12345":
            session["admin_logged_in"] = True
            return redirect("/admin/dashboard")
        else:
            return render_template("admin_login.html", error="Invalid credentials")

    return render_template("admin_login.html")


# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return redirect("/admin/login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT * FROM products")
    products = c.fetchall()

    conn.close()
    return render_template("dashboard.html", products=products)


# ---------------- EDIT PRODUCT ----------------
@app.route("/admin/edit/<int:pid>", methods=["GET", "POST"])
def edit_product(pid):
    if not session.get("admin_logged_in"):
        return redirect("/admin/login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT * FROM products WHERE id=?", (pid,))
    product = c.fetchone()

    if not product:
        conn.close()
        return "Product Not Found"

    if request.method == "POST":
        name = request.form["name"]
        price = request.form["price"]
        image = request.form["image"]

        c.execute(
            "UPDATE products SET name=?, price=?, image=? WHERE id=?",
            (name, price, image, pid),
        )

        conn.commit()
        conn.close()
        return redirect("/admin/dashboard")

    conn.close()
    return render_template("edit_product.html", product=product)


# ---------------- LOGOUT ----------------
@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect("/admin/login")


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
