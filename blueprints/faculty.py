"""Faculty Blueprint: applying for leaves."""
from datetime import date
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from extensions import db
from models import LeaveApplication
from blueprints.decorators import roles_required
from models import ROLE_FACULTY

faculty_bp = Blueprint("faculty", __name__, url_prefix="/faculty")

@faculty_bp.route("/leaves", methods=["GET", "POST"])
@login_required
@roles_required(ROLE_FACULTY)
def leaves():
    if request.method == "POST":
        start_date_str = request.form.get("start_date")
        end_date_str = request.form.get("end_date")
        reason = request.form.get("reason", "").strip()
        
        try:
            start_date = date.fromisoformat(start_date_str)
            end_date = date.fromisoformat(end_date_str)
            
            if start_date > end_date:
                flash("End date must be after start date.", "danger")
            elif not reason:
                flash("Reason is required.", "danger")
            else:
                leave = LeaveApplication(
                    user_id=current_user.id,
                    start_date=start_date,
                    end_date=end_date,
                    reason=reason
                )
                db.session.add(leave)
                db.session.commit()
                flash("Leave application submitted successfully.", "success")
                return redirect(url_for("faculty.leaves"))
        except (ValueError, TypeError):
            flash("Invalid dates provided.", "danger")
            
    # GET: show leave history
    my_leaves = LeaveApplication.query.filter_by(user_id=current_user.id).order_by(LeaveApplication.created_at.desc()).all()
    return render_template("faculty/leaves.html", leaves=my_leaves, today=date.today().isoformat())
