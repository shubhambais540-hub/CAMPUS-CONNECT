
  #---- photo add-----
import os
from werkzeug.utils import secure_filename


import secrets
import os
from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, g
)
import sqlite3
import os
from datetime import timedelta
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)


# Profile Photo Configuration

UPLOAD_FOLDER = os.path.join(
    app.root_path,
    "static",
    "uploads",
    "profile_photos"
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
# Complaint Photo Configuration

COMPLAINT_UPLOAD_FOLDER = os.path.join(
    app.root_path,
    "static",
    "uploads",
    "complaints"
)

os.makedirs(COMPLAINT_UPLOAD_FOLDER, exist_ok=True)

ALLOWED_COMPLAINT_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


# --------------
load_dotenv()

app.secret_key = os.getenv("SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("SECRET_KEY is missing!")


print("Root Path:", app.root_path)
print("Template Folder:", app.template_folder)

# Flask configuration
# Flask configuration

app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=15)
app.config["SESSION_REFRESH_EACH_REQUEST"] = False

# Database configuration
os.makedirs("instance", exist_ok=True)
DATABASE = os.path.join("instance", "campus.db")


# ---------------- DATABASE ----------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DATABASE) as db:

        # Users table
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'student'
            )
        """)

        # Complaints table
        db.execute("""
            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT DEFAULT 'Pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
                # Users table
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'student'
            )
        """)

        # Add profile_photo column
        columns = db.execute(
            "PRAGMA table_info(users)"
        ).fetchall()

        column_names = [column[1] for column in columns]

        if "profile_photo" not in column_names:
            db.execute("""
                ALTER TABLE users
                ADD COLUMN profile_photo TEXT
            """)


                # Add must_change_password column
        columns = db.execute(
            "PRAGMA table_info(users)"
        ).fetchall()

        column_names = [column[1] for column in columns]

        if "must_change_password" not in column_names:
            db.execute("""
                ALTER TABLE users
                ADD COLUMN must_change_password INTEGER DEFAULT 0
            """)

        # Complaints table




                # Complaint Status Timeline
        db.execute("""
            CREATE TABLE IF NOT EXISTS complaint_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                complaint_id INTEGER NOT NULL,
                old_status TEXT,
                new_status TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (complaint_id) REFERENCES complaints(id)
            )
        """)

                # Add priority column to existing complaints table
        columns = db.execute(
            "PRAGMA table_info(complaints)"
        ).fetchall()

        column_names = [column[1] for column in columns]

        if "priority" not in column_names:
            db.execute("""
                ALTER TABLE complaints
                ADD COLUMN priority TEXT DEFAULT 'Medium'
            """)
                # Add complaint photo column
        columns = db.execute(
            "PRAGMA table_info(complaints)"
        ).fetchall()

        column_names = [column[1] for column in columns]

        if "photo" not in column_names:
            db.execute("""
                ALTER TABLE complaints
                ADD COLUMN photo TEXT
            """)

        # Notices table
        db.execute("""
            CREATE TABLE IF NOT EXISTS notices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create default admin if not already present
        admin = db.execute(
            "SELECT id FROM users WHERE email = ?",
            ("admin@campus.com",)
        ).fetchone()

        if admin is None:
            db.execute("""
                INSERT INTO users (name, email, password, role)
                VALUES (?, ?, ?, ?)
            """, (
                "Administrator",
                "admin@campus.com",
                generate_password_hash("Admin@123"),
                "admin"
            ))


init_db()


# ---------------- AUTHENTICATION ----------------


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first.")
            return redirect(url_for("login"))

        # Force student to change temporary password
        if session.get("must_change_password"):
            if request.endpoint not in ["change_password", "logout"]:
                return redirect(url_for("change_password"))

        return view(*args, **kwargs)

    return wrapped



def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Admin access required.")
            return redirect(url_for("dashboard"))

        return view(*args, **kwargs)

    return wrapped


# ---------------- HOME ----------------


@app.route("/")
def home():
    db = get_db()

    notices = db.execute("""
        SELECT *
        FROM notices
        ORDER BY id DESC
        LIMIT 5
    """).fetchall()

    return render_template("index.html", notices=notices)



# ---------------- REGISTER ----------------



