from datetime import date

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone


@shared_task
def send_revisit_reminders():
    """Send email reminders for due/overdue revisit schedules."""
    from .models import RevisitSchedule

    today = date.today()
    due_schedules = (
        RevisitSchedule.objects
        .filter(next_revisit__lte=today)
        .select_related("user")
    )

    sent_count = 0
    for schedule in due_schedules:
        # Skip if already notified for this cycle
        if schedule.notified_at and schedule.notified_at.date() >= schedule.next_revisit:
            continue

        user = schedule.user
        if not user.email:
            continue

        days_overdue = (today - schedule.next_revisit).days
        if days_overdue == 0:
            status_text = "is due today"
        else:
            status_text = f"was due {days_overdue} day{'s' if days_overdue != 1 else ''} ago"

        base_url = "https://sponda.capital"
        ticker_url = f"{base_url}/en/{schedule.ticker}"

        plain_message = (
            f"Revisit reminder: {schedule.ticker}\n\n"
            f"Your scheduled revisit for {schedule.ticker} {status_text}.\n\n"
            f"View company: {ticker_url}\n\n"
            "---\n"
            "Sponda · sponda.capital"
        )

        html_message = (
            '<div style="font-family: Inter, system-ui, sans-serif; max-width: 480px; margin: 0 auto;">'
            '<div style="text-align: center; padding: 24px 0 16px;">'
            '<span style="font-family: Satoshi, sans-serif; font-size: 22px; font-weight: 500; color: #1b347e;">SPONDA</span>'
            '</div>'
            '<div style="background: #f5f7fa; border-radius: 8px; padding: 24px; margin: 0 16px;">'
            f'<p style="font-size: 14px; color: #0c1829; margin: 0 0 8px;">Revisit reminder</p>'
            f'<p style="font-size: 24px; font-weight: 600; color: #0c1829; margin: 0 0 16px;">{schedule.ticker}</p>'
            f'<p style="font-size: 14px; color: #5570a0; margin: 0 0 20px;">Your scheduled revisit {status_text}.</p>'
            f'<a href="{ticker_url}" style="display: inline-block; background: #1b347e; color: #ffffff; '
            f'text-decoration: none; padding: 10px 24px; border-radius: 6px; font-size: 14px; font-weight: 500;">'
            f'View {schedule.ticker}</a>'
            '</div>'
            '<p style="font-size: 11px; color: #5570a0; text-align: center; margin: 16px 0;">sponda.capital</p>'
            '</div>'
        )

        send_mail(
            subject=f"Sponda · Revisit reminder: {schedule.ticker}",
            message=plain_message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@sponda.capital"),
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=True,
        )

        schedule.notified_at = timezone.now()
        schedule.save(update_fields=["notified_at"])
        sent_count += 1

    return sent_count
