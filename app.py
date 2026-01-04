from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import sqlite3
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "secretkey123")

DB_NAME = "students.db"

# ================= DATABASE =================
def get_db():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS students (
        roll TEXT PRIMARY KEY,
        name TEXT,
        section TEXT,
        attendance INTEGER,
        assignments INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS marks (
        roll TEXT,
        exam TEXT,
        s1 INTEGER, s2 INTEGER, s3 INTEGER,
        s4 INTEGER, s5 INTEGER, s6 INTEGER,
        PRIMARY KEY (roll, exam)
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ================= USERS =================
ADMIN = {"username": "admin", "password": "admin"}

STUDENTS = {
    "2511039": "18122002",
    "2510361": "27102003",
    "2510701": "07111992",
    "2512322": "16052004",
    "2511040": "19052004"
}

# ================= AUTH =================
@app.route("/")
def login_page():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if username == ADMIN["username"] and password == ADMIN["password"]:
        session.clear()
        session["role"] = "admin"
        return jsonify({"success": True, "role": "admin"})

    if username in STUDENTS and STUDENTS[username] == password:
        session.clear()
        session["role"] = "student"
        session["roll"] = username
        return jsonify({"success": True, "role": "student"})

    return jsonify({"success": False})

# ================= ADMIN =================
@app.route("/admin")
def admin_page():
    if session.get("role") != "admin":
        return redirect(url_for("login_page"))
    return render_template("admin.html")

@app.route("/admin/save", methods=["POST"])
def admin_save():
    if session.get("role") != "admin":
        return jsonify({"message": "Unauthorized"}), 401

    data = request.json
    roll = data["roll"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO students VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(roll) DO UPDATE SET
      name=excluded.name,
      section=excluded.section,
      attendance=excluded.attendance,
      assignments=excluded.assignments
    """, (
        roll, data["name"], data["section"],
        data["attendance"], data["assignments"]
    ))

    marks = data["marks"]

    cur.execute("""
    INSERT INTO marks VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(roll, exam) DO UPDATE SET
      s1=excluded.s1, s2=excluded.s2, s3=excluded.s3,
      s4=excluded.s4, s5=excluded.s5, s6=excluded.s6
    """, (
        roll, data["exam"],
        marks[0], marks[1], marks[2],
        marks[3], marks[4], marks[5]
    ))

    conn.commit()
    conn.close()

    return jsonify({"message": "Data saved successfully"})

# ================= STUDENT =================
@app.route("/dashboard")
def student_dashboard():
    if session.get("role") != "student":
        return redirect(url_for("login_page"))
    return render_template("dashboard.html")

@app.route("/student/data")
def student_data():
    if session.get("role") != "student":
        return jsonify({"error": "Unauthorized"}), 401

    roll = session.get("roll")
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM students WHERE roll=?", (roll,))
    student = cur.fetchone()
    if not student:
        return jsonify({"error": "No data"}), 404

    data = {
        "roll": student[0],
        "name": student[1],
        "section": student[2],
        "attendance": student[3],
        "assignments": student[4],
        "cat1": [],
        "cat2": [],
        "model": []
    }

    for exam in ["cat1", "cat2", "model"]:
        cur.execute("SELECT s1,s2,s3,s4,s5,s6 FROM marks WHERE roll=? AND exam=?",
                    (roll, exam))
        row = cur.fetchone()
        if row:
            data[exam] = list(row)

    conn.close()
    return jsonify({"data": data})

# ================= AI PREDICTION =================
@app.route("/student/predict")
def student_predict():
    if session.get("role") != "student":
        return jsonify({"error": "Unauthorized"}), 401

    roll = session.get("roll")
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT attendance, assignments FROM students WHERE roll=?", (roll,))
    s = cur.fetchone()
    if not s:
        return jsonify({"prediction": "No Data"})

    attendance, assignments = s

    cur.execute("SELECT s1,s2,s3,s4,s5,s6 FROM marks WHERE roll=?", (roll,))
    rows = cur.fetchall()
    conn.close()

    marks = [m for r in rows for m in r]

    if not marks:
        return jsonify({
            "attendance": attendance,
            "average_marks": "--",
            "assignments": assignments,
            "prediction": "No Data"
        })

    avg = sum(marks) / len(marks)

    if attendance >= 85 and avg >= 80 and assignments >= 2:
        result = "Excellent"
    elif attendance >= 70 and avg >= 65:
        result = "Good"
    elif attendance >= 50 and avg >= 50:
        result = "Average"
    else:
        result = "Needs Improvement"

    return jsonify({
        "attendance": attendance,
        "average_marks": round(avg, 2),
        "assignments": assignments,
        "prediction": result
    })

# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

if __name__ == "__main__":
    app.run()
