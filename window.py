#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gdk, GLib, Gio, Pango
import threading
import datetime
from pathlib import Path

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from engine import (
    Config, EventLog, Scanner, QuarantineManager,
    EncryptionEngine, RealTimeMonitor, SecurityEvent
)

# ── Tutarlı tasarım sabitleri ─────────────────────────────────────────────────
PAGE_M   = 28   # sayfa kenar boşluğu
CARD_SP  = 12   # kartlar arası spacing
SECT_SP  = 20   # bölümler arası spacing

CSS = """
* { box-sizing: border-box; }

.darksq-sidebar {
    background-color: alpha(@window_bg_color, 0.6);
    border-right: 1px solid alpha(@borders, 0.5);
}
.sidebar-btn {
    border-radius: 8px;
    padding: 9px 14px;
    margin: 1px 10px;
    font-size: 13px;
}
.sidebar-btn.active {
    background-color: alpha(@accent_bg_color, 0.15);
    font-weight: 600;
}
.sidebar-label { font-size: 13px; }
.sidebar-section {
    font-size: 10px;
    font-weight: 700;
    opacity: 0.4;
    letter-spacing: 0.8px;
    margin: 12px 14px 4px 14px;
}

/* Kartlar */
.card {
    border-radius: 12px;
    padding: 16px;
    background-color: @card_bg_color;
    border: 1px solid alpha(@borders, 0.3);
}
.hero-card {
    border-radius: 16px;
    padding: 22px 24px;
    background-color: @card_bg_color;
    border: 1px solid alpha(@borders, 0.3);
}
.stat-card {
    border-radius: 12px;
    padding: 14px 16px;
    background-color: @card_bg_color;
    border: 1px solid alpha(@borders, 0.3);
    margin: 3px;
}

/* Tipografi */
.page-title  { font-size: 22px; font-weight: 700; letter-spacing: -0.3px; }
.page-sub    { font-size: 12px; opacity: 0.5; font-weight: 400; }
.sect-title  { font-size: 13px; font-weight: 600; opacity: 0.7; letter-spacing: 0.2px; }
.metric-val  { font-size: 24px; font-weight: 700; letter-spacing: -0.5px; }
.metric-lbl  { font-size: 10px; font-weight: 600; opacity: 0.5; letter-spacing: 0.4px; }

/* Rozet */
.badge-ok {
    border-radius: 20px; padding: 3px 12px;
    background-color: alpha(#30d158, 0.12); color: #30d158;
    font-weight: 700; font-size: 10px; letter-spacing: 0.5px;
}
.badge-danger {
    border-radius: 20px; padding: 3px 12px;
    background-color: alpha(#ff453a, 0.12); color: #ff453a;
    font-weight: 700; font-size: 10px;
}

/* Olaylar */
.ev-info   { color: @accent_bg_color; }
.ev-warn   { color: #ff9f0a; }
.ev-danger { color: #ff453a; }

/* Satır stilleri */
.threat-row {
    border-radius: 10px; padding: 12px 14px; margin: 2px 0;
    background-color: alpha(#ff453a, 0.05);
    border: 1px solid alpha(#ff453a, 0.15);
}
.qrow {
    border-radius: 10px; padding: 12px 14px; margin: 2px 0;
    background-color: alpha(#ff9f0a, 0.05);
    border: 1px solid alpha(#ff9f0a, 0.18);
}
.ev-row {
    border-radius: 8px; padding: 8px 10px; margin: 1px 0;
}
.ev-row:hover { background-color: alpha(@accent_bg_color, 0.06); }

/* Şifreleme drop zone */
.drop-zone {
    border-radius: 14px;
    border: 1.5px dashed alpha(@accent_bg_color, 0.35);
    padding: 28px 20px;
    background-color: alpha(@accent_bg_color, 0.03);
}

/* Butonlar */
.action-btn  { border-radius: 8px; padding: 8px 18px; font-weight: 600; font-size: 13px; }
.pill-btn    { border-radius: 20px; padding: 6px 18px; font-weight: 600; font-size: 12px; }

/* Toggle satırı */
.toggle-row {
    border-radius: 10px; padding: 13px 16px; margin: 2px 0;
    background-color: @card_bg_color;
    border: 1px solid alpha(@borders, 0.28);
}
.info-row {
    border-radius: 10px; padding: 11px 16px; margin: 2px 0;
    background-color: alpha(@window_bg_color, 0.5);
    border: 1px solid alpha(@borders, 0.2);
}
"""