@app.route("/register", methods=["GET", "POST"])
def register():

    db = get_db()

    # Add profile columns safely
    existing_columns = [
        row[1] for row in db.execute(
            "PRAGMA table_info(users)"
        ).fetchall()
    ]

    new_columns = {
        "username": "TEXT",
        "roll_no": "TEXT",
        "gender": "TEXT",
        "branch": "TEXT",
        "course": "TEXT"
    }

    for column, data_type in new_columns.items():
        if column not in existing_columns:
            db.execute(
                f"ALTER TABLE users ADD COLUMN {column} {data_type}"
            )
    db.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS
        idx_users_username ON users(username)
    """)

    db.commit()

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        roll_no = request.form.get("roll_no", "").strip()
        gender = request.form.get("gender", "").strip()
        branch = request.form.get("branch", "").strip()
        course = request.form.get("course", "").strip()
        password = request.form.get("password", "")

        # Check required fields
        if not all([
            name,username, email, roll_no, gender,
            branch, course, password
        ]):
            flash("Please fill all fields.")
            return redirect(url_for("register"))

        if len(password) < 8:
            flash("Password must be at least 8 characters.")
            return redirect(url_for("register"))


        existing_username = db.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        if existing_username:
            flash("Username already exists! Please choose another.")
            return redirect(url_for("register"))

        try:
            db.execute("""
                INSERT INTO users
                (name, username, email, password, roll_no,
                 gender, branch, course)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name,
                username,
                email,
                generate_password_hash(password),
                roll_no,
                gender,
                branch,
                course
            ))

            db.commit()

            flash("Registration successful! Please login.")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            db.rollback()
            flash("Email or Roll Number already exists.")

    return render_template("register.html")

#----------forget password-------------
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    db = get_db()

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not email or not new_password or not confirm_password:
            flash("Please fill all fields.")
            return redirect(url_for("forgot_password"))

        if len(new_password) < 8:
            flash("Password must be at least 8 characters.")
            return redirect(url_for("forgot_password"))

        if new_password != confirm_password:
            flash("Passwords do not match.")
            return redirect(url_for("forgot_password"))

        user = db.execute(
            "SELECT id FROM users WHERE LOWER(email) = LOWER(?)",
            (email,)
        ).fetchone()

        if not user:
            flash("Account not found.")
            return redirect(url_for("forgot_password"))

        db.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (generate_password_hash(new_password), user["id"])
        )

        db.commit()

        flash("Password reset successful! Please login.")
        return redirect(url_for("login"))

    return render_template("forgot_password.html")



# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        user = get_db().execute(
            "SELECT * FROM users WHERE email = ?",
            (username,)
        ).fetchone()

        if user and check_password_hash(user["password"], password):

            session.clear()

            # Session expires after 15 minutes
            session.permanent = True

            
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]

            flash("Login successful!")

            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))

            if user["must_change_password"] == 1:
                session["must_change_password"] = True
                return redirect(url_for("change_password"))

            return redirect(url_for("dashboard"))


        flash("Invalid username or password.")

    return render_template("login.html")


# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():

    session.clear()

    flash("You have been logged out.")

    return redirect(url_for("home"))


# ---------------- STUDENT DASHBOARD ----------------

