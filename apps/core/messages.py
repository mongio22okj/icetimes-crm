"""Toast helpers built on Django's messages framework.

The base layouts include the toast container partial (`partials/toasts.html`),
which drains all unread messages on render and shows them as auto-dismissing
toast popovers via the `apexToasts()` Alpine factory.

Use `toast(request, level, body)` instead of plain `messages.add_message`
when you want extras like an action button or a persistent (no auto-dismiss)
toast. Existing `messages.success(request, "...")` calls light up too — they
just don't carry actions.
"""
from django.contrib import messages

LEVEL_SUCCESS = messages.SUCCESS
LEVEL_INFO = messages.INFO
LEVEL_WARNING = messages.WARNING
LEVEL_ERROR = messages.ERROR

# Sentinel separators inside extra_tags. Chosen so they don't collide with
# anything Django uses (no spaces, no commas).
_SEP = "::"
_PERSISTENT_TAG = "persistent"
_ACTION_PREFIX = f"action{_SEP}"


def toast(request, level, body, *, action=None, persistent=False, extra_tags=""):
    """Push a toast.

    Args:
        request: HttpRequest
        level: one of messages.{SUCCESS, INFO, WARNING, ERROR}
        body: plain-text message body
        action: optional {"label": str, "url": str} — renders a button on the toast
        persistent: when True, the toast does not auto-dismiss
        extra_tags: forwarded to messages.add_message; combined with our own
    """
    tags = list(filter(None, extra_tags.split())) if extra_tags else []
    if persistent:
        tags.append(_PERSISTENT_TAG)
    if action:
        # Encode as action::Label::URL so the template tag can parse it back
        # without changing the messages framework's storage.
        label = action["label"].replace(_SEP, "")
        url = action["url"].replace(_SEP, "")
        tags.append(f"{_ACTION_PREFIX}{label}{_SEP}{url}")
    messages.add_message(request, level, body, extra_tags=" ".join(tags))


def parse_extra_tags(raw: str) -> dict:
    """Parse a message's extra_tags string into our metadata.

    Returns: {"action": {"label", "url"} | None, "persistent": bool,
              "other_tags": list[str]}
    """
    action = None
    persistent = False
    other = []
    for tag in (raw or "").split():
        if tag == _PERSISTENT_TAG:
            persistent = True
        elif tag.startswith(_ACTION_PREFIX):
            payload = tag[len(_ACTION_PREFIX):]
            label, _, url = payload.partition(_SEP)
            if label and url:
                action = {"label": label, "url": url}
        else:
            other.append(tag)
    return {"action": action, "persistent": persistent, "other_tags": other}