# ── Yardımcı fonksiyonlar ─────────────────────────────────────────────────────

def lbl(text, css=None, halign=Gtk.Align.START, wrap=False, ellipsize=None):
    w = Gtk.Label(label=text, halign=halign, wrap=wrap)
    if css:
        for c in css: w.add_css_class(c)
    if ellipsize: w.set_ellipsize(ellipsize)
    return w

def ico(name, size=16, css=None):
    w = Gtk.Image.new_from_icon_name(name)
    w.set_pixel_size(size)
    if css:
        for c in css: w.add_css_class(c)
    return w

def hbox(sp=8):
    return Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=sp)

def vbox(sp=6):
    return Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=sp)

def scroll(child):
    s = Gtk.ScrolledWindow()
    s.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    s.set_child(child)
    return s

def clear_box(box):
    child = box.get_first_child()
    while child:
        nxt = child.get_next_sibling()
        box.remove(child)
        child = nxt

def page_box():
    """Standart sayfa wrapper'ı"""
    b = vbox(SECT_SP)
    b.set_margin_top(PAGE_M); b.set_margin_bottom(PAGE_M)
    b.set_margin_start(PAGE_M); b.set_margin_end(PAGE_M)
    return b

def card(child_or_list, css='card'):
    c = vbox(10)
    c.add_css_class(css)
    if isinstance(child_or_list, list):
        for ch in child_or_list: c.append(ch)
    else:
        c.append(child_or_list)
    return c

# ── Ana pencere ───────────────────────────────────────────────────────────────

