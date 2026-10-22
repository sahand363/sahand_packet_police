#!/bin/bash

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SVC="traffic-inspector"
VENV="$APP_DIR/venv"

# ANSI Colors
G="\033[0;32m"
R="\033[0;31m"
C="\033[0;36m"
B="\033[1m"
N="\033[0m"

if [ "$EUID" -ne 0 ]; then
  echo -e "${R}Please run with root privileges: sudo bash menu.sh${N}"
  exit 1
fi

install_all() {
  echo -e "\n${C}[1/4] Updating packages...${N}"
  apt update -y && apt install -y python3-pip python3-venv tshark libpcap-dev ufw

  echo -e "${C}[2/4] Configuring Python venv...${N}"
  [ ! -d "$VENV" ] && python3 -m venv "$VENV"
  "$VENV/bin/pip" install --upgrade pip
  "$VENV/bin/pip" install -r "$APP_DIR/requirements.txt"

  echo -e "${C}[3/4] Registering persistent systemd service...${N}"
  cat << EOF > "/etc/systemd/system/${SVC}.service"
[Unit]
Description=Traffic Camouflage Inspector
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
ExecStart=$VENV/bin/streamlit run $APP_DIR/apsah.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable ${SVC}.service
  systemctl restart ${SVC}.service
  ufw allow 8501/tcp 2>/dev/null || true

  echo -e "${G}[✔] Setup finished. Running and enabled on system boot.${N}"
  read -rp "Press Enter to continue..."
}

while true; do
  clear
  # Status checks
  if systemctl is-active --quiet ${SVC}.service; then
    STAT="${G}● Running${N}"
  else
    STAT="${R}○ Inactive${N}"
  fi

  if systemctl is-enabled --quiet ${SVC}.service 2>/dev/null; then
    BOOT="${G}Enabled${N}"
  else
    BOOT="${R}Disabled${N}"
  fi

  IP=$(hostname -I | awk '{print $1}')

  echo -e "${B}──────────────────────────────────────────────${N}"
  echo -e " ${B}Traffic Camouflage Inspector${N}"
  echo -e "${B}──────────────────────────────────────────────${N}"
  echo -e " Status     : $STAT"
  echo -e " Auto-boot  : $BOOT"
  echo -e " Panel Link : ${C}http://${IP}:8501${N}"
  echo -e "${B}──────────────────────────────────────────────${N}"
  echo -e "  ${B}1${N}) Install / Reinstall & Enable Autostart"
  echo -e "  ${B}2${N}) Restart Service"
  echo -e "  ${B}3${N}) Stop Service"
  echo -e "  ${B}4${N}) View Live Logs"
  echo -e "  ${B}0${N}) Exit"
  echo -e "${B}──────────────────────────────────────────────${N}"
  read -rp " Select: " opt

  case $opt in
    1) install_all ;;
    2) systemctl restart ${SVC}.service && sleep 1 ;;
    3) systemctl stop ${SVC}.service && sleep 1 ;;
    4) journalctl -u ${SVC}.service -n 25 --no-pager ; echo "" ; read -rp "Press Enter..." ;;
    0) clear; exit 0 ;;
    *) echo -e "${R}Invalid option.${N}"; sleep 0.8 ;;
  esac
done
