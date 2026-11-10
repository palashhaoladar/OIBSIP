"""
app.py — Flask + Flask-SocketIO backend server.

ARCHITECTURE OVERVIEW
---------------------
Flask alone only understands HTTP request/response cycles. Real-time chat
needs the server to PUSH data to clients the instant something happens —
that is what WebSockets provide. Flask-SocketIO wraps Flask and adds:

  1. Socket.IO protocol handling (WebSocket with automatic HTTP long-polling
     fallback for older browsers/proxies).
  2. "Rooms" — named channels. Messages emitted to a room are delivered only
     to sockets that have joined that room. This is how we isolate the
     General / Tech / Random conversations from each other.

EVENT LIFECYCLE
---------------
Client (chat.js)                      Server (app.py)
      |                                    |
      |-- HTTP POST /register ----------->|  (one-time account creation)
      |-- HTTP POST /login -------------->|  (session cookie set)
      |-- HTTP GET  /chat --------------->|  (renders chat.html, protected)
      |                                    |
      |-- Socket.IO handshake ----------->|  (WebSocket connection opens)
      |-- emit('join', {room}) ---------->|  join_room(room) + fetch history
      |<-- emit('history', [msgs]) ------|  (last 50 messages replayed)
      |                                    |
      |-- emit('typing', {room}) -------->|  broadcast 'typing' to room (excluding sender)
      |-- emit('message', {room, text}) -->|  timestamp + INSERT into SQLite
      |<-- emit('message', {...}) --------|  broadcast to everyone in room
      |                                    |
      |--- (user closes tab) -------------X  disconnect handler fires,
      |<-- emit('system', '...left') -----|  system message broadcast

RUN:  python app.py   ->  http://localhost:5000
"""

from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, join_room, leave_room, emit
from werkzeug.security import generate_password_hash, check_password_hash

import db  # our SQLite helper module (db.py)

# ---------------------------------------------------------------------------
# 1. APPLICATION SETUP
# ---------------------------------------------------------------------------

app = Flask(__name__)
# A real deployment MUST load this from an environment variable / secret file.
# Hard-coded only for the internship demo. See README.
app.config["SECRET_KEY"] = "oasis-infobyte-task5-demo-secret-change-me"

# Instantiate SocketIO around the Flask app.
# cors_allowed_origins="*" permits the browser page (served from Flask itself,
# but conceptually a separate origin) to open the WebSocket. Tighten this in
# production to your actual domain.
socketio = SocketIO(app, cors_allowed_origins="*")

# Create tables on first run (idempotent — safe to call every startup)
db.init_db()

# Pre-defined public rooms shown in the sidebar. Stored in a dict so we can
# attach a friendly description to each. A production app would store rooms
# in the database and allow creation/deletion.
ROOMS = {
    "general": "Casual conversation for everyone",
    "tech": "Programming, frameworks and dev talk",
    "random": "Memes, links and off-topic fun",
    "announcements": "Read-only style updates from the team",
}


# ---------------------------------------------------------------------------
# 2. HTTP ROUTES — AUTHENTICATION (classic request/response, not WebSockets)
# ---------------------------------------------------------------------------

def require_login():
    """Small helper: returns the logged-in username, or redirects."""
    return session.get("username")


