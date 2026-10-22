#!/bin/bash

# بررسی دسترسی روت
if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run this script with sudo or as root."
  exit 1
fi

echo "[+] Updating system packages..."
apt update && apt upgrade -y

echo "[+] Installing Python, Pip, and Tshark..."
apt install -y python3-pip python3-venv tshark libpcap-dev

echo "[+] Installing Python dependencies..."
pip3 install -r requirements.txt

# گرفتن مسیر دقیق نصب streamlit
STREAMLIT_PATH=$(which streamlit)
if [ -z "$STREAMLIT_PATH" ]; then
  STREAMLIT_PATH="/usr/local/bin/streamlit"
fi

# پیدا کردن مسیر فعلی اسکریپت
PROJECT_DIR="$(pwd)"
APP_FILE="$PROJECT_DIR/apsah.py"

echo "[+] Configuring Systemd service for continuous running..."
SERVICE_FILE="/etc/systemd/system/traffic-inspector.service"

cat << EOF > "$SERVICE_FILE"
[Unit]
Description=Traffic Camouflage Inspector Service
After=network.service

[Service]
User=root
WorkingDirectory=$PROJECT_DIR
ExecStart=$STREAMLIT_PATH run $APP_FILE --server.port=8501 --server.address=0.0.0.0
Restart=always

[Install]
WantedBy=multi-user.target
EOF

echo "[+] Enabling and starting the service..."
systemctl daemon-reload
systemctl enable traffic-inspector.service
systemctl restart traffic-inspector.service

echo "--------------------------------------------------------"
echo "[✔] Setup completed successfully!"
echo "[✔] You can access the panel via: http://<your-server-ip>:8501"
echo "[✔] Default Login -> Username: admin | Password: Sahand@2026"
echo "--------------------------------------------------------"