@app.route("/dashboard")
@login_required
def dashboard():

    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))

    db = get_db()

        # Student Profile Photo
    user = db.execute("""
        SELECT profile_photo
        FROM users
        WHERE id = ?
    """, (session["user_id"],)).fetchone()

    # Total Complaints
    total = db.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE user_id = ?
    """, (session["user_id"],)).fetchone()[0]

    # Pending Complaints
    pending = db.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE user_id = ? AND status = 'Pending'
    """, (session["user_id"],)).fetchone()[0]

    # Resolved Complaints
    resolved = db.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE user_id = ? AND status = 'Resolved'
    """, (session["user_id"],)).fetchone()[0]

    # College Notices
    notices = db.execute("""
        SELECT *
        FROM notices
        ORDER BY id DESC
    """).fetchall()

    # Recent Complaints
    recent_complaints = db.execute("""
        SELECT *
        FROM complaints
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 5
    """, (session["user_id"],)).fetchall()

    return render_template(
        "dashboard.html",
        total=total,
        pending=pending,
        resolved=resolved,
        notices=notices,
        recent_complaints=recent_complaints,
        user = user
    )

    #profile add

@app.route("/profile")
@login_required
def profile():

    db = get_db()

    user = db.execute("""
        SELECT id, name, email, roll_no, gender, branch, course, profile_photo
        FROM users
        WHERE id = ?
    """, (session["user_id"],)).fetchone()

    return render_template("profile.html", user=user)

@app.route("/upload_profile_photo", methods=["POST"])
@login_required
def upload_profile_photo():

    if "photo" not in request.files:
        flash("Please select a photo.")
        return redirect(url_for("profile"))

    photo = request.files["photo"]

    if photo.filename == "":
        flash("No photo selected.")
        return redirect(url_for("profile"))

    filename = secure_filename(photo.filename)

    allowed_extensions = {"png", "jpg", "jpeg", "webp"}

    if "." not in filename or filename.rsplit(".", 1)[1].lower() not in allowed_extensions:
        flash("Only PNG, JPG, JPEG and WEBP images are allowed.")
        return redirect(url_for("profile"))

    # Create unique filename
    extension = filename.rsplit(".", 1)[1].lower()
    filename = f"profile_{session['user_id']}.{extension}"

    # Save photo
    photo.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    db = get_db()

    # Update profile photo in database
    db.execute("""
        UPDATE users
        SET profile_photo = ?
        WHERE id = ?
    """, (filename, session["user_id"]))

    db.commit()

    flash("Profile photo uploaded successfully!")

    return redirect(url_for("profile"))


@app.route("/delete_profile_photo", methods=["POST"])
@login_required
def delete_profile_photo():

    db = get_db()

    user = db.execute("""
        SELECT profile_photo
        FROM users
        WHERE id = ?
    """, (session["user_id"],)).fetchone()

    if user and user["profile_photo"]:

        filename = os.path.basename(user["profile_photo"])

        photo_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )

        # Delete photo from folder
        if os.path.isfile(photo_path):
            os.remove(photo_path)

        # Remove photo name from database
        db.execute("""
            UPDATE users
            SET profile_photo = NULL
            WHERE id = ?
        """, (session["user_id"],))

        db.commit()

        flash("Profile photo deleted successfully!")

    else:
        flash("No profile photo found.")

    return redirect(url_for("profile"))


    #edit karna par store

@app.route("/edit_profile")
@login_required
def edit_profile():

    db = get_db()

    user = db.execute("""
        SELECT id, name, email, roll_no, gender, branch, course
        FROM users
        WHERE id = ?
    """, (session["user_id"],)).fetchone()

    return render_template("edit_profile.html", user=user)


    # upadte student detail

@app.route("/update_profile", methods=["POST"])
@login_required
def update_profile():

    name = request.form.get("name", "").strip()
    roll_no = request.form.get("roll_no", "").strip()
    gender = request.form.get("gender", "").strip()
    branch = request.form.get("branch", "").strip()
    course = request.form.get("course", "").strip()

    if not name:
        flash("Name cannot be empty.")
        return redirect(url_for("profile"))

    db = get_db()

    db.execute("""
        UPDATE users
        SET name = ?, roll_no = ?, gender = ?, branch = ?, course = ?
        WHERE id = ?
    """, (
        name, roll_no, gender, branch, course,
        session["user_id"]
    ))

    db.commit()

    session["name"] = name

    flash("Profile updated successfully!")

    return redirect(url_for("profile"))

# change password-----

@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():

    if request.method == "POST":

        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        db = get_db()

        user = db.execute(
            "SELECT password FROM users WHERE id = ?",
            (session["user_id"],)
        ).fetchone()

        if not check_password_hash(user["password"], current_password):
            flash("Current password is incorrect.")
            return redirect(url_for("change_password"))

        if len(new_password) < 8:
            flash("Password must be at least 8 characters.")
            return redirect(url_for("change_password"))

        if new_password != confirm_password:
            flash("New passwords do not match.")
            return redirect(url_for("change_password"))

        hashed_password = generate_password_hash(new_password)

        
        db.execute(
            """UPDATE users
                SET password = ?, must_change_password = 0
                WHERE id = ?""",
            (hashed_password, session["user_id"])
        )

        db.commit()

        session.pop("must_change_password", None)

        flash("Password changed successfully!")


        return redirect(url_for("profile"))

    return render_template("change_password.html")




# ---------------- SUBMIT COMPLAINT ----------------


@app.route("/complaint/new", methods=["GET", "POST"])
@login_required
def submit_complaint():

    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":

        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        priority = request.form.get("priority", "Medium")
        description = request.form.get("description", "").strip()

        if not title or not category or not description:
            flash("Please fill all fields.")
            return redirect(url_for("submit_complaint"))

        # Get uploaded photo
        photo = request.files.get("complaint_photo")
        photo_filename = None

        if photo and photo.filename:

            if "." not in photo.filename:
                flash("Invalid photo file.")
                return redirect(url_for("submit_complaint"))

            extension = photo.filename.rsplit(".", 1)[1].lower()

            if extension not in ALLOWED_COMPLAINT_EXTENSIONS:
                flash("Only JPG, JPEG, PNG and WEBP photos are allowed.")
                return redirect(url_for("submit_complaint"))

            safe_name = secure_filename(photo.filename)

            photo_filename = secrets.token_hex(8) + "_" + safe_name

            photo_path = os.path.join(
                COMPLAINT_UPLOAD_FOLDER,
                photo_filename
            )

            photo.save(photo_path)

        db = get_db()

        db.execute("""
            INSERT INTO complaints
            (user_id, title, category, description, priority, photo)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            title,
            category,
            description,
            priority,
            photo_filename
        ))

        db.commit()

        flash("Complaint submitted successfully!")

        return redirect(url_for("complaints"))

    return render_template("submit_complaint.html")



