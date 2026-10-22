#!/bin/bash

SCRIPT_SOURCE="$(readlink -f "${BASH_SOURCE[0]}")"
APP_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)"
SVC="traffic-inspector"
VENV="$APP_DIR/venv"
CONFIG_FILE="$APP_DIR/config.json"
GLOBAL_CMD="/usr/local/bin/sahandpolice"

# ANSI Colors
G="\033[0;32m"
R="\033[0;31m"
C="\033[0;36m"
B="\033[1m"
Y="\033[1;33m"
N="\033[0m"

if [ "$EUID" -ne 0 ]; then
  echo -e "${R}Please run with root privileges: sudo sahandpolice${N}"
  exit 1
fi

if [ ! -L "$GLOBAL_CMD" ] || [ "$(readlink -f "$GLOBAL_CMD")" != "$SCRIPT_SOURCE" ]; then
  ln -sf "$SCRIPT_SOURCE" "$GLOBAL_CMD"
  chmod +x "$SCRIPT_SOURCE"
fi

manage_credentials() {
  echo -e "\n${C}── Web Dashboard Access Control ──${N}"
  echo -e "  1) Set or Change Username & Password"
  echo -e "  2) Remove Password (Open / Public Access)"
  echo -e "  0) Back"
  read -rp " Select [0-2]: " cred_choice

  case $cred_choice in
    1)
      read -rp "Enter username: " new_user
      read -rp "Enter password: " new_pass
      if [ -n "$new_user" ] && [ -n "$new_pass" ]; then
        echo "{\"username\": \"$new_user\", \"password\": \"$new_pass\"}" > "$CONFIG_FILE"
        chmod 600 "$CONFIG_FILE"
        echo -e "${G}[✔] Password protection enabled!${N}"
        systemctl restart ${SVC}.service 2>/dev/null || true
      else
        echo -e "${R}Username and password cannot be empty.${N}"
      fi
      ;;
    2)
      rm -f "$CONFIG_FILE"
      echo -e "${G}[✔] Password removed. Dashboard is now accessible without login.${N}"
      systemctl restart ${SVC}.service 2>/dev/null || true
      ;;
    *) ;;
  esac
  read -rp "Press Enter to return to menu..."
}

install_all() {
  echo -e "\n${C}[1/4] Updating system packages...${N}"
  apt update -y && apt install -y python3-pip python3-venv tshark libpcap-dev ufw

  echo -e "${C}[2/4] Setting up Python virtual environment...${N}"
  [ ! -d "$VENV" ] && python3 -m venv "$VENV"
  "$VENV/bin/pip" install --upgrade pip
  "$VENV/bin/pip" install -r "$APP_DIR/requirements.txt"

  echo -e "${C}[3/4] Registering persistent systemd service...${N}"
  cat << EOF > "/etc/systemd/system/${SVC}.service"
[Unit]
Description=Sahand Police Traffic Inspector
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

  echo -e "${C}[4/4] Starting service...${N}"
  systemctl daemon-reload
  systemctl enable ${SVC}.service
  systemctl restart ${SVC}.service
  ufw allow 8501/tcp 2>/dev/null || true

  echo -e "\n${G}[✔] Successfully installed!${N}"
  echo -e "${G}[✔] Accessible without login by default. Use Option 2 to add a password anytime.${N}"
  read -rp "Press Enter to return to menu..."
}

uninstall_all() {
  echo -e "\n${R}Are you sure you want to completely uninstall? (y/n)${N}"
  read -rp "Select: " confirm
  if [[ "$confirm" =~ ^[Yy]$ ]]; then
    echo -e "${C}[*] Stopping and disabling service...${N}"
    systemctl stop ${SVC}.service 2>/dev/null || true
    systemctl disable ${SVC}.service 2>/dev/null || true
    rm -f "/etc/systemd/system/${SVC}.service"
    systemctl daemon-reload

    echo -e "${C}[*] Removing shortcut and files...${N}"
    rm -f "$GLOBAL_CMD"
    rm -rf "$APP_DIR"
    rm -rf /usr/local/bin/venv 2>/dev/null || true

    echo -e "${G}[✔] Uninstalled successfully.${N}\n"
    exit 0
  else
    echo -e "${C}Canceled.${N}"
    sleep 1
  fi
}

while true; do
  clear
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

  if [ -f "$CONFIG_FILE" ]; then
    AUTH_STAT="${Y}🔒 Password Protected${N}"
  else
    AUTH_STAT="${G}🔓 Open (No Password)${N}"
  fi

  IP=$(hostname -I | awk '{print $1}')

  echo -e "${B}──────────────────────────────────────────────${N}"
  echo -e " ${C}${B}               SAHAND POLICE                  ${N}"
  echo -e " ${B}        Traffic Camouflage Inspector          ${N}"
  echo -e "${B}──────────────────────────────────────────────${N}"
  echo -e " Status      : $STAT"
  echo -e " Security    : $AUTH_STAT"
  echo -e " Auto-boot   : $BOOT"
  echo -e " Panel Link  : ${C}http://${IP}:8501${N}"
  echo -e " Command     : ${B}sahandpolice${N}"
  echo -e "${B}──────────────────────────────────────────────${N}"
  echo -e "  ${B}1${N}) Install / Reinstall & Enable Autostart"
  echo -e "  ${B}2${N}) Manage Login (Set / Remove Password)"
  echo -e "  ${B}3${N}) Restart Service"
  echo -e "  ${B}4${N}) Stop Service"
  echo -e "  ${B}5${N}) View Live Logs"
  echo -e "  ${B}6${N}) Completely Uninstall"
  echo -e "  ${B}0${N}) Exit"
  echo -e "${B}──────────────────────────────────────────────${N}"
  read -rp " Select [0-6]: " opt

  case $opt in
    1) install_all ;;
    2) manage_credentials ;;
    3) systemctl restart ${SVC}.service && sleep 1 ;;
    4) systemctl stop ${SVC}.service && sleep 1 ;;
    5) journalctl -u ${SVC}.service -n 25 --no-pager ; echo "" ; read -rp "Press Enter..." ;;
    6) uninstall_all ;;
    0) clear; exit 0 ;;
    *) echo -e "${R}Invalid option.${N}"; sleep 0.8 ;;
  esac
done
