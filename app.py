from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import date, timedelta
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "bump-house-secret-2024")

# Database config — uses DATABASE_URL from .env (Supabase/Postgres)
# Falls back to SQLite for local testing
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///bumphouse.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ── Model ──────────────────────────────────────────────────────────────────────
class Member(db.Model):
    __tablename__ = "members"

    id        = db.Column(db.Integer, primary_key=True)
    name      = db.Column(db.String(100), nullable=False)
    phone     = db.Column(db.String(20),  nullable=True)
    start     = db.Column(db.Date,        nullable=False)
    days      = db.Column(db.Integer,     nullable=False)   # subscription duration
    amount    = db.Column(db.Integer,     nullable=True)    # amount paid (EGP)
    notes     = db.Column(db.String(200), nullable=True)
    created   = db.Column(db.Date, default=date.today)

    @property
    def end_date(self):
        return self.start + timedelta(days=self.days)

    @property
    def days_left(self):
        return (self.end_date - date.today()).days

    @property
    def status(self):
        d = self.days_left
        if d < 0:   return "expired"
        if d <= 7:  return "warning"
        return "ok"

    @property
    def status_label(self):
        return {"ok": "تمام", "warning": "قرب يخلص", "expired": "خلص"}[self.status]

    @property
    def sub_label(self):
        labels = {30:"شهر", 60:"شهرين", 90:"3 شهور", 180:"6 شهور", 365:"سنة"}
        return labels.get(self.days, f"{self.days} يوم")


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "status")   # status | name | end

    query = Member.query
    if q:
        query = query.filter(Member.name.ilike(f"%{q}%"))

    members = query.all()

    # Sort in Python (status involves computed property)
    order = {"expired": 0, "warning": 1, "ok": 2}
    if sort == "name":
        members.sort(key=lambda m: m.name)
    elif sort == "end":
        members.sort(key=lambda m: m.end_date)
    else:
        members.sort(key=lambda m: (order[m.status], m.days_left))

    counts = {
        "ok":      sum(1 for m in Member.query.all() if m.status == "ok"),
        "warning": sum(1 for m in Member.query.all() if m.status == "warning"),
        "expired": sum(1 for m in Member.query.all() if m.status == "expired"),
    }

    return render_template("index.html", members=members, counts=counts, q=q, sort=sort)


@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        name  = request.form.get("name", "").strip()
        start = request.form.get("start")
        days  = request.form.get("days")

        if not name or not start or not days:
            flash("الاسم والتاريخ ونوع الاشتراك مطلوبين", "error")
            return redirect(url_for("add"))

        member = Member(
            name   = name,
            phone  = request.form.get("phone", "").strip() or None,
            start  = date.fromisoformat(start),
            days   = int(days),
            amount = int(request.form.get("amount")) if request.form.get("amount") else None,
            notes  = request.form.get("notes", "").strip() or None,
        )
        db.session.add(member)
        db.session.commit()
        flash(f"تم إضافة {name} ✓", "success")
        return redirect(url_for("index"))

    return render_template("add.html", today=date.today().isoformat())


@app.route("/member/<int:id>")
def member_detail(id):
    member = Member.query.get_or_404(id)
    return render_template("member_detail.html", member=member)


@app.route("/member/<int:id>/renew", methods=["POST"])
def renew(id):
    member = Member.query.get_or_404(id)
    days   = int(request.form.get("days", member.days))
    amount = request.form.get("amount")

    # Renew from today or from end_date, whichever is later
    new_start = max(date.today(), member.end_date)
    member.start  = new_start
    member.days   = days
    if amount:
        member.amount = int(amount)

    db.session.commit()
    flash(f"تم تجديد اشتراك {member.name} ✓", "success")
    return redirect(url_for("member_detail", id=id))


@app.route("/member/<int:id>/delete", methods=["POST"])
def delete(id):
    member = Member.query.get_or_404(id)
    name = member.name
    db.session.delete(member)
    db.session.commit()
    flash(f"تم حذف {name}", "success")
    return redirect(url_for("index"))


# ── API: expiring soon (for future notifications) ─────────────────────────────
@app.route("/api/expiring")
def api_expiring():
    members = [m for m in Member.query.all() if 0 <= m.days_left <= 7]
    return jsonify([{
        "id": m.id, "name": m.name, "phone": m.phone,
        "days_left": m.days_left, "end_date": m.end_date.isoformat()
    } for m in members])


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
