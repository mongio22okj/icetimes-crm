# Phase 12 — Forms 2.0

**Date:** 2026-04-29
**Status:** Draft
**Scope:** Replace the current basic forms gallery with a polished form widget system and rewrite the gallery as the canonical reference. Visible polish — buyers grade dashboards by how forms look and feel.

## Context

Per [phases 10–19 roadmap](2026-04-29-phase10-19-roadmap.md#phase-12--forms-20) — current forms render plain Bootstrap-era inputs with no floating labels, no icon prefixes, no rich multi-selects, no file dropzone, no character counters. Material Tailwind / Velzon / Metronic ship 30+ form patterns. This phase ships ours and applies them to the existing flows (customer create, invoice create, profile settings, help article create).

## Goals

- Ten new widgets, each accessible (keyboard + screen reader), each respects `prefers-reduced-motion`.
- Forms gallery becomes the canonical reference: every widget × every state × every size, with copy-paste markup.
- All major existing create/edit forms upgraded to use new widgets — no more plain inputs visible in primary flows.
- Validation states (success / warning / error) rendered consistently across every widget.
- Phase 10 primitives (modal, popover, dropzone shell) are leveraged where it makes sense — no duplication.

## Non-goals

- Multi-step wizard rewrite (already shipped in Phase 8).
- Drag-to-reorder form builder (different product).
- Survey / poll builder.
- Inline cell editing in datatables (deferred follow-up after Phase 11).
- Server-driven schema-to-form (`django-formtools` style) generation — explicit Python forms remain authoritative.
- Image-cropper inside the file uploader (defer; the dropzone surfaces previews only).

## Features

### Widgets shipped

| Widget | Replaces / new | Key behaviour |
|---|---|---|
| `FloatingLabelInput` | plain `<input>` | Label sits inside, floats on focus / fill |
| `FloatingLabelTextarea` | plain `<textarea>` | Same float pattern; auto-grow up to `max-rows` |
| `IconPrefixInput` | new | Icon (lucide name) inside left edge |
| `IconSuffixInput` | new | Icon inside right edge; clickable variant for password show/hide etc. |
| `MultiSelect` | new | Tag-style chips inside the field; keyboard + screen-reader friendly; no jQuery |
| `TagInput` | new | Free-form tags; comma/Enter splits; paste-to-split |
| `Combobox` | new | Typeahead from URL endpoint or static list; HTMX-powered async option load |
| `RichText` | new | Self-hosted EasyMDE; markdown-first, GFM compatible; toolbar configurable |
| `FileDropzone` | new (shell from Phase 10) | Drag-drop, multi-file, image previews, per-file progress, per-file cancel/remove |
| `DateRangePicker` | new | Lightweight vanilla; preset shortcuts; keyboard nav; localized |
| `CharacterCounter` | mixin | Renders `n / max` under any text input/textarea |
| `ConditionalReveal` | Alpine helper | Show/hide group based on another field's value |

### Validation state vocabulary

Every widget recognizes four visual states (mapped from Django form errors / programmatic API):

- **default** — no special styling.
- **success** — green ring + small check icon (e.g. "username available").
- **warning** — amber ring + warning icon (e.g. "weak password but accepted").
- **error** — red ring + error icon + helper-text replaced by error message.

State is set by:
- Django form errors → `error` automatically.
- Programmatic `data-state="success"` on the widget root.
- HTMX async validation endpoint that swaps just the field group.

### Sizes

Every widget supports three sizes via Tailwind classes:

- `sm` (h-8, text-sm) — for toolbars and inline forms.
- `md` (h-10, text-sm) — default.
- `lg` (h-12, text-base) — auth pages, hero forms.

Density-aware: respects the `density-compact / -comfortable / -spacious` classes already shipped.

### Existing forms upgraded

| Surface | Widgets applied |
|---|---|
| Customer create/edit | FloatingLabelInput (name/email), MultiSelect (tags), Combobox (owner), RichText (notes) |
| Invoice create | Combobox (customer), MultiSelect (line-item product picker), DateRangePicker (issued/due), CharacterCounter (notes) |
| Profile settings | FloatingLabelInput, IconPrefixInput (twitter handle, website), FileDropzone (avatar upload, single file image-only) |
| Help article create | FloatingLabelInput (title), Combobox (category), TagInput (tags), RichText (body) |
| Help search | IconPrefixInput (search icon) — preview only |
| Project create | FloatingLabelInput, MultiSelect (members), DateRangePicker (start/end), RichText (description) |
| Mail compose | Combobox (to/cc with contact suggestions), TagInput (cc tag-pill style), FileDropzone (attachments), RichText (body) |
| Settings → Notifications | ConditionalReveal pattern (per-channel sub-options) |

### Forms gallery rewrite

`templates/pages/forms_gallery.html` becomes a 10-section reference. Each section:

1. Section heading + 1-line description.
2. Widget rendered with realistic content.
3. All variants (sizes × states × options) in a grid.
4. Markup snippet via `_codeblock.html`.
5. Accessibility notes (keyboard map, ARIA roles, screen reader behaviour).
6. Backend usage snippet (Python — how to declare in a `forms.Form`).

Add a left-rail TOC mirroring the components library pattern from Phase 10.

## Architecture

### URLs

No new top-level URLs. `/pages/forms/` (existing) is rewritten in-place.

### App layout

```text
apps/core/widgets/
├── __init__.py           public exports
├── inputs.py             FloatingLabelInput, FloatingLabelTextarea, IconPrefixInput, IconSuffixInput
├── choice.py             MultiSelect, TagInput, Combobox
├── rich.py               RichText
├── upload.py             FileDropzone
├── date.py               DateRangePicker
├── helpers.py            CharacterCounter mixin, ConditionalReveal helper
└── tests/
    ├── test_render.py    each widget renders correct HTML structure
    ├── test_validation.py  validation state plumbing
    └── test_upload.py    FileDropzone POST handling

templates/widgets/
├── floating_input.html
├── floating_textarea.html
├── icon_prefix_input.html
├── icon_suffix_input.html
├── multi_select.html
├── tag_input.html
├── combobox.html
├── rich_text.html
├── file_dropzone.html
├── date_range_picker.html
└── _field_wrapper.html   shared label / helper / error block

static_src/js/widgets.ts   Alpine factories: apexFloating(), apexMultiSelect(), apexTagInput(),
                           apexCombobox(), apexRichText(), apexDropzone(), apexDateRange()
```

### Widget API (Django)

All widgets subclass `django.forms.Widget` and accept the same kwargs as their stdlib equivalents, plus widget-specific options:

```python
# apps/core/widgets/inputs.py
from django.forms.widgets import TextInput

class FloatingLabelInput(TextInput):
    template_name = "widgets/floating_input.html"

    def __init__(self, *, size="md", icon=None, suffix=None, helper=None,
                 max_length_counter=False, attrs=None):
        super().__init__(attrs)
        self.size = size
        self.icon = icon
        self.suffix = suffix
        self.helper = helper
        self.max_length_counter = max_length_counter

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        ctx["widget"].update({
            "size": self.size,
            "icon": self.icon,
            "suffix": self.suffix,
            "helper": self.helper,
            "max_length_counter": self.max_length_counter,
        })
        return ctx
```

Usage in a form:

```python
from django import forms
from apps.core.widgets import FloatingLabelInput, MultiSelect, RichText, Combobox

class CustomerForm(forms.ModelForm):
    name = forms.CharField(widget=FloatingLabelInput(icon="user"))
    email = forms.EmailField(widget=FloatingLabelInput(icon="mail"))
    tags = forms.MultipleChoiceField(widget=MultiSelect(creatable=True))
    owner = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=Combobox(async_url="users:typeahead"),
    )
    notes = forms.CharField(required=False, widget=RichText(toolbar="basic"))

    class Meta:
        model = Customer
        fields = ["name", "email", "tags", "owner", "notes"]
```

### Combobox — async option loading

Uses HTMX. Widget renders an `<input>` plus a `<ul role="listbox">` swap target. Typing triggers `hx-get="{async_url}?q=..."` debounced 200ms. Server returns option `<li>` HTML. Selection is via mouse, Enter, or arrow-keys + Enter. Each list view that's used as a combobox source must implement a `?_typeahead=1` mode returning the partial — small mixin in `apps/core/widgets/combobox.py`:

```python
class TypeaheadMixin:
    typeahead_fields = ()
    typeahead_template = "widgets/_combobox_options.html"
    typeahead_limit = 20

    def get(self, request, *args, **kwargs):
        if request.GET.get("_typeahead") == "1":
            qs = self.filter_typeahead(self.get_queryset(), request.GET.get("q", ""))
            return render(request, self.typeahead_template,
                          {"options": qs[:self.typeahead_limit]})
        return super().get(request, *args, **kwargs)
```

### RichText — EasyMDE self-hosted

EasyMDE chosen over TipTap for this phase: smaller bundle (~50KB vs ~200KB), markdown-first matches our blog/help app content, simpler keyboard model, no headless complexity. TipTap is the obvious upgrade later if buyers ask for WYSIWYG with custom blocks.

Bundled via npm, output to `static/js/dist/easymde.js` per Phase 19 bundling — but for Phase 12 we ship the file via `npm install easymde` + a one-shot copy script in `package.json`:

```json
"scripts": {
  "vendor:easymde": "cp node_modules/easymde/dist/easymde.min.js static/js/vendor/easymde.js && cp node_modules/easymde/dist/easymde.min.css static/css/vendor/easymde.css"
}
```

Toolbar presets: `minimal` (bold/italic/link), `basic` (+ heading/list/quote/code), `full` (+ table/image/preview).

### FileDropzone — vanilla, no dep

~120-LOC vanilla JS. Handles:
- Drag enter / over / leave / drop with visual states.
- Click-to-browse fallback.
- Multi-file via `<input type="file" multiple>` mirror.
- Per-file: thumbnail (image MIME types), name, size, progress bar, remove button.
- XHR upload with progress events; one request per file (parallel cap configurable).
- Server endpoint: re-uses Django's standard file upload to a configured target view URL.

API:

```python
FileDropzone(
    upload_url="files:upload",      # POST endpoint
    accept="image/*",                # MIME filter
    max_files=10,
    max_size_mb=20,
    parallel=3,
)
```

Widget renders a hidden `<input>` whose `value` is a JSON list of uploaded file IDs, populated by the dropzone JS as uploads complete. Form `clean_<field>` resolves IDs to model instances.

### DateRangePicker — vanilla, ~200 LOC

Calendar grid, two months side-by-side on desktop, one month on mobile. Preset shortcuts (Today, Yesterday, Last 7 days, Last 30 days, This month, Last month, Custom). Keyboard: arrow keys to navigate days, Enter to select start/end. Localized via `Intl.DateTimeFormat(navigator.language)`.

No external date library — wrapping native `Date` is fine for this scope. If we later add timezone arithmetic or recurring rules, swap to `date-fns` in Phase 19's bundling.

### Styling

All widgets use Tailwind utility classes against the existing OKLCh tokens (`border-input`, `ring-ring`, `bg-card`, `text-foreground`, etc.). No new colors. Validation state colors map to `success / warning / destructive` tokens already defined.

### Accessibility checklist (gates each widget's PR)

- Tab/Shift+Tab order is correct.
- Each widget has a programmatic label association.
- Validation errors are announced via `aria-describedby` + `aria-invalid="true"`.
- Combobox follows ARIA 1.2 combobox pattern.
- MultiSelect chips are reachable + removable via keyboard (Backspace deletes last selected).
- FileDropzone has accessible click trigger + keyboard-triggerable.
- DateRangePicker grid uses `role="grid"` with proper row/cell roles + `aria-selected`.
- Reduced-motion: animations conditional on the media query.
- All widgets pass axe-core with 0 violations.

## Testing

### Unit (~20 new tests)

- Each widget renders expected HTML structure (root class, label position, helper, error slot).
- Each widget honors `size` parameter (correct class applied).
- Validation state plumbing: form with errors renders `error` state for each upgraded widget.
- `FileDropzone` upload endpoint accepts multi-file POST, returns ID list, rejects oversize.
- `Combobox` async endpoint via `TypeaheadMixin` returns expected partial.
- `CharacterCounter` updates remaining count text on input.

### Form integration (~6 new tests)

- Customer create end-to-end: submit form with new widgets, model saved with correct values.
- Invoice create with combobox customer + dropzone attachments.
- Help article create with rich text body — markdown stored, rendered HTML on detail.
- Profile avatar upload via dropzone.
- Project create with date range + multi-select members.
- Mail compose stores recipients from combobox + attachments from dropzone.

### E2E (~6 new tests, marked `e2e`)

- Forms gallery: scroll through, every widget visible and interactive.
- Customer create: fill via floating label inputs + multi-select tags + combobox owner + rich text notes; submit; redirected to detail with values shown.
- Combobox typeahead: type "ad", assert options narrowed; select with Enter; chip appears.
- File dropzone: drag a fake image (Playwright `setInputFiles`), assert preview + progress + saved.
- Date range picker: open, click preset "Last 7 days", assert hidden inputs reflect dates; close.
- Validation: submit invalid form, assert each field shows error state with helper text replaced.

## Dependencies

- `easymde` (npm, dev) — markdown editor; copied to `static/js/vendor/`.
- No new Python deps — uses stdlib `forms.Widget` + existing `django.forms` infra.

## Rollout — 7 commits

1. **docs** — this spec.
2. **scaffolding** — `apps/core/widgets/` package, base templates, `_field_wrapper.html`, validation state plumbing, no per-widget body yet. Update forms gallery to a TOC + empty section placeholders.
3. **inputs group** — FloatingLabelInput, FloatingLabelTextarea, IconPrefixInput, IconSuffixInput + Alpine factory + tests + gallery section.
4. **choice group** — MultiSelect, TagInput, Combobox (incl. TypeaheadMixin) + Alpine factories + tests + gallery section.
5. **upload + date** — FileDropzone (incl. server endpoint reuse via `apps/files`), DateRangePicker + Alpine factories + tests + gallery section.
6. **rich text + helpers** — vendor EasyMDE, RichText widget, CharacterCounter mixin, ConditionalReveal helper + tests + gallery section.
7. **upgrade existing forms + screenshots + E2E** — Customer, Invoice, Profile, Help article, Project, Mail compose all rewritten; 6 E2E tests; refresh screenshots; README/CHANGELOG entries.

## Branch + parent

- Branch: `phase12-forms`
- Parent: `phase11-datatable` (uses Phase 11's `UserPreference` model for "remember last used filter" on combobox; uses Phase 10's modal for confirmation on dropzone remove-all).

## Open questions

- **EasyMDE vs TipTap?** EasyMDE recommended above (smaller, markdown-first). Confirm or override.
- **Combobox: server-render `<option>` HTML or JSON?** Server-rendered HTML keeps the JS dumb and keyboard nav works without re-binding. JSON would let us share the typeahead endpoint with the upcoming Phase 15 API. Suggest: HTML now, Phase 15 adds an `Accept: application/json` variant on the same endpoint so both work.
- **Drag-drop on touch devices?** Native HTML5 drag-drop is shaky on mobile. Suggest: dropzone falls through to "tap to browse" on touch, no drag indicator.
- **Should `MultiSelect` and `TagInput` merge into one widget with a `creatable` flag?** Conceptually yes — but the keyboard + ARIA models differ enough (MultiSelect is a combobox-with-listbox, TagInput is a text-with-tokenizer). Keep them separate; share the chip rendering partial.
- **Error state for async-validated fields (e.g. "username taken"):** debounce 400ms, show spinner during check, then success/error. Implementation lands as a small `ApexAsyncValidate` Alpine helper alongside the inputs group.
