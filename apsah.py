import os
import json
import math
import time
import queue
import threading
from collections import Counter
import streamlit as st
from scapy.all import sniff, TCP, Raw

st.set_page_config(page_title="Sahand Police — Traffic Inspector", layout="wide")

# Mobile-friendly styling and card padding
st.markdown(
    """
    <style>
        @media (max-width: 768px) {
            h1 { font-size: 1.35rem !important; line-height: 1.3 !important; }
            h2, h3 { font-size: 1.05rem !important; }
            div[data-testid="stMetricValue"] {
                font-size: 1.05rem !important;
                white-space: normal !important;
                word-break: break-word !important;
            }
            div[data-testid="stMetricLabel"] { font-size: 0.75rem !important; }
            .block-container { padding: 1.5rem 0.6rem 2rem 0.6rem !important; }
            .stButton button { width: 100% !important; font-size: 0.85rem !important; }
        }
    </style>
    """,
    unsafe_allow_html=True,
)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def get_auth_credentials():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                data = json.load(f)
                user = data.get("username", "").strip()
                pwd = data.get("password", "").strip()
                if user and pwd:
                    return user, pwd
        except Exception:
            pass
    return None, None


def calculate_shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    entropy = 0.0
    length = len(data)
    counts = Counter(data)
    for count in counts.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


def compute_real_stealth_score(packet_bytes: bytes, is_handshake_done: bool):
    score = 0
    leak_detected = False

    # Check 1: Zero-Leak Test (Max 20 pts)
    if b"DEST:" in packet_bytes or b"q-qoq" in packet_bytes:
        leak_detected = True
    else:
        score += 20

    # Check 2: Valid Handshake or Frame Header (Max 40 pts)
    is_masked_ws = False
    if is_handshake_done:
        if len(packet_bytes) > 2 and packet_bytes[0] == 0x82 and (packet_bytes[1] & 0x80):
            score += 40
            is_masked_ws = True
    else:
        if b"Upgrade: websocket" in packet_bytes or b"HTTP/1.1 101" in packet_bytes:
            score += 40

    # Check 3: Shannon Entropy (Max 40 pts)
    payload_to_measure = packet_bytes[6:] if is_masked_ws else packet_bytes
    entropy = calculate_shannon_entropy(payload_to_measure)
    entropy_score = min(40, int((entropy / 8.0) * 40))
    score += entropy_score

    label = f"DPI Stealth: {score}% (Entropy: {entropy:.2f}/8.00)"
    return score, label, entropy, leak_detected, is_masked_ws


# --- State Initialization ---
if "packet_queue" not in st.session_state:
    st.session_state.packet_queue = queue.Queue()

if "stop_event" not in st.session_state:
    st.session_state.stop_event = threading.Event()

if "is_sniffing" not in st.session_state:
    st.session_state.is_sniffing = False

if "log_history" not in st.session_state:
    st.session_state.log_history = []

if "latest_stats" not in st.session_state:
    st.session_state.latest_stats = {
        "score": 0,
        "entropy": 0.0,
        "leaks": 0,
        "frame_type": "None",
        "last_label": "No packets analyzed yet",
    }

# --- Optional Login ---
valid_user, valid_pass = get_auth_credentials()
if valid_user and valid_pass:
    def password_entered():
        if (
            st.session_state.get("username") == valid_user
            and st.session_state.get("password") == valid_pass
        ):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state or not st.session_state["password_correct"]:
        st.subheader("🔒 Login Required")
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.button("Login", on_click=password_entered)
        if st.session_state.get("password_correct") is False:
            st.error("😕 Username or password incorrect")
        st.stop()

# --- Top Header & Documentation ---
st.title("🛡️ Sahand Police — Live Traffic Inspector")

st.sidebar.markdown("### ⚙️ Port Configuration")
port = st.sidebar.number_input(
    "Target Port",
    min_value=1,
    max_value=65535,
    value=10004,
    step=1,
    key="selected_port",
    help="The network port being monitored on this server."
)
st.sidebar.caption(f"Listening on port: **{port}**")

if valid_user and valid_pass:
    if st.sidebar.button("Logout"):
        st.session_state["password_correct"] = False
        st.session_state.stop_event.set()
        st.session_state.is_sniffing = False
        st.rerun()

# --- Metrics with Built-in Tooltips ---
m_col1, m_col2, m_col3 = st.columns(3)

m_col1.metric(
    label="Monitored Port",
    value=port,
    delta="Sniffer Active" if st.session_state.is_sniffing else "Idle",
    help="The server TCP port currently intercepted by Scapy."
)

m_col2.metric(
    label="DPI Stealth Score",
    value=f"{st.session_state.latest_stats['score']}%",
    delta=st.session_state.latest_stats['frame_type'],
    help="Scores resistance against DPI firewalls (0-100%). High scores (>80%) require valid WebSocket framing (0x82) and high payload entropy."
)

m_col3.metric(
    label="Shannon Entropy",
    value=f"{st.session_state.latest_stats['entropy']:.2f} / 8.00",
    delta="0 Leaks Detected" if st.session_state.latest_stats['leaks'] == 0 else f"{st.session_state.latest_stats['leaks']} CLEAR-TEXT LEAKS!",
    help="Measures data randomness. Plain ASCII text / JSON scores 3.0-5.5. Encrypted / masked WebSocket payloads score 7.80-8.00."
)

