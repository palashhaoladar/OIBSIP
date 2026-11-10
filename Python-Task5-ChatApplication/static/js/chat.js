/**
 * chat.js — Socket.IO client for the Oasis Chat dashboard.
 *
 * Responsibilities:
 *   1. Open the WebSocket connection (io()).
 *   2. Build the room sidebar and emit 'join' when a room is clicked.
 *   3. Render incoming 'history' / 'message' / 'system' events into the DOM,
 *      formatted as:  [HH:MM] Username: Message
 *   4. Parse emoji shortcodes (:smile:) into Unicode emoji before sending.
 *   5. Auto-scroll to the newest message.
 *   6. Fire a browser Notification for new messages when the tab is unfocused.
 *   7. Broadcast and display real-time typing indicators.
 *
 * Depends on globals injected by chat.html: CURRENT_USER, ROOMS.
 */

"use strict";

// ===========================================================================
// 1. WEBSOCKET CONNECTION
// ===========================================================================

// io() with no URL connects back to the server that served this page.
// The connection upgrades from HTTP long-polling to a true WebSocket
// automatically (Socket.IO's default transport strategy).
const socket = io();

// Track which room the user is currently viewing. Starts on the first room.
let currentRoom = Object.keys(ROOMS)[0];

// Typing state globals
const typers = new Set(); // Tracks everyone currently typing
let typingTimeout = null; 
const typingIndicator = document.getElementById("typing-indicator");

// ===========================================================================
// 2. EMOJI PARSER
// ===========================================================================

/**
 * Shortcode -> Unicode emoji lookup table.
 * Add or remove entries freely — the parser below reads from this map.
 */
const EMOJI_MAP = {
    ":smile:":      "😄",
    ":laughing:":   "😂",
    ":rocket:":     "🚀",
    ":heart:":      "❤️",
    ":thumbsup:":   "👍",
    ":thumbsdown:": "👎",
    ":fire:":       "🔥",
    ":tada:":       "🎉",
    ":cry:":        "😢",
    ":wink:":       "😉",
    ":thinking:":   "🤔",
    ":coffee:":     "☕",
    ":ok_hand:":    "👌",
    ":clap:":       "👏",
    ":eyes:":       "👀",
};

/**
 * Replace emoji shortcodes in a message string with real Unicode emoji.
 * Uses a single regex built from the map keys, so "hello :smile: :rocket:"
 * gets both replaced in one pass.
 */
function parseEmojis(text) {
    const escapedKeys = Object.keys(EMOJI_MAP)
        .map(k => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) // escape regex metachars
        .join("|");
    const regex = new RegExp(escapedKeys, "g");

    return text.replace(regex, (match) => EMOJI_MAP[match] || match);
}

// ===========================================================================
// 3. SIDEBAR CONSTRUCTION
// ===========================================================================

const roomList = document.getElementById("room-list");

/** Render each room from the ROOMS constant as a clickable <li>. */
function buildSidebar() {
    for (const [name, description] of Object.entries(ROOMS)) {
        const li = document.createElement("li");
        li.textContent = `# ${name}`;
        li.dataset.room = name;
        li.title = description; // native tooltip shows the description

        // Highlight the room the user is currently in.
        if (name === currentRoom) li.classList.add("active");

        li.addEventListener("click", () => switchRoom(name));
        roomList.appendChild(li);
    }

    // Fill in the header for the initial room.
    document.getElementById("room-desc").textContent = ROOMS[currentRoom];
}

/** Switch rooms: update UI state, then tell the server. */
function switchRoom(name) {
    if (name === currentRoom) return;
    currentRoom = name;

    // Update sidebar highlight.
    roomList.querySelectorAll("li").forEach(li =>
        li.classList.toggle("active", li.dataset.room === name));

    // Update header.
    document.getElementById("room-title").textContent = `# ${name}`;
    document.getElementById("room-desc").textContent = ROOMS[name];

    // Clear old messages so history doesn't mix across rooms.
    document.getElementById("messages").innerHTML = "";

    // Clear typing states when changing rooms
    typers.clear();
    updateTypingUI();

    // Ask the server to join this room (server will reply with 'history').
    socket.emit("join", { room: name });
}

// ===========================================================================
// 4. DOM RENDERING HELPERS
// ===========================================================================

const messagesEl = document.getElementById("messages");

/**
 * Render a chat message in the EXACT required format:
 *     [HH:MM] Username: Message
 */
