"""Un-flag capability probes that were recorded as failures.

Clients probe optional capabilities on every connect — Claude's connector
sends server/discover, others try resources/list. Answering "method not
found" is the protocol-correct "no" and the caller proceeds normally, but
until assistant.mcp learned that, every probe was written with failed=True
and inflated the dashboard's error column by one per connection.

The rule is exact rather than a method allowlist: no supported method
outside tools/call ever sets failed=True (initialize, ping and tools/list
cannot fail, notifications are acknowledged unconditionally), so every
failed row on another method is a probe.
"""
from django.db import migrations

METHOD_TOOLS_CALL = "tools/call"


def unflag_capability_probes(apps, schema_editor):
    McpCall = apps.get_model("assistant", "McpCall")
    McpCall.objects.filter(failed=True).exclude(
        method=METHOD_TOOLS_CALL
    ).update(failed=False)


class Migration(migrations.Migration):

    dependencies = [
        ("assistant", "0004_mcpcall_arguments_mcpcall_result_count"),
    ]

    # No reverse: which non-tools/call rows once carried failed=True is not
    # recoverable from the remaining data, and restoring a known-misleading
    # flag would have no consumer anyway.
    operations = [
        migrations.RunPython(unflag_capability_probes, migrations.RunPython.noop),
    ]
