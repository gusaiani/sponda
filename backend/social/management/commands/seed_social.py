"""Seed the local database with users, Sponds, replies, likes, follows.

Run with:
    python manage.py seed_social
    python manage.py seed_social --reset    # wipes existing seeded data first
    python manage.py seed_social --password=letmein   # default is "sponda"

Idempotent: re-running without --reset only adds missing rows. Every seeded
user is verified, has a handle and display name, and gets a deterministic
password so you can log in as any of them. Logins printed at the end.
"""
from __future__ import annotations

import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from quotes.models import Ticker
from social.mentions import extract_handle_mentions, extract_ticker_mentions
from social.models import (
    Block,
    Follow,
    Mute,
    Notification,
    Spond,
    SpondLike,
    SpondMention,
    SpondTickerMention,
)


User = get_user_model()


SEED_USERS = [
    {
        "handle": "alice",
        "display_name": "Alice Pereira",
        "email": "alice@seed.sponda.local",
        "bio": "Value investor. PE10 maximalist. Long-only.",
        "is_private": False,
    },
    {
        "handle": "bruno",
        "display_name": "Bruno Costa",
        "email": "bruno@seed.sponda.local",
        "bio": "Building a Brazilian value fund. Petrobras and Vale watcher.",
        "is_private": False,
    },
    {
        "handle": "carla",
        "display_name": "Carla Mendes",
        "email": "carla@seed.sponda.local",
        "bio": "Banking analyst. Following ITUB4, BBDC4 since 2018.",
        "is_private": False,
    },
    {
        "handle": "diego",
        "display_name": "Diego Almeida",
        "email": "diego@seed.sponda.local",
        "bio": "US tech. Mostly Apple and Microsoft.",
        "is_private": False,
    },
    {
        "handle": "elena",
        "display_name": "Elena Santos",
        "email": "elena@seed.sponda.local",
        "bio": "Quant turned fundamentalist. Skeptical of growth stories.",
        "is_private": True,  # one private account so you can test approval flow
    },
]


SEED_TICKERS = [
    ("PETR4", "Petrobras", "Energy"),
    ("VALE3", "Vale", "Mining"),
    ("ITUB4", "Itaú Unibanco", "Banking"),
    ("BBDC4", "Bradesco", "Banking"),
    ("WEGE3", "WEG", "Industrial"),
    ("AAPL", "Apple", "Technology"),
    ("MSFT", "Microsoft", "Technology"),
]


SEED_SPONDS = [
    # (author_handle, body, ticker_or_None)
    (
        "alice",
        "Voltei a olhar $PETR4. Com PE10 abaixo de 6 e dividend yield acima de 13%, "
        "mesmo descontando a volatilidade política, parece barata para 5+ anos.",
        "PETR4",
    ),
    (
        "bruno",
        "Concordo com a tese de @alice no $PETR4 mas o risco político não é ruído — "
        "é estrutural. Sizing pequeno faz sentido.",
        "PETR4",
    ),
    (
        "carla",
        "$ITUB4 com ROE de 21% e P/L histórico abaixo de 9. Banco bem capitalizado, "
        "PDD controlada. Posição de longo prazo.",
        "ITUB4",
    ),
    (
        "diego",
        "$AAPL: serviços ainda crescendo 15% YoY mesmo com hardware fraco. "
        "Ativo de qualidade, paga prêmio por isso.",
        "AAPL",
    ),
    (
        "diego",
        "Reduzi $MSFT depois do rally de 2024-2025. Pago crescimento de IA mas múltiplo "
        "ficou acima da média histórica. Vou esperar.",
        "MSFT",
    ),
    (
        "alice",
        "Lembrete pra mim mesma: ignorar previsões macro. Foco em balanços e fluxo de caixa.",
        None,
    ),
    (
        "bruno",
        "$VALE3 com Dívida/FCL médio em 1.2 — folga gigante. Se minério estabilizar acima "
        "de 90 USD/t, o desconto atual não faz sentido.",
        "VALE3",
    ),
    (
        "carla",
        "Curto prazo é ruído. Quem ficou em $ITUB4 desde 2020 dobrou capital + dividendos.",
        "ITUB4",
    ),
    (
        "elena",
        "Saí de growth completamente em 2024. P/E 40x para crescer 12% ao ano não fecha conta.",
        None,
    ),
    (
        "alice",
        "@bruno boa observação sobre $VALE3 — mas considerou o capex de descarbonização? "
        "Fluxo livre dos próximos 3 anos vai ser pressionado.",
        "VALE3",
    ),
]