class DarkSQWindow(Gtk.ApplicationWindow):
    zexisv = "X1"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title('DarkSQ')
        self.set_default_size(1100, 720)
        self.set_size_request(880, 600)

        provider = Gtk.CssProvider()
        try:
            provider.load_from_data(CSS, -1)
        except TypeError:
            try:
                provider.load_from_data(CSS.encode())
            except TypeError:
                provider.load_from_data(CSS.encode(), len(CSS.encode()))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.config        = Config()
        self.event_log     = EventLog()
        self.quarantine_mgr = QuarantineManager(self.event_log)
        self.rt_monitor    = RealTimeMonitor(
            self.config, self.event_log,
            alert_cb=lambda ev: GLib.idle_add(self._on_rt_alert, ev))
        self._scan_thread      = None
        self._current_scanner  = None
        self._active_page      = 'dashboard'
        self._sidebar_buttons  = {}
        self.dashboard_events_box = vbox(2)

        self._build_ui()
        self._start_stats_updater()
        if self.config.get('realtime_protection'):
            self.rt_monitor.start()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        header = Gtk.HeaderBar()
        header.set_show_title_buttons(True)
        header.set_decoration_layout('close,minimize,maximize:')
        self.set_titlebar(header)

        root = hbox(0)
        root.set_vexpand(True); root.set_hexpand(True)

        sidebar = self._build_sidebar()
        sidebar.set_size_request(210, -1)
        root.append(sidebar)
        root.append(Gtk.Separator())

        self.content_stack = Gtk.Stack()
        self.content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.content_stack.set_transition_duration(250)
        self.content_stack.set_hexpand(True)
        self.content_stack.set_vexpand(True)

        pages = [
            ('dashboard',  self._build_dashboard),
            ('scan',       self._build_scan_page),
            ('events',     self._build_events_page),
            ('quarantine', self._build_quarantine_page),
            ('encrypt',    self._build_encrypt_page),
            ('settings',   self._build_settings_page),
        ]
        for name, builder in pages:
            self.content_stack.add_named(builder(), name)

        root.append(self.content_stack)

        self._toast_overlay = Adw.ToastOverlay()
        self._toast_overlay.set_child(root)
        self.set_child(self._toast_overlay)
        self.content_stack.set_visible_child_name('dashboard')
        self._sidebar_buttons['dashboard'].add_css_class('active')

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self):
        box = vbox(0)
        box.add_css_class('darksq-sidebar')
        box.set_vexpand(True)

        # Logo
        logo = hbox(10)
        logo.set_margin_top(18); logo.set_margin_bottom(12)
        logo.set_margin_start(14); logo.set_margin_end(14)
        logo.set_valign(Gtk.Align.CENTER)
        logo.append(ico('security-high-symbolic', 24, ['accent']))
        t = vbox(1)
        title_lbl = lbl('DarkSQ', ['page-title'])
        title_lbl.set_margin_bottom(0)
        t.append(title_lbl)
        t.append(lbl('ZeXis Security', ['page-sub']))
        logo.append(t)
        box.append(logo)
        box.append(Gtk.Separator())

        sp = Gtk.Box(); sp.set_size_request(-1, 4); box.append(sp)

        nav = [
            ('dashboard',  'view-grid-symbolic',            'Gösterge Paneli'),
            ('scan',       'folder-saved-search-symbolic',  'Tarama'),
            ('events',     'document-open-recent-symbolic', 'Olaylar'),
            ('quarantine', 'process-stop-symbolic',         'Karantina'),
            ('encrypt',    'channel-secure-symbolic',       'Şifreleme'),
            ('settings',   'preferences-system-symbolic',   'Ayarlar'),
        ]
        for pid, iname, label_text in nav:
            btn = Gtk.Button()
            btn.add_css_class('flat')
            btn.add_css_class('sidebar-btn')
            row = hbox(10)
            row.set_valign(Gtk.Align.CENTER)
            row.append(ico(iname, 16))
            l = lbl(label_text, ['sidebar-label'], halign=Gtk.Align.START)
            l.set_hexpand(True)
            row.append(l)
            btn.set_child(row)
            btn.connect('clicked', self._nav, pid)
            self._sidebar_buttons[pid] = btn
            box.append(btn)

        sp2 = Gtk.Box(); sp2.set_vexpand(True); box.append(sp2)
        box.append(Gtk.Separator())

        ver = lbl(f'v{self.config.get("version")}  ·  ZeXis {self.zexisv}',
                  ['page-sub'], halign=Gtk.Align.CENTER)
        ver.set_margin_top(10); ver.set_margin_bottom(12)
        box.append(ver)
        return box

    def _nav(self, btn, page_id):
        if self._active_page:
            self._sidebar_buttons[self._active_page].remove_css_class('active')
        self._sidebar_buttons[page_id].add_css_class('active')
        self._active_page = page_id
        self.content_stack.set_visible_child_name(page_id)

    # ── Dashboard ─────────────────────────────────────────────────────────────

    def _build_dashboard(self):
        outer = page_box()

        # Başlık satırı
        hdr = hbox(0)
        hdr.append(lbl('Gösterge Paneli', ['page-title']))
        dl = lbl(datetime.date.today().strftime('%d %B %Y'), ['page-sub'], halign=Gtk.Align.END)
        dl.set_hexpand(True)
        hdr.append(dl)
        outer.append(hdr)

        # Hero
        outer.append(self._build_hero())

        # İstatistik kartları — eşit genişlikte 4 kart
        stats_row = hbox(0)
        stats_row.set_homogeneous(True)
        self.stat_files   = self._stat_card('0',  'TARANAN',  'folder-symbolic')
        self.stat_threats = self._stat_card('0',  'TEHDİT',   'security-low-symbolic')
        self.stat_cpu     = self._stat_card('—',  'CPU',      'preferences-system-symbolic')
        self.stat_ram     = self._stat_card('—',  'RAM',      'drive-harddisk-symbolic')
        for s in [self.stat_files, self.stat_threats, self.stat_cpu, self.stat_ram]:
            stats_row.append(s)
        outer.append(stats_row)

        # Hızlı işlemler
        outer.append(lbl('Hızlı İşlemler', ['sect-title']))
        qa = hbox(10)
        qa.set_homogeneous(True)
        for label_text, css_list, cb in [
            ('⚡  Hızlı Tarama', ['suggested-action', 'action-btn'], lambda b: self._quick_scan()),
            ('🗂  Dosya Tara',   ['action-btn'],                     lambda b: self._pick_file_scan()),
            ('🔒  Karantina',    ['destructive-action', 'action-btn'],lambda b: self._nav(None, 'quarantine')),
        ]:
            b = Gtk.Button(label=label_text)
            for c in css_list: b.add_css_class(c)
            b.connect('clicked', cb)
            qa.append(b)
        outer.append(card(qa))

        # Son olaylar
        outer.append(lbl('Son Olaylar', ['sect-title']))
        ev_card = vbox(0)
        ev_card.add_css_class('card')
        ev_card.append(self.dashboard_events_box)
        outer.append(ev_card)

        self._refresh_dash_events()
        return scroll(outer)

    def _build_hero(self):
        c = hbox(24)
        c.add_css_class('hero-card')

        # Kalkan
        shield_box = vbox(8)
        shield_box.set_valign(Gtk.Align.CENTER)
        shield_box.set_halign(Gtk.Align.CENTER)
        shield_box.set_margin_end(8)
        self._shield_icon = ico('security-high-symbolic', 48, ['success'])
        shield_box.append(self._shield_icon)
        self._protection_badge = lbl('KORUNUYOR', ['badge-ok'], halign=Gtk.Align.CENTER)
        shield_box.append(self._protection_badge)
        c.append(shield_box)

        # Bilgi
        info = vbox(4)
        info.set_hexpand(True)
        info.set_valign(Gtk.Align.CENTER)
        self._hero_title = lbl('Sisteminiz Korunuyor', ['page-title'])
        self._hero_sub   = lbl('Gerçek zamanlı koruma aktif. Tüm sistemler normal.', ['page-sub'])
        self._hero_sub.set_wrap(True)
        self._last_scan  = lbl('Son tarama: Henüz yapılmadı', ['page-sub'])
        info.append(self._hero_title)
        info.append(self._hero_sub)
        info.append(self._last_scan)
        c.append(info)
        return c

    def _stat_card(self, value, label_text, icon_name):
        c = vbox(4)
        c.add_css_class('stat-card')
        c.append(ico(icon_name, 16, ['accent']))
        val = lbl(value, ['metric-val'])
        c.append(val)
        c.append(lbl(label_text, ['metric-lbl']))
        c._val = val
        return c

    def _refresh_dash_events(self):
        clear_box(self.dashboard_events_box)
        events = self.event_log.get_recent(5)
        if not events:
            empty = lbl('Henüz olay yok.', ['page-sub'])
            empty.set_margin_top(6); empty.set_margin_bottom(6)
            self.dashboard_events_box.append(empty)
            return
        for ev in events:
            self.dashboard_events_box.append(self._ev_row(ev))

    def _ev_row(self, ev_dict):
        row = hbox(10)
        row.add_css_class('ev-row')
        sev = ev_dict.get('severity', 'info')
        imap = {
            'info':    'emblem-ok-symbolic',
            'warning': 'dialog-warning-symbolic',
            'danger':  'dialog-error-symbolic'
        }
        ic = ico(imap.get(sev, 'dialog-information-symbolic'), 14,
                 ['ev-info' if sev == 'info' else f'ev-{sev}'])
        ic.set_valign(Gtk.Align.START)
        ic.set_margin_top(2)
        row.append(ic)

        t = vbox(1)
        t.set_hexpand(True)
        msg = ev_dict.get('message', '')
        try:
            ts_fmt = datetime.datetime.fromisoformat(
                ev_dict.get('timestamp', '')).strftime('%H:%M')
        except Exception:
            ts_fmt = ''
        ml = lbl(msg, wrap=True)
        ml.set_ellipsize(Pango.EllipsizeMode.END)
        ml.set_max_width_chars(60)
        t.append(ml)
        t.append(lbl(ts_fmt, ['page-sub']))
        row.append(t)
        return row

    # ── Tarama ────────────────────────────────────────────────────────────────

    def _build_scan_page(self):
        outer = page_box()
        outer.append(lbl('Tarama', ['page-title']))
        outer.append(lbl('Sistem dosyalarını güvenlik tehditlerine karşı tara', ['page-sub']))

        btns = hbox(8)
        for label_text, css_list, cb in [
            ('⚡  Hızlı Tarama',        ['suggested-action', 'action-btn'], lambda b: self._quick_scan()),
            ('🗂  Dosya/Klasör Seç',    ['action-btn'],                     lambda b: self._pick_file_scan()),
            ('🔍  Tam Sistem Taraması', ['action-btn'],                     lambda b: self._full_scan()),
        ]:
            b = Gtk.Button(label=label_text)
            for c in css_list: b.add_css_class(c)
            b.connect('clicked', cb)
            btns.append(b)
        outer.append(btns)

        # İlerleme kartı
        prog = vbox(10)
        prog.add_css_class('card')
        self.scan_status = lbl('Tarama bekleniyor…', ['page-sub'])
        self.scan_file_l = lbl('', ['page-sub'], ellipsize=Pango.EllipsizeMode.START)
        self.scan_bar    = Gtk.ProgressBar()
        self.scan_bar.set_fraction(0)
        self.scan_result = lbl('', halign=Gtk.Align.CENTER)
        self.stop_btn    = Gtk.Button(label='Durdur')
        self.stop_btn.add_css_class('destructive-action')
        self.stop_btn.add_css_class('pill-btn')
        self.stop_btn.set_halign(Gtk.Align.END)
        self.stop_btn.set_sensitive(False)
        self.stop_btn.connect('clicked', lambda b: self._stop_scan())
        for w in [self.scan_status, self.scan_file_l, self.scan_bar,
                  self.scan_result, self.stop_btn]:
            prog.append(w)
        outer.append(prog)

        outer.append(lbl('Bulunan Tehditler', ['sect-title']))
        self.threats_box = vbox(4)
        outer.append(card(self.threats_box))
        self.no_threat_lbl = lbl('Henüz tehdit bulunamadı.', ['page-sub'])
        self.no_threat_lbl.set_margin_top(4)
        self.no_threat_lbl.set_margin_bottom(4)
        self.threats_box.append(self.no_threat_lbl)

        return scroll(outer)

    def _clear_threats(self):
        clear_box(self.threats_box)
        self.threats_box.append(self.no_threat_lbl)

    def _add_threat(self, file_path, threat_name):
        def do():
            if self.no_threat_lbl.get_parent() == self.threats_box:
                self.threats_box.remove(self.no_threat_lbl)
            row = hbox(12); row.add_css_class('threat-row')
            row.append(ico('dialog-error-symbolic', 18))
            info = vbox(3); info.set_hexpand(True)
            info.append(lbl(Path(file_path).name))
            info.append(lbl(threat_name, ['ev-danger']))
            info.append(lbl(file_path, ['page-sub'], ellipsize=Pango.EllipsizeMode.START))
            row.append(info)
            qb = Gtk.Button(label='Karantinaya Al')
            qb.add_css_class('destructive-action')
            qb.add_css_class('pill-btn')
            qb.set_valign(Gtk.Align.CENTER)
            qb.connect('clicked', lambda b, f=file_path, r=row: self._quarantine_file(f, r))
            row.append(qb)
            self.threats_box.append(row)
        GLib.idle_add(do)

    def _quick_scan(self): self._start_scan(str(Path.home()))
    def _full_scan(self):  self._start_scan('/')

    def _pick_file_scan(self):
        d = Gtk.FileDialog(); d.set_title('Taranacak Dosya/Klasör Seç')
        d.open(self, None, self._on_picked_scan)

    def _on_picked_scan(self, dialog, result):
        try:
            f = dialog.open_finish(result)
            if f: self._start_scan(f.get_path())
        except Exception: pass

    def _start_scan(self, path):
        if self._scan_thread and self._scan_thread.is_alive(): return
        self._clear_threats()
        self.scan_bar.set_fraction(0)
        self.scan_result.set_text('')
        self.scan_status.set_text(f'Taranıyor: {path}')
        self.stop_btn.set_sensitive(True)
        self._nav(None, 'scan')

        def prog_cb(scanned, total, cur):
            def u():
                self.scan_bar.set_fraction(scanned / max(total, 1))
                self.scan_status.set_text(f'{scanned} / {total} dosya tarandı')
                self.scan_file_l.set_text(cur)
            GLib.idle_add(u)

        scanner = Scanner(self.config, self.event_log, prog_cb, self._add_threat)
        self._current_scanner = scanner

        def run():
            scanned, threats = scanner.scan_path(path)
            def done():
                self.scan_bar.set_fraction(1.0)
                self.stop_btn.set_sensitive(False)
                self.scan_result.set_text(f'✓  Tamamlandı — {scanned} dosya, {threats} tehdit')
                self._last_scan.set_text(
                    f'Son tarama: {datetime.datetime.now().strftime("%d.%m.%Y %H:%M")}')
                self.stat_files._val.set_text(str(self.config.get('files_scanned_today')))
                self.stat_threats._val.set_text(str(threats))
                self._refresh_dash_events()
                self._refresh_events_list()
            GLib.idle_add(done)

        self._scan_thread = threading.Thread(target=run, daemon=True)
        self._scan_thread.start()

    def _stop_scan(self):
        if self._current_scanner: self._current_scanner.stop()
        self.stop_btn.set_sensitive(False)
        self.scan_status.set_text('Tarama durduruldu.')

    def _quarantine_file(self, file_path, row):
        try:
            self.quarantine_mgr.quarantine(file_path)
            self.threats_box.remove(row)
            self._refresh_quarantine_list()
            self._refresh_dash_events()
            self._toast('Dosya karantinaya alındı')
        except Exception as e:
            self._toast(f'Hata: {e}')

    # ── Olaylar ───────────────────────────────────────────────────────────────

    def _build_events_page(self):
        outer = page_box()
        hdr = hbox(0)
        hdr.append(lbl('Sistem Olayları', ['page-title']))
        rb = Gtk.Button()
        rb.set_icon_name('view-refresh-symbolic')
        rb.add_css_class('flat')
        rb.set_halign(Gtk.Align.END)
        rb.set_hexpand(True)
        rb.connect('clicked', lambda b: self._refresh_events_list())
        hdr.append(rb)
        outer.append(hdr)
        outer.append(lbl('Güvenlik olayları ve sistem aktivitesi', ['page-sub']))

        self.events_list = vbox(0)
        ec = vbox(0); ec.add_css_class('card'); ec.append(self.events_list)
        s = Gtk.ScrolledWindow()
        s.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        s.set_vexpand(True)
        s.set_child(ec)
        outer.append(s)

        self._refresh_events_list()
        return outer

    def _refresh_events_list(self):
        clear_box(self.events_list)
        events = self.event_log.get_recent(60)
        if not events:
            empty = lbl('Henüz olay kaydedilmedi.', ['page-sub'])
            empty.set_margin_top(8); empty.set_margin_bottom(8)
            self.events_list.append(empty)
            return
        for ev in events:
            self.events_list.append(self._ev_row(ev))

    # ── Karantina ─────────────────────────────────────────────────────────────

    def _build_quarantine_page(self):
        outer = page_box()
        outer.append(lbl('Karantina', ['page-title']))
        outer.append(lbl('Tehlikeli olarak işaretlenen ve izole edilen dosyalar', ['page-sub']))

        self.qlist = vbox(4)
        qc = vbox(0); qc.add_css_class('card'); qc.append(self.qlist)
        s = Gtk.ScrolledWindow()
        s.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        s.set_vexpand(True)
        s.set_child(qc)
        outer.append(s)

        self._refresh_quarantine_list()
        return outer

    def _refresh_quarantine_list(self):
        clear_box(self.qlist)
        items = self.quarantine_mgr.list_quarantined()
        if not items:
            empty = lbl('Karantina boş. İyi günler! ✓', ['page-sub'])
            empty.set_margin_top(6); empty.set_margin_bottom(6)
            self.qlist.append(empty)
            return
        for qp in items:
            row = hbox(12); row.add_css_class('qrow')
            row.append(ico('process-stop-symbolic', 18))
            info = vbox(3); info.set_hexpand(True)
            info.append(lbl(qp.stem))
            info.append(lbl(str(qp), ['page-sub'], ellipsize=Pango.EllipsizeMode.START))
            row.append(info)
            btns = hbox(6)
            btns.set_valign(Gtk.Align.CENTER)
            rb2 = Gtk.Button(label='Geri Yükle')
            rb2.add_css_class('pill-btn')
            db  = Gtk.Button(label='Sil')
            db.add_css_class('destructive-action')
            db.add_css_class('pill-btn')
            rb2.connect('clicked', lambda b, p=qp, r=row: self._restore_q(str(p), r))
            db.connect('clicked',  lambda b, p=qp, r=row: self._delete_q(str(p), r))
            btns.append(rb2); btns.append(db)
            row.append(btns)
            self.qlist.append(row)

    def _restore_q(self, path, row):
        try:
            self.quarantine_mgr.restore(path)
            self.qlist.remove(row)
            self._refresh_dash_events()
            self._toast('Dosya geri yüklendi')
        except Exception as e:
            self._toast(f'Hata: {e}')

    def _delete_q(self, path, row):
        d = Adw.MessageDialog(transient_for=self, heading='Kalıcı Sil',
                              body='Bu dosya kalıcı olarak silinecek. Devam edilsin mi?')
        d.add_response('cancel', 'İptal')
        d.add_response('delete', 'Sil')
        d.set_response_appearance('delete', Adw.ResponseAppearance.DESTRUCTIVE)
        d.connect('response', lambda dlg, r, p=path, r2=row: self._confirm_delete(r, p, r2))
        d.present()

    def _confirm_delete(self, response, path, row):
        if response == 'delete':
            self.quarantine_mgr.delete(path)
            self.qlist.remove(row)
            self._refresh_dash_events()
            self._toast('Kalıcı olarak silindi')

    # ── Şifreleme ─────────────────────────────────────────────────────────────

    def _build_encrypt_page(self):
        outer = page_box()
        outer.append(lbl('Dosya Şifreleme', ['page-title']))
        outer.append(lbl('Dosyaları .zxfe formatında şifrele veya geri çöz', ['page-sub']))

        # Şifrele kartı
        enc_inner = vbox(12)
        enc_inner.append(lbl('🔐  Dosya Şifrele', ['sect-title']))
        drop = vbox(12)
        drop.add_css_class('drop-zone')
        drop.set_halign(Gtk.Align.FILL)
        drop.set_valign(Gtk.Align.CENTER)
        drop.append(ico('channel-secure-symbolic', 36, ['accent']))
        drop.append(lbl('Şifrelenecek dosyayı seçin', halign=Gtk.Align.CENTER))
        drop.append(lbl('.zxfe uzantısıyla aynı klasöre kaydedilir',
                        ['page-sub'], halign=Gtk.Align.CENTER))
        eb = Gtk.Button(label='Dosya Seç ve Şifrele')
        eb.add_css_class('suggested-action')
        eb.add_css_class('action-btn')
        eb.set_halign(Gtk.Align.CENTER)
        eb.connect('clicked', lambda b: self._pick_encrypt())
        drop.append(eb)
        enc_inner.append(drop)
        outer.append(card(enc_inner))

        # Çöz kartı
        dec_inner = vbox(10)
        dec_inner.append(lbl('🔓  Dosya Çöz', ['sect-title']))
        dec_inner.append(lbl('.zxfe dosyasını orijinal formatına geri dönüştür', ['page-sub']))
        db = Gtk.Button(label='.zxfe Dosyası Seç ve Çöz')
        db.add_css_class('action-btn')
        db.connect('clicked', lambda b: self._pick_decrypt())
        dec_inner.append(db)
        outer.append(card(dec_inner))

        self.enc_result = lbl('', ['page-sub'], wrap=True)
        outer.append(self.enc_result)

        return scroll(outer)

    def _pick_encrypt(self):
        d = Gtk.FileDialog(); d.set_title('Şifrelenecek Dosyayı Seç')
        d.open(self, None, self._on_encrypt_picked)

    def _on_encrypt_picked(self, dialog, result):
        try:
            f = dialog.open_finish(result)
            if f:
                try:
                    dest = EncryptionEngine.encrypt_file(f.get_path())
                    self.event_log.add(SecurityEvent(
                        'encrypt', f'Şifrelendi: {Path(f.get_path()).name}', 'info'))
                    self.enc_result.set_text(f'✓  Şifrelendi: {dest}')
                    self._toast('Dosya şifrelendi')
                    self._refresh_dash_events()
                except Exception as e:
                    self.enc_result.set_text(f'Hata: {e}')
        except Exception: pass

    def _pick_decrypt(self):
        d = Gtk.FileDialog(); d.set_title('.zxfe Dosyasını Seç')
        ff = Gtk.FileFilter()
        ff.set_name('ZeXis Encrypted (*.zxfe)')
        ff.add_pattern('*.zxfe')
        ls = Gio.ListStore.new(Gtk.FileFilter)
        ls.append(ff)
        d.set_filters(ls)
        d.open(self, None, self._on_decrypt_picked)

    def _on_decrypt_picked(self, dialog, result):
        try:
            f = dialog.open_finish(result)
            if f:
                try:
                    dest = EncryptionEngine.decrypt_file(f.get_path())
                    self.event_log.add(SecurityEvent(
                        'decrypt', f'Çözüldü: {Path(f.get_path()).name}', 'info'))
                    self.enc_result.set_text(f'✓  Çözüldü: {dest}')
                    self._toast('Dosya çözüldü')
                    self._refresh_dash_events()
                except Exception as e:
                    self.enc_result.set_text(f'Hata: {e}')
        except Exception: pass

    # ── Ayarlar ───────────────────────────────────────────────────────────────

    def _build_settings_page(self):
        outer = page_box()
        outer.append(lbl('Ayarlar', ['page-title']))
        outer.append(lbl('Koruma ve tarama tercihlerinizi yönetin', ['page-sub']))

        # Koruma toggleları
        outer.append(lbl('KORUMA', ['sect-title']))
        for key, title, subtitle, cb in [
            ('realtime_protection', 'Gerçek Zamanlı Koruma',
             'Downloads ve /tmp klasörlerini anlık izler', self._on_rt_toggle),
            ('zexis_ecosystem', 'ZeXis Ekosistemi Koruması',
             'ZeXis özel dosya ve klasörlerini korur', None),
            ('daily_scan', 'Günlük Otomatik Tarama',
             'Her gün sistemi otomatik olarak tarar', None),
        ]:
            outer.append(self._toggle_row(key, title, subtitle, cb))

        # Uygulama bilgisi
        outer.append(lbl('UYGULAMA BİLGİSİ', ['sect-title']))
        for title, value in [
            ('Sürüm',            self.config.get('version')),
            ('ZeXis Serisi',     self.zexisv),
            ('İşletim Sistemi',  'ZeXis OS'),
            ('Masaüstü',         'GNOME'),
        ]:
            rc = hbox(0); rc.add_css_class('info-row')
            rc.append(lbl(title))
            vl = lbl(value, ['page-sub'], halign=Gtk.Align.END)
            vl.set_hexpand(True)
            rc.append(vl)
            outer.append(rc)

        # Tehlikeli bölge
        outer.append(lbl('TEHLİKELİ BÖLGE', ['sect-title']))
        clr = hbox(0); clr.add_css_class('toggle-row')
        clr_t = vbox(2); clr_t.set_hexpand(True)
        clr_t.append(lbl('Olay Günlüğünü Temizle'))
        clr_t.append(lbl('Tüm kayıtlı güvenlik olaylarını siler', ['page-sub']))
        clr.append(clr_t)
        cb2 = Gtk.Button(label='Temizle')
        cb2.add_css_class('destructive-action')
        cb2.add_css_class('pill-btn')
        cb2.set_valign(Gtk.Align.CENTER)
        cb2.connect('clicked', lambda b: self._clear_log())
        clr.append(cb2)
        outer.append(clr)

        return scroll(outer)

    def _toggle_row(self, key, title, subtitle, extra_cb=None):
        row = hbox(0); row.add_css_class('toggle-row')
        info = vbox(2); info.set_hexpand(True)
        info.append(lbl(title))
        info.append(lbl(subtitle, ['page-sub']))
        row.append(info)
        sw = Gtk.Switch()
        sw.set_valign(Gtk.Align.CENTER)
        sw.set_active(self.config.get(key))
        def on_toggle(s, p, k=key, cb=extra_cb):
            self.config.set(k, s.get_active())
            if cb: cb(s.get_active())
        sw.connect('notify::active', on_toggle)
        row.append(sw)
        return row

    def _on_rt_toggle(self, active):
        if active: self.rt_monitor.start()
        else:      self.rt_monitor.stop()

    def _clear_log(self):
        self.event_log.events.clear()
        try:
            from engine import LOG_FILE
            LOG_FILE.unlink(missing_ok=True)
        except Exception: pass
        self._refresh_dash_events()
        self._refresh_events_list()
        self._toast('Olay günlüğü temizlendi')

    # ── Yardımcılar ───────────────────────────────────────────────────────────

    def _on_rt_alert(self, ev):
        if hasattr(self, 'dashboard_events_box'): self._refresh_dash_events()
        if hasattr(self, 'events_list'):          self._refresh_events_list()
        return False

    def _start_stats_updater(self):
        if HAS_PSUTIL: psutil.cpu_percent(interval=None)
        def update():
            try:
                if HAS_PSUTIL:
                    self.stat_cpu._val.set_text(f'{psutil.cpu_percent(interval=None):.0f}%')
                    self.stat_ram._val.set_text(f'{psutil.virtual_memory().percent:.0f}%')
                self.stat_files._val.set_text(str(self.config.get('files_scanned_today')))
            except Exception: pass
            return True
        GLib.timeout_add(2000, update)

    def _toast(self, msg):
        t = Adw.Toast(title=msg); t.set_timeout(3)
        self._toast_overlay.add_toast(t)