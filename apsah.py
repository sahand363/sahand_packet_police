import streamlit as st
import threading
import queue
import time
from scapy.all import sniff, TCP, Raw

# تنظیمات صفحه
st.set_page_config(page_title="Traffic Camouflage Inspector", layout="wide")

# --- سیستم احراز هویت (امنیت صفحه) ---
def check_password():
    """Returns True if the user entered the correct password."""
    def password_entered():
        if (
            st.session_state["username"] == "admin"
            and st.session_state["password"] == "Sahand@2026" # رمز عبور خود را اینجا تغییر دهید
        ):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show inputs for login
        st.subheader("🔒 Login Required")
        st.text_input("Username", value="", key="username")
        st.text_input("Password", type="password", value="", key="password")
        st.button("Login", on_click=password_entered)
        return False
    elif not st.session_state["password_correct"]:
        st.subheader("🔒 Login Required")
        st.text_input("Username", value="", key="username")
        st.text_input("Password", type="password", value="", key="password")
        st.button("Login", on_click=password_entered)
        st.error("😕 User name or password incorrect")
        return False
    else:
        return True

if not check_password():
    st.stop()  # توقف اجرای ادامه برنامه اگر کاربر لاگین نکرده باشد

# --- پنل اصلی بعد از ورود موفق ---
st.title("🛡️ Live Traffic & WebSocket Camouflage Inspector")

if 'packet_queue' not in st.session_state:
    st.session_state.packet_queue = queue.Queue()

if 'is_sniffing' not in st.session_state:
    st.session_state.is_sniffing = False

# سایدبار تنظیمات پورت
port = st.sidebar.selectbox("Select Port to Monitor", [10001, 10004], index=1, key="selected_port")
st.sidebar.markdown(f"**Current Status:** Listening on port `{port}`")

# دکمه خروج امن
if st.sidebar.button("Logout"):
    st.session_state["password_correct"] = False
    st.rerun()

col1, col2, col3 = st.columns([1, 1.5, 1.5])
col1.metric("Monitored Port", port, "Active")
col2.metric("Camouflage Type", "WebSocket (0x82)" if port == 10004 else "Raw TCP")
col3.metric("Packet Status", "Secure / Hidden" if port == 10004 else "Exposed (DPI)")

st.markdown("---")
st.subheader("📡 Real-time Packet Log Stream")

def packet_callback(packet):
    if packet.haslayer(TCP) and packet.haslayer(Raw):
        payload = packet[Raw].load
        src_port = packet[TCP].sport
        dst_port = packet[TCP].dport
        
        if dst_port == port or src_port == port:
            log_entry = ""
            if b"HTTP/1.1" in payload or b"Upgrade: websocket" in payload:
                log_entry = f"[+] WebSocket Handshake Detected on Port {dst_port}"
            elif payload.startswith(b'\x82') or payload.startswith(b'\x81'):
                log_entry = f"[+] WebSocket Binary Frame (0x82) on Port {dst_port}"
            else:
                log_entry = f"[!] Raw/Unencrypted Data on Port {dst_port}: {payload[:30]}"
            
            st.session_state.packet_queue.put(log_entry)

def run_sniffing(monitored_port):
    try:
        sniff(filter=f"tcp port {monitored_port}", prn=packet_callback, store=0, stop_filter=lambda x: not st.session_state.is_sniffing)
    except Exception as e:
        st.session_state.packet_queue.put(f"[Error] Sniffing failed: {e}")

col_btn1, col_btn2 = st.columns(2)
start_btn = col_btn1.button("Start Live Capture")
stop_btn = col_btn2.button("Stop Capture")

if start_btn and not st.session_state.is_sniffing:
    st.session_state.is_sniffing = True
    threading.Thread(target=run_sniffing, args=(port,), daemon=True).start()
    st.success(f"Packet capture started on port {port}...")

if stop_btn:
    st.session_state.is_sniffing = False
    st.warning("Packet capture stopped.")

log_box = st.empty()
logs = []
while not st.session_state.packet_queue.empty():
    logs.append(st.session_state.packet_queue.get())

if logs:
    log_box.code("\n".join(logs[-10:]), language="text")
else:
    log_box.info("Waiting for traffic... Send traffic to the target port to see live packets.")
