from flask import Flask, request, render_template, jsonify
from pymongo import MongoClient
from datetime import datetime, timezone
import certifi
import os

MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://xkernal:xkernal@xkerneldb.tvyaced.mongodb.net/event_tickets?retryWrites=true&w=majority",
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client.event_tickets
tickets = db.tickets


@app.route("/")
def scanner():
    return render_template("scanner.html")


@app.route("/students")
def students_page():
    all_tickets = list(tickets.find().sort("ticket_id", 1))
    return render_template("students.html", students=all_tickets)


@app.route("/scan", methods=["POST"])
def scan_ticket():
    """
    Step 1: QR scanned.
    Just checks ticket + returns details, does NOT change `used`.
    """
    raw = (request.json or {}).get("ticket_data", "").strip()
    if not raw:
        return jsonify({"ok": False, "message": "Empty QR data"}), 400

    # If QR is just ticket_id like "69B83920", use directly.
    # If QR is "TICKET:69B83920:anokha", extract middle part.
    ticket_id = raw
    if raw.startswith("TICKET:"):
        parts = raw.split(":")
        if len(parts) >= 2:
            ticket_id = parts[1]

    ticket = tickets.find_one({"ticket_id": ticket_id})
    if not ticket:
        return jsonify({"ok": False, "message": "Invalid ticket"}), 404

    return jsonify({
        "ok": True,
        "ticket_id": ticket["ticket_id"],
        "name": ticket.get("name"),
        "event": ticket.get("event"),
        "used": bool(ticket.get("used", False)),
        "scanned_at": ticket.get("scanned_at"),
    })


@app.route("/proceed", methods=["POST"])
def proceed_ticket():
    """
    Step 2: volunteer taps Proceed.
    Marks used = True only if it was False.
    """
    ticket_id = (request.json or {}).get("ticket_id", "").strip()
    if not ticket_id:
        return jsonify({"ok": False, "message": "Missing ticket_id"}), 400

    ticket = tickets.find_one({"ticket_id": ticket_id})
    if not ticket:
        return jsonify({"ok": False, "message": "Invalid ticket"}), 404

    # If already used, just respond (no second use)
    if ticket.get("used"):
        return jsonify({
            "ok": True,
            "status": "already_used",
            "message": "Ticket already used",
            "ticket_id": ticket["ticket_id"],
            "name": ticket.get("name"),
            "event": ticket.get("event"),
            "used": True,
            "scanned_at": ticket.get("scanned_at"),
        })

    # Mark as used now (first and only time)
    now_utc = datetime.now(timezone.utc).isoformat()
    tickets.update_one(
        {"_id": ticket["_id"]},
        {"$set": {"used": True, "scanned_at": now_utc}},
    )

    return jsonify({
        "ok": True,
        "status": "marked",
        "message": "Ticket marked used",
        "ticket_id": ticket["ticket_id"],
        "name": ticket.get("name"),
        "event": ticket.get("event"),
        "used": True,
        "scanned_at": now_utc,
    })


if __name__ == "__main__":
    app.run(debug=True)
