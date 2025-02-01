from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectField, IntegerField
from wtforms.validators import DataRequired, Email, EqualTo
from config import Config


app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = "login"

def init_db():
    from flask_migrate import upgrade
    with app.app_context():
        upgrade()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Workout(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False)
    start_time = db.Column(db.String(5), nullable=False)
    duration = db.Column(db.String(10), nullable=False)
    notes = db.Column(db.Text)
    user = db.relationship('User', backref=db.backref('workouts', lazy=True))


class Exercise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workout_id = db.Column(db.Integer, db.ForeignKey('workout.id'), nullable=False)
    body_part = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    sets = db.Column(db.Integer, nullable=False)
    reps = db.Column(db.Integer, nullable=False)

    workout = db.relationship('Workout', backref=db.backref('exercises', lazy=True))


class RegisterForm(FlaskForm):
    username = StringField("Nazwa użytkownika", validators=[DataRequired()])
    email = StringField("Email np.user@example.com", validators=[DataRequired(), Email()])
    password = PasswordField("Hasło",
                             validators=[DataRequired(), EqualTo("password2", message="Hasła muszą być takie same!")])
    password2 = PasswordField("Powtórz hasło", validators=[DataRequired()])
    submit = SubmitField("Zarejestruj się")


class LoginForm(FlaskForm):
    email = StringField("Email np.user@example.com", validators=[DataRequired(), Email()])
    password = PasswordField("Hasło", validators=[DataRequired()])
    submit = SubmitField("Zaloguj się")


class WorkoutForm(FlaskForm):
    date = StringField("Data", validators=[DataRequired()])
    start_time = StringField("Godzina rozpoczęcia", validators=[DataRequired()])
    duration = StringField("Czas trwania", validators=[DataRequired()])
    notes = TextAreaField("Notatki")
    submit = SubmitField("Dodaj trening")


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))



@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash("Ten adres e-mail jest już zajęty. Wybierz inny.", "danger")
            return redirect(url_for("register"))
        
        existing_username = User.query.filter_by(username=form.username.data).first()
        if existing_username:
            flash("Ta nazwa użytkownika jest już zajęta. Wybierz inną.", "danger")
            return redirect(url_for("register"))

        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("Konto utworzone! Możesz się zalogować.", "success")
        return redirect(url_for("login"))
    return render_template("register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for("dashboard"))
        flash("Błędny email lub hasło", "danger")
    return render_template("login.html", form=form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    workouts = Workout.query.filter_by(user_id=current_user.id).all()
    return render_template("dashboard.html", user=current_user, workouts=workouts)


@app.route("/add_workout", methods=["GET", "POST"])
@login_required
def add_workout():
    form = WorkoutForm()
    if form.validate_on_submit():
        workout = Workout(
            user_id=current_user.id,
            date=form.date.data,
            start_time=form.start_time.data,
            duration=form.duration.data,
            notes=form.notes.data
        )
        db.session.add(workout)
        db.session.commit()

        exercise_names = request.form.getlist('exercise_name')
        exercise_body_parts = request.form.getlist('exercise_body_part')
        exercise_sets = request.form.getlist('exercise_sets')
        exercise_reps = request.form.getlist('exercise_reps')

        for i in range(len(exercise_names)):
            if exercise_names[i].strip():
                exercise = Exercise(
                    workout_id=workout.id,
                    body_part=exercise_body_parts[i],
                    name=exercise_names[i],
                    sets=int(exercise_sets[i]),
                    reps=int(exercise_reps[i])
                )
                db.session.add(exercise)

        db.session.commit()
        flash("Trening dodany!", "success")
        return redirect(url_for("dashboard"))

    return render_template("add_workout.html", form=form)


@app.route("/workout_history")
@login_required
def workout_history():
    workouts = Workout.query.filter_by(user_id=current_user.id).all()

    for workout in workouts:
        workout.exercises = Exercise.query.filter_by(workout_id=workout.id).all()

    return render_template("workout_history.html", workouts=workouts)


@app.route("/workout/<int:workout_id>")
@login_required
def view_workout(workout_id):
    workout = Workout.query.get_or_404(workout_id)
    exercises = Exercise.query.filter_by(workout_id=workout.id).all()
    return render_template("view_workout.html", workout=workout, exercises=exercises)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)