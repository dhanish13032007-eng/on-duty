from flask import current_app
from flask_mail import Mail, Message

mail = Mail()

def send_application_email(od_request):
    """Send notification to HOD & Admin when a new OD is submitted."""
    try:
        student = od_request.student
        subject = f"[Smart OD] New OD Application — {student.name}"
        body = f"""
A new On-Duty application has been submitted.

Student Details:
  Name        : {student.name}
  Reg. No.    : {student.username}
  Department  : {student.department}
  Section     : {student.section or 'N/A'}
  Year        : {student.year or 'N/A'}
  Batch       : {student.batch_number or 'N/A'}
  Email       : {student.email}

Event Details:
  Event Name  : {od_request.event_name}
  College     : {od_request.college_name}
  OD Date     : {od_request.od_date.strftime('%d %B %Y')} ({od_request.od_day})
  No. of Days : {od_request.number_of_days}

Please log in to the Smart OD portal to review and approve/reject this request.

— Smart OD Management System
"""
        recipients = []
        hod_email   = current_app.config.get('HOD_EMAIL')
        admin_email  = current_app.config.get('ADMIN_EMAIL')
        if hod_email:   recipients.append(hod_email)
        if admin_email: recipients.append(admin_email)
        # Also CC student
        recipients.append(student.email)

        if current_app.config.get('MAIL_USERNAME'):
            msg = Message(subject=subject, recipients=recipients, body=body)
            mail.send(msg)
            print(f"[Email Sent] OD application notification to {recipients}")
        else:
            # Fallback: print to console if mail not configured
            print(f"\n{'='*55}")
            print(f"[EMAIL — Not configured, printing to console]")
            print(f"To: {recipients}")
            print(f"Subject: {subject}")
            print(body)
            print('='*55 + '\n')

    except Exception as e:
        print(f"[Email Error] {e}")


def send_reminder_email(user, od_request):
    """Send reminder to student to upload certificate."""
    try:
        subject = f"[Smart OD] Reminder: Upload Certificate for {od_request.event_name}"
        body = f"""
Dear {user.name},

This is a reminder that you have not yet uploaded your certificate for the following OD:

  Event  : {od_request.event_name}
  College: {od_request.college_name}
  Date   : {od_request.od_date.strftime('%d %B %Y')}

⚠ IMPORTANT: Failure to upload your certificate within 1 month of the OD date will
result in your OD being converted to Leave and a 3-month penalty where you will not
be able to apply for any OD.

Please log in and upload your certificate immediately.

— Smart OD Management System
"""
        if current_app.config.get('MAIL_USERNAME'):
            msg = Message(subject=subject, recipients=[user.email], body=body)
            mail.send(msg)
            print(f"[Email Sent] Reminder to {user.email}")
        else:
            print(f"\n{'='*55}")
            print(f"[REMINDER EMAIL — Console]")
            print(f"To: {user.email}")
            print(f"Subject: {subject}")
            print(body)
            print('='*55 + '\n')

    except Exception as e:
        print(f"[Email Error] {e}")


def send_status_email(user, od_request, status):
    """Notify student when their OD is approved or rejected."""
    try:
        subject = f"[Smart OD] OD {status} — {od_request.event_name}"
        body = f"""
Dear {user.name},

Your OD application has been {status.lower()}.

  Event  : {od_request.event_name}
  College: {od_request.college_name}
  Date   : {od_request.od_date.strftime('%d %B %Y')}
  Status : {status}

{'Please log in and upload your certificate after the event.' if status == 'Approved' else 'Please contact your HOD or Admin for more information.'}

— Smart OD Management System
"""
        if current_app.config.get('MAIL_USERNAME'):
            msg = Message(subject=subject, recipients=[user.email], body=body)
            mail.send(msg)
        else:
            print(f"\n[STATUS EMAIL] To: {user.email} | Status: {status}\n")

    except Exception as e:
        print(f"[Email Error] {e}")
