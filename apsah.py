import streamlit as st
import threading
import queue
import time
from scapy.all import sniff, TCP, Raw

st.set_page_config(page_title="Traffic Camouflage Inspector", layout="wide")

if "packet_queue" not in st.session_state:
    st.session_state.packet_queue = queue.Queue()

if "stop_event" not in st.session_state:
    st.session_state.stop_event = threading.Event()

if "is_sniffing" not in st.session_state:
    st.session_state.is_sniffing = False

if "log_history" not in st.session_state:
    st.session_state.log_history = []

def check_password():
    def password_entered():
        if (
            st.session_state.get("username") == "admin"
            and st.session_state.get("password") == "Sahand@2026"
        ):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.subheader("🔒 Login Required")
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.button("Login", on_click=password_entered)
        return False
    elif not st.session_state["password_correct"]:
        st.subheader("🔒 Login Required")
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.button("Login", on_click=password_entered)
        st.error("😕 Username or password incorrect")
        return False
    return True

if not check_password():
    st.stop()

st.title("🛡️ Live Traffic & WebSocket Camouflage Inspector")

port = st.sidebar.selectbox("Select Port to Monitor", [10001, 10004], index=1, key="selected_port")
st.sidebar.markdown(f"**Current Status:** Listening on port `{port}`")

if st.sidebar.button("Logout"):
    st.session_state["password_correct"] = False
    st.session_state.stop_event.set()
    st.session_state.is_sniffing = False
    st.rerun()

col1, col2, col3 = st.columns([1, 1.5, 1.5])
col1.metric("Monitored Port", port, "Active")
col2.metric("Camouflage Type", "WebSocket (0x82)" if port == 10004 else "Raw TCP")
col3.metric("Packet Status", "Secure / Hidden" if port == 10004 else "Exposed (DPI)")

st.markdown("---")
st.subheader("📡 Real-time Packet Log Stream")

def packet_callback(packet, target_port, q):
    if packet.haslayer(TCP) and packet.haslayer(Raw):
        payload = bytes(packet[Raw].load)
        src_port = packet[TCP].sport
        dst_port = packet[TCP].dport

        if dst_port == target_port or src_port == target_port:
            if b"HTTP/1.1" in payload or b"Upgrade: websocket" in payload:
                log_entry = f"[+] WebSocket Handshake Detected on Port {dst_port}"
            elif payload.startswith(b"\x82") or payload.startswith(b"\x81"):
                log_entry = f"[+] WebSocket Binary Frame (0x82) on Port {dst_port}"
            else:
                log_entry = f"[!] Raw/Unencrypted Data on Port {dst_port}: {payload[:30]!r}"

            q.put(log_entry)

def run_sniffing(monitored_port, q, stop_evt):
    try:
        sniff(
            filter=f"tcp port {monitored_port}",
            prn=lambda pkt: packet_callback(pkt, monitored_port, q),
            store=0,
            stop_filter=lambda _: stop_evt.is_set(),
        )
    except Exception as e:
        q.put(f"[Error] Sniffing failed: {e}")

col_btn1, col_btn2 = st.columns(2)
start_btn = col_btn1.button("Start Live Capture", disabled=st.session_state.is_sniffing)
stop_btn = col_btn2.button("Stop Capture", disabled=not st.session_state.is_sniffing)

if start_btn:
    st.session_state.is_sniffing = True
    st.session_state.stop_event.clear()
    threading.Thread(
        target=run_sniffing,
        args=(port, st.session_state.packet_queue, st.session_state.stop_event),
        daemon=True,
    ).start()
    st.rerun()

if stop_btn:
    st.session_state.stop_event.set()
    st.session_state.is_sniffing = False
    st.rerun()

log_box = st.empty()

if st.session_state.is_sniffing:
    st.caption("🟢 Sniffing active. Polling live packets...")
    while st.session_state.is_sniffing:
        while not st.session_state.packet_queue.empty():
            st.session_state.log_history.append(st.session_state.packet_queue.get())

        if st.session_state.log_history:
            log_box.code("\n".join(st.session_state.log_history[-15:]), language="text")
        else:
            log_box.info("Waiting for traffic... Send packets to the target port.")

        time.sleep(1)
else:
    if st.session_state.log_history:
        log_box.code("\n".join(st.session_state.log_history[-15:]), language="text")
    else:
        log_box.info("Capture stopped. Click 'Start Live Capture' to begin.")
