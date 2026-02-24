#!/bin/bash
# DarkSQ - ZeXis OS Security Suite
# Kurulum scripti

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ID="com.zexis.darksq"
APP_NAME="DarkSQ"
INSTALL_DIR="/usr/share/darksq"
BIN_DIR="/usr/local/bin"
DESKTOP_DIR="/usr/share/applications"
ICON_DIR="/usr/share/icons/hicolor"

echo "🛡  DarkSQ — ZeXis OS Security Suite"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check dependencies
echo "→ Bağımlılıklar kontrol ediliyor..."

check_dep() {
    if ! python3 -c "import $1" 2>/dev/null; then
        echo "  Yükleniyor: $1"
        pip3 install "$2" --break-system-packages 2>/dev/null || true
    else
        echo "  ✓ $1"
    fi
}

check_dep gi "PyGObject"
check_dep psutil "psutil"

# Check GTK4 and Adwaita
if ! python3 -c "import gi; gi.require_version('Gtk','4.0'); gi.require_version('Adw','1'); from gi.repository import Gtk, Adw" 2>/dev/null; then
    echo "  GTK4/libadwaita bulunamadı! Lütfen kurun:"
    echo "  sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1"
    exit 1
fi
echo "  ✓ GTK4 + libadwaita"

echo ""
echo "→ Uygulama dosyaları kopyalanıyor..."

# Create install dir
sudo mkdir -p "$INSTALL_DIR"
sudo cp "$SCRIPT_DIR"/*.py "$INSTALL_DIR/"
sudo chmod +x "$INSTALL_DIR/main.py"

# Create launcher
cat > /tmp/darksq-launcher <<'EOF'
#!/bin/bash
exec python3 /usr/share/darksq/main.py "$@"
EOF
sudo cp /tmp/darksq-launcher "$BIN_DIR/darksq"
sudo chmod +x "$BIN_DIR/darksq"

# Desktop entry
cat > /tmp/darksq.desktop <<EOF
[Desktop Entry]
Name=DarkSQ
GenericName=Security Suite
Comment=ZeXis OS Güvenlik Paketi
Exec=darksq
Icon=security-high
Terminal=false
Type=Application
Categories=GNOME;GTK;System;Security;
StartupWMClass=darksq
Keywords=security;antivirus;protection;firewall;
EOF

sudo cp /tmp/darksq.desktop "$DESKTOP_DIR/$APP_ID.desktop"
sudo update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ DarkSQ başarıyla kuruldu!"
echo ""
echo "   Terminalde: darksq"
echo "   GNOME menüsünden: DarkSQ arayın"
echo ""