SEED_REPLIES = [
    # (parent_index_in_SEED_SPONDS, author_handle, body)
    (0, "carla", "Concordo. Adicionei $PETR4 na carteira em outubro."),
    (0, "diego", "Tese boa, mas prefiro $XOM nos EUA — menos risco de governança."),
    (2, "alice", "@carla bom call. ROE consistente é o que importa nesse setor."),
    (3, "bruno", "@diego serviços é o moat real. Hardware é commodity premium agora."),
    (6, "elena", "Capex de descarbonização vai pressionar FCL nos próximos 3 anos. "
                "Cuidado com extrapolação."),
]


class Command(BaseCommand):
    help = "Seed users, Sponds, likes, replies, follows for local testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete every seeded user (and cascade their data) before seeding.",
        )
        parser.add_argument(
            "--password",
            default="sponda",
            help="Password for every seeded user. Default: 'sponda'.",
        )

    @transaction.atomic
    def handle(self, *args, reset, password, **kwargs):
        if reset:
            self._reset()

        users = self._seed_users(password)
        self._seed_tickers()
        sponds = self._seed_sponds(users)
        self._seed_replies(users, sponds)
        self._seed_likes(users, sponds)
        self._seed_follows(users)

        self.stdout.write(self.style.SUCCESS("\n✔ Seeded social data.\n"))
        self.stdout.write("Login as any of these users (password: %r):\n" % password)
        for handle, user in users.items():
            mark = " (private)" if user.is_private else ""
            self.stdout.write(f"  {user.email}  →  @{handle}{mark}")

    # ─── individual seeding steps ─────────────────────────────────────────────

    def _reset(self):
        emails = [u["email"] for u in SEED_USERS]
        deleted, _ = User.objects.filter(email__in=emails).delete()
        self.stdout.write(self.style.WARNING(f"Reset: deleted {deleted} rows.\n"))

    def _seed_users(self, password):
        users: dict[str, "User"] = {}
        for spec in SEED_USERS:
            user, created = User.objects.get_or_create(
                email=spec["email"],
                defaults={
                    "username": spec["email"],
                    "handle": spec["handle"],
                    "display_name": spec["display_name"],
                    "bio": spec["bio"],
                    "is_private": spec["is_private"],
                    "email_verified": True,
                },
            )
            if created:
                user.set_password(password)
                user.save(update_fields=["password"])
            else:
                # Make sure profile fields are populated even if the user
                # pre-existed from a previous run without --reset.
                changed = False
                for field in ("handle", "display_name", "bio", "is_private"):
                    if getattr(user, field) != spec[field]:
                        setattr(user, field, spec[field])
                        changed = True
                if not user.email_verified:
                    user.email_verified = True
                    changed = True
                if changed:
                    user.save()
            users[spec["handle"]] = user
        return users

    def _seed_tickers(self):
        for symbol, name, sector in SEED_TICKERS:
            Ticker.objects.update_or_create(
                symbol=symbol,
                defaults={
                    "name": name,
                    "display_name": name,
                    "sector": sector,
                },
            )

    def _seed_sponds(self, users):
        """Create top-level Sponds, dating them backward across the last
        few days so the feed has visual variety."""
        created: list[Spond] = []
        now = timezone.now()
        for index, (handle, body, ticker) in enumerate(SEED_SPONDS):
            author = users[handle]
            # Skip if an identical body from this author already exists —
            # keeps reruns idempotent.
            existing = Spond.objects.filter(
                author=author, body=body, deleted_at__isnull=True,
            ).first()
            if existing is not None:
                created.append(existing)
                continue
            spond = Spond.objects.create(
                author=author,
                body=body,
                ticker=ticker or "",
            )
            # Spread the timestamps so the feed shows a range.
            spond.created_at = now - timedelta(hours=index * 5 + 1)
            spond.save(update_fields=["created_at"])
            self._persist_mentions(spond, body, users)
            created.append(spond)
        return created

    def _seed_replies(self, users, sponds):
        for parent_index, handle, body in SEED_REPLIES:
            parent = sponds[parent_index]
            author = users[handle]
            existing = Spond.objects.filter(
                author=author, body=body, parent=parent, deleted_at__isnull=True,
            ).first()
            if existing is not None:
                continue
            reply = Spond.objects.create(
                author=author,
                body=body,
                parent=parent,
            )
            reply.created_at = parent.created_at + timedelta(hours=1)
            reply.save(update_fields=["created_at"])
            self._persist_mentions(reply, body, users)
            # Notify the parent's author.
            if parent.author_id != author.id:
                Notification.objects.create(
                    recipient=parent.author,
                    actor=author,
                    verb=Notification.VERB_REPLIED,
                    target=reply,
                )

    def _seed_likes(self, users, sponds):
        """Have everyone (except the author) like roughly half of each Spond."""
        rng = random.Random(42)  # deterministic so reruns produce the same shape
        for spond in sponds:
            for user in users.values():
                if user.id == spond.author_id:
                    continue
                if rng.random() < 0.55:
                    like, created = SpondLike.objects.get_or_create(
                        user=user, spond=spond,
                    )
                    if created and spond.author_id != user.id:
                        Notification.objects.get_or_create(
                            recipient=spond.author,
                            actor=user,
                            verb=Notification.VERB_LIKED,
                            target_content_type=_content_type_for(Spond),
                            target_object_id=str(spond.pk),
                        )

    def _seed_follows(self, users):
        """Build a small follow graph:
          alice ↔ bruno (mutual)
          alice → carla, diego
          carla → bruno, alice
          bruno → diego
          diego → alice
        And one PENDING follow request: bruno → elena (private).
        """
        pairs = [
            ("alice", "bruno", Follow.STATE_ACCEPTED),
            ("bruno", "alice", Follow.STATE_ACCEPTED),
            ("alice", "carla", Follow.STATE_ACCEPTED),
            ("alice", "diego", Follow.STATE_ACCEPTED),
            ("carla", "bruno", Follow.STATE_ACCEPTED),
            ("carla", "alice", Follow.STATE_ACCEPTED),
            ("bruno", "diego", Follow.STATE_ACCEPTED),
            ("diego", "alice", Follow.STATE_ACCEPTED),
            ("bruno", "elena", Follow.STATE_PENDING),
        ]
        for follower_handle, followee_handle, state in pairs:
            follower = users[follower_handle]
            followee = users[followee_handle]
            follow, created = Follow.objects.get_or_create(
                follower=follower, followee=followee,
                defaults={
                    "state": state,
                    "accepted_at": (
                        timezone.now() if state == Follow.STATE_ACCEPTED else None
                    ),
                },
            )
            if not created:
                continue
            if state == Follow.STATE_ACCEPTED:
                Notification.objects.create(
                    recipient=followee,
                    actor=follower,
                    verb=Notification.VERB_FOLLOWED,
                    target=follow,
                )
            else:
                Notification.objects.create(
                    recipient=followee,
                    actor=follower,
                    verb=Notification.VERB_FOLLOW_REQUESTED,
                    target=follow,
                )

    # ─── helpers ──────────────────────────────────────────────────────────────

    def _persist_mentions(self, spond, body, users):
        for handle in extract_handle_mentions(body):
            if handle in users:
                SpondMention.objects.get_or_create(
                    spond=spond, mentioned_user=users[handle],
                )
                if users[handle].id != spond.author_id:
                    Notification.objects.get_or_create(
                        recipient=users[handle],
                        actor=spond.author,
                        verb=Notification.VERB_MENTIONED,
                        target_content_type=_content_type_for(Spond),
                        target_object_id=str(spond.pk),
                    )
        for symbol in extract_ticker_mentions(body):
            if Ticker.objects.filter(symbol=symbol).exists():
                SpondTickerMention.objects.get_or_create(
                    spond=spond, ticker=symbol,
                )


def _content_type_for(model_cls):
    from django.contrib.contenttypes.models import ContentType
    return ContentType.objects.get_for_model(model_cls)
