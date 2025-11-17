# --------------------------
@app.route("/add-to-cart/<int:plan_id>")
def add_to_cart(plan_id):
    p = get_plan_by_id(plan_id)
    if not p:
        flash("Plan not found!")
        return redirect("/")

    cart = session.get("cart", [])
    if plan_id not in cart:
        cart.append(plan_id)
    session["cart"] = cart

    return redirect(url_for("cart_page"))

@app.route("/buy-now/<int:plan_id>")
def buy_now(plan_id):
    session["cart"] = [plan_id]
    return redirect("/checkout")

@app.route("/cart")
def cart_page():
    cart = session.get("cart", [])
    items = [get_plan_by_id(i) for i in cart]
    total = sum(i["price"] for i in items if i)
    return render_template("cart.html", cart=items, total=total)

@app.route("/cart/remove/<int:pid>")
def remove_cart(pid):
    cart = session.get("cart", [])
    if pid in cart:
        cart.remove(pid)
    session["cart"] = cart
    return redirect("/cart")

# --------------------------
# CHECKOUT + UTR SUBMIT
# --------------------------
@app.route("/checkout")
def checkout():
    cart = session.get("cart", [])
    items = [get_plan_by_id(i) for i in cart]
    total = sum(i["price"] for i in items)
    qr_url = url_for("static", filename="img/qr.png")
    return render_template("checkout.html", cart=items, total=total, qr_url=qr_url)

@app.route("/submit_utr", methods=["POST"])
def submit_utr():
    name = request.form.get("name")
    phone = request.form.get("phone")
    utr = request.form.get("utr")
    email = request.form.get("email")

    cart = session.get("cart", [])
    items = [get_plan_by_id(i) for i in cart]
    total = sum(i["price"] for i in items)
    products = ", ".join([i["name"] for i in items])

    if not utr:
        flash("UTR required!")
        return redirect("/checkout")

    # Telegram Message
    message = f"""
New Payment Received
Name: {name}
Phone: {phone}
Email: {email}
UTR: {utr}
Amount: ₹{total}
Products: {products}
Time: {datetime.utcnow().isoformat()}
"""
    notify_owner_telegram(message)

    # Generate PDF Invoice
    filename = generate_invoice(name, phone, utr, total, products)
    invoice_url = url_for("static", filename=f"invoices/{filename}")

    session.pop("cart", None)

    return render_template("submit_utr_result.html", invoice_url=invoice_url, ok=True)

# --------------------------
# ADMIN
# --------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("username") == ADMIN_USER and request.form.get("password") == ADMIN_PASS:
            session["admin_logged"] = True
            return redirect("/admin/dashboard")
        flash("Invalid login")
    return render_template("admin_login.html")

def admin_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrap(*a, **k):
        if not session.get("admin_logged"):
            return redirect("/admin/login")
        return fn(*a, **k)
    return wrap

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    return render_template("admin_dashboard.html", plans=get_plans())

@app.route("/admin/edit/<int:pid>", methods=["GET", "POST"])
@admin_required
def admin_edit(pid):
    data = load_data()
    plans = data.get("plans", [])
    plan = next((p for p in plans if p["id"] == pid), None)
    if not plan:
        abort(404)

    if request.method == "POST":
        plan["name"] = request.form.get("name")
        plan["price"] = int(request.form.get("price"))
        plan["desc"] = request.form.get("desc")
        plan["logo"] = request.form.get("logo")
        plan["available"] = True if request.form.get("available") else False
        save_data(data)
        flash("Updated successfully")
        return redirect("/admin/dashboard")

    return render_template("admin_edit.html", plan=plan)

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged", None)
    return redirect("/")

# --------------------------
# START
# --------------------------
if name == "__main__":
    init_data()
    app.run(host="0.0.0.0", port=5000, debug=True)
