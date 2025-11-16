from flask import Flask, render_template, redirect, request, session, url_for
import telegram

app = Flask(__name__)
app.secret_key = "supersecret123"

# Telegram Bot Details
BOT_TOKEN = "8162787624:AAGlBqWs32zSKFd76PNXjBT-e66Y9mh0nY4"
CHAT_ID = "1857783746"
bot = telegram.Bot(token=BOT_TOKEN)

# PRODUCT DATABASE
plans = [
    {"id": 1, "name": "Netflix Premium", "price": 199, "stock": 100, "img": "netflix.png", "desc": "Premium UHD Plan"},
    {"id": 2, "name": "Amazon Prime", "price": 149, "stock": 100, "img": "prime.png", "desc": "Prime Video + Delivery"},
    {"id": 3, "name": "Disney+ Hotstar", "price": 99, "stock": 100, "img": "hotstar.png", "desc": "Premium + Sports"},
    {"id": 4, "name": "Sony Liv Premium", "price": 89, "stock": 100, "img": "sonyliv.png", "desc": "Premium Plan"}
]


# ------------------------------------------
# HOME PAGE
# ------------------------------------------
@app.route("/")
def home():
    return render_template("index.html", plans=plans)


# ------------------------------------------
# VIEW ALL PLANS
# ------------------------------------------
@app.route("/plans")
def all_plans():
    return render_template("plans.html", plans=plans)


# ------------------------------------------
# PRODUCT DETAILS
# ------------------------------------------
@app.route("/plan/<int:id>")
def plan_details(id):
    plan = next((p for p in plans if p["id"] == id), None)
    if not plan:
        return "Plan not found"
    return render_template("plan-details.html", plan=plan)


# ------------------------------------------
# CART SYSTEM
# ------------------------------------------
@app.route("/add-to-cart/<int:id>")
def add_to_cart(id):
    plan = next((p for p in plans if p["id"] == id), None)
    if not plan:
        return redirect("/")

    cart = session.get("cart", [])
    cart.append(plan)
    session["cart"] = cart

    return redirect("/")


@app.route("/cart")
def cart_view():
    cart = session.get("cart", [])
    total = sum(item["price"] for item in cart)
    return render_template("cart.html", cart=cart, total=total)


@app.route("/remove/<int:id>")
def remove_item(id):
    cart = session.get("cart", [])
    cart = [item for item in cart if item["id"] != id]
    session["cart"] = cart
    return redirect("/cart")


# ------------------------------------------
# BUY NOW
# ------------------------------------------
@app.route("/buy-now/<int:id>")
def buy_now(id):
    plan = next((p for p in plans if p["id"] == id), None)
    if not plan:
        return redirect("/")
    session["cart"] = [plan]
    return redirect("/checkout")


# ------------------------------------------
# CHECKOUT
# ------------------------------------------
@app.route("/checkout")
def checkout():
    return render_template("checkout.html")


# ------------------------------------------
# SUBMIT UTR (SENDS TELEGRAM MESSAGE)
# ------------------------------------------
@app.route("/submit_utr", methods=["POST"])
def submit_utr():
    utr = request.form.get("utr")
    cart = session.get("cart", [])

    if not cart:
        return redirect("/")

    message = "📢 *New Order Received*\n\n"
    for item in cart:
        message += f"🔹 {item['name']} - ₹{item['price']}\n"

    message += f"\n💰 *UTR:* {utr}"

    try:
        bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")
    except:
        pass

    session["cart"] = []
    return render_template("utr_submitted.html")


# ------------------------------------------
# ADMIN LOGIN
# ------------------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == "admin" and password == "12345":
            session["admin"] = True
            return redirect("/admin/dashboard")
        else:
            return render_template("admin_login.html", error=True)

    return render_template("admin_login.html")


# ------------------------------------------
# ADMIN DASHBOARD
# ------------------------------------------
@app.route("/admin/dashboard")
def dashboard():
    if not session.get("admin"):
        return redirect("/admin/login")

    return render_template("dashboard.html", plans=plans)


# ------------------------------------------
# EDIT PRODUCT
# ------------------------------------------
@app.route("/admin/edit/<int:id>", methods=["GET", "POST"])
def edit_product(id):
    if not session.get("admin"):
        return redirect("/admin/login")

    plan = next((p for p in plans if p["id"] == id), None)

    if not plan:
        return "Product not found"

    if request.method == "POST":
        plan["name"] = request.form.get("name")
        plan["price"] = int(request.form.get("price"))
        plan["stock"] = int(request.form.get("stock"))
        plan["img"] = request.form.get("img")

        return redirect("/admin/dashboard")

    return render_template("edit_product.html", plan=plan)


# ------------------------------------------
# LOGOUT
# ------------------------------------------
@app.route("/admin/logout")
def logout():
    session.pop("admin", None)
    return redirect("/")


# RUN APP
if __name__ == "__main__":
    app.run(debug=True)
