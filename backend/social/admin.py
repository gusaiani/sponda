from django.contrib import admin

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


@admin.register(Spond)
class SpondAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "ticker", "parent", "deleted_at", "created_at")
    list_filter = ("ticker", "deleted_at")
    search_fields = ("body", "author__email", "author__handle")
    raw_id_fields = ("author", "parent")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SpondLike)
class SpondLikeAdmin(admin.ModelAdmin):
    list_display = ("user", "spond", "created_at")
    raw_id_fields = ("user", "spond")


@admin.register(SpondMention)
class SpondMentionAdmin(admin.ModelAdmin):
    list_display = ("spond", "mentioned_user", "created_at")
    raw_id_fields = ("spond", "mentioned_user")


@admin.register(SpondTickerMention)
class SpondTickerMentionAdmin(admin.ModelAdmin):
    list_display = ("spond", "ticker", "created_at")
    raw_id_fields = ("spond",)


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ("follower", "followee", "state", "created_at", "accepted_at")
    list_filter = ("state",)
    raw_id_fields = ("follower", "followee")


@admin.register(Mute)
class MuteAdmin(admin.ModelAdmin):
    list_display = ("actor", "target", "created_at")
    raw_id_fields = ("actor", "target")


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ("actor", "target", "created_at")
    raw_id_fields = ("actor", "target")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "actor", "verb", "read_at", "created_at")
    list_filter = ("verb",)
    raw_id_fields = ("recipient", "actor")
