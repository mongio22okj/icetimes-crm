import zlib

from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

register = template.Library()

ICONS = {
    "layout-dashboard": '<rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>',
    "shopping-cart": '<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/>',
    "package": '<path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="M3.3 7 12 12l8.7-5"/><path d="M12 22V12"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "settings": '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
    "dollar-sign": '<line x1="12" x2="12" y1="2" y2="22"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
    "activity": '<path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.5.5 0 0 1-.96 0L9.24 3.18a.5.5 0 0 0-.96 0l-2.35 8.36A2 2 0 0 1 4 13H2"/>',
    "arrow-up-right": '<path d="M7 7h10v10"/><path d="M7 17 17 7"/>',
    "arrow-down-right": '<path d="M7 7v10h10"/><path d="m7 7 10 10"/>',
    "bell": '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
    "log-out": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/>',
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "shield": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
    "shield-off": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0"/><path d="m2 2 20 20"/>',
    "arrow-right": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    "chevron-left": '<path d="m15 18-6-6 6-6"/>',
    "edit-3": '<path d="M12 20h9"/><path d="M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 1-.855.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z"/>',
    "box": '<path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',
    "github": '<path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"/><path d="M9 18c-4.51 2-5-2-7-2"/>',
    "alert-triangle": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "menu": '<line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="18" y2="18"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "user": '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "user-plus": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" x2="19" y1="8" y2="14"/><line x1="22" x2="16" y1="11" y2="11"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "book-open": '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
    "plus": '<path d="M5 12h14"/><path d="M12 5v14"/>',
    "moon": '<path d="M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401"/>',
    "chevron-right": '<path d="m9 18 6-6-6-6"/>',
    "file-text": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z"/><polyline points="14 2 14 8 20 8"/><line x1="16" x2="8" y1="13" y2="13"/><line x1="16" x2="8" y1="17" y2="17"/><line x1="10" x2="8" y1="9" y2="9"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
    "mail": '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
    "star": '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
    "trash": '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    "message-circle": '<path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>',
    "calendar": '<rect width="18" height="18" x="3" y="4" rx="2" ry="2"/><line x1="16" x2="16" y1="2" y2="6"/><line x1="8" x2="8" y1="2" y2="6"/><line x1="3" x2="21" y1="10" y2="10"/>',
    "trello": '<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><rect width="3" height="9" x="7" y="7"/><rect width="3" height="5" x="14" y="7"/>',
    "folder": '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
    "rocket": '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>',
    "eye": '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
    "mouse-pointer": '<path d="M3 3l7.07 16.97 2.51-7.39 7.39-2.51L3 3z"/><path d="M13 13l6 6"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "trending-up": '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
    "trophy": '<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "shopping-bag": '<path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/><line x1="3" x2="21" y1="6" y2="6"/><path d="M16 10a4 4 0 0 1-8 0"/>',
    "rotate-ccw": '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
    "user-minus": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="22" x2="16" y1="11" y2="11"/>',
    "user-check": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><polyline points="16 11 18 13 22 9"/>',
    "bar-chart-3": '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
    "briefcase": '<rect width="20" height="14" x="2" y="7" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>',
    "check": '<polyline points="20 6 9 17 4 12"/>',
    "map-pin": '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
    # ── Components library additions (Phase 10) ──
    "blocks": '<rect width="7" height="7" x="14" y="3" rx="1"/><path d="M10 21V8a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-5a1 1 0 0 0-1-1h-3"/>',
    "panel-right": '<rect width="18" height="18" x="3" y="3" rx="2"/><line x1="15" x2="15" y1="3" y2="21"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "message-square": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    "layout": '<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><line x1="3" x2="21" y1="9" y2="9"/><line x1="9" x2="9" y1="21" y2="9"/>',
    "chevrons-up-down": '<path d="m7 15 5 5 5-5"/><path d="m7 9 5-5 5 5"/>',
    "list-ordered": '<line x1="10" x2="21" y1="6" y2="6"/><line x1="10" x2="21" y1="12" y2="12"/><line x1="10" x2="21" y1="18" y2="18"/><path d="M4 6h1v4"/><path d="M4 10h2"/><path d="M6 18H4c0-1 2-2 2-3s-1-1.5-2-1"/>',
    "calendar-range": '<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/><path d="M17 14h-6"/><path d="M13 18H7"/>',
    "palette": '<circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/><circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"/>',
    "list-checks": '<path d="m3 17 2 2 4-4"/><path d="m3 7 2 2 4-4"/><path d="M13 6h8"/><path d="M13 12h8"/><path d="M13 18h8"/>',
    "tag": '<path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z"/><circle cx="7.5" cy="7.5" r=".5" fill="currentColor"/>',
    "toggle-right": '<rect width="20" height="12" x="2" y="6" rx="6" ry="6"/><circle cx="16" cy="12" r="2"/>',
    "sliders-horizontal": '<line x1="21" x2="14" y1="4" y2="4"/><line x1="10" x2="3" y1="4" y2="4"/><line x1="21" x2="12" y1="12" y2="12"/><line x1="8" x2="3" y1="12" y2="12"/><line x1="21" x2="16" y1="20" y2="20"/><line x1="12" x2="3" y1="20" y2="20"/><line x1="14" x2="14" y1="2" y2="6"/><line x1="8" x2="8" y1="10" y2="14"/><line x1="16" x2="16" y1="18" y2="22"/>',
    "upload-cloud": '<path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M12 12v9"/><path d="m16 16-4-4-4 4"/>',
    "inbox": '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
    "user-circle": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="10" r="3"/><path d="M7 20.662V19a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v1.662"/>',
    "badge": '<path d="M3.85 8.62a4 4 0 0 1 4.78-4.77 4 4 0 0 1 6.74 0 4 4 0 0 1 4.78 4.78 4 4 0 0 1 0 6.74 4 4 0 0 1-4.77 4.78 4 4 0 0 1-6.75 0 4 4 0 0 1-4.78-4.77 4 4 0 0 1 0-6.76Z"/>',
    "loader-circle": '<path d="M21 12a9 9 0 1 1-6.219-8.56"/>',
    "square-stack": '<path d="M4 10c-1.1 0-2 .9-2 2v8c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2"/><path d="M8 6c0-1.1.9-2 2-2h8c1.1 0 2 .9 2 2v8c0 1.1-.9 2-2 2H10a2 2 0 0 1-2-2Z"/>',
    "send": '<path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/><path d="m21.854 2.147-10.94 10.939"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "copy": '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    "clipboard-list": '<rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M12 11h4"/><path d="M12 16h4"/><path d="M8 11h.01"/><path d="M8 16h.01"/>',
    "settings-2": '<path d="M20 7h-9"/><path d="M14 17H5"/><circle cx="17" cy="17" r="3"/><circle cx="7" cy="7" r="3"/>',
    "lightbulb": '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>',
    "plug": '<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"/>',
    "code-2": '<path d="m18 16 4-4-4-4"/><path d="m6 8-4 4 4 4"/><path d="m14.5 4-5 16"/>',
    "code": '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>',
    "table": '<path d="M12 3v18"/><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M3 15h18"/>',
}


