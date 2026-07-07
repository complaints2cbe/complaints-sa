import os
from datetime import datetime, timezone

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from werkzeug.security import check_password_hash, generate_password_hash
from wtforms import PasswordField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Optional

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///" + os.path.join(os.path.dirname(os.path.abspath(__file__)), "complaints.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "info"


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class ComplaintForm(FlaskForm):
    name = StringField("Your Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    subject = StringField("Subject", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField("Description", validators=[DataRequired(), Length(min=10, max=5000)])
    submit = SubmitField("Submit Complaint")


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(max=80)])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign In")


class StatusForm(FlaskForm):
    status = SelectField(
        "Status",
        choices=[("pending", "Pending"), ("in_progress", "In Progress"), ("resolved", "Resolved")],
        validators=[DataRequired()],
    )
    submit = SubmitField("Update")


def init_db():
    db.create_all()
    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin")
        admin.set_password("admin")
        db.session.add(admin)
        db.session.commit()


@app.route("/", methods=["GET", "POST"])
def index():
    form = ComplaintForm()
    if form.validate_on_submit():
        complaint = Complaint(
            name=form.name.data.strip(),
            email=form.email.data.strip(),
            subject=form.subject.data.strip(),
            description=form.description.data.strip(),
        )
        db.session.add(complaint)
        db.session.commit()
        flash(f"Complaint #{complaint.id} submitted successfully. We'll be in touch soon.", "success")
        return redirect(url_for("index"))
    return render_template("index.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get("next")
            return redirect(next_page or url_for("admin"))
        flash("Invalid username or password.", "error")
    return render_template("login.html", form=form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin():
    status_form = StatusForm()
    if request.method == "POST" and status_form.validate_on_submit():
        complaint_id = request.form.get("complaint_id", type=int)
        complaint = db.session.get(Complaint, complaint_id)
        if complaint:
            complaint.status = status_form.status.data
            db.session.commit()
            flash(f"Complaint #{complaint.id} marked as {complaint.status.replace('_', ' ')}.", "success")
        return redirect(url_for("admin"))

    complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()
    return render_template("admin.html", complaints=complaints, status_form=status_form)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        # Create default admin if not exists
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin")
            admin.set_password("Pureobject2026!")
            db.session.add(admin)
            db.session.commit()
    app.run(debug=True)
