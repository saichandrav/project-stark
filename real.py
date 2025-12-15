import cv2
import time
import socket
import sqlite3
import threading
from pathlib import Path
from ultralytics import YOLO
from twilio.rest import Client
import cloudinary
import cloudinary.uploader


# ----------------- log function ------------------
def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

# ----------------- TWILIO CONFIGURATION ------------------
ACCOUNT_SID = "twilio_sid"
AUTH_TOKEN = "twilio_auth_token"

WHATSAPP_FROM = "whatsapp:twilio_number"
WHATSAPP_TO1 = "whatsapp:countrycode + user_number1"
WHATSAPP_TO1 = "whatsapp:countrycode + user_number2"

# ----------------- CLOUDINARY CONFIGURATION--------------------
cloudinary.config(
    cloud_name="cname",
    api_key="capi_key",
    api_secret="cloud seret key"
)

# ----------------- MODEL CONFIGURATION ------------------
MODEL_NAME = "model.pt"
CONFIDENCE_THRESHOLD = 0.70
ALERT_COOLDOWN = 20
DETECT_EVERY_N_FRAMES = 5
INFER_SIZE = (640, 480)

OFFLINE_SYNC_INTERVAL = 600  #  10 minutes

THREAT_CLASSES = {"knife", "scissors", "pistol", "Gun", "rifle"}  # "cell phone"

# ----------------- OFFLINE STORAGE ----------------
OFFLINE_DIR = Path("offline_alerts")
IMAGES_DIR = OFFLINE_DIR / "images"
DB_FILE = OFFLINE_DIR / "alerts.db"

OFFLINE_DIR.mkdir(exist_ok=True)
IMAGES_DIR.mkdir(exist_ok=True)

# ----------------- DATABASE INIT -----------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            threat TEXT,
            image_path TEXT,
            timestamp INTEGER,
            synced INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ----------------- INTERNET CHECK ----------------
def internet_available():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=1.5)
        return True
    except:
        return False

# ----------------- STORE OFFLINE ALERT ------------
def store_offline_alert(threat, image_path):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO alerts (threat, image_path, timestamp) VALUES (?, ?, ?)",
        (threat, image_path, int(time.time()))
    )
    conn.commit()
    conn.close()
    log(f"Alert stored OFFLINE ({threat})")

# ----------------- SYNC LOCK ---------------------
sync_lock = threading.Lock()

# ----------------- SYNC OFFLINE ALERTS ------------
def sync_offline_alerts():
    if not sync_lock.acquire(blocking=False):
        return  # another sync running

    try:
        if not internet_available():
            return

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT id, threat, image_path FROM alerts WHERE synced=0")
        rows = c.fetchall()

        if not rows:
            conn.close()
            return

        log(f" Syncing {len(rows)} offline alerts")
        client = Client(ACCOUNT_SID, AUTH_TOKEN)

        for alert_id, threat, image_path in rows:
            try:
                upload = cloudinary.uploader.upload(image_path)
                image_url = upload["secure_url"]

                for target in (WHATSAPP_TO1, WHATSAPP_TO2):
                    client.messages.create(
                        from_=WHATSAPP_FROM,
                        to=target,
                        body=f"🚨 DELAYED ALERT: {threat.upper()} detected",
                        media_url=[image_url]
                    )

                c.execute("UPDATE alerts SET synced=1 WHERE id=?", (alert_id,))
                conn.commit()
                log(f"Offline alert synced ({threat})")

            except Exception as e:
                log(f"⚠ Offline sync failed: {e}")

        conn.close()

    finally:
        sync_lock.release()

# ----------------- SEND ALERT ---------------------
def send_whatsapp_with_photo(threat, frame):
    try:
        log(f"🚨 Alert triggered: {threat}")

        frame = cv2.resize(frame, INFER_SIZE)
        image_path = str(IMAGES_DIR / f"{threat}_{int(time.time())}.jpg")
        cv2.imwrite(image_path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])

        if not internet_available():
            log("⚠" \
            " No internet — switching to OFFLINE mode")
            store_offline_alert(threat, image_path)
            return

        upload = cloudinary.uploader.upload(image_path)
        image_url = upload["secure_url"]

        client = Client(ACCOUNT_SID, AUTH_TOKEN)

        for target in (WHATSAPP_TO1, WHATSAPP_TO2):
            client.messages.create(
                from_=WHATSAPP_FROM,
                to=target,
                body=f"🚨 ALERT: {threat.upper()} detected",
                media_url=[image_url]
            )
            log(f"WhatsApp sent → {target}")

    except Exception as e:
        log(f" WhatsApp send failed: {e}")
        store_offline_alert(threat, image_path)

# ----------------- DRAW BOX -----------------------
def draw_box(frame, x1, y1, x2, y2, label, color):
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 1)
    cv2.putText(frame, label, (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

# ================= MAIN LOOP =====================
def main():
    log("🟢 PROJECT STARK ACTIVE")

    model = YOLO(MODEL_NAME)
    cap = cv2.VideoCapture(0)

    last_alert_time = {}
    frame_count = 0
    last_results = None
    last_sync_time = time.time()  #  IMPORTANT

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                log("⚠ Camera read failed")
                break

            frame_count += 1

            #  TIME-BASED SYNC (10 MIN)
            now = time.time()
            if now - last_sync_time >= OFFLINE_SYNC_INTERVAL:
                log(" 10-minute offline sync triggered")
                threading.Thread(target=sync_offline_alerts, daemon=True).start()
                last_sync_time = now

            #  DETECTION
            if frame_count % DETECT_EVERY_N_FRAMES == 0:
                small_frame = cv2.resize(frame, INFER_SIZE)
                last_results = model(small_frame, verbose=False)

            if last_results:
                h_ratio = frame.shape[0] / INFER_SIZE[1]
                w_ratio = frame.shape[1] / INFER_SIZE[0]

                for r in last_results:
                    for box in r.boxes:
                        conf = float(box.conf[0])
                        if conf < CONFIDENCE_THRESHOLD:
                            continue

                        cls = int(box.cls[0])
                        name = model.names[cls]

                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        x1, x2 = int(x1 * w_ratio), int(x2 * w_ratio)
                        y1, y2 = int(y1 * h_ratio), int(y2 * h_ratio)

                        if name in THREAT_CLASSES:
                            if now - last_alert_time.get(name, 0) > ALERT_COOLDOWN:
                                threading.Thread(
                                    target=send_whatsapp_with_photo,
                                    args=(name, frame.copy()),
                                    daemon=True
                                ).start()
                                last_alert_time[name] = now

                            draw_box(frame, x1, y1, x2, y2,
                                     f"THREAT: {name} {conf:.2f}", (0, 0, 255))
                        else:
                            label = "SAFE PERSON" if name == "person" else f"SAFE: {name}"
                            draw_box(frame, x1, y1, x2, y2,
                                     f"{label} {conf:.2f}", (0, 255, 0))

            cv2.imshow("PROJECT STARK - LIVE", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                log("🛑 Q pressed — shutting down")
                break
    except KeyboardInterrupt:
        log("🛑 Keyboard Interrupt detected")

    finally:
        cap.release()
        cv2.destroyAllWindows()
        log(" PROJECT STARK SHUTDOWN")

if __name__ == "__main__":
    main()

    