# ---------------- STUDENT COMPLAINTS ----------------


@app.route("/complaints")
@login_required
def complaints():

    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))

    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()
    priority = request.args.get("priority", "").strip()

    db = get_db()

    query = """
        SELECT * FROM complaints
        WHERE user_id = ?
    """

    params = [session["user_id"]]

    # Search by complaint title
    if search:
        query += " AND title LIKE ?"
        params.append(f"%{search}%")

    # Filter by status
    if status in ["Pending", "In Progress", "Resolved"]:
        query += " AND status = ?"
        params.append(status)

    # Filter by priority
    if priority in ["Low", "Medium", "High"]:
        query += " AND priority = ?"
        params.append(priority)

    query += " ORDER BY id DESC"

    records = db.execute(query, params).fetchall()

    history = db.execute("""
        SELECT complaint_history.*
        FROM complaint_history
        JOIN complaints
        ON complaint_history.complaint_id = complaints.id
        WHERE complaints.user_id = ?
        ORDER BY complaint_history.updated_at ASC
    """, (session["user_id"],)).fetchall()

    return render_template(
        "complaints.html",
        complaints=records,
        search=search,
        selected_status=status,
        selected_priority=priority,
        history=history
    )



# ---------------- COLLEGE NOTICES ----------------


@app.route("/notices")
@login_required
def notices():

    db = get_db()

    # Add category column if it does not exist
    columns = db.execute("PRAGMA table_info(notices)").fetchall()

    if not any(column[1] == "category" for column in columns):
        db.execute("""
            ALTER TABLE notices
            ADD COLUMN category TEXT DEFAULT 'Academic'
        """)
        db.commit()

    category = request.args.get("category", "").strip()

    if category in ["Academic", "Examination", "Events"]:
        records = db.execute("""
            SELECT *
            FROM notices
            WHERE category = ?
            ORDER BY id DESC
        """, (category,)).fetchall()
    else:
        records = db.execute("""
            SELECT *
            FROM notices
            ORDER BY id DESC
        """).fetchall()

    return render_template(
        "notices.html",
        notices=records,
        selected_category=category
    )



# ---------------- ADMIN DASHBOARD ----------------



