"""Small helper tags used by the docs templates.

Most pages just compose Tailwind divs directly — these are for the
two patterns repeated often enough to be worth a tag:

  {% code lang="bash" %}npm install{% endcode %}
  {% feature title="2FA" %}TOTP + recovery codes ship out of the box.{% endfeature %}
"""
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.tag(name="code")
def do_code(parser, token):
    """`{% code lang="bash" %}...{% endcode %}` — fenced code block."""
    bits = token.split_contents()
    lang = "text"
    for bit in bits[1:]:
        if bit.startswith("lang="):
            lang = bit.split("=", 1)[1].strip().strip('"').strip("'")
    nodelist = parser.parse(("endcode",))
    parser.delete_first_token()
    return CodeNode(nodelist, lang)


class CodeNode(template.Node):
    def __init__(self, nodelist, lang):
        self.nodelist = nodelist
        self.lang = lang

    def render(self, context):
        body = self.nodelist.render(context).strip("\n")
        # Escape so HTML inside the snippet renders literal.
        from django.utils.html import escape as _escape
        escaped = _escape(body)
        return mark_safe(
            '<div class="group relative my-4 overflow-hidden rounded-lg border border-border bg-muted/30">'
            f'  <div class="flex items-center justify-between border-b border-border bg-muted/50 px-3 py-1.5 text-xs text-muted-foreground">'
            f'    <span class="font-mono uppercase tracking-wider">{self.lang}</span>'
            f'  </div>'
            f'  <pre class="overflow-x-auto p-4 text-xs leading-relaxed"><code>{escaped}</code></pre>'
            '</div>',
        )


@register.tag(name="feature")
def do_feature(parser, token):
    """`{% feature title="2FA" %}...{% endfeature %}` — bulleted item with bold title."""
    bits = token.split_contents()
    title = ""
    for bit in bits[1:]:
        if bit.startswith("title="):
            title = bit.split("=", 1)[1].strip().strip('"').strip("'")
    nodelist = parser.parse(("endfeature",))
    parser.delete_first_token()
    return FeatureNode(nodelist, title)


class FeatureNode(template.Node):
    def __init__(self, nodelist, title):
        self.nodelist = nodelist
        self.title = title

    def render(self, context):
        body = self.nodelist.render(context).strip()
        from django.utils.html import escape as _escape
        return mark_safe(
            '<li class="flex items-start gap-2.5">'
            '  <span class="mt-2 block size-1.5 shrink-0 rounded-full bg-primary"></span>'
            '  <span>'
            f'    <strong class="text-foreground">{_escape(self.title)}</strong>'
            f'    <span class="text-muted-foreground"> — {body}</span>'
            '  </span>'
            '</li>',
        )


@register.simple_tag
def badge(label):
    """`{% badge "Tailwind v4" %}` — pill-style stack tag."""
    from django.utils.html import escape as _escape
    return mark_safe(
        '<span class="inline-flex items-center rounded-md bg-muted px-2 py-1 '
        'text-xs font-medium text-muted-foreground">'
        f'{_escape(label)}</span>',
    )


@register.tag(name="callout")
def do_callout(parser, token):
    """`{% callout type="note"|"warn"|"tip" %}...{% endcallout %}` — bordered admonition."""
    bits = token.split_contents()
    callout_type = "note"
    for bit in bits[1:]:
        if bit.startswith("type="):
            callout_type = bit.split("=", 1)[1].strip().strip('"').strip("'")
    nodelist = parser.parse(("endcallout",))
    parser.delete_first_token()
    return CalloutNode(nodelist, callout_type)


_CALLOUT_STYLES = {
    "note": ("border-blue-500/40 bg-blue-500/5",  "info",          "text-blue-500", "Note"),
    "warn": ("border-amber-500/40 bg-amber-500/5", "alert-triangle", "text-amber-500", "Warning"),
    "tip":  ("border-emerald-500/40 bg-emerald-500/5", "check",      "text-emerald-500", "Tip"),
}


class CalloutNode(template.Node):
    def __init__(self, nodelist, callout_type):
        self.nodelist = nodelist
        self.callout_type = callout_type

    def render(self, context):
        from apps.core.templatetags.apex import icon as _icon
        cls, icon_name, icon_cls, label = _CALLOUT_STYLES.get(
            self.callout_type, _CALLOUT_STYLES["note"],
        )
        body = self.nodelist.render(context).strip()
        return mark_safe(
            f'<div class="my-4 flex gap-3 rounded-lg border {cls} p-4 text-sm">'
            f'  <span class="{icon_cls} shrink-0 mt-0.5">{_icon(icon_name, 16)}</span>'
            f'  <div class="space-y-1">'
            f'    <p class="font-semibold text-foreground">{label}</p>'
            f'    <div class="text-muted-foreground leading-relaxed">{body}</div>'
            f'  </div>'
            f'</div>',
        )
