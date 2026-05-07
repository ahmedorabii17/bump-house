from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import date, timedelta
from dotenv import load_dotenv
from functools import wraps
import csv, io, os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "pump-house-secret-2024")

# Database config
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///pumphouse.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ── Login credentials from env ─────────────────────────────────────────────────
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "coach")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "pumphouse2024")


# ── Login required decorator ───────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ── Model ──────────────────────────────────────────────────────────────────────
class Member(db.Model):
    __tablename__ = "members"

    id      = db.Column(db.Integer, primary_key=True)
    name    = db.Column(db.String(100), nullable=False)
    phone   = db.Column(db.String(20),  nullable=True)
    start   = db.Column(db.Date,        nullable=False)
    days    = db.Column(db.Integer,     nullable=False)
    amount  = db.Column(db.Integer,     nullable=True)
    notes   = db.Column(db.String(200), nullable=True)
    created = db.Column(db.Date, default=date.today)

    @property
    def end_date(self):
        return self.start + timedelta(days=self.days)

    @property
    def days_left(self):
        return (self.end_date - date.today()).days

    @property
    def status(self):
        d = self.days_left
        if d < 0:  return "expired"
        if d <= 7: return "warning"
        return "ok"

    @property
    def status_label(self):
        return {"ok": "تمام", "warning": "قرب يخلص", "expired": "خلص"}[self.status]

    @property
    def sub_label(self):
        labels = {30: "شهر", 60: "شهرين", 90: "3 شهور", 180: "6 شهور", 365: "سنة"}
        return labels.get(self.days, f"{self.days} يوم")


# ── Auth routes ────────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        flash("اسم المستخدم أو كلمة السر غلط", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── Main routes ────────────────────────────────────────────────────────────────
@app.route("/")
@login_required
def index():
    q    = request.args.get("q", "").strip()
    sort = request.args.get("sort", "status")

    query = Member.query
    if q:
        query = query.filter(Member.name.ilike(f"%{q}%"))

    members = query.all()

    order = {"expired": 0, "warning": 1, "ok": 2}
    if sort == "name":
        members.sort(key=lambda m: m.name)
    elif sort == "end":
        members.sort(key=lambda m: m.end_date)
    else:
        members.sort(key=lambda m: (order[m.status], m.days_left))

    all_members = Member.query.all()
    counts = {
        "ok":      sum(1 for m in all_members if m.status == "ok"),
        "warning": sum(1 for m in all_members if m.status == "warning"),
        "expired": sum(1 for m in all_members if m.status == "expired"),
        "total":   len(all_members),
    }

    return render_template("index.html", members=members, counts=counts, q=q, sort=sort)


@app.route("/add", methods=["GET", "POST"])
@login_required
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
@login_required
def member_detail(id):
    member = Member.query.get_or_404(id)
    return render_template("member_detail.html", member=member)


@app.route("/member/<int:id>/renew", methods=["POST"])
@login_required
def renew(id):
    member    = Member.query.get_or_404(id)
    days      = int(request.form.get("days", member.days))
    amount    = request.form.get("amount")
    new_start = request.form.get("new_start")

    if not new_start:
        flash("لازم تحدد تاريخ التجديد", "error")
        return redirect(url_for("member_detail", id=id))

    member.start = date.fromisoformat(new_start)
    member.days  = days
    if amount:
        member.amount = int(amount)

    db.session.commit()
    flash(f"تم تجديد اشتراك {member.name} ✓", "success")
    return redirect(url_for("member_detail", id=id))


@app.route("/member/<int:id>/delete", methods=["POST"])
@login_required
def delete(id):
    member = Member.query.get_or_404(id)
    name   = member.name
    db.session.delete(member)
    db.session.commit()
    flash(f"تم حذف {name}", "success")
    return redirect(url_for("index"))


# ── CSV Export ─────────────────────────────────────────────────────────────────
@app.route("/export/csv")
@login_required
def export_csv():
    members = Member.query.order_by(Member.name).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["الاسم", "الموبايل", "بداية الاشتراك", "نهاية الاشتراك",
                     "نوع الاشتراك", "المبلغ", "الحالة", "باقي (أيام)", "ملاحظات"])

    for m in members:
        writer.writerow([
            m.name,
            m.phone or "",
            m.start.strftime("%d/%m/%Y"),
            m.end_date.strftime("%d/%m/%Y"),
            m.sub_label,
            m.amount or "",
            m.status_label,
            m.days_left,
            m.notes or "",
        ])

    output.seek(0)
    filename = f"pump_house_{date.today().isoformat()}.csv"
    return Response(
        "\ufeff" + output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ── API ────────────────────────────────────────────────────────────────────────
@app.route("/api/expiring")
@login_required
def api_expiring():
    members = [m for m in Member.query.all() if 0 <= m.days_left <= 7]
    return jsonify([{
        "id": m.id, "name": m.name, "phone": m.phone,
        "days_left": m.days_left, "end_date": m.end_date.isoformat()
    } for m in members])


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
