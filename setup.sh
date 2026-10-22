#### 2. Fixed `setup.sh`
# This version creates a dedicated Python virtual environment (`venv`) to prevent `pip` installation errors and configures systemd to run Streamlit from that environment:

```bash
#!/bin/bash
set -e

# Verify root privileges
if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run this script with sudo or as root."
  exit 1
fi

PROJECT_DIR="$(pwd)"
APP_FILE="$PROJECT_DIR/apsah.py"
VENV_DIR="$PROJECT_DIR/venv"
SERVICE_FILE="/etc/systemd/system/traffic-inspector.service"

echo "[+] Updating system packages..."
apt update && apt upgrade -y

echo "[+] Installing system dependencies..."
apt install -y python3-pip python3-venv tshark libpcap-dev

echo "[+] Setting up Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

echo "[+] Installing Python dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r requirements.txt

STREAMLIT_BIN="$VENV_DIR/bin/streamlit"

echo "[+] Configuring Systemd service..."
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

echo "[+] Enabling and starting service..."
systemctl daemon-reload
systemctl enable traffic-inspector.service
systemctl restart traffic-inspector.service

echo "--------------------------------------------------------"
echo "[✔] Setup completed successfully!"
echo "[✔] Access your panel at: http://<your-server-ip>:8501"
echo "[✔] Default Login -> Username: admin | Password: Sahand@2026"
echo "--------------------------------------------------------"