@app.route("/admin")
@admin_required
def admin_dashboard():

    db = get_db()

    # All complaints
    records = db.execute("""
        SELECT complaints.*, users.name, users.email
        FROM complaints
        JOIN users ON complaints.user_id = users.id
        ORDER BY complaints.id DESC
    """).fetchall()

    # Registered students
    students = db.execute("""
        SELECT id, name, username, email, roll_no, gender, branch, course
        FROM users
        WHERE role = 'student'
        ORDER BY branch, course, name
    """).fetchall()

    # Branch-wise students
    branches = db.execute("""
        SELECT DISTINCT branch
        FROM users
        WHERE role = 'student'
        ORDER BY branch
    """).fetchall()

    # Course-wise students
    courses = db.execute("""
        SELECT DISTINCT course
        FROM users
        WHERE role = 'student'
        ORDER BY course
    """).fetchall()

    # Dashboard statistics
    total_students = len(students)
    total_complaints = db.execute(
        "SELECT COUNT(*) FROM complaints"
    ).fetchone()[0]

    pending_complaints = db.execute(
        "SELECT COUNT(*) FROM complaints WHERE status = 'Pending'"
    ).fetchone()[0]

    progress_complaints = db.execute(
        "SELECT COUNT(*) FROM complaints WHERE status = 'In Progress'"
    ).fetchone()[0]

    resolved_complaints = db.execute(
        "SELECT COUNT(*) FROM complaints WHERE status = 'Resolved'"
    ).fetchone()[0]

    # Recent notices
    recent_notices = db.execute("""
        SELECT *
        FROM notices
        ORDER BY id DESC
        LIMIT 5
    """).fetchall()

    return render_template(
        "admin_dashboard.html",
        complaints=records,
        students=students,
        total_students=total_students,
        branches=branches,
        courses=courses,
        total_complaints=total_complaints,
        pending_complaints=pending_complaints,
        progress_complaints=progress_complaints,
        resolved_complaints=resolved_complaints,
        recent_notices=recent_notices
    )



