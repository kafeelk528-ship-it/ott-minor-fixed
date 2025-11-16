
import os, json, requests
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, abort
from werkzeug.utils import secure_filename

BASE = Path(__file__).parent
DATA_FILE = BASE / "data.json"
UPLOAD_FOLDER = BASE / "static" / "img"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", "dev_secret_key")

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "12345")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def ensure_data():
    if not DATA_FILE.exists():
        default = {
            "plans": [
                {"id":1,"name":"Netflix Premium","price":199,"stock":10,"logo":"netflix.png","desc":"4K UHD • 4 Screens"},
                {"id":2,"name":"Amazon Prime Video","price":149,"stock":8,"logo":"prime.png","desc":"Full HD • Originals"},
                {"id":3,"name":"Disney+ Hotstar","price":299,"stock":5,"logo":"hotstar.png","desc":"Sports + Movies"},
                {"id":4,"name":"Sony LIV","price":129,"stock":12,"logo":"sonyliv.png","desc":"TV Shows & Originals"}
            ],
            "orders": [],
            "settings":{"qr":"qr.png"}
        }
        DATA_FILE.write_text(json.dumps(default, indent=2), encoding="utf-8")

def load_data():
    ensure_data()
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))

def save_data(d):
    DATA_FILE.write_text(json.dumps(d, indent=2), encoding="utf-8")

def get_plan(pid):
    d = load_data()
    for p in d["plans"]:
        if int(p["id"]) == int(pid):
            return p
    return None

# Public routes
@app.route("/")
def home():
    d = load_data()
    return render_template("index.html", plans=d["plans"])

@app.route("/plans")
def plans():
    d = load_data()
    return render_template("plans.html", plans=d["plans"])

@app.route("/plan/<int:pid>")
def plan_details(pid):
    p = get_plan(pid)
    if not p:
        abort(404)
    return render_template("plan-details.html", plan=p)

# Cart & buy
@app.route("/add-to-cart/<int:pid>")
def add_to_cart(pid):
    if not get_plan(pid):
        flash("Plan not found", "danger")
        return redirect(url_for("plans"))
    cart = session.get("cart", [])
    if pid not in cart:
        cart.append(pid)
    session["cart"] = cart
    flash("Added to cart", "success")
    return redirect(request.referrer or url_for("plans"))

@app.route("/buy-now/<int:pid>")
def buy_now(pid):
    if not get_plan(pid):
        flash("Plan not found", "danger")
        return redirect(url_for("plans"))
    session["cart"] = [pid]
    return redirect(url_for("checkout"))

@app.route("/cart")
def cart():
    d = load_data()
    cart_ids = session.get("cart", [])
    items = [p for p in d["plans"] if p["id"] in cart_ids]
    total = sum(int(p["price"]) for p in items)
    return render_template("cart.html", items=items, total=total)

@app.route("/cart/remove/<int:pid>")
def cart_remove(pid):
    cart = session.get("cart", [])
    if pid in cart:
        cart.remove(pid)
        session["cart"] = cart
    return redirect(url_for("cart"))

@app.route("/checkout")
def checkout():
    d = load_data()
    cart_ids = session.get("cart", [])
    items = [p for p in d["plans"] if p["id"] in cart_ids]
    total = sum(int(p["price"]) for p in items)
    qr = d.get("settings", {}).get("qr", "qr.png")
    return render_template("checkout.html", items=items, total=total, qr=qr)

@app.route("/submit_utr", methods=["POST"])
def submit_utr():
    name = request.form.get("name","").strip()
    phone = request.form.get("phone","").strip()
    utr = request.form.get("utr","").strip()
    if not utr:
        flash("Please enter UTR", "danger")
        return redirect(url_for("checkout"))
    d = load_data()
    cart_ids = session.get("cart", [])
    items = [p for p in d["plans"] if p["id"] in cart_ids]
    amount = sum(int(p["price"]) for p in items)
    order = {
        "id": len(d.get("orders", [])) + 1,
        "name": name,
        "phone": phone,
        "utr": utr,
        "amount": amount,
        "items": [{"id": p["id"], "name": p["name"], "price": p["price"]} for p in items],
        "status": "pending",
        "created_at": datetime.utcnow().isoformat()
    }
    d.setdefault("orders", []).append(order)
    save_data(d)
    # Telegram notify
    if BOT_TOKEN and CHAT_ID:
        try:
            text = f"New UTR Payment\\nOrder: {order['id']}\\nName: {name}\\nPhone: {phone}\\nUTR: {utr}\\nAmount: ₹{amount}"
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": text})
        except Exception as e:
            app.logger.error("Telegram failed: %s", e)
    session.pop("cart", None)
    flash("UTR submitted. Admin will verify.", "success")
    return render_template("success.html", order=order)

# Admin
def admin_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return fn(*a, **kw)
    return wrapper

@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if request.method=="POST":
        u = request.form.get("username")
        p = request.form.get("password")
        if u == ADMIN_USER and p == ADMIN_PASS:
            session["is_admin"] = True
            flash("Welcome admin", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Invalid credentials", "danger")
    return render_template("admin-login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("home"))

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    d = load_data()
    return render_template("admin-dashboard.html", products=d.get("plans",[]), orders=d.get("orders",[]))

@app.route("/admin/add", methods=["GET","POST"])
@admin_required
def admin_add():
    if request.method=="POST":
        name = request.form.get("name")
        price = int(request.form.get("price") or 0)
        stock = int(request.form.get("stock") or 0)
        file = request.files.get("logo")
        filename = "placeholder.png"
        if file:
            filename = secure_filename(f"{int(datetime.utcnow().timestamp())}_{file.filename}")
            file.save(UPLOAD_FOLDER / filename)
        d = load_data()
        nid = max([p["id"] for p in d["plans"]] or [0]) + 1
        d["plans"].append({"id":nid,"name":name,"price":price,"stock":stock,"logo":filename,"desc":request.form.get("desc","")})
        save_data(d)
        flash("Product added", "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin-add.html")

@app.route("/admin/edit/<int:pid>", methods=["GET","POST"])
@admin_required
def admin_edit(pid):
    d = load_data()
    prod = get_plan(pid)
    if not prod:
        flash("Product not found","danger")
        return redirect(url_for("admin_dashboard"))
    if request.method=="POST":
        prod["name"] = request.form.get("name") or prod["name"]
        prod["price"] = int(request.form.get("price") or prod["price"])
        prod["stock"] = int(request.form.get("stock") or prod.get("stock",0))
        file = request.files.get("logo")
        if file:
            filename = secure_filename(f"{int(datetime.utcnow().timestamp())}_{file.filename}")
            file.save(UPLOAD_FOLDER / filename)
            prod["logo"] = filename
        prod["desc"] = request.form.get("desc","")
        save_data(d)
        flash("Updated", "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin-edit.html", product=prod)

@app.route("/admin/delete/<int:pid>", methods=["POST"])
@admin_required
def admin_delete(pid):
    d = load_data()
    d["plans"] = [p for p in d["plans"] if p["id"] != pid]
    save_data(d)
    flash("Deleted", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/static/img/<path:fname>")
def static_img(fname):
    return send_from_directory(UPLOAD_FOLDER, fname)

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",5000)), debug=(os.getenv("FLASK_ENV","development")!="production"))