@register.simple_tag
def icon(name, size=18, cls=""):
    body = ICONS.get(name, "")
    return mark_safe(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(size)}" height="{int(size)}" '
        f'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true" '
        f'class="{conditional_escape(cls)}">{body}</svg>'
    )


AVATAR_PALETTE = ["#15803d", "#0e7490", "#4f46e5", "#b45309", "#be185d", "#047857", "#6d28d9", "#0369a1"]


@register.filter
def json_dumps(value):
    """JSON-serialize a value for safe embedding in JS contexts.

    Used by widgets that initialize Alpine state from server-side data:
        x-data='{...,  value: {{ initial|json_dumps }}, ... }'

    Output is marked safe — the JSON encoder escapes already.
    """
    import json as _json
    return mark_safe(_json.dumps(value, ensure_ascii=False))


@register.filter
def urlencode_dict(value):
    """URL-encode a dict whose values may be lists (multi-value query params).

    Used by the saved-views switcher to turn a stored {filter: [vals]}
    blob back into `?filter=val1&filter=val2`. Empty / non-dict input
    returns "".
    """
    if not isinstance(value, dict):
        return ""
    from urllib.parse import urlencode
    flat: list[tuple[str, str]] = []
    for k, v in value.items():
        if isinstance(v, list | tuple):
            for item in v:
                flat.append((k, str(item)))
        else:
            flat.append((k, str(v)))
    return urlencode(flat)


