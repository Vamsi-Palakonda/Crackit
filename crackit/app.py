import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, session, url_for
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "devsecret")

MONGO_URI = os.environ.get("MONGO_URI")
if not MONGO_URI:
    raise ValueError("No MONGO_URI set in environment variables")

client = MongoClient(MONGO_URI)
db = client["questionbank"]
questions_collection = db["questions"]
users_collection = db["users"]


# ------------------ HOME PAGE ------------------
@app.route("/")
def home():
    companies = questions_collection.distinct("company")
    company_data = []

    for company in companies:
        count = questions_collection.count_documents({"company": company})
        company_data.append({
            "name": company,
            "count": count
        })

    return render_template("index.html", companies=company_data)


# ------------------ COMPANY PAGE ------------------
@app.route("/company/<company_name>")
def company(company_name):
    company_name = company_name.upper()
    questions = list(questions_collection.find({"company": company_name}))
    return render_template("company.html",
                           questions=questions,
                           company=company_name)


# ------------------ LOGIN ------------------
@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():

    # HARD CODED SUPER ADMIN
    super_username = "questionadmin"
    super_password_hash = "scrypt:32768:8:1$xW4InlOMW1ERy2Xc$f58c62e679bd5db03a0dab17acc5800873ed1c931f6758fb300b169cafbd6038e53c660c804a49b8f68531a9b23ec76994548f11fbf02dcecccbb4a0ba2af716"

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # CHECK SUPER ADMIN
        if username == super_username and check_password_hash(super_password_hash, password):
            session["username"] = username
            session["role"] = "super_admin"
            return redirect(url_for("dashboard"))

        # CHECK EDITORS FROM DB
        user = users_collection.find_one({"username": username})

        if user and check_password_hash(user["password"], password):
            session["username"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))

        return "Invalid Credentials"

    return render_template("login.html")


# ------------------ DASHBOARD ------------------
@app.route("/dashboard")
def dashboard():
    if not session.get("username"):
        return redirect(url_for("admin_login"))

    questions = questions_collection.find().sort("created_at", -1)

    return render_template("dashboard.html",
                           questions=questions,
                           role=session.get("role"))


# ------------------ ADD QUESTION ------------------
@app.route("/add-question", methods=["GET", "POST"])
def add_question():
    if not session.get("username"):
        return redirect(url_for("admin_login"))

    companies = questions_collection.distinct("company")

    if request.method == "POST":
        company = request.form.get("company").strip().upper()
        category = request.form.get("category")
        difficulty = request.form.get("difficulty")
        question = request.form.get("question")

        questions_collection.insert_one({
            "company": company,
            "category": category if category else "General",
            "difficulty": difficulty if difficulty else "Medium",
            "question": question.strip(),
            "created_at": datetime.utcnow()
        })

        return redirect(url_for("dashboard"))

    return render_template("add_question.html", companies=companies)


# ------------------ EDIT QUESTION (SUPER ADMIN ONLY) ------------------
@app.route("/edit-question/<id>", methods=["GET", "POST"])
def edit_question(id):
    if session.get("role") != "super_admin":
        return "Unauthorized"

    question = questions_collection.find_one({"_id": ObjectId(id)})

    if request.method == "POST":
        updated_company = request.form.get("company").strip().upper()
        updated_category = request.form.get("category")
        updated_question = request.form.get("question")

        questions_collection.update_one(
            {"_id": ObjectId(id)},
            {"$set": {
                "company": updated_company,
                "category": updated_category,
                "question": updated_question
            }}
        )

        return redirect(url_for("dashboard"))

    return render_template("edit_question.html", question=question)


# ------------------ DELETE QUESTION (SUPER ADMIN ONLY) ------------------
@app.route("/delete-question/<id>")
def delete_question(id):
    if session.get("role") != "super_admin":
        return "Unauthorized"

    questions_collection.delete_one({"_id": ObjectId(id)})
    return redirect(url_for("dashboard"))


# ------------------ EDIT COMPANY (SUPER ADMIN ONLY) ------------------
@app.route("/edit-company/<company_name>", methods=["POST"])
def edit_company(company_name):
    if session.get("role") != "super_admin":
        return "Unauthorized"

    new_name = request.form.get("new_name").strip().upper()

    questions_collection.update_many(
        {"company": company_name},
        {"$set": {"company": new_name}}
    )

    return redirect(url_for("dashboard"))


# ------------------ DELETE COMPANY (SUPER ADMIN ONLY) ------------------
@app.route("/delete-company/<company_name>")
def delete_company(company_name):
    if session.get("role") != "super_admin":
        return "Unauthorized"

    questions_collection.delete_many({"company": company_name})
    return redirect(url_for("dashboard"))


# ------------------ CREATE EDITOR (SUPER ADMIN ONLY) ------------------
@app.route("/create-user", methods=["GET", "POST"])
def create_user():
    if session.get("role") != "super_admin":
        return "Unauthorized"

    if request.method == "POST":
        username = request.form.get("username")
        password = generate_password_hash(request.form.get("password"))
        role = request.form.get("role")  # editor or super_admin

        users_collection.insert_one({
            "username": username,
            "password": password,
            "role": role
        })

        return redirect(url_for("dashboard"))

    return render_template("create_user.html")


# ------------------ LOGOUT ------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)