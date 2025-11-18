from flask import Flask, render_template, request, redirect, send_file
import json
import io
from reportlab.pdfgen import canvas
import requests

app = Flask(__name__)

# -------------------------------
# Load movie/product data
# -------------------------------
def load_data():
    with open("data.json", "r") as f:
        return json.load(f)

# -----------------------------------
# Home Page
# -----------------------------------
@app.route("/")
def index():
    data = load_data()
    return render_template("index.html", data=data)

# -----------------------------------
# Cart Page
# -----------------------------------
@app.route("/cart")
def cart():
    return render_template("cart.html")

# -----------------------------------
# Checkout Page
# -----------------------------------
@app.route("/checkout")
def checkout():
    return render_template("checkout.html")

# -----------------------------------
# Submit UTR Page (form)
# -----------------------------------
@app.route("/submit_utr", methods=["GET", "POST"])
def submit_utr():
    if request.method == "POST":
        utr = request.form.get("utr")

        # Send telegram notification (already working)
        telegram_token = "YOUR_TELEGRAM_BOT_TOKEN"
        chat_id = "YOUR_CHAT_ID"

        message = f"New Payment Received!\nUTR: {utr}"
        url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
        requests.post(url, data={"chat_id": chat_id, "text": message})

        return render_template("success.html", utr=utr)

    return render_template("submit_utr.html")

# -----------------------------------
# INVOICE PDF GENERATOR (IMPORTANT)
# -----------------------------------
@app.route("/invoice")
def invoice():
    utr = request.args.get("utr")

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)

    p.setTitle("Invoice")

    # Heading
    p.drawString(100, 780, "INVOICE")

    # Details
    p.drawString(100, 740, f"UTR Number: {utr}")
    p.drawString(100, 720, "Payment Status: RECEIVED")
    p.drawString(100, 700, "Service: OTT Subscription / Movie Purchase")
    p.drawString(100, 660, "Thank you for your payment!")

    p.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"invoice_{utr}.pdf",
        mimetype="application/pdf"
    )

# -----------------------------------
# Run App
# -----------------------------------
if __name__ == "__main__":
    app.run(debug=True)