@app.route("/delete-student/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def delete_student(user_id):

    db = get_db()

    # Student account check
    student = db.execute(
        "SELECT id FROM users WHERE id = ? AND role = 'student'",
        (user_id,)
    ).fetchone()

    if student is None:
        flash("Student account not found!")
        return redirect(url_for("admin_dashboard"))

    # Delete only student account
    db.execute(
        "DELETE FROM users WHERE id = ? AND role = 'student'",
        (user_id,)
    )

    db.commit()

    flash("Student account deleted successfully!")
    return redirect(url_for("admin_dashboard"))


@app.route("/delete-complaint/<int:complaint_id>", methods=["POST"])
@login_required
@admin_required
def delete_complaint(complaint_id):

    db = get_db()

    db.execute(
        "DELETE FROM complaints WHERE id = ?",
        (complaint_id,)
    )

    db.commit()

    flash("Complaint deleted successfully!")
    return redirect(url_for("admin_dashboard"))


@app.route("/edit-complaint/<int:complaint_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_complaint(complaint_id):

    db = get_db()

    complaint = db.execute(
        "SELECT * FROM complaints WHERE id = ?",
        (complaint_id,)
    ).fetchone()

    if complaint is None:
        flash("Complaint not found!")
        return redirect(url_for("admin_complaints"))

    if request.method == "POST":

        title = request.form["title"]
        category = request.form["category"]
        description = request.form["description"]

        db.execute("""
            UPDATE complaints
            SET title = ?, category = ?, description = ?
            WHERE id = ?
        """, (title, category, description, complaint_id))

        db.commit()

        flash("Complaint updated successfully!")
        return redirect(url_for("admin_complaints"))

    return render_template(
        "edit_complaint.html",
        complaint=complaint
    )



@app.route("/admin/complaints")
@login_required
@admin_required
def admin_complaints():

    db = get_db()

    complaints = db.execute("""
        SELECT complaints.*, users.name, users.email
        FROM complaints
        JOIN users ON complaints.user_id = users.id
        ORDER BY complaints.id DESC
    """).fetchall()

    total_complaints = db.execute(
        "SELECT COUNT(*) FROM complaints"
    ).fetchone()[0]

    pending_complaints = db.execute(
        "SELECT COUNT(*) FROM complaints WHERE status = 'Pending'"
    ).fetchone()[0]

    progress_complaints = db.execute(
        "SELECT COUNT(*) FROM complaints WHERE status = 'In Progress'"
    ).fetchone()[0]

    resolved_complaints = db.execute(
        "SELECT COUNT(*) FROM complaints WHERE status = 'Resolved'"
    ).fetchone()[0]

    return render_template(
        "admin_complaints.html",
        complaints=complaints,
        total_complaints=total_complaints,
        pending_complaints=pending_complaints,
        progress_complaints=progress_complaints,
        resolved_complaints=resolved_complaints
    )



@app.route("/admin/track-complaint/<int:complaint_id>")
@login_required
@admin_required
def admin_track_complaint(complaint_id):

    db = get_db()

    complaint = db.execute("""
        SELECT complaints.*, users.name, users.email
        FROM complaints
        JOIN users ON complaints.user_id = users.id
        WHERE complaints.id = ?
    """, (complaint_id,)).fetchone()

    if complaint is None:
        flash("Complaint not found!")
        return redirect(url_for("admin_complaints"))

    history = db.execute("""
        SELECT old_status, new_status, updated_at
        FROM complaint_history
        WHERE complaint_id = ?
        ORDER BY updated_at ASC, id ASC
    """, (complaint_id,)).fetchall()

    return render_template(
        "admin_track_complaint.html",
        complaint=complaint,
        history=history
    )


@app.route("/my-complaints")
@login_required
def my_complaints():

    db = get_db()

    complaints = db.execute("""
        SELECT *
        FROM complaints
        WHERE user_id = ?
        ORDER BY id DESC
    """, (session["user_id"],)).fetchall()

    complaint_history = {}

    for complaint in complaints:
        history = db.execute("""
            SELECT old_status, new_status, updated_at
            FROM complaint_history
            WHERE complaint_id = ?
            ORDER BY updated_at ASC, id ASC
        """, (complaint["id"],)).fetchall()

        complaint_history[complaint["id"]] = history

    return render_template(
        "my_complaints.html",
        complaints=complaints,
        complaint_history=complaint_history
    )


@app.route("/edit-student/<int:user_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_student(user_id):

    db = get_db()

    student = db.execute(
        "SELECT * FROM users WHERE id = ? AND role = 'student'",
        (user_id,)
    ).fetchone()

    if student is None:
        flash("Student not found!")
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        roll_no = request.form.get("roll_no", "").strip()
        gender = request.form.get("gender", "").strip()
        branch = request.form.get("branch", "").strip()
        course = request.form.get("course", "").strip()

        db.execute("""
            UPDATE users
            SET name = ?, username = ?, email = ?,
                roll_no = ?, gender = ?, branch = ?, course = ?
            WHERE id = ? AND role = 'student'
        """, (
            name, username, email,
            roll_no, gender, branch, course, user_id
        ))

        db.commit()

        flash("Student details updated successfully!")
        return redirect(url_for("admin_dashboard"))

    return render_template("edit_student.html", student=student)

@app.route("/admin/students")
@login_required
@admin_required
def admin_students():

    db = get_db()

    students = db.execute("""
        SELECT id, name, username, email, roll_no, gender, branch, course
        FROM users
        WHERE role = 'student'
        ORDER BY branch, course, name
    """).fetchall()

    return render_template(
        "admin_students.html",
        students=students
    )


# ---------------- ADMIN CREATE STUDENT ACCOUNT ----------------

@app.route("/admin/create-student", methods=["GET", "POST"])
@admin_required
def create_student():

    db = get_db()
    temporary_password = None

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        roll_no = request.form.get("roll_no", "").strip()
        gender = request.form.get("gender", "").strip()
        branch = request.form.get("branch", "").strip()
        course = request.form.get("course", "").strip()

        if not all([name, username, email, roll_no, gender, branch, course]):
            flash("Please fill all student details.")
            return redirect(url_for("create_student"))

        # Check duplicate details
        existing = db.execute("""
            SELECT id FROM users
            WHERE LOWER(email) = LOWER(?)
               OR username = ?
               OR roll_no = ?
        """, (email, username, roll_no)).fetchone()

        if existing:
            flash("Email, username or roll number already exists.")
            return redirect(url_for("create_student"))

        # Generate secure temporary password
        characters = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789@#$!"
        temporary_password = "".join(
            secrets.choice(characters) for _ in range(14)
        )

        db.execute("""
            INSERT INTO users
            (name, username, email, password, roll_no,
             gender, branch, course, role, must_change_password)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'student', 1)
        """, (
            name,
            username,
            email,
            generate_password_hash(temporary_password),
            roll_no,
            gender,
            branch,
            course
        ))

        db.commit()

        return render_template(
            "admin_create_student.html",
            temporary_password=temporary_password,
            student_name=name,
            student_email=email
        )

    return render_template("admin_create_student.html")


# ---------------- UPDATE COMPLAINT STATUS ----------------

@app.route("/admin/update/<int:complaint_id>", methods=["POST"])
@admin_required
def update_status(complaint_id):

    status = request.form.get("status")

    allowed_statuses = [
        "Pending",
        "In Progress",
        "Resolved"
    ]

    if status not in allowed_statuses:
        flash("Invalid status.")
        return redirect(url_for("admin_dashboard"))

    db = get_db()

    # Get current complaint status
    complaint = db.execute("""
        SELECT status
        FROM complaints
        WHERE id = ?
    """, (complaint_id,)).fetchone()

    if complaint is None:
        flash("Complaint not found.")
        return redirect(url_for("admin_dashboard"))

    old_status = complaint["status"]

    # Update complaint status
    db.execute("""
        UPDATE complaints
        SET status = ?
        WHERE id = ?
    """, (status, complaint_id))

    # Save status history
    if old_status != status:
        db.execute("""
            INSERT INTO complaint_history
            (complaint_id, old_status, new_status)
            VALUES (?, ?, ?)
        """, (complaint_id, old_status, status))

    db.commit()
    flash("Complaint status updated!")

    return redirect(url_for("admin_dashboard"))


# ---------------- ADD NOTICE (ADMIN) ----------------


@app.route("/admin/notice/add", methods=["POST"])
@admin_required
def add_notice():

    title = request.form.get("title", "").strip()
    message = request.form.get("message", "").strip()
    category = request.form.get("category", "").strip()

    if category not in ["Academic", "Examination", "Events"]:
        flash("Please select a valid notice category.")
        return redirect(url_for("admin_dashboard"))

    if not title or not message:
        flash("Please fill notice details.")
        return redirect(url_for("admin_dashboard"))

    db = get_db()

    # Ensure category column exists
    columns = db.execute("PRAGMA table_info(notices)").fetchall()

    if not any(column[1] == "category" for column in columns):
        db.execute("""
            ALTER TABLE notices
            ADD COLUMN category TEXT DEFAULT 'Academic'
        """)

    db.execute("""
        INSERT INTO notices (title, message, category)
        VALUES (?, ?, ?)
    """, (title, message, category))

    db.commit()

    flash("Notice published successfully!")

    return redirect(url_for("admin_dashboard"))



@app.route("/admin/delete-notice/<int:notice_id>", methods=["POST"])
@admin_required
def delete_notice(notice_id):

    db = get_db()

    notice = db.execute(
        "SELECT id FROM notices WHERE id = ?",
        (notice_id,)
    ).fetchone()

    if notice is None:
        flash("Notice not found!")
        return redirect(url_for("admin_dashboard"))

    db.execute(
        "DELETE FROM notices WHERE id = ?",
        (notice_id,)
    )

    db.commit()

    flash("Notice deleted successfully!")

    return redirect(url_for("admin_dashboard"))




    #-----------kar diya----------

def add_profile_columns():
    db = get_db()

    columns = [
        row[1] for row in db.execute(
            "PRAGMA table_info(users)"
        ).fetchall()
    ]

    new_columns = {
        "username": "TEXT",
        "roll_no": "TEXT",
        "gender": "TEXT",
        "branch": "TEXT",
        "course": "TEXT"
    }

    for column, data_type in new_columns.items():
        if column not in columns:
            db.execute(
                f"ALTER TABLE users ADD COLUMN {column} {data_type}"
            )

    db.commit()




# -----admin email -----------------


@app.route("/make-me-admin")
def make_me_admin():
    db = get_db()

    db.execute(
        "UPDATE users SET role = 'admin' WHERE LOWER(email) = LOWER(?)",
        ("Shubhambais@campus.com",)
    )

    db.commit()
    return "Shubham is now Admin!"




@app.route("/delete-team-admins", methods=["POST"])
@login_required
@admin_required
def delete_team_admins():

    db = get_db()

    emails = [
        "shubhambais@campus.com",
        "anmolhardiya@campus.com",
        "luckysinghdevda@campus.com",
        "nikhildayima@campus.com"
    ]

    for email in emails:
        db.execute(
            "DELETE FROM users WHERE LOWER(email) = LOWER(?) AND role = 'admin'",
            (email,)
        )

    db.commit()

    flash("Team Admin accounts permanently deleted!")
    return redirect(url_for("admin_dashboard"))


# ---------------- RUN APPLICATION ----------------

if __name__ == "__main__":
    with app.app_context():
        add_profile_columns()

    app.run(debug=True)
