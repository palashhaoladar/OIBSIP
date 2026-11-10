<div align="center">

# Oasis Real-Time Chat Application

**Oasis Infobyte Internship — Task 5**

<img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" /> <img src="https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask" /> <img src="https://img.shields.io/badge/Socket.io-010101?style=for-the-badge&logo=socket.io&logoColor=white" alt="Socket.io" /> <img src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite" /> <img src="https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black" alt="JavaScript" />

</div>

<br>

A robust, real-time web chat application built with Flask and WebSockets. This project demonstrates session-based authentication, real-time bidirectional communication, and persistent database storage, wrapped in a responsive, modern dark-themed user interface.

---

### Key Features

* **Real-Time Messaging:** Powered by Flask-SocketIO for instant, low-latency communication across multiple clients.
* **Dynamic Chat Rooms:** Users can seamlessly switch between isolated channels (General, Tech, Random, Announcements) without reloading the page.
* **Secure Authentication:** Features a complete login and registration system. Passwords are securely hashed using PBKDF2-SHA256 with random per-password salting.
* **Persistent History:** All users, messages, and timestamps are securely stored in a local SQLite database, allowing users to view the last 50 messages upon joining a room.
* **Live User Engagement:** Includes real-time typing indicators, automated shortcode parsing, and desktop notifications for background tabs.
* **Modern Dark UI:** A sleek, fully responsive frontend utilizing native CSS variables, flexbox layouts, and a clean typography hierarchy.

---

### Tech Stack

* **Backend:** Python 3, Flask, Flask-Session, Flask-SocketIO, Eventlet
* **Database:** SQLite (built-in `sqlite3` module with threaded access)
* **Frontend:** HTML5, CSS3, Vanilla JavaScript, Socket.IO Client
* **Security:** Werkzeug Security

---

### Prerequisites

Ensure you have Python 3.8 or higher installed. The application uses `eventlet` as the asynchronous WSGI server to handle thousands of concurrent WebSocket connections efficiently.

---

### Installation & Setup

**1. Clone the repository**
```bash
git clone https://github.com/palashhaoladar/OIBSIP.git
cd Python-Task5-ChatApplication
```

**2. Create a Virtual Environment**
```bash
# For macOS/Linux
python -m venv venv
source venv/bin/activate

# For Windows
python -m venv venv
venv\Scripts\activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Run the application**
```bash
python app.py
```
*The SQLite database (`chat.db`) and tables are automatically initialized upon the first run.*

**5. Access the Dashboard**
Open your web browser and navigate to: `http://localhost:5000`

---

### Security Transparency & Limitations

**Data Storage:** All chat messages are intentionally stored in plain text within the SQLite database. This is a design choice to allow the server to fulfill features like full-text search, moderation, and chat history retrieval. 

**End-to-End Encryption (E2EE):** This educational project intentionally omits E2EE. Anyone with read access to the database file can read the messages. For production deployment, it is highly recommended to implement database encryption at rest (e.g., SQLCipher) and enforce TLS in transit.