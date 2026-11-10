"""
Advanced BMI Calculator - Oasis Infobyte Internship (Task 2)
=============================================================

Single-file desktop application with:
  - Metric (kg / cm or m) and US Customary (lbs / ft + in) unit tabs
  - Full 8-tier WHO BMI classification, BMI Prime, Ponderal Index,
    and Healthy Weight Range calculations
  - SQLite persistence (users + records with an enforced FOREIGN KEY)
  - Modern dark GUI built with CustomTkinter
  - Embedded Matplotlib line chart of BMI history

Run:
    python main.py
"""

import math
import os
import sqlite3
from datetime import datetime

import customtkinter as ctk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# --------------------------------------------------------------------------- #
# Application-wide appearance configuration
# --------------------------------------------------------------------------- #
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "bmi_history.db"
)

# Exact conversion constants matching standard medical/calculator references
LB_TO_KG = 0.45359237
INCH_TO_M = 0.0254


# =========================================================================== #
# SECTION 1 — SQLite Database Layer
# =========================================================================== #

def initialise_database(db_path=DB_PATH):
    """Create the database and both tables if they do not already exist."""
    connection = None
    try:
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id        INTEGER NOT NULL,
                timestamp      TEXT    NOT NULL,
                age            INTEGER DEFAULT 25,
                gender         TEXT    DEFAULT 'Male',
                weight         REAL    NOT NULL,
                height         REAL    NOT NULL,
                bmi            REAL    NOT NULL,
                bmi_prime      REAL     DEFAULT 0.0,
                ponderal_index REAL    DEFAULT 0.0,
                category       TEXT    NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        # Ensure backward compatibility if an older table already exists
        cursor.execute("PRAGMA table_info(records);")
        existing_cols = {row[1] for row in cursor.fetchall()}
        migrations = {
            "age": "ALTER TABLE records ADD COLUMN age INTEGER DEFAULT 25;",
            "gender": "ALTER TABLE records ADD COLUMN gender TEXT DEFAULT 'Male';",
            "bmi_prime": "ALTER TABLE records ADD COLUMN bmi_prime REAL DEFAULT 0.0;",
            "ponderal_index": "ALTER TABLE records ADD COLUMN ponderal_index REAL DEFAULT 0.0;",
        }
        for col_name, sql in migrations.items():
            if col_name not in existing_cols:
                cursor.execute(sql)

        connection.commit()
    except sqlite3.Error as exc:
        print(f"[DB ERROR] Failed to initialise database: {exc}")
    finally:
        if connection is not None:
            connection.close()


def insert_user(name, db_path=DB_PATH):
    """Insert a new user and return their id, or None if the name exists."""
    connection = None
    try:
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("INSERT INTO users (name) VALUES (?)", (name,))
        connection.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    except sqlite3.Error as exc:
        print(f"[DB ERROR] insert_user: {exc}")
        return None
    finally:
        if connection is not None:
            connection.close()


def fetch_all_users(db_path=DB_PATH):
    """Return every user as a list of (id, name) tuples, ordered by name."""
    connection = None
    try:
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        cursor.execute("SELECT id, name FROM users ORDER BY name ASC")
        return cursor.fetchall()
    except sqlite3.Error as exc:
        print(f"[DB ERROR] fetch_all_users: {exc}")
        return []
    finally:
        if connection is not None:
            connection.close()


def insert_record(
    user_id,
    age,
    gender,
    weight_kg,
    height_m,
    bmi,
    bmi_prime,
    ponderal_index,
    category,
    timestamp_str,
    db_path=DB_PATH,
):
    """Insert a single BMI record linked to a user via the foreign key."""
    connection = None
    try:
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute(
            """
            INSERT INTO records (
                user_id, timestamp, age, gender, weight, height,
                bmi, bmi_prime, ponderal_index, category
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                timestamp_str,
                age,
                gender,
                round(weight_kg, 2),
                round(height_m, 4),
                round(bmi, 2),
                round(bmi_prime, 2),
                round(ponderal_index, 2),
                category,
            ),
        )
        connection.commit()
        return True
    except sqlite3.Error as exc:
        print(f"[DB ERROR] insert_record: {exc}")
        return False
    finally:
        if connection is not None:
            connection.close()


def fetch_user_history(user_id, db_path=DB_PATH):
    """Return chronological (timestamp, bmi) history for charting."""
    connection = None
    try:
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT timestamp, bmi FROM records
            WHERE user_id = ?
            ORDER BY timestamp ASC, id ASC
            """,
            (user_id,),
        )
        return cursor.fetchall()
    except sqlite3.Error as exc:
        print(f"[DB ERROR] fetch_user_history: {exc}")
        return []
    finally:
        if connection is not None:
            connection.close()


# =========================================================================== #
# SECTION 2 — Accurate BMI Domain Logic
# =========================================================================== #

def calculate_metrics(weight_kg, height_m):
    """Compute exact BMI, BMI Prime, Ponderal Index, and Healthy Weight range."""
    raw_bmi = weight_kg / (height_m ** 2)
    bmi = round(raw_bmi, 1)
    bmi_prime = round(raw_bmi / 25.0, 2)
    ponderal_index = round(weight_kg / (height_m ** 3), 1)

    min_healthy_kg = 18.5 * (height_m ** 2)
    max_healthy_kg = 25.0 * (height_m ** 2)

    return {
        "raw_bmi": raw_bmi,
        "bmi": bmi,
        "bmi_prime": bmi_prime,
        "ponderal_index": ponderal_index,
        "min_kg": round(min_healthy_kg, 1),
        "max_kg": round(max_healthy_kg, 1),
        "min_lbs": round(min_healthy_kg / LB_TO_KG, 1),
        "max_lbs": round(max_healthy_kg / LB_TO_KG, 1),
    }


def classify_bmi(bmi):
    """Full 8-category WHO adult classification."""
    if bmi < 16.0:
        return "Severe Thinness"
    elif bmi < 17.0:
        return "Moderate Thinness"
    elif bmi < 18.5:
        return "Mild Thinness"
    elif bmi < 25.0:
        return "Normal"
    elif bmi < 30.0:
        return "Overweight"
    elif bmi < 35.0:
        return "Obese Class I"
    elif bmi < 40.0:
        return "Obese Class II"
    else:
        return "Obese Class III"


CATEGORY_COLOURS = {
    "Severe Thinness":   "#EF4444",  # red
    "Moderate Thinness": "#FB923C",  # orange
    "Mild Thinness":     "#FACC15",  # yellow/amber
    "Normal":            "#22C55E",  # green
    "Overweight":        "#FACC15",  # yellow/amber
    "Obese Class I":     "#FB923C",  # orange
    "Obese Class II":    "#EF4444",  # red
    "Obese Class III":   "#DC2626",  # deep crimson
}


# =========================================================================== #
# SECTION 3 — GUI (CustomTkinter)
# =========================================================================== #

class BMICalculatorApp(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.title("Advanced BMI Calculator — Oasis Infobyte Task 2")
        self.geometry("1220x720")
        self.minsize(1020, 620)
        self.configure(fg_color="#0F172A")

        initialise_database()

        self.users = {}
        self.refresh_user_menu()

        self._build_layout()
        self.refresh_chart()

    # ----------------------------------------------------------------------- #
    # Layout construction
    # ----------------------------------------------------------------------- #
    def _build_layout(self):
        """Create the two-column grid: scrollable form (left) | chart (right)."""
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --------------------------- LEFT PANEL --------------------------- #
        left = ctk.CTkScrollableFrame(
            self, width=380, fg_color="#1E293B", corner_radius=16
        )
        left.grid(row=0, column=0, padx=(20, 10), pady=20, sticky="nsew")
        left.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            left,
            text="BMI Calculator",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(12, 2))

        ctk.CTkLabel(
            left,
            text="WHO Classification • BMI Prime • Ponderal Index",
            text_color="#94A3B8",
            font=ctk.CTkFont(size=12),
        ).grid(row=1, column=0, padx=20, pady=(0, 14))

        # --- User management section ---
        ctk.CTkLabel(
            left, text="Select User", anchor="w", text_color="#CBD5E1"
        ).grid(row=2, column=0, padx=20, sticky="w")

        self.user_menu = ctk.CTkOptionMenu(
            left,
            values=self._menu_values(),
            command=self.on_user_selected,
            fg_color="#334155",
            button_color="#3B82F6",
            button_hover_color="#2563EB",
        )
        self.user_menu.grid(row=3, column=0, padx=20, pady=(4, 10), sticky="ew")

        user_add_row = ctk.CTkFrame(left, fg_color="transparent")
        user_add_row.grid(row=4, column=0, padx=20, pady=(0, 14), sticky="ew")
        user_add_row.grid_columnconfigure(0, weight=1)

        self.new_user_entry = ctk.CTkEntry(
            user_add_row,
            placeholder_text="New user name (e.g. Alex)",
            fg_color="#0F172A",
            border_color="#334155",
        )
        self.new_user_entry.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        ctk.CTkButton(
            user_add_row,
            text="Add User",
            width=90,
            command=self.add_user,
            fg_color="#334155",
            hover_color="#475569",
        ).grid(row=0, column=1)

        # --- Age & Gender row ---
        demo_frame = ctk.CTkFrame(left, fg_color="transparent")
        demo_frame.grid(row=5, column=0, padx=20, pady=(0, 12), sticky="ew")
        demo_frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            demo_frame, text="Age (2 - 120)", anchor="w", text_color="#CBD5E1"
        ).grid(row=0, column=0, padx=(0, 6), sticky="w")
        ctk.CTkLabel(
            demo_frame, text="Gender", anchor="w", text_color="#CBD5E1"
        ).grid(row=0, column=1, padx=(6, 0), sticky="w")

        self.age_entry = ctk.CTkEntry(
            demo_frame,
            placeholder_text="25",
            fg_color="#0F172A",
            border_color="#334155",
        )
        self.age_entry.insert(0, "25")
        self.age_entry.grid(row=1, column=0, padx=(0, 6), pady=(4, 0), sticky="ew")

        self.gender_menu = ctk.CTkOptionMenu(
            demo_frame,
            values=["Male", "Female"],
            fg_color="#334155",
            button_color="#475569",
        )
        self.gender_menu.grid(row=1, column=1, padx=(6, 0), pady=(4, 0), sticky="ew")

        # --- Unit Mode Switcher (Metric vs US Units) ---
        ctk.CTkLabel(
            left, text="Unit System", anchor="w", text_color="#CBD5E1"
        ).grid(row=6, column=0, padx=20, sticky="w")

        self.unit_mode = ctk.CTkSegmentedButton(
            left,
            values=["Metric Units", "US Units"],
            command=self.on_unit_mode_changed,
            selected_color="#3B82F6",
            selected_hover_color="#2563EB",
        )
        self.unit_mode.set("Metric Units")
        self.unit_mode.grid(row=7, column=0, padx=20, pady=(4, 12), sticky="ew")

        # --- Metric Inputs Frame ---
        self.metric_frame = ctk.CTkFrame(left, fg_color="transparent")
        self.metric_frame.grid(row=8, column=0, padx=20, pady=0, sticky="ew")
        self.metric_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.metric_frame,
            text="Height (cm or m)",
            anchor="w",
            text_color="#CBD5E1",
        ).grid(row=0, column=0, sticky="w")
        self.height_metric_entry = ctk.CTkEntry(
            self.metric_frame,
            placeholder_text="e.g. 177.8 (cm) or 1.78 (m)",
            fg_color="#0F172A",
            border_color="#334155",
        )
        self.height_metric_entry.grid(row=1, column=0, pady=(4, 10), sticky="ew")

        ctk.CTkLabel(
            self.metric_frame,
            text="Weight (kg)",
            anchor="w",
            text_color="#CBD5E1",
        ).grid(row=2, column=0, sticky="w")
        self.weight_metric_entry = ctk.CTkEntry(
            self.metric_frame,
            placeholder_text="e.g. 72.6",
            fg_color="#0F172A",
            border_color="#334155",
        )
        self.weight_metric_entry.grid(row=3, column=0, pady=(4, 12), sticky="ew")

        # --- US Units Inputs Frame ---
        self.us_frame = ctk.CTkFrame(left, fg_color="transparent")
        self.us_frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            self.us_frame,
            text="Height (feet / inches)",
            anchor="w",
            text_color="#CBD5E1",
        ).grid(row=0, column=0, columnspan=2, sticky="w")

        self.height_ft_entry = ctk.CTkEntry(
            self.us_frame,
            placeholder_text="Feet (e.g. 5)",
            fg_color="#0F172A",
            border_color="#334155",
        )
        self.height_ft_entry.grid(
            row=1, column=0, padx=(0, 6), pady=(4, 10), sticky="ew"
        )

        self.height_in_entry = ctk.CTkEntry(
            self.us_frame,
            placeholder_text="Inches (e.g. 10)",
            fg_color="#0F172A",
            border_color="#334155",
        )
        self.height_in_entry.grid(
            row=1, column=1, padx=(6, 0), pady=(4, 10), sticky="ew"
        )

        ctk.CTkLabel(
            self.us_frame,
            text="Weight (pounds)",
            anchor="w",
            text_color="#CBD5E1",
        ).grid(row=2, column=0, columnspan=2, sticky="w")
        self.weight_lbs_entry = ctk.CTkEntry(
            self.us_frame,
            placeholder_text="e.g. 160",
            fg_color="#0F172A",
            border_color="#334155",
        )
        self.weight_lbs_entry.grid(
            row=3, column=0, columnspan=2, pady=(4, 12), sticky="ew"
        )

        # --- Calculate & Clear Buttons ---
        btn_row = ctk.CTkFrame(left, fg_color="transparent")
        btn_row.grid(row=9, column=0, padx=20, pady=(2, 12), sticky="ew")
        btn_row.grid_columnconfigure(0, weight=2)
        btn_row.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            btn_row,
            text="Calculate & Log",
            command=self.calculate_and_log,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#3B82F6",
            hover_color="#2563EB",
            height=42,
        ).grid(row=0, column=0, padx=(0, 8), sticky="ew")

        ctk.CTkButton(
            btn_row,
            text="Clear",
            command=self.clear_inputs,
            font=ctk.CTkFont(size=14),
            fg_color="#334155",
            hover_color="#475569",
            height=42,
        ).grid(row=0, column=1, sticky="ew")

        # --- Error & Results Card ---
        self.error_label = ctk.CTkLabel(
            left,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="#F87171",
            wraplength=330,
        )
        self.error_label.grid(row=10, column=0, padx=20, pady=(0, 6))

        result_card = ctk.CTkFrame(left, fg_color="#0F172A", corner_radius=12)
        result_card.grid(row=11, column=0, padx=20, pady=(4, 16), sticky="ew")
        result_card.grid_columnconfigure(0, weight=1)

        self.result_label = ctk.CTkLabel(
            result_card,
            text="BMI = —",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#64748B",
        )
        self.result_label.grid(row=0, column=0, padx=16, pady=(14, 2))

        self.category_label = ctk.CTkLabel(
            result_card,
            text="Enter measurements above",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#94A3B8",
        )
        self.category_label.grid(row=1, column=0, padx=16, pady=(0, 10))

        self.metrics_label = ctk.CTkLabel(
            result_card,
            text=(
                "• Healthy BMI range: 18.5 - 25 kg/m²\n"
                "• Healthy weight for height: —\n"
                "• BMI Prime: —\n"
                "• Ponderal Index: —"
            ),
            font=ctk.CTkFont(size=12),
            text_color="#CBD5E1",
            justify="left",
            anchor="w",
        )
        self.metrics_label.grid(row=2, column=0, padx=16, pady=(0, 12), sticky="ew")

        self.detail_label = ctk.CTkLabel(
            result_card,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#64748B",
            wraplength=320,
        )
        self.detail_label.grid(row=3, column=0, padx=16, pady=(0, 12))

        # --------------------------- RIGHT PANEL -------------------------- #
        right = ctk.CTkFrame(self, fg_color="#1E293B", corner_radius=16)
        right.grid(row=0, column=1, padx=(10, 20), pady=20, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            right,
            text="BMI History & WHO Reference Bands",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(16, 0), sticky="nw")

        self.chart_frame = ctk.CTkFrame(
            right, fg_color="#0F172A", corner_radius=12
        )
        self.chart_frame.grid(row=1, column=0, padx=16, pady=16, sticky="nsew")

        self.figure, self.ax = plt.subplots(
            figsize=(6.6, 4.5), facecolor="#0F172A"
        )
        self.ax.set_facecolor("#0F172A")
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.chart_frame)
        self.canvas.get_tk_widget().pack(
            fill="both", expand=True, padx=8, pady=8
        )
        self._style_axes()

    def _style_axes(self):
        """Apply the dark theme styling to the matplotlib axes."""
        for spine in self.ax.spines.values():
            spine.set_color("#334155")
        self.ax.tick_params(colors="#94A3B8", labelsize=9)
        self.ax.grid(
            True, color="#334155", linestyle="--", linewidth=0.6, alpha=0.6
        )

    # ----------------------------------------------------------------------- #
    # Widget / data helpers
    # ----------------------------------------------------------------------- #
    def _menu_values(self):
        """Names for the option menu; a placeholder keeps the widget valid."""
        return list(self.users.keys()) or ["— no users —"]

    def refresh_user_menu(self):
        """Reload users from the DB and rebuild the {name: id} map."""
        rows = fetch_all_users()
        self.users = {name: uid for uid, name in rows}

        if hasattr(self, "user_menu"):
            self.user_menu.configure(values=self._menu_values())

    def current_user_id(self):
        """Resolve the selected option-menu name to a database user id."""
        name = self.user_menu.get()
        return self.users.get(name)

    def on_unit_mode_changed(self, mode):
        """Switch visible input fields between Metric and US Customary units."""
        self.clear_error()
        if mode == "Metric Units":
            self.us_frame.grid_forget()
            self.metric_frame.grid(row=8, column=0, padx=20, pady=0, sticky="ew")
        else:
            self.metric_frame.grid_forget()
            self.us_frame.grid(row=8, column=0, padx=20, pady=0, sticky="ew")

    def clear_inputs(self):
        """Clear measurement fields and error messages."""
        self.height_metric_entry.delete(0, "end")
        self.weight_metric_entry.delete(0, "end")
        self.height_ft_entry.delete(0, "end")
        self.height_in_entry.delete(0, "end")
        self.weight_lbs_entry.delete(0, "end")
        self.clear_error()

    # ----------------------------------------------------------------------- #
    # Event handlers
    # ----------------------------------------------------------------------- #
    def add_user(self):
        """Validate the new-user entry and persist the user."""
        name = self.new_user_entry.get().strip()
        if not name:
            self.show_error("Please enter a name for the new user.")
            return

        user_id = insert_user(name)
        if user_id is None:
            self.show_error(f"'{name}' already exists — select it above.")
            return

        self.new_user_entry.delete(0, "end")
        self.clear_error()
        self.refresh_user_menu()
        self.user_menu.set(name)
        self.refresh_chart()

    def on_user_selected(self, _choice):
        """OptionMenu command callback — fired on every selection change."""
        self.clear_error()
        self.refresh_chart()

    def _parse_inputs(self):
        """Validate and convert Age, Gender, Weight, and Height to SI units."""
        age_raw = self.age_entry.get().strip()
        try:
            age = int(float(age_raw))
        except ValueError:
            raise ValueError("Age must be a valid whole number between 2 and 120.")

        if age < 2 or age > 120:
            raise ValueError("Age must be between 2 and 120.")

        gender = self.gender_menu.get()
        mode = self.unit_mode.get()

        if mode == "Metric Units":
            w_raw = self.weight_metric_entry.get().strip()
            h_raw = self.height_metric_entry.get().strip()
            try:
                weight_kg = float(w_raw)
                height_val = float(h_raw)
            except ValueError:
                raise ValueError(
                    "Enter valid numeric values for metric weight and height."
                )

            if not (math.isfinite(weight_kg) and math.isfinite(height_val)):
                raise ValueError("Weight and height must be finite numbers.")

            if weight_kg <= 0 or height_val <= 0:
                raise ValueError("Weight and height must be positive values.")

            # Smart conversion: if height > 3.0, user entered centimetres (e.g. 175)
            height_m = height_val / 100.0 if height_val > 3.0 else height_val
            display_input = f"{weight_kg:.1f} kg, {height_m * 100:.1f} cm"

        else:
            ft_raw = self.height_ft_entry.get().strip()
            in_raw = self.height_in_entry.get().strip() or "0"
            lbs_raw = self.weight_lbs_entry.get().strip()
            try:
                feet = float(ft_raw)
                inches = float(in_raw)
                weight_lbs = float(lbs_raw)
            except ValueError:
                raise ValueError(
                    "Enter valid numbers for feet, inches, and pounds."
                )

            if not (
                math.isfinite(feet)
                and math.isfinite(inches)
                and math.isfinite(weight_lbs)
            ):
                raise ValueError("All measurement inputs must be finite numbers.")

            if feet < 0 or inches < 0 or weight_lbs <= 0:
                raise ValueError(
                    "Weight must be positive and height cannot be negative."
                )

            total_inches = (feet * 12.0) + inches
            if total_inches <= 0:
                raise ValueError("Total height must be greater than zero.")

            height_m = total_inches * INCH_TO_M
            weight_kg = weight_lbs * LB_TO_KG
            display_input = f"{weight_lbs:.1f} lbs, {int(feet)}'{inches:g}\""

        if not (0.3 <= height_m <= 2.75):
            raise ValueError(
                "Height is outside realistic human range (30 cm – 275 cm)."
            )
        if not (2.0 <= weight_kg <= 650.0):
            raise ValueError(
                "Weight is outside realistic human range (2 kg – 650 kg)."
            )

        return age, gender, weight_kg, height_m, mode, display_input

    def calculate_and_log(self):
        """Validate inputs, compute all BMI metrics, persist, and update chart."""
        user_id = self.current_user_id()
        if user_id is None:
            self.show_error("Add or select a user first.")
            return

        try:
            age, gender, weight_kg, height_m, mode, display_input = (
                self._parse_inputs()
            )
        except ValueError as err:
            self.show_error(str(err))
            return

        metrics = calculate_metrics(weight_kg, height_m)
        bmi = metrics["bmi"]
        category = classify_bmi(metrics["raw_bmi"])
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if not insert_record(
            user_id,
            age,
            gender,
            weight_kg,
            height_m,
            bmi,
            metrics["bmi_prime"],
            metrics["ponderal_index"],
            category,
            timestamp_str,
        ):
            self.show_error("Could not save the record to the database.")
            return

        colour = CATEGORY_COLOURS.get(category, "#3B82F6")
        self.result_label.configure(
            text=f"BMI = {bmi:.1f} kg/m²", text_color=colour
        )

        age_note = "" if age >= 20 else " (Adult WHO scale; age < 20 uses CDC percentiles)"
        self.category_label.configure(
            text=f"{category}{age_note}", text_color=colour
        )

        if mode == "US Units":
            healthy_wt_str = f"{metrics['min_lbs']} lbs - {metrics['max_lbs']} lbs"
        else:
            healthy_wt_str = f"{metrics['min_kg']} kg - {metrics['max_kg']} kg"

        self.metrics_label.configure(
            text=(
                f"• Healthy BMI range: 18.5 kg/m² - 25 kg/m²\n"
                f"• Healthy weight for height: {healthy_wt_str}\n"
                f"• BMI Prime: {metrics['bmi_prime']:.2f}\n"
                f"• Ponderal Index: {metrics['ponderal_index']:.1f} kg/m³"
            )
        )

        self.detail_label.configure(
            text=f"Logged ({display_input}) at {timestamp_str}"
        )
        self.clear_error()
        self.refresh_chart()

    # ----------------------------------------------------------------------- #
    # Matplotlib chart refresh
    # ----------------------------------------------------------------------- #
    def refresh_chart(self):
        """Redraw the line chart for the currently selected user."""
        self.ax.clear()
        self._style_axes()

        user_id = self.current_user_id()
        history = fetch_user_history(user_id) if user_id else []

        # Reference lines for WHO thresholds
        self.ax.axhline(
            18.5,
            color="#22C55E",
            linestyle="--",
            linewidth=1.1,
            alpha=0.8,
            label="Normal lower (18.5)",
        )
        self.ax.axhline(
            25.0,
            color="#FACC15",
            linestyle="--",
            linewidth=1.1,
            alpha=0.8,
            label="Normal upper (25.0)",
        )
        self.ax.axhline(
            30.0,
            color="#EF4444",
            linestyle=":",
            linewidth=1.1,
            alpha=0.75,
            label="Obese threshold (30.0)",
        )

        if history:
            dates = [row[0] for row in history]
            bmis = [row[1] for row in history]

            self.ax.plot(
                dates,
                bmis,
                color="#3B82F6",
                marker="o",
                markersize=6,
                linewidth=2.2,
                label="User BMI",
            )

            low = min(bmis + [16.0]) - 2
            high = max(bmis + [31.0]) + 2
            self.ax.set_ylim(low, high)

            for label in self.ax.get_xticklabels():
                label.set_rotation(25)
                label.set_ha("right")

            self.ax.legend(
                facecolor="#1E293B",
                labelcolor="#E2E8F0",
                edgecolor="#334155",
                fontsize=8,
                loc="best",
            )
        else:
            self.ax.text(
                0.5,
                0.5,
                "No records yet for this user.\nCalculate your first BMI!",
                transform=self.ax.transAxes,
                ha="center",
                va="center",
                color="#64748B",
                fontsize=12,
            )
            self.ax.set_ylim(14, 36)

        self.ax.set_title("BMI Over Time", color="#E2E8F0", fontsize=13, pad=10)
        self.ax.set_xlabel("Timestamp", color="#94A3B8", fontsize=10)
        self.ax.set_ylabel("BMI (kg/m²)", color="#94A3B8", fontsize=10)

        self.figure.tight_layout()
        self.canvas.draw()

    # ----------------------------------------------------------------------- #
    # Feedback helpers
    # ----------------------------------------------------------------------- #
    def show_error(self, message):
        self.error_label.configure(text=message)

    def clear_error(self):
        self.error_label.configure(text="")


# =========================================================================== #
# SECTION 4 — Entry point
# =========================================================================== #

if __name__ == "__main__":
    app = BMICalculatorApp()
    app.mainloop()