# --- In-App Reference Guide ---
with st.expander("ℹ️ How to Read These Metrics & Logs"):
    st.markdown(
        """
        * **DPI Stealth Score:**
          * **0% - 40% (Exposed):** Traffic contains raw JSON, ASCII logs, or lacks binary WebSocket headers. Easy for network firewalls to inspect.
          * **70% - 100% (Camouflaged):** Traffic properly negotiated a WebSocket handshake and uses binary frames (`0x82`) with random 4-byte masking keys.
        * **Shannon Entropy (0.00 to 8.00):**
          * **3.00 - 5.50:** Unencrypted text or predictable structured data (JSON, HTTP headers).
          * **7.80 - 8.00:** Pseudorandom cryptographic stream (indistinguishable from genuine TLS/HTTPS).
        * **Log Indicators:**
          * `[✔ WS 0x82]`: Clean WebSocket binary frame detected with mask bytes.
          * `[+] Handshake`: WebSocket connection negotiation occurred.
          * `[!] Raw Data`: Unmasked data packet detected on the port.
          * `[🚨 LEAK DETECTED]`: Clear-text routing strings (`DEST:` or `q-qoq`) leaked into the payload.
        """
    )

st.markdown("---")
st.subheader("📡 Real-time Packet Log Stream")


def packet_callback(packet, target_port, q, connection_state):
    if packet.haslayer(TCP) and packet.haslayer(Raw):
        payload = bytes(packet[Raw].load)
        src_port = packet[TCP].sport
        dst_port = packet[TCP].dport

        if dst_port == target_port or src_port == target_port:
            if b"Upgrade: websocket" in payload or b"HTTP/1.1 101" in payload:
                connection_state["handshake_done"] = True

            score, label, entropy, leak_detected, is_masked_ws = compute_real_stealth_score(
                payload, connection_state.get("handshake_done", False)
            )

            frame_type = "Raw TCP"
            if is_masked_ws:
                mask_hex = payload[2:6].hex() if len(payload) >= 6 else "N/A"
                frame_type = f"0x82 (Mask: {mask_hex})"
                log_entry = f"[✔ WS 0x82] Masked Frame | Entropy: {entropy:.2f} | Stealth: {score}%"
            elif b"HTTP/1.1" in payload or b"Upgrade: websocket" in payload:
                frame_type = "WS Handshake"
                log_entry = f"[+] Handshake Negotiated on Port {dst_port}"
            else:
                log_entry = f"[!] Raw Data: {payload[:25]!r} | Entropy: {entropy:.2f}"

            if leak_detected:
                log_entry = f"[🚨 LEAK DETECTED] Routing string exposed in packet! -> {log_entry}"

            q.put(
                {
                    "log": log_entry,
                    "score": score,
                    "entropy": entropy,
                    "leak": leak_detected,
                    "frame_type": frame_type,
                    "label": label,
                }
            )


def run_sniffing(monitored_port, q, stop_evt):
    connection_state = {"handshake_done": False}
    try:
        sniff(
            filter=f"tcp port {monitored_port}",
            prn=lambda pkt: packet_callback(pkt, monitored_port, q, connection_state),
            store=0,
            stop_filter=lambda _: stop_evt.is_set(),
        )
    except Exception as e:
        q.put({"log": f"[Error] Sniffing failed: {e}", "score": 0, "entropy": 0.0, "leak": False, "frame_type": "Error", "label": "Error"})


col_btn1, col_btn2 = st.columns(2)
start_btn = col_btn1.button("Start Live Capture", disabled=st.session_state.is_sniffing)
stop_btn = col_btn2.button("Stop Capture", disabled=not st.session_state.is_sniffing)

if start_btn:
    st.session_state.is_sniffing = True
    st.session_state.stop_event.clear()
    threading.Thread(
        target=run_sniffing,
        args=(int(port), st.session_state.packet_queue, st.session_state.stop_event),
        daemon=True,
    ).start()
    st.rerun()

if stop_btn:
    st.session_state.stop_event.set()
    st.session_state.is_sniffing = False
    st.rerun()

log_box = st.empty()

if st.session_state.is_sniffing:
    st.caption("🟢 Live packet capture running. Polling stream...")
    while st.session_state.is_sniffing:
        new_data = False
        while not st.session_state.packet_queue.empty():
            item = st.session_state.packet_queue.get()
            st.session_state.log_history.append(item["log"])
            st.session_state.latest_stats["score"] = item["score"]
            st.session_state.latest_stats["entropy"] = item["entropy"]
            st.session_state.latest_stats["frame_type"] = item["frame_type"]
            st.session_state.latest_stats["last_label"] = item["label"]
            if item["leak"]:
                st.session_state.latest_stats["leaks"] += 1
            new_data = True

        if st.session_state.log_history:
            log_box.code("\n".join(st.session_state.log_history[-15:]), language="text")
        else:
            log_box.info("Waiting for traffic... Send packets to the target port.")

        if new_data:
            time.sleep(0.5)
            st.rerun()

        time.sleep(1)
else:
    if st.session_state.log_history:
        log_box.code("\n".join(st.session_state.log_history[-15:]), language="text")
    else:
        log_box.info("Capture stopped. Click 'Start Live Capture' to begin.")
