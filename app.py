"""BrowserAI local dashboard + in-process browser worker.

Run on the same Windows computer as Ollama and Microsoft Edge.
The server intentionally binds to 127.0.0.1 (this computer only).
"""
import hmac
import os
import threading
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__)

INVITE_CODES = [
    code.strip() for code in os.environ.get("BROWSERAI_INVITE_CODES", "browserai-local").split(",")
    if code.strip()
]
ADMIN_PASSWORD = os.environ.get("BROWSERAI_ADMIN_PASSWORD", "")
AGENT_ENABLED = os.environ.get("BROWSERAI_AGENT_ENABLED", "true").lower() == "true"

TASKS = {}
TASKS_LOCK = threading.Lock()
ACTIVE_LOCK = threading.Lock()
ACTIVE_TASK_ID = None


def invite_is_valid():
    supplied = request.headers.get("X-Invite-Code", "")
    return any(hmac.compare_digest(supplied, code) for code in INVITE_CODES)


def admin_is_valid():
    auth = request.authorization
    password = auth.password if auth else ""
    username = auth.username if auth else ""
    return bool(ADMIN_PASSWORD) and username == "aham" and hmac.compare_digest(password, ADMIN_PASSWORD)


def run_browser_task(task_id, prompt):
    global ACTIVE_TASK_ID
    driver = None
    try:
        # Lazy import lets /health and the dashboard load even before dependencies are installed.
        import browser_agent as agent
        if not agent.validate_task(prompt):
            raise ValueError("Task is empty or exceeds the agent's 1,000-character limit.")
        with TASKS_LOCK:
            TASKS[task_id]["message"] = "Connecting to Ollama and starting Microsoft Edge..."
        driver = agent.start_browser()
        with TASKS_LOCK:
            TASKS[task_id]["message"] = "Planning and executing approved browser actions..."
        driver, result = agent.run_task(prompt, driver)
        # Only return JSON-safe fields; never expose the Selenium driver or local paths.
        public_result = {
            key: result.get(key) for key in (
                "status", "total", "completed", "failed", "rejected", "commands", "errors", "observations"
            ) if key in result
        }
        with TASKS_LOCK:
            TASKS[task_id].update(status="completed", result=public_result, message="Task finished.")
    except Exception as exc:
        app.logger.exception("Browser task %s failed", task_id)
        with TASKS_LOCK:
            TASKS[task_id].update(status="failed", error=f"{type(exc).__name__}: {str(exc)[:500]}", message="Task failed.")
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                app.logger.exception("Could not close browser cleanly")
        with ACTIVE_LOCK:
            ACTIVE_TASK_ID = None


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


@app.get("/health")
def health():
    return jsonify({"ok": True, "mode": "local"})


@app.get("/api/status")
def status():
    if not invite_is_valid():
        return jsonify({"enabled": False, "message": "Enter a valid invitation code."}), 401
    if not AGENT_ENABLED:
        return jsonify({"enabled": False, "message": "Browser automation is disabled in the server configuration."})
    try:
        import browser_agent
        import ollama
        # Confirm that the local Ollama service responds and the configured model exists.
        model_list = ollama.list()
        model_items = (
            model_list.get("models", [])
            if isinstance(model_list, dict)
            else getattr(model_list, "models", [])
        )
        available_models = set()
        for item in model_items:
            if isinstance(item, dict):
                model_name = item.get("model", item.get("name", ""))
            else:
                model_name = getattr(item, "model", getattr(item, "name", ""))
            if model_name:
                available_models.add(str(model_name))
        configured_model = browser_agent.MODEL
        model_ready = any(
            name == configured_model or name.startswith(configured_model + ":")
            for name in available_models
        )
        if not model_ready:
            return jsonify({
                "enabled": False,
                "message": f"Ollama is running, but model '{configured_model}' is not installed. Run: ollama pull {configured_model}"
            })
    except Exception as exc:
        return jsonify({
            "enabled": False,
            "message": f"Agent is not ready: {type(exc).__name__}: {str(exc)[:180]}. Check Ollama and Python dependencies."
        })
    return jsonify({"enabled": True, "message": f"Browser agent connected. Ollama model '{configured_model}' is ready."})


@app.get("/api/websites")
def websites():
    if not invite_is_valid():
        return jsonify({"error": "Invalid invitation code."}), 401
    try:
        import browser_agent
        items = [{"name": name.title(), "url": url} for name, url in browser_agent.WEBSITES.items()]
    except Exception as exc:
        return jsonify({"error": f"Could not load approved websites: {str(exc)[:180]}"}), 503
    return jsonify({"websites": items})


@app.post("/api/tasks")
def create_task():
    global ACTIVE_TASK_ID
    if not invite_is_valid():
        return jsonify({"error": "Invalid invitation code."}), 401
    if not admin_is_valid():
        return jsonify({"error": "Admin password was not accepted. Set BROWSERAI_ADMIN_PASSWORD before starting the app."}), 401
    if not AGENT_ENABLED:
        return jsonify({"error": "Browser automation is disabled."}), 503
    payload = request.get_json(silent=True) or {}
    prompt = payload.get("prompt", "")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt.strip()) > 1000:
        return jsonify({"error": "Enter a task between 1 and 1,000 characters."}), 400
    with ACTIVE_LOCK:
        if ACTIVE_TASK_ID is not None:
            return jsonify({"error": "Another browser task is already running. Wait for it to finish."}), 409
        task_id = uuid.uuid4().hex
        ACTIVE_TASK_ID = task_id
    with TASKS_LOCK:
        TASKS[task_id] = {"id": task_id, "status": "running", "message": "Task queued."}
    thread = threading.Thread(target=run_browser_task, args=(task_id, prompt.strip()), daemon=True)
    thread.start()
    return jsonify({"id": task_id, "status": "running"}), 202


@app.get("/api/tasks/<task_id>")
def get_task(task_id):
    if not invite_is_valid():
        return jsonify({"error": "Invalid invitation code."}), 401
    with TASKS_LOCK:
        task = TASKS.get(task_id)
        if task is None:
            return jsonify({"error": "Task not found. It may have expired when the local server restarted."}), 404
        return jsonify(dict(task))


if __name__ == "__main__":
    # Local-only: do not expose the computer's browser/profile to the public internet.
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False, threaded=True)
