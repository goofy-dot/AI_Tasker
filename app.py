
import hmac
import os
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__)

# Set these as environment variables in Render.
INVITE_CODE = os.environ.get("BROWSERAI_INVITE_CODE", "")
ADMIN_PASSWORD = os.environ.get("BROWSERAI_ADMIN_PASSWORD", "")

# The AI/browser worker is deliberately disabled until it is hosted
# and connected. Do not report it as ready when it is not.
AGENT_ENABLED = os.environ.get("BROWSERAI_AGENT_ENABLED", "false").lower() == "true"


def invite_is_valid():
    supplied = request.headers.get("X-Invite-Code", "")
    return bool(INVITE_CODE) and hmac.compare_digest(supplied, INVITE_CODE)


def admin_is_valid():
    password = request.authorization.password if request.authorization else ""
    username = request.authorization.username if request.authorization else ""
    return (
        bool(ADMIN_PASSWORD)
        and username == "aham"
        and hmac.compare_digest(password, ADMIN_PASSWORD)
    )


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/api/status")
def status():
    if not invite_is_valid():
        return jsonify({"enabled": False, "message": "Enter a valid invitation code."}), 401

    if not AGENT_ENABLED:
        return jsonify({
            "enabled": False,
            "message": "The website is online. The AI and browser worker has not been connected yet."
        })

    return jsonify({
        "enabled": True,
        "message": "Agent service is configured."
    })


@app.get("/api/websites")
def websites():
    if not invite_is_valid():
        return jsonify({"error": "Invalid invitation code."}), 401

    # This list is intentionally empty until the server-side allowlist
    # is connected to the browser agent.
    return jsonify({"websites": []})


@app.post("/api/tasks")
def create_task():
    if not invite_is_valid():
        return jsonify({"error": "Invalid invitation code."}), 401

    if not admin_is_valid():
        return jsonify({"error": "Task service is not configured for this account."}), 503

    if not AGENT_ENABLED:
        return jsonify({
            "error": "The AI/browser worker is not connected yet."
        }), 503

    # Do not accept tasks until a real, authenticated worker is connected.
    return jsonify({"error": "No browser worker is connected."}), 503


@app.get("/api/tasks/<task_id>")
def get_task(task_id):
    if not invite_is_valid():
        return jsonify({"error": "Invalid invitation code."}), 401

    return jsonify({"error": "No task worker is connected."}), 503


@app.get("/health")
def health():
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