@register.filter
def dotted_attr(obj, path):
    """Walk a dotted attribute path on `obj` (e.g. "owner.email").

    Returns "" on any miss along the way (None, AttributeError, KeyError).
    Calls the leaf if it's a callable. Used by the datatable `_row.html`
    partial to render `Column.key` paths without having to write a custom
    `formatter` for every plain-attribute column.
    """
    if obj is None:
        return ""
    cur = obj
    for part in str(path).split("."):
        if cur is None:
            return ""
        try:
            cur = getattr(cur, part)
        except AttributeError:
            try:
                cur = cur[part]
            except (TypeError, KeyError, IndexError):
                return ""
    if callable(cur):
        try:
            cur = cur()
        except TypeError:
            pass
    return cur


@register.filter
def initials(obj):
    if not obj:
        return ""
    # Customer-shaped objects expose an initials() method
    method = getattr(obj, "initials", None)
    if callable(method):
        try:
            return method()
        except TypeError:
            pass
    # User-shaped: first_name + last_name
    first = (getattr(obj, "first_name", "") or "").strip()
    last = (getattr(obj, "last_name", "") or "").strip()
    if first or last:
        return (first[:1] + last[:1]).upper() or "?"
    # Fallback: username (User) or name (Customer)
    name = (getattr(obj, "username", "") or getattr(obj, "name", "") or "").strip()
    return name[:2].upper() if name else "?"


@register.filter
def avatar_color(obj):
    if not obj:
        return AVATAR_PALETTE[0]
    seed = (
        getattr(obj, "pk", None)
        or getattr(obj, "email", "")
        or getattr(obj, "username", "")
        or getattr(obj, "name", "")
        or ""
    )
    return AVATAR_PALETTE[zlib.crc32(str(seed).encode()) % len(AVATAR_PALETTE)]


@register.simple_tag
def active(current_path, href, exact=False, cls="bg-sidebar-accent text-sidebar-accent-foreground"):
    if exact:
        return cls if current_path == href else ""
    # Match the Dashboard "/" link only when current_path is exactly "/"
    if href == "/":
        return cls if current_path == "/" else ""
    return cls if current_path.startswith(href) else ""


@register.simple_tag
def is_active(current_path, href, exact=False):
    """Boolean sibling of `active` — for emitting aria-current="page".

    Mirrors the matching rules of `active()` so the active class and the
    aria attribute always agree.
    """
    if exact:
        return current_path == href
    if href == "/":
        return current_path == "/"
    return current_path.startswith(href)


@register.inclusion_tag("partials/breadcrumbs.html", takes_context=False)
def breadcrumbs(crumbs):
    """Render the breadcrumb bar; returns empty context if fewer than 2 crumbs."""
    crumbs = list(crumbs or [])
    return {"crumbs": crumbs if len(crumbs) >= 2 else []}


@register.simple_tag
def page_ids_script(object_list, table_key):
    """Render `<script id="table-pageids-<key>" type="application/json">[…]</script>`.

    Feeds the apexBulk Alpine factory's "select all on page" logic.
    The script is dropped in via `{% page_ids_script object_list config.key %}`
    inside the table partial.
    """
    import json
    pks = [getattr(o, "pk", None) for o in object_list if getattr(o, "pk", None) is not None]
    payload = json.dumps(pks)
    return mark_safe(
        f'<script id="table-pageids-{conditional_escape(table_key)}" '
        f'type="application/json">{payload}</script>'
    )


