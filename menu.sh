#!/bin/bash

SERVICE_NAME="traffic-inspector"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
STREAMLIT_BIN="$VENV_DIR/bin/streamlit"
APP_FILE="$PROJECT_DIR/apsah.py"

if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run this script with root privileges (sudo bash menu.sh)"
  exit 1
fi

install_app() {
  echo "[+] Updating packages..."
  apt update -y
  apt install -y python3-pip python3-venv tshark libpcap-dev ufw

  echo "[+] Setting up Python virtual environment..."
  if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
  fi

  echo "[+] Installing Python dependencies..."
  "$VENV_DIR/bin/pip" install --upgrade pip
  "$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt"

  echo "[+] Creating systemd service..."
  cat << EOF > "$SERVICE_FILE"
[Unit]
Description=Traffic Camouflage Inspector Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
ExecStart=$STREAMLIT_BIN run $APP_FILE --server.port=8501 --server.address=0.0.0.0 --server.headless=true
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable ${SERVICE_NAME}.service
  systemctl restart ${SERVICE_NAME}.service
  ufw allow 8501/tcp 2>/dev/null || true

  echo ""
  echo "=========================================================="
  echo "[✔] Installed successfully!"
  echo "[✔] Service is ENABLED on boot and RUNNING right now."
  echo "[✔] URL: http://$(hostname -I | awk '{print $1}'):8501"
  echo "=========================================================="
  read -p "Press Enter to return to menu..."
}

enable_boot() {
  systemctl enable ${SERVICE_NAME}.service
  echo "[✔] Auto-start on system boot is now ENABLED."
  read -p "Press Enter to return to menu..."
}

disable_boot() {
  systemctl disable ${SERVICE_NAME}.service
  echo "[✔] Auto-start on system boot is now DISABLED."
  read -p "Press Enter to return to menu..."
}

start_service() {
  systemctl start ${SERVICE_NAME}.service
  echo "[✔] Service started."
  read -p "Press Enter to return to menu..."
}

stop_service() {
  systemctl stop ${SERVICE_NAME}.service
  echo "[✔] Service stopped."
  read -p "Press Enter to return to menu..."
}

restart_service() {
  systemctl restart ${SERVICE_NAME}.service
  echo "[✔] Service restarted."
  read -p "Press Enter to return to menu..."
}

view_status() {
  systemctl status ${SERVICE_NAME}.service --no-pager
  echo ""
  read -p "Press Enter to return to menu..."
}

view_logs() {
  journalctl -u ${SERVICE_NAME}.service -n 50 --no-pager
  echo ""
  read -p "Press Enter to return to menu..."
}

while true; do
  clear
  BOOT_STATUS=$(systemctl is-enabled ${SERVICE_NAME}.service 2>/dev/null || echo "not installed")
  ACTIVE_STATUS=$(systemctl is-active ${SERVICE_NAME}.service 2>/dev/null || echo "inactive")

  echo "=================================================="
  echo "      Traffic Camouflage Inspector Manager        "
  echo "=================================================="
  echo " Service Status   : $ACTIVE_STATUS"
  echo " Autostart on Boot: $BOOT_STATUS"
  echo " Web Interface    : http://$(hostname -I | awk '{print $1}'):8501"
  echo "=================================================="
  echo "1) Full Install / Reinstall & Configure Service"
  echo "2) Start Dashboard"
  echo "3) Stop Dashboard"
  echo "4) Restart Dashboard"
  echo "5) Enable Auto-Run on Boot (Always Run on Restart)"
  echo "6) Disable Auto-Run on Boot"
  echo "7) Check Service Status"
  echo "8) View Live Logs"
  echo "9) Exit"
  echo "=================================================="
  read -p "Select an option [1-9]: " choice

  case $choice in
    1) install_app ;;
    2) start_service ;;
    3) stop_service ;;
    4) restart_service ;;
    5) enable_boot ;;
    6) disable_boot ;;
    7) view_status ;;
    8) view_logs ;;
    9) exit 0 ;;
    *) echo "Invalid option." ; sleep 1 ;;
  esac
done
