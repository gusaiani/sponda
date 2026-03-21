#!/usr/bin/env python3
"""Generate the Sponda setup guide PDF."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    HRFlowable,
)

OUTPUT_PATH = "sponda-setup-guide.pdf"

BLUE = HexColor("#1e40af")
DARK = HexColor("#0c1829")
MUTED = HexColor("#5570a0")
BORDER = HexColor("#d0daea")
HIGHLIGHT_BG = HexColor("#fef3c7")  # amber-100
HIGHLIGHT_BORDER = HexColor("#f59e0b")  # amber-500
GREEN_BG = HexColor("#dcfce7")
GREEN_BORDER = HexColor("#16a34a")

styles = getSampleStyleSheet()

TITLE_STYLE = ParagraphStyle(
    "CustomTitle",
    parent=styles["Title"],
    fontSize=22,
    textColor=DARK,
    spaceAfter=6 * mm,
    fontName="Helvetica-Bold",
)

H1 = ParagraphStyle(
    "H1",
    parent=styles["Heading1"],
    fontSize=16,
    textColor=DARK,
    spaceBefore=8 * mm,
    spaceAfter=3 * mm,
    fontName="Helvetica-Bold",
)

H2 = ParagraphStyle(
    "H2",
    parent=styles["Heading2"],
    fontSize=13,
    textColor=BLUE,
    spaceBefore=6 * mm,
    spaceAfter=2 * mm,
    fontName="Helvetica-Bold",
)

BODY = ParagraphStyle(
    "Body",
    parent=styles["Normal"],
    fontSize=10,
    textColor=DARK,
    spaceAfter=2 * mm,
    leading=14,
)

CODE = ParagraphStyle(
    "Code",
    parent=styles["Normal"],
    fontSize=9,
    fontName="Courier",
    textColor=DARK,
    spaceAfter=2 * mm,
    leftIndent=10 * mm,
    leading=13,
    backColor=HexColor("#f1f5f9"),
)

BULLET = ParagraphStyle(
    "Bullet",
    parent=BODY,
    leftIndent=10 * mm,
    bulletIndent=5 * mm,
    spaceAfter=1 * mm,
)


def claude_can_do_banner():
    """Yellow banner: CLAUDE CAN DO THIS FOR YOU."""
    data = [
        [
            Paragraph(
                '<b>⚡ CLAUDE CAN DO THIS FOR YOU</b> — Give Claude the API key/credentials '
                "and ask it to configure this step.",
                ParagraphStyle("banner", parent=BODY, fontSize=10, textColor=HexColor("#92400e")),
            )
        ]
    ]
    return Table(
        data,
        colWidths=[170 * mm],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), HIGHLIGHT_BG),
                ("BOX", (0, 0), (-1, -1), 1, HIGHLIGHT_BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        ),
    )


def human_only_banner():
    """Green banner: requires human action."""
    data = [
        [
            Paragraph(
                "<b>👤 REQUIRES HUMAN ACTION</b> — This step must be done by you in a browser "
                "or external dashboard. Claude cannot do it.",
                ParagraphStyle("banner", parent=BODY, fontSize=10, textColor=HexColor("#166534")),
            )
        ]
    ]
    return Table(
        data,
        colWidths=[170 * mm],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), GREEN_BG),
                ("BOX", (0, 0), (-1, -1), 1, GREEN_BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        ),
    )


def env_table(rows):
    """Table of environment variable = value."""
    header = [
        Paragraph("<b>Variable</b>", ParagraphStyle("th", parent=BODY, fontSize=9, fontName="Helvetica-Bold")),
        Paragraph("<b>Value / Description</b>", ParagraphStyle("th", parent=BODY, fontSize=9, fontName="Helvetica-Bold")),
    ]
    data = [header]
    for var, desc in rows:
        data.append(
            [
                Paragraph(f"<font name='Courier' size='9'>{var}</font>", BODY),
                Paragraph(desc, ParagraphStyle("td", parent=BODY, fontSize=9)),
            ]
        )
    return Table(
        data,
        colWidths=[55 * mm, 115 * mm],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#e2e8f0")),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        ),
    )


def build():
    doc = SimpleDocTemplate(
        OUTPUT_PATH,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    story = []

    # ── Title page ──
    story.append(Spacer(1, 30 * mm))
    story.append(Paragraph("SPONDA", ParagraphStyle("logo", parent=TITLE_STYLE, fontSize=36, textColor=BLUE)))
    story.append(Paragraph("Setup &amp; Service Connection Guide", TITLE_STYLE))
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("Everything you need to configure for local development and production deployment.", BODY))
    story.append(Spacer(1, 10 * mm))
    story.append(HRFlowable(width="100%", color=BORDER))
    story.append(Spacer(1, 5 * mm))

    # Legend
    story.append(Paragraph("<b>Legend</b>", H2))
    story.append(claude_can_do_banner())
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("Steps marked with this banner can be completed by Claude if you provide the credentials.", BODY))
    story.append(Spacer(1, 2 * mm))
    story.append(human_only_banner())
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("Steps marked with this banner require you to act in a browser or external service.", BODY))

    story.append(PageBreak())

    # ── TABLE OF CONTENTS ──
    story.append(Paragraph("Table of Contents", H1))
    toc_items = [
        "1. Local Development Quick Start",
        "2. Email Service (Resend via SMTP)",
        "3. Google OAuth",
        "4. Production Environment Variables",
        "5. Production Deployment",
        "6. Create Superuser (Admin Dashboard)",
        "7. DNS &amp; Domain Verification (Resend)",
        "8. Complete .env Reference",
        "9. Verification Checklist",
    ]
    for item in toc_items:
        story.append(Paragraph(item, BULLET))
    story.append(Spacer(1, 5 * mm))

    # ════════════════════════════════════════
    # 1. LOCAL DEV
    # ════════════════════════════════════════
    story.append(Paragraph("1. Local Development Quick Start", H1))
    story.append(claude_can_do_banner())
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("Most of this is already configured. Locally, emails print to the console and SQLite is used.", BODY))

    story.append(Paragraph("1.1  Start the backend", H2))
    story.append(Paragraph("cd backend", CODE))
    story.append(Paragraph("DJANGO_SETTINGS_MODULE=config.settings.development python manage.py migrate", CODE))
    story.append(Paragraph("DJANGO_SETTINGS_MODULE=config.settings.development python manage.py runserver", CODE))

    story.append(Paragraph("1.2  Start the frontend (separate terminal)", H2))
    story.append(Paragraph("cd frontend", CODE))
    story.append(Paragraph("npm install", CODE))
    story.append(Paragraph("npm run dev", CODE))
    story.append(Paragraph("The app runs at <b>http://localhost:5173</b>. The Vite dev server proxies API calls to Django on port 8000.", BODY))

    story.append(Paragraph("1.3  Local email behavior", H2))
    story.append(Paragraph(
        "In development, <font name='Courier'>EMAIL_BACKEND</font> is set to "
        "<font name='Courier'>django.core.mail.backends.console.EmailBackend</font>. "
        "Password recovery and feedback emails print to the Django terminal — no SMTP needed locally.",
        BODY,
    ))

    story.append(PageBreak())

    # ════════════════════════════════════════
    # 2. EMAIL (RESEND)
    # ════════════════════════════════════════
    story.append(Paragraph("2. Email Service (Resend via SMTP)", H1))
    story.append(Paragraph(
        "Used for: <b>password recovery emails</b> and <b>feedback form delivery</b>. "
        "We use Resend's SMTP relay so Django's built-in <font name='Courier'>send_mail</font> works with zero extra dependencies.",
        BODY,
    ))

    story.append(Paragraph("2.1  Create a Resend account", H2))
    story.append(human_only_banner())
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("• Go to <b>https://resend.com</b> and sign up", BULLET))
    story.append(Paragraph("• Free tier: 100 emails/day, 1 domain — more than enough", BULLET))

    story.append(Paragraph("2.2  Add and verify your domain", H2))
    story.append(human_only_banner())
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("• In Resend dashboard → <b>Domains</b> → <b>Add Domain</b>", BULLET))
    story.append(Paragraph("• Enter: <font name='Courier'>sponda.poe.ma</font> (or your production domain)", BULLET))
    story.append(Paragraph("• Resend gives you DNS records (SPF, DKIM, optional DMARC) to add", BULLET))
    story.append(Paragraph("• Add these DNS records in your domain registrar/DNS provider", BULLET))
    story.append(Paragraph("• Wait for verification (usually 5–30 minutes)", BULLET))

    story.append(Paragraph("2.3  Generate an API key", H2))
    story.append(human_only_banner())
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("• In Resend dashboard → <b>API Keys</b> → <b>Create API Key</b>", BULLET))
    story.append(Paragraph("• Name it something like <font name='Courier'>sponda-prod</font>", BULLET))
    story.append(Paragraph("• Copy the key (starts with <font name='Courier'>re_</font>)", BULLET))

    story.append(Paragraph("2.4  Configure Django settings", H2))
    story.append(claude_can_do_banner())
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "Add these to <font name='Courier'>production.py</font> (or provide the API key to Claude and ask it to do this):",
        BODY,
    ))
    story.append(Paragraph("EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'", CODE))
    story.append(Paragraph("EMAIL_HOST = 'smtp.resend.com'", CODE))
    story.append(Paragraph("EMAIL_PORT = 465", CODE))
    story.append(Paragraph("EMAIL_USE_SSL = True", CODE))
    story.append(Paragraph("EMAIL_HOST_USER = 'resend'", CODE))
    story.append(Paragraph("EMAIL_HOST_PASSWORD = env('RESEND_API_KEY')", CODE))
    story.append(Paragraph("DEFAULT_FROM_EMAIL = 'Sponda &lt;noreply@sponda.poe.ma&gt;'", CODE))
    story.append(Paragraph("SITE_BASE_URL = 'https://sponda.poe.ma'", CODE))
    story.append(Paragraph("FEEDBACK_EMAIL = 'gustavo@poe.ma'", CODE))

    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("Add to <font name='Courier'>.env</font>:", BODY))
    story.append(env_table([
        ("RESEND_API_KEY", "Your Resend API key (starts with <font name='Courier'>re_</font>)"),
    ]))

    story.append(PageBreak())

    # ════════════════════════════════════════
    # 3. GOOGLE OAUTH
    # ════════════════════════════════════════
    story.append(Paragraph("3. Google OAuth", H1))
    story.append(Paragraph('Used for: <b>&ldquo;Sign in with Google&rdquo;</b> button on login and signup pages.', BODY))

    story.append(Paragraph("3.1  Create a Google Cloud project", H2))
    story.append(human_only_banner())
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("• Go to <b>https://console.cloud.google.com</b>", BULLET))
    story.append(Paragraph("• Create a new project (or use existing) named <font name='Courier'>Sponda</font>", BULLET))

    story.append(Paragraph("3.2  Configure the OAuth consent screen", H2))
    story.append(human_only_banner())
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("• Navigate to <b>APIs &amp; Services → OAuth consent screen</b>", BULLET))
    story.append(Paragraph("• User Type: <b>External</b>", BULLET))
    story.append(Paragraph("• App name: <font name='Courier'>Sponda</font>", BULLET))
    story.append(Paragraph("• Support email: your email", BULLET))
    story.append(Paragraph("• Scopes: add <font name='Courier'>openid</font>, <font name='Courier'>email</font>, <font name='Courier'>profile</font>", BULLET))
    story.append(Paragraph("• Authorized domains: <font name='Courier'>sponda.poe.ma</font> and <font name='Courier'>poe.ma</font>", BULLET))
    story.append(Paragraph("• Save. Publish the app (move from Testing to Production) so anyone can sign in", BULLET))

    story.append(Paragraph("3.3  Create OAuth credentials", H2))
    story.append(human_only_banner())
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("• Go to <b>APIs &amp; Services → Credentials → Create Credentials → OAuth client ID</b>", BULLET))
    story.append(Paragraph("• Application type: <b>Web application</b>", BULLET))
    story.append(Paragraph("• Name: <font name='Courier'>Sponda Web</font>", BULLET))
    story.append(Paragraph("• Authorized JavaScript origins:", BULLET))
    story.append(Paragraph("  <font name='Courier'>https://sponda.poe.ma</font>", CODE))
    story.append(Paragraph("  <font name='Courier'>http://localhost:5173</font> (for local dev)", CODE))
    story.append(Paragraph("• Authorized redirect URIs:", BULLET))
    story.append(Paragraph("  <font name='Courier'>https://sponda.poe.ma/api/auth/google/callback</font>", CODE))
    story.append(Paragraph("  <font name='Courier'>http://localhost:5173/api/auth/google/callback</font>", CODE))
    story.append(Paragraph("• Copy the <b>Client ID</b> and <b>Client Secret</b>", BULLET))

    story.append(Paragraph("3.4  Configure Django settings", H2))
    story.append(claude_can_do_banner())
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("Add to <font name='Courier'>production.py</font> (and optionally <font name='Courier'>development.py</font>):", BODY))
    story.append(Paragraph("GOOGLE_CLIENT_ID = env('GOOGLE_CLIENT_ID')", CODE))
    story.append(Paragraph("GOOGLE_CLIENT_SECRET = env('GOOGLE_CLIENT_SECRET')", CODE))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("Add to <font name='Courier'>.env</font>:", BODY))
    story.append(env_table([
        ("GOOGLE_CLIENT_ID", "From Google Cloud Console (long string ending in .apps.googleusercontent.com)"),
        ("GOOGLE_CLIENT_SECRET", "From Google Cloud Console (starts with GOCSPX-)"),
    ]))

    story.append(PageBreak())

    # ════════════════════════════════════════
    # 4. PRODUCTION ENV VARS
    # ════════════════════════════════════════
    story.append(Paragraph("4. Production Environment Variables", H1))
    story.append(claude_can_do_banner())
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "Add these to your <font name='Courier'>.env</font> file on the production server. "
        "Give Claude the values and ask it to update the file.",
        BODY,
    ))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("<b>Existing variables</b> (already in .env.example):", BODY))
    story.append(env_table([
        ("DJANGO_SECRET_KEY", "Random string. Generate with: <font name='Courier'>python -c \"import secrets; print(secrets.token_urlsafe(50))\"</font>"),
        ("BRAPI_API_KEY", "Your BRAPI API key"),
        ("DATABASE_URL", "<font name='Courier'>postgres://sponda:PASSWORD@db:5432/sponda</font>"),
        ("ALLOWED_HOSTS", "<font name='Courier'>sponda.poe.ma,localhost</font>"),
        ("DEBUG", "<font name='Courier'>False</font>"),
    ]))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("<b>New variables</b> (needed for new features):", BODY))
    story.append(env_table([
        ("RESEND_API_KEY", "From Resend dashboard (re_xxxx...)"),
        ("GOOGLE_CLIENT_ID", "From Google Cloud Console"),
        ("GOOGLE_CLIENT_SECRET", "From Google Cloud Console"),
        ("FEEDBACK_EMAIL", "Email to receive feedback (default: gustavo@poe.ma)"),
    ]))

    story.append(Paragraph("4.1  Update production.py", H2))
    story.append(claude_can_do_banner())
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "The production settings file needs the email backend, Google OAuth, and site URL configs added. "
        "Tell Claude: <i>\"Add the email and Google OAuth settings to production.py, "
        "here are my keys: ...\"</i>",
        BODY,
    ))

    story.append(PageBreak())

    # ════════════════════════════════════════
    # 5. PRODUCTION DEPLOYMENT
    # ════════════════════════════════════════
    story.append(Paragraph("5. Production Deployment", H1))
    story.append(Paragraph("5.1  Build and deploy", H2))
    story.append(Paragraph("The Dockerfile builds both frontend and backend in a multi-stage build:", BODY))
    story.append(Paragraph("docker compose build", CODE))
    story.append(Paragraph("docker compose up -d", CODE))

    story.append(Paragraph("5.2  Run migrations", H2))
    story.append(Paragraph("Migrations run automatically via the docker-compose command, but you can also run:", BODY))
    story.append(Paragraph("docker compose exec web python manage.py migrate", CODE))

    story.append(Paragraph("5.3  Nginx reverse proxy", H2))
    story.append(Paragraph(
        "Make sure your Nginx config proxies to port <font name='Courier'>8710</font> (the port exposed by docker-compose). "
        "Your existing Nginx setup at <font name='Courier'>sponda.poe.ma</font> should already handle this.",
        BODY,
    ))

    # ════════════════════════════════════════
    # 6. SUPERUSER
    # ════════════════════════════════════════
    story.append(Paragraph("6. Create Superuser (Admin Dashboard)", H1))
    story.append(claude_can_do_banner())
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("You need a superuser to access <font name='Courier'>/admin-dashboard</font>.", BODY))

    story.append(Paragraph("<b>Local:</b>", BODY))
    story.append(Paragraph(
        "DJANGO_SETTINGS_MODULE=config.settings.development "
        "python backend/manage.py createsuperuser --email your@email.com --username your@email.com",
        CODE,
    ))

    story.append(Paragraph("<b>Production (Docker):</b>", BODY))
    story.append(Paragraph("docker compose exec web python manage.py createsuperuser --email your@email.com --username your@email.com", CODE))
    story.append(Paragraph(
        "Or, if you already have a regular user account, promote it: tell Claude "
        "<i>\"Make my user gustavo@poe.ma a superuser\"</i> and it can run the Django shell command.",
        BODY,
    ))

    story.append(PageBreak())

    # ════════════════════════════════════════
    # 7. DNS
    # ════════════════════════════════════════
    story.append(Paragraph("7. DNS &amp; Domain Verification (Resend)", H1))
    story.append(human_only_banner())
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "When you add your domain in Resend (step 2.2), you'll get DNS records to add. "
        "These go in your DNS provider (wherever <font name='Courier'>poe.ma</font> is managed).",
        BODY,
    ))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("<b>Required DNS records from Resend:</b>", BODY))
    story.append(Spacer(1, 1 * mm))

    dns_data = [
        [
            Paragraph("<b>Type</b>", ParagraphStyle("th", parent=BODY, fontSize=9, fontName="Helvetica-Bold")),
            Paragraph("<b>Name</b>", ParagraphStyle("th", parent=BODY, fontSize=9, fontName="Helvetica-Bold")),
            Paragraph("<b>Value</b>", ParagraphStyle("th", parent=BODY, fontSize=9, fontName="Helvetica-Bold")),
            Paragraph("<b>Purpose</b>", ParagraphStyle("th", parent=BODY, fontSize=9, fontName="Helvetica-Bold")),
        ],
        [
            Paragraph("TXT", BODY),
            Paragraph("(provided by Resend)", ParagraphStyle("td", parent=BODY, fontSize=8)),
            Paragraph("(provided by Resend)", ParagraphStyle("td", parent=BODY, fontSize=8)),
            Paragraph("SPF — authorizes Resend to send from your domain", ParagraphStyle("td", parent=BODY, fontSize=8)),
        ],
        [
            Paragraph("CNAME", BODY),
            Paragraph("(provided by Resend)", ParagraphStyle("td", parent=BODY, fontSize=8)),
            Paragraph("(provided by Resend)", ParagraphStyle("td", parent=BODY, fontSize=8)),
            Paragraph("DKIM — email authentication", ParagraphStyle("td", parent=BODY, fontSize=8)),
        ],
        [
            Paragraph("TXT", BODY),
            Paragraph("_dmarc", ParagraphStyle("td", parent=BODY, fontSize=8)),
            Paragraph("v=DMARC1; p=none", ParagraphStyle("td", parent=BODY, fontSize=8)),
            Paragraph("DMARC — optional but recommended", ParagraphStyle("td", parent=BODY, fontSize=8)),
        ],
    ]
    story.append(Table(
        dns_data,
        colWidths=[15 * mm, 40 * mm, 60 * mm, 55 * mm],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#e2e8f0")),
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]),
    ))

    story.append(PageBreak())

    # ════════════════════════════════════════
    # 8. COMPLETE .ENV REFERENCE
    # ════════════════════════════════════════
    story.append(Paragraph("8. Complete .env Reference", H1))
    story.append(claude_can_do_banner())
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("Here is the full <font name='Courier'>.env</font> file with all variables:", BODY))
    story.append(Spacer(1, 2 * mm))

    env_lines = [
        "# === Core ===",
        "DJANGO_SECRET_KEY=<generate-a-random-key>",
        "BRAPI_API_KEY=<your-brapi-key>",
        "DATABASE_URL=postgres://sponda:sponda@db:5432/sponda",
        "ALLOWED_HOSTS=sponda.poe.ma,localhost",
        "DEBUG=False",
        "",
        "# === Email (Resend) ===",
        "RESEND_API_KEY=re_xxxxxxxxxxxx",
        "",
        "# === Google OAuth ===",
        "GOOGLE_CLIENT_ID=xxxx.apps.googleusercontent.com",
        "GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxx",
        "",
        "# === Optional ===",
        "FEEDBACK_EMAIL=gustavo@poe.ma",
    ]
    for line in env_lines:
        story.append(Paragraph(line if line else "&nbsp;", CODE))

    story.append(PageBreak())

    # ════════════════════════════════════════
    # 9. VERIFICATION CHECKLIST
    # ════════════════════════════════════════
    story.append(Paragraph("9. Verification Checklist", H1))
    story.append(Paragraph("After completing all steps, verify each feature works:", BODY))
    story.append(Spacer(1, 2 * mm))

    checks = [
        ("Signup", "Go to /signup, create an account → should succeed and auto-login"),
        ("Login", "Go to /login, sign in with your new account → should redirect home"),
        ("Logout", "Click your email in top-right → Account → Sair → should log out"),
        ("Forgot password", "Go to /forgot-password, enter email → should receive email (check console in dev, inbox in prod)"),
        ("Reset password", "Click the link from the email → should show password reset form"),
        ("Change password", "Go to /account → change password form should work"),
        ("Google sign-in", "Go to /login → 'Entrar com Google' button → should redirect to Google and back"),
        ("Favorites", "On any ticker page (e.g. /PETR4), click the star → should appear on home page under 'Seus favoritos'"),
        ("Save comparison", "Go to /PETR4/comparar → 'Salvar esta comparação' → should save and show share link"),
        ("Shared link", "Open the share link → should show explanation of what was shared"),
        ("Feedback", "Click 'Feedback' in top-right → fill form → should send (console in dev)"),
        ("Admin dashboard", "Login as superuser → 'Admin' link appears → /admin-dashboard shows stats"),
        ("Company tooltip", "On compare table, hover over a truncated company name → should show full name"),
    ]

    check_data = [
        [
            Paragraph("<b>Feature</b>", ParagraphStyle("th", parent=BODY, fontSize=9, fontName="Helvetica-Bold")),
            Paragraph("<b>How to verify</b>", ParagraphStyle("th", parent=BODY, fontSize=9, fontName="Helvetica-Bold")),
            Paragraph("<b>✓</b>", ParagraphStyle("th", parent=BODY, fontSize=9, fontName="Helvetica-Bold")),
        ]
    ]
    for feature, how in checks:
        check_data.append([
            Paragraph(feature, ParagraphStyle("td", parent=BODY, fontSize=9)),
            Paragraph(how, ParagraphStyle("td", parent=BODY, fontSize=8)),
            Paragraph("☐", ParagraphStyle("td", parent=BODY, fontSize=12, alignment=1)),
        ])

    story.append(Table(
        check_data,
        colWidths=[35 * mm, 120 * mm, 15 * mm],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#e2e8f0")),
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]),
    ))

    story.append(Spacer(1, 10 * mm))
    story.append(HRFlowable(width="100%", color=BORDER))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "Generated for Sponda · sponda.poe.ma · March 2026",
        ParagraphStyle("footer", parent=BODY, fontSize=8, textColor=MUTED, alignment=1),
    ))

    doc.build(story)
    print(f"PDF generated: {OUTPUT_PATH}")


if __name__ == "__main__":
    build()