@register.simple_tag(takes_context=True)
def sort_link(context, column_key, label):
    """Render a sortable column header anchor.

    Toggles asc → desc → unsorted on each click. HTMX swaps the wrapping
    `#table-<key>` div so the click feels instant.
    """
    request = context["request"]
    config = context["config"]
    current_sort = request.GET.get("sort", "")
    # Determine current direction for THIS column (multi-sort: take the first
    # term that matches; everything else is preserved as-is).
    direction = None
    new_sort = column_key
    arrow = '<span class="opacity-30">↕</span>'
    for term in current_sort.split(","):
        term = term.strip()
        if term.lstrip("-") != column_key:
            continue
        direction = "desc" if term.startswith("-") else "asc"
        break
    if direction == "asc":
        new_sort = f"-{column_key}"
        arrow = "↓"
    elif direction == "desc":
        new_sort = ""  # next click clears the sort
        arrow = "↑"

    params = request.GET.copy()
    if new_sort:
        params["sort"] = new_sort
    else:
        params.pop("sort", None)
    params.pop("page", None)  # always reset to page 1 on sort change
    qs = params.urlencode()
    href = f"{request.path}?{qs}" if qs else request.path

    target = f"#table-{config.key}"
    swap_url = f"{href}{'&' if '?' in href else '?'}_partial=table"
    aria = "ascending" if direction == "asc" else "descending" if direction == "desc" else "none"

    return mark_safe(
        f'<a href="{conditional_escape(href)}" '
        f'hx-get="{conditional_escape(swap_url)}" '
        f'hx-target="{conditional_escape(target)}" '
        f'hx-swap="outerHTML" '
        f'hx-push-url="{conditional_escape(href)}" '
        f'aria-sort="{aria}" '
        f'class="inline-flex items-center gap-1 hover:text-foreground transition">'
        f'{conditional_escape(label)} {arrow}'
        f'</a>'
    )


@register.simple_tag(takes_context=True)
def table_url(context, **overrides):
    """Build a table URL preserving current params with optional overrides.

    Used by pagination links + saved-view switcher etc. A param set to None
    is removed; otherwise it's set/replaced.
    """
    request = context["request"]
    params = request.GET.copy()
    for k, v in overrides.items():
        if v is None:
            params.pop(k, None)
        else:
            params[k] = v
    params.pop("_partial", None)  # don't ever leak the swap flag into URLs
    qs = params.urlencode()
    return f"{request.path}?{qs}" if qs else request.path


@register.inclusion_tag("widgets/_field_wrapper.html")
def apex_field(bound_field, label=None, helper=None, label_above=True):
    """Render a Django BoundField wrapped in the canonical Apex field shell.

    The wrapper provides label, the widget itself, helper text, character
    counter (if the widget enables it), and per-state colored ring/error
    text. State is derived from `apps.core.widgets._base.field_state` —
    so a form with errors auto-renders the "error" state without callers
    needing to do anything.

    Args:
        bound_field: a Django BoundField (`form["name"]`).
        label: override label text (default = bound_field.label).
        helper: override helper text (default = widget.helper or bound_field.help_text).
        label_above: when False, suppresses the label (useful for inline
                     forms where the label lives elsewhere).
    """
    from apps.core.widgets._base import field_state, field_state_classes

    state = field_state(bound_field)
    widget = bound_field.field.widget
    return {
        "field": bound_field,
        "label": label if label is not None else bound_field.label,
        "label_above": label_above,
        "helper": (helper if helper is not None
                   else getattr(widget, "helper", None) or bound_field.help_text),
        "state": state,
        "state_classes": field_state_classes(state),
        "errors": list(bound_field.errors) if bound_field.errors else [],
        "id": bound_field.auto_id,
        "required": bound_field.field.required,
    }


@register.inclusion_tag("partials/toasts.html", takes_context=True)
def apex_toasts(context):
    """Render the toast container, draining all unread Django messages.

    Each message becomes a toast with level + body + optional action +
    optional persistent flag, parsed out of `extra_tags` by
    apps.core.messages.parse_extra_tags.
    """
    from django.contrib.messages import get_messages

    from apps.core.messages import parse_extra_tags

    request = context.get("request")
    payload = []
    if request is not None:
        for m in get_messages(request):
            meta = parse_extra_tags(m.extra_tags)
            payload.append({
                "level": m.level_tag,  # success | info | warning | error | debug
                "body": str(m),
                "action": meta["action"],
                "persistent": meta["persistent"],
            })
    return {"toasts_payload": payload}