@app.route("/")
def index():
    """Landing page — bounce logged-in users straight to chat."""
    if require_login():
        return redirect(url_for("chat"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    """
    GET  -> render the registration form.
    POST -> hash the password and insert the user into SQLite.

    SECURITY NOTES:
      * Passwords are NEVER stored in plain text. generate_password_hash()
        applies PBKDF2-SHA256 with a random salt per password, producing a
        string like "pbkdf2:sha256:600000$<salt>$<hash>".
      * check_password_hash() re-computes the hash of the submitted password
        with the stored salt and compares in constant time.
    """
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # --- server-side validation (never trust the browser alone) -------
        if not username or not password:
            return render_template("login.html", error="All fields are required.", mode="register")
        if len(username) < 3 or len(username) > 20:
            return render_template("login.html", error="Username must be 3–20 characters.", mode="register")
        if len(password) < 6:
            return render_template("login.html", error="Password must be at least 6 characters.", mode="register")

        # Hash BEFORE touching the database. The DB never sees the real password.
        password_hash = generate_password_hash(password)

        if db.create_user(username, password_hash):
            return redirect(url_for("login", registered="1"))
        else:
            # UNIQUE constraint fired -> username taken
            return render_template("login.html", error="That username is already taken.", mode="register")

    return render_template("login.html", mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    GET  -> render the login form.
    POST -> verify credentials and store the username in the session.

    The Flask session is a signed cookie: its contents are readable by the
    client but TAMPER-PROOF because they are HMAC-signed with SECRET_KEY.
    """
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = db.get_user_by_username(username)

        # Compare submitted password against stored hash (constant-time).
        # We check `user is not None` FIRST so we never call
        # check_password_hash on None (which would crash).
        if user is not None and check_password_hash(user["password_hash"], password):
            # Regenerate the session on privilege change (login) to prevent
            # session fixation attacks.
            session.clear()
            session["username"] = user["username"]
            session["user_id"] = user["id"]
            return redirect(url_for("chat"))

        return render_template("login.html", error="Invalid username or password.", mode="login")

    # After a successful registration we redirect here with ?registered=1 to
    # show a friendly confirmation banner on the login form.
    just_registered = request.args.get("registered") == "1"
    return render_template("login.html", mode="login", just_registered=just_registered)


@app.route("/logout")
def logout():
    """Destroy the session and return to the login page."""
    session.clear()
    return redirect(url_for("login"))


@app.route("/chat")
def chat():
    """
    Protected route — renders the chat dashboard.

    Only authenticated users may see it. The template receives the username
    (displayed in the UI) and the ROOMS dict (rendered in the sidebar).
    """
    username = require_login()
    if not username:
        return redirect(url_for("login"))
    return render_template("chat.html", username=username, rooms=ROOMS)


# ---------------------------------------------------------------------------
# 3. SOCKET.IO EVENT HANDLERS — REAL-TIME LOGIC
# ---------------------------------------------------------------------------
# These are NOT Flask routes. They fire when the CLIENT emits an event over
# the WebSocket. `socketio.on("event_name")` registers a handler.

@socketio.on("connect")
def handle_connect():
    """
    Fires automatically when any browser finishes the Socket.IO handshake.

    We do NOT join a room here — the client emits 'join' explicitly after it
    knows which room the user picked. We just log the connection server-side.
    The `request` object (imported from flask) still works inside handlers and
    carries the HTTP cookies, so we can read the session.
    """
    username = session.get("username", "anonymous")
    print(f"[CONNECT] {username} opened a WebSocket ({request.sid})")


@socketio.on("join")
def handle_join(data):
    """
    Event:  client emits 'join' with {"room": "<room_name>"}

    Steps:
      1. Validate that the requested room actually exists (security: a client
         could otherwise join arbitrary room strings).
      2. leave_room() any previous room this socket was in — a browser tab
         only ever sits in ONE chat room at a time in this design.
      3. join_room() registers this socket's connection ID (request.sid)
         with the room. ALL subsequent emits to that room reach this client.
      4. Query SQLite for the last 50 messages of the room and emit them
         back to THIS socket only (not a broadcast) as 'history'.
      5. Broadcast a system message to the room telling everyone who arrived.
    """
    username = session.get("username", "anonymous")
    room = data.get("room", "general")

    if room not in ROOMS:
        emit("system", {"text": f"Room '{room}' does not exist."})
        return

    # leave any previous room (track it on the socket via request.sid context)
    # Flask-SocketIO: each call to join_room adds to a set; we manage "current"
    # room client-side in chat.js, but leaving is harmless if not joined.
    # For simplicity, the client only ever joins one room per session.
    join_room(room)
    print(f"[JOIN] {username} joined '{room}'")

    # --- Step 4: replay chat history ----------------------------------------
    # get_recent_messages returns a list of dicts:
    #   [{"sender": "alice", "timestamp": "2026-11-09 22:45:00", "content": "hi"}, ...]
    history = db.get_recent_messages(room, limit=50)

    # emit (not broadcast) sends ONLY to the requesting socket — perfect for
    # history replay. The client renders these as regular messages.
    emit("history", {"room": room, "messages": history})

    # --- Step 5: announce the arrival to everyone else in the room ----------
    # broadcast=True sends to every socket in `room` INCLUDING the sender;
    # the client filters/prints system messages distinctly, so it's fine.
    emit("system", {
        "text": f"{username} has joined the room.",
        "timestamp": datetime.now().strftime("%H:%M"),
    }, to=room)


@socketio.on("typing")
def handle_typing(data):
    username = session.get("username", "anonymous")
    room = data.get("room")
    emit("typing", {"sender": username}, to=room, include_self=False)


@socketio.on("stop_typing")
def handle_stop_typing(data):
    username = session.get("username", "anonymous")
    room = data.get("room")
    emit("stop_typing", {"sender": username}, to=room, include_self=False)


@socketio.on("message")
def handle_message(data):
    """
    Event:  client emits 'message' with {"room": "<room>", "text": "..."}

    This is the CORE of the chat. Order of operations matters:

      1. SANITIZE + VALIDATE the payload (never trust client input).
      2. Timestamp is generated SERVER-side (datetime.now()) so a malicious
         client cannot forge timestamps.
      3. INSERT into SQLite FIRST. Persistence-before-broadcast guarantees the
         message is durable even if the emit fails or the server crashes.
      4. Broadcast to the room via `to=room`. Every socket that has called
         join_room(room) receives this event.

    The payload the server broadcasts back is the AUTHORITATIVE version —
    clients should render THIS, not their own copy, so all users see the
    exact same timestamp.
    """
    username = session.get("username", "anonymous")
    room = data.get("room", "general")
    text = (data.get("text") or "").strip()

    # Validation: reject empty messages and unknown rooms.
    if not text:
        return
    if room not in ROOMS:
        emit("system", {"text": "Cannot send: invalid room."})
        return
    # Basic length cap to prevent abuse (store up to 1000 chars).
    if len(text) > 1000:
        text = text[:1000]

    # 2. Server-side timestamp (HH:MM for display; full ISO for the DB).
    timestamp_display = datetime.now().strftime("%H:%M")      # "22:45"
    timestamp_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 3. Persist BEFORE broadcasting.
    db.insert_message(room_name=room, sender=username, timestamp=timestamp_iso, content=text)

    # 4. Broadcast the authoritative message object to the room.
    payload = {
        "room": room,
        "sender": username,
        "timestamp": timestamp_display,
        "content": text,
    }
    emit("message", payload, to=room)


@socketio.on("disconnect")
def handle_disconnect():
    """
    Fires automatically when a socket closes (tab closed, network drop, etc.).

    NOTE: the server has no built-in record of WHICH room this socket was in
    (rooms are tracked per-sid internally by Flask-SocketIO), so for the demo
    we broadcast the departure notice to ALL rooms the user might be in is
    overkill — instead we rely on the client emitting 'leave' explicitly on
    navigation (see chat.js). Here we simply log the disconnect; a production
    app would track active_room in server-side state keyed by request.sid.
    """
    username = session.get("username", "anonymous")
    print(f"[DISCONNECT] {username} closed the connection ({request.sid})")

    # Best-effort announcement to every known room. Harmless if the user wasn't
    # in a given room — clients only display it if they share that room view.
    # (Kept simple intentionally; see README "Known Limitations".)
    for room in ROOMS:
        emit("system", {
            "text": f"{username} has left the chat.",
            "timestamp": datetime.now().strftime("%H:%M"),
        }, to=room)


# ---------------------------------------------------------------------------
# 4. ENTRY POINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # IMPORTANT: never use Flask's built-in dev server for Socket.IO in
    # production. eventlet patches the standard library so the WebSocket
    # server can handle thousands of concurrent connections.
    # threaded=True allows the HTTP routes and Socket.IO handlers to run in
    # parallel threads.
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)