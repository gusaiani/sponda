from datetime import date

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

# Human-readable labels for indicator names. Used in alert email subjects and
# bodies so users see "Debt / Equity ≤ 1.0" instead of "debt_to_equity lte 1.0".
INDICATOR_LABELS = {
    "pe10": "PE10",
    "pfcf10": "P/FCF10",
    "peg": "PEG",
    "pfcf_peg": "P/FCF PEG",
    "debt_to_equity": "Debt / Equity",
    "debt_ex_lease_to_equity": "Debt (ex-lease) / Equity",
    "liabilities_to_equity": "Liabilities / Equity",
    "current_ratio": "Current Ratio",
    "debt_to_avg_earnings": "Debt / Avg Earnings",
    "debt_to_avg_fcf": "Debt / Avg FCF",
    "market_cap": "Market Cap",
}


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


def _format_threshold(value):
    """Render a Decimal threshold without trailing zeros for email display."""
    normalized = value.normalize() if hasattr(value, "normalize") else value
    text = f"{normalized:f}" if hasattr(normalized, "__format__") else str(normalized)
    # Strip trailing zeros after a decimal point, but keep integers as-is.
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _build_alert_email(alert, indicator_value):
    """Return (subject, plain_body, html_body) for a triggered alert."""
    label = INDICATOR_LABELS.get(alert.indicator, alert.indicator)
    operator = "≤" if alert.comparison == "lte" else "≥"
    threshold_text = _format_threshold(alert.threshold)
    value_text = _format_threshold(indicator_value)
    ticker_url = f"https://sponda.capital/en/{alert.ticker}"

    subject = f"Sponda · {alert.ticker} · {label} {operator} {threshold_text}"
    plain_body = (
        f"Indicator alert: {alert.ticker}\n\n"
        f"{label} is {value_text} ({operator} {threshold_text}).\n\n"
        f"View company: {ticker_url}\n\n"
        "---\n"
        "Sponda · sponda.capital"
    )
    html_body = (
        '<div style="font-family: Inter, system-ui, sans-serif; max-width: 480px; margin: 0 auto;">'
        '<div style="text-align: center; padding: 24px 0 16px;">'
        '<span style="font-family: Satoshi, sans-serif; font-size: 22px; font-weight: 500; color: #1b347e;">SPONDA</span>'
        '</div>'
        '<div style="background: #f5f7fa; border-radius: 8px; padding: 24px; margin: 0 16px;">'
        '<p style="font-size: 14px; color: #0c1829; margin: 0 0 8px;">Indicator alert</p>'
        f'<p style="font-size: 24px; font-weight: 600; color: #0c1829; margin: 0 0 16px;">{alert.ticker}</p>'
        f'<p style="font-size: 14px; color: #5570a0; margin: 0 0 20px;">'
        f'{label} is <strong>{value_text}</strong> ({operator} {threshold_text}).'
        '</p>'
        f'<a href="{ticker_url}" style="display: inline-block; background: #1b347e; color: #ffffff; '
        'text-decoration: none; padding: 10px 24px; border-radius: 6px; font-size: 14px; font-weight: 500;">'
        f'View {alert.ticker}</a>'
        '</div>'
        '<p style="font-size: 11px; color: #5570a0; text-align: center; margin: 16px 0;">sponda.capital</p>'
        '</div>'
    )
    return subject, plain_body, html_body


@shared_task
def check_indicator_alerts():
    """Evaluate every active alert against the latest indicator snapshot.

    One-shot behaviour: when a condition is met the task emails the user,
    creates an in-app AlertNotification, and deletes the IndicatorAlert.
    Alerts whose condition is *not* met are left untouched.

    Returns a dict with ``triggered``, ``emails_sent`` counts so the
    management command can surface them.
    """
    from quotes.models import IndicatorSnapshot

    from .models import AlertNotification, IndicatorAlert

    active_alerts = list(
        IndicatorAlert.objects.filter(active=True).select_related("user"),
    )

    tickers = {alert.ticker for alert in active_alerts}
    snapshots = {
        snapshot.ticker: snapshot
        for snapshot in IndicatorSnapshot.objects.filter(ticker__in=tickers)
    }

    triggered_count = 0
    emails_sent = 0
    triggered_ids = []

    for alert in active_alerts:
        snapshot = snapshots.get(alert.ticker)
        if snapshot is None:
            continue
        indicator_value = getattr(snapshot, alert.indicator, None)
        if not alert.is_triggered_by(indicator_value):
            continue

        AlertNotification.objects.create(
            user=alert.user,
            ticker=alert.ticker,
            indicator=alert.indicator,
            comparison=alert.comparison,
            threshold=alert.threshold,
            indicator_value=indicator_value,
        )
        triggered_count += 1
        triggered_ids.append(alert.pk)

        if alert.user.email:
            subject, plain_body, html_body = _build_alert_email(alert, indicator_value)
            send_mail(
                subject=subject,
                message=plain_body,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@sponda.capital"),
                recipient_list=[alert.user.email],
                html_message=html_body,
                fail_silently=True,
            )
            emails_sent += 1

    if triggered_ids:
        IndicatorAlert.objects.filter(pk__in=triggered_ids).delete()

    return {
        "triggered": triggered_count,
        "emails_sent": emails_sent,
    }
