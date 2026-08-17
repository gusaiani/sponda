"""Per-locale copy for the unsubscribe page.

Kept apart from the flow itself so adding a language is a text change and
nothing else. Mirrors the shape of :mod:`accounts.email_subjects`.
"""
from .models import DEFAULT_LANGUAGE

# ``lang`` attribute for the page's <html> element, per locale.
HTML_LANG = {
    "pt": "pt-BR",
    "en": "en",
    "es": "es",
    "zh": "zh-CN",
    "fr": "fr",
    "de": "de",
    "it": "it",
}

# Every locale carries one entry per page state plus the three strings the
# page reuses across states. ``{email}`` is filled in by the view.
UNSUBSCRIBE_COPY = {
    "pt": {
        "confirm": {
            "title": "Cancelar os emails da Sponda",
            "body": "Você vai parar de receber os emails da Sponda enviados para {email}.",
        },
        "done": {
            "title": "Pronto",
            "body": "{email} saiu da lista. Envios já em andamento podem levar alguns minutos para parar.",
        },
        "already": {
            "title": "Você já está fora da lista",
            "body": "{email} não recebe mais os emails da Sponda.",
        },
        "invalid": {
            "title": "Link inválido",
            "body": "Este link de descadastro não é válido. Entre na sua conta para ajustar suas preferências de contato.",
        },
        "action": "Confirmar descadastro",
        "note": "Emails da sua conta, como confirmação de endereço e redefinição de senha, continuam chegando.",
        "account_action": "Abrir Minha conta",
    },
    "en": {
        "confirm": {
            "title": "Unsubscribe from Sponda emails",
            "body": "You will stop receiving Sponda emails at {email}.",
        },
        "done": {
            "title": "Done",
            "body": "{email} is off the list. Sends already in flight can take a few minutes to stop.",
        },
        "already": {
            "title": "You are already off the list",
            "body": "{email} no longer receives Sponda emails.",
        },
        "invalid": {
            "title": "Invalid link",
            "body": "This unsubscribe link is not valid. Sign in to your account to change your contact preferences.",
        },
        "action": "Confirm unsubscribe",
        "note": "Account email, such as address confirmation and password resets, keeps coming.",
        "account_action": "Open My account",
    },
    "es": {
        "confirm": {
            "title": "Cancelar los emails de Sponda",
            "body": "Dejarás de recibir los emails de Sponda enviados a {email}.",
        },
        "done": {
            "title": "Listo",
            "body": "{email} salió de la lista. Los envíos ya en curso pueden tardar unos minutos en detenerse.",
        },
        "already": {
            "title": "Ya estás fuera de la lista",
            "body": "{email} ya no recibe los emails de Sponda.",
        },
        "invalid": {
            "title": "Enlace no válido",
            "body": "Este enlace de baja no es válido. Entra en tu cuenta para ajustar tus preferencias de contacto.",
        },
        "action": "Confirmar la baja",
        "note": "Los emails de tu cuenta, como la confirmación de dirección y el restablecimiento de contraseña, se siguen enviando.",
        "account_action": "Abrir Mi cuenta",
    },
    "zh": {
        "confirm": {
            "title": "取消订阅 Sponda 邮件",
            "body": "{email} 将不再收到 Sponda 的邮件。",
        },
        "done": {
            "title": "已完成",
            "body": "{email} 已从名单中移除。已在发送中的邮件可能需要几分钟才会停止。",
        },
        "already": {
            "title": "您已不在名单中",
            "body": "{email} 不再接收 Sponda 的邮件。",
        },
        "invalid": {
            "title": "链接无效",
            "body": "此退订链接无效。请登录您的账户以调整联系偏好。",
        },
        "action": "确认取消订阅",
        "note": "账户邮件仍会发送，例如地址确认和密码重置。",
        "account_action": "打开我的账户",
    },
    "fr": {
        "confirm": {
            "title": "Se désabonner des emails Sponda",
            "body": "Vous ne recevrez plus les emails Sponda envoyés à {email}.",
        },
        "done": {
            "title": "C'est fait",
            "body": "{email} est retiré de la liste. Les envois déjà en cours peuvent mettre quelques minutes à s'arrêter.",
        },
        "already": {
            "title": "Vous êtes déjà hors de la liste",
            "body": "{email} ne reçoit plus les emails Sponda.",
        },
        "invalid": {
            "title": "Lien non valide",
            "body": "Ce lien de désabonnement n'est pas valide. Connectez-vous à votre compte pour modifier vos préférences de contact.",
        },
        "action": "Confirmer le désabonnement",
        "note": "Les emails liés au compte, comme la confirmation d'adresse et la réinitialisation du mot de passe, continuent d'arriver.",
        "account_action": "Ouvrir Mon compte",
    },
    "de": {
        "confirm": {
            "title": "Sponda-E-Mails abbestellen",
            "body": "Sie erhalten keine Sponda-E-Mails mehr an {email}.",
        },
        "done": {
            "title": "Erledigt",
            "body": "{email} steht nicht mehr auf der Liste. Bereits laufende Versände können einige Minuten brauchen.",
        },
        "already": {
            "title": "Sie stehen bereits nicht mehr auf der Liste",
            "body": "{email} erhält keine Sponda-E-Mails mehr.",
        },
        "invalid": {
            "title": "Ungültiger Link",
            "body": "Dieser Abmeldelink ist ungültig. Melden Sie sich in Ihrem Konto an, um Ihre Kontakteinstellungen zu ändern.",
        },
        "action": "Abbestellung bestätigen",
        "note": "Konto-E-Mails wie Adressbestätigung und Passwort-Zurücksetzung kommen weiterhin an.",
        "account_action": "Mein Konto öffnen",
    },
    "it": {
        "confirm": {
            "title": "Annullare le email di Sponda",
            "body": "Non riceverai più le email di Sponda inviate a {email}.",
        },
        "done": {
            "title": "Fatto",
            "body": "{email} è fuori dalla lista. Gli invii già in corso possono richiedere qualche minuto per fermarsi.",
        },
        "already": {
            "title": "Sei già fuori dalla lista",
            "body": "{email} non riceve più le email di Sponda.",
        },
        "invalid": {
            "title": "Link non valido",
            "body": "Questo link di annullamento non è valido. Accedi al tuo account per modificare le preferenze di contatto.",
        },
        "action": "Conferma l'annullamento",
        "note": "Le email dell'account, come la conferma dell'indirizzo e il reset della password, continuano ad arrivare.",
        "account_action": "Apri Il mio account",
    },
}


def unsubscribe_copy(language):
    """Return the copy block for ``language``, falling back to the default."""
    return UNSUBSCRIBE_COPY.get(language, UNSUBSCRIBE_COPY[DEFAULT_LANGUAGE])


def html_lang(language):
    """Return the <html lang> value for ``language``, falling back to the default."""
    return HTML_LANG.get(language, HTML_LANG[DEFAULT_LANGUAGE])
