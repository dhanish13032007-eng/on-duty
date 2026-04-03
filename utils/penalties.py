from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from models import db, ODRequest, User

def evaluate_penalties(user):
    """
    Check all OD requests for the user. If an OD request is approved
    but the certificate is not verified within 1 month of the OD date,
    apply a penalty.
    """
    if not user.is_under_penalty:
        # Check all past ODs where final_status is Approved
        # but verification_status != 'Verified'
        past_ods = ODRequest.query.filter_by(student_id=user.id, final_status='Approved').all()
        for od in past_ods:
            if od.verification_status != 'Verified':
                # Check if it has been 1 month since the OD date
                one_month_ago = datetime.utcnow().date() - timedelta(days=30)
                if od.od_date < one_month_ago:
                    # Apply penalty
                    od.is_leave = True
                    user.is_under_penalty = True
                    user.penalty_end_date = datetime.utcnow() + relativedelta(months=3)
                    db.session.commit()
                    break

    # If user is under penalty, check if it has expired
    if user.is_under_penalty and user.penalty_end_date:
        if datetime.utcnow() > user.penalty_end_date:
            user.is_under_penalty = False
            user.penalty_end_date = None
            db.session.commit()
