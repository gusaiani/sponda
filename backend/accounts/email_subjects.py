"""Per-locale subjects and share strings for account emails."""
from urllib.parse import quote_plus

WELCOME_SUBJECTS = {
    "pt": "Te damos as boas-vindas à Sponda!",
    "en": "Welcome to Sponda!",
    "es": "¡Te damos la bienvenida a Sponda!",
    "fr": "Bienvenue sur Sponda !",
    "de": "Willkommen bei Sponda!",
    "it": "Benvenuto su Sponda!",
    "zh": "欢迎来到 Sponda！",
}

VERIFICATION_SUBJECTS = {
    "pt": "Sponda · Confirme seu email",
    "en": "Sponda · Confirm your email",
    "es": "Sponda · Confirma tu email",
    "fr": "Sponda · Confirmez votre e-mail",
    "de": "Sponda · E-Mail bestätigen",
    "it": "Sponda · Conferma la tua email",
    "zh": "Sponda · 确认您的邮箱",
}

_SHARE_TEXT = {
    "pt": "Conheça a Sponda — indicadores de empresas para investidores em valor",
    "en": "Check out Sponda — company indicators for value investors",
    "es": "Descubre Sponda — indicadores de empresas para inversores de valor",
    "fr": "Découvrez Sponda — indicateurs d'entreprises pour les investisseurs value",
    "de": "Entdecken Sie Sponda — Unternehmenskennzahlen für Value-Investoren",
    "it": "Scopri Sponda — indicatori aziendali per investitori value",
    "zh": "了解 Sponda — 为价值投资者设计的公司指标",
}

_SHARE_SUBJECT = {
    "pt": "Conheça a Sponda",
    "en": "Check out Sponda",
    "es": "Descubre Sponda",
    "fr": "Découvrez Sponda",
    "de": "Entdecken Sie Sponda",
    "it": "Scopri Sponda",
    "zh": "了解 Sponda",
}


def share_strings(language):
    language = language if language in _SHARE_TEXT else "en"
    return {
        "share_text_encoded": quote_plus(_SHARE_TEXT[language]),
        "share_subject_encoded": quote_plus(_SHARE_SUBJECT[language]),
    }
