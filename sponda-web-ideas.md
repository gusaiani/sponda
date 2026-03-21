# Sponda Web — Product Ideas

## 1. User Authentication (Professional)

Full sign-in/sign-up flow:

- **Email + password** registration and login
- **Password recovery** via email
- **Update password** for logged-in users
- **Google OAuth** sign-in

Must feel extremely professional and polished.

## 2. Favorite Companies

Logged-in users can **favorite companies**. Favorited companies:

- Appear at the **top of the home page** (above the standard popular grid)
- Are **removed from the standard list** to avoid duplication
- Provide quick access to companies the user tracks regularly

## 3. Saved Lists

On the compare tab, users can customize by adding/removing companies and reordering rows. Logged-in users can:

- **Save a list** (preserving tickers, order, and years setting)
- **Access saved lists** later from their account
- **Share a list via link** — the recipient sees an explanation of what was shared

## 4. Company Name Tooltip (Compare Table)

Company names in the comparison table are often too long — the meaningful part gets hidden or wrapped. Add a **hover tooltip** showing the full company name.

## 5. Feedback Button

A **"Feedback" link** at the top-right corner of every page. Opens a lightweight form:

- Email address field
- Simple human verification (e.g., "What is 3 + 4?")
- Text area for the message

Sends feedback via email using Django's `send_mail` with SMTP (Resend or another provider as relay).