function appendMessage({ timestamp, sender, content }) {
    const div = document.createElement("div");
    div.className = "msg" + (sender === CURRENT_USER ? " own" : "");

    const ts = document.createElement("span");
    ts.className = "msg-ts";
    ts.textContent = `[${timestamp}]`;

    const user = document.createElement("span");
    user.className = "msg-user";
    user.textContent = `${sender}:`;

    const body = document.createElement("span");
    body.className = "msg-body";
    body.textContent = content; // XSS-safe: inserted as text, not HTML

    div.append(ts, user, body);
    messagesEl.appendChild(div);
    scrollToBottom();
}

/** Render an italic grey system line ("alice has joined the room."). */
function appendSystemMessage({ text, timestamp }) {
    const div = document.createElement("div");
    div.className = "msg system";

    const ts = document.createElement("span");
    ts.className = "msg-ts";
    ts.textContent = `[${timestamp}]`;

    const body = document.createElement("span");
    body.className = "msg-body";
    body.textContent = text;

    div.append(ts, body);
    messagesEl.appendChild(div);
    scrollToBottom();
}

/** Keep the newest message visible without the user scrolling manually. */
function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

// ===========================================================================
// 5. DESKTOP NOTIFICATIONS
// ===========================================================================

document.addEventListener("click", function askPermission() {
    if ("Notification" in window && Notification.permission === "default") {
        Notification.requestPermission();
    }
    document.removeEventListener("click", askPermission);
}, { once: false });

function notifyIfUnfocused(sender, content) {
    if (sender === CURRENT_USER) return;

    const tabNotVisible = document.hidden || !document.hasFocus();
    if (!tabNotVisible) return;
    if (!("Notification" in window) || Notification.permission !== "granted") return;

    const n = new Notification(`💬 New message from ${sender}`, {
        body: content.length > 80 ? content.slice(0, 80) + "…" : content,
        tag: "oasis-chat-" + currentRoom,
    });

    n.onclick = () => window.focus();
    setTimeout(() => n.close(), 5000);
}

// ===========================================================================
// 6. SOCKET EVENT LISTENERS
// ===========================================================================

socket.on("connect", () => {
    console.log("[SOCKET] Connected:", socket.id);
    socket.emit("join", { room: currentRoom });
});

socket.on("disconnect", () => {
    console.log("[SOCKET] Disconnected");
});

socket.on("history", (data) => {
    data.messages.forEach(m => {
        appendMessage({
            timestamp: m.timestamp.slice(11, 16),
            sender:    m.sender,
            content:   m.content,
        });
    });
    appendSystemMessage({ text: `You joined #${data.room}.`, timestamp: now() });
});

socket.on("message", (data) => {
    appendMessage(data); 
    notifyIfUnfocused(data.sender, data.content);
});

socket.on("system", (data) => {
    appendSystemMessage(data);
});

function now() {
    const d = new Date();
    return d.getHours().toString().padStart(2, "0") + ":" +
           d.getMinutes().toString().padStart(2, "0");
}

// ===========================================================================
// 7. OUTGOING MESSAGES & TYPING INDICATORS
// ===========================================================================

const form  = document.getElementById("chat-form");
const input = document.getElementById("message-input");

// 1. Emit typing events when the local user types
input.addEventListener("input", () => {
    // If the box is empty (user deleted everything), stop typing immediately
    if (!input.value) {
        clearTimeout(typingTimeout);
        socket.emit("stop_typing", { room: currentRoom });
        return;
    }

    socket.emit("typing", { room: currentRoom });

    // Clear the timer every time they hit a key
    clearTimeout(typingTimeout);

    // If they stop typing for 1.5 seconds, automatically emit stop_typing
    typingTimeout = setTimeout(() => {
        socket.emit("stop_typing", { room: currentRoom });
    }, 1500);
});

// 2. Listen for typing events from the server
socket.on("typing", (data) => {
    typers.add(data.sender);
    updateTypingUI();
});

socket.on("stop_typing", (data) => {
    typers.delete(data.sender);
    updateTypingUI();
});

function updateTypingUI() {
    if (typers.size === 0) {
        typingIndicator.textContent = "";
    } else if (typers.size === 1) {
        typingIndicator.textContent = `${Array.from(typers)[0]} is typing...`;
    } else {
        typingIndicator.textContent = "Several people are typing...";
    }
}

// 3. Handle sending the message
form.addEventListener("submit", (e) => {
    e.preventDefault();                 
    const raw = input.value.trim();
    if (!raw) return;

    // Clear local typing state instantly when the message is sent
    clearTimeout(typingTimeout);
    socket.emit("stop_typing", { room: currentRoom });

    const parsed = parseEmojis(raw);

    socket.emit("message", { room: currentRoom, text: parsed });

    input.value = "";                   
    input.focus();
});

// ===========================================================================
// 8. BOOT
// ===========================================================================

buildSidebar();