<div align="center">

# Advanced BMI Calculator

**Oasis Infobyte Data Python Programming Internship — Task 2**

<img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" /> <img src="https://img.shields.io/badge/CustomTkinter-4B8BBE?style=for-the-badge" alt="CustomTkinter" /> <img src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite" /> <img src="https://img.shields.io/badge/Matplotlib-11557C?style=for-the-badge" alt="Matplotlib" />

</div>

<br>

A modern, professional desktop application built with Python to accurately track and analyze Body Mass Index (BMI). This tool goes beyond basic calculations by providing comprehensive health metrics, World Health Organization (WHO) classifications, and visualized historical data for multiple users.

---

### Features

* **Multi-User Profiles:** Create and manage individual profiles. All historical data is securely saved locally using SQLite.
* **Dual Unit Support:** Seamlessly switch between Metric (kg / cm or m) and US Customary (lbs / ft + in) systems.
* **Interactive Data Visualization:** Embedded Matplotlib line chart tracking your BMI history over time alongside standard WHO threshold reference lines.
* **Modern Dark UI:** A sleek, user-friendly interface built using the CustomTkinter framework.
* **Advanced Health Metrics:**
  * **BMI Calculation:** Standard Body Mass Index.
  * **WHO Classification:** Full 8-tier adult categorization, ranging from Severe Thinness to Obese Class III.
  * **BMI Prime:** Ratio of actual BMI to the upper limit optimal BMI (25).
  * **Ponderal Index:** A measure of leanness or corpulence (weight divided by height cubed).
  * **Healthy Weight Range:** Calculates target weight bounds based on the user's exact height.

---

### Prerequisites

Before running the application, ensure you have Python 3.8 or higher installed on your system. You will also need to install the required third-party libraries.

---

### Installation

**1. Clone the repository**
```bash
git clone https://github.com/palashhaoladar/OIBSIP.git
cd Python-Task2-BMICalculator
```

**2. Create and activate a Virtual Environment (Recommended)**
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

---

### Usage

Launch the application by running the main script in your terminal:

```bash
python main.py
```

* **Add a User:** On the left panel, type a name into the "New user name" box and click **Add User**.
* **Select Unit System:** Toggle between "Metric Units" and "US Units" depending on your preference.
* **Log Data:** Enter your Age, Gender, Height, and Weight, then click **Calculate & Log**.
* **Review:** View your detailed health metrics on the bottom-left card, and see your new data point appear instantly on the history chart on the right.

---

### Project Structure

* `main.py` — The single-file application script containing the database layer, BMI domain logic, and GUI components.
* `requirements.txt` — The list of required third-party dependencies for the application.
* `bmi_history.db` — The SQLite database file (auto-generated upon the first run) storing user data and history.

---

> **Disclaimer:** This application is designed for educational and informational purposes only. The BMI scale and related metrics are general indicators and should not be treated as professional medical advice. Always consult a healthcare provider for medical inquiries.
