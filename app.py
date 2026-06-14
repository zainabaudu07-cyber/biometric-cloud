from flask import Flask, render_template_string, request, jsonify
import cv2
import numpy as np
import base64
import os
import sys
import time
import face_recognition

app = Flask(__name__)

def get_base_path():
    if hasattr(sys, '_MEIPASS'):
        return os.path.dirname(sys.executable)
    return os.path.abspath(".")

BASE_DIR = get_base_path()
DATABASE_DIR = os.path.join(BASE_DIR, "database")
LOG_FILE_PATH = os.path.join(BASE_DIR, "security_log.txt")

if not os.path.exists(DATABASE_DIR):
    os.makedirs(DATABASE_DIR)

def log_security_event(name_status):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_FILE_PATH, "a") as log_file:
            log_file.write(f"[{timestamp}] CLOUD_AUTH: {name_status}\n")
    except Exception as e:
        print(f"[LOG ERROR] File-system write failure: {e}")

# Frontend Biometric Panel HTML Layout
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Biometric Cloud Dashboard</title>
    <style>
        body { background-color: #121212; color: white; font-family: 'Segoe UI', Tahoma, sans-serif; text-align: center; padding-top: 30px; }
        .container { display: inline-block; background: #1e1e1e; padding: 25px; border-radius: 12px; box-shadow: 0px 6px 15px rgba(0,0,0,0.6); border: 1px solid #333; }
        video, canvas { border: 3px solid #00ff00; border-radius: 6px; width: 640px; height: 480px; background-color: #000; transform: scaleX(-1); }
        h1 { color: #00ff00; margin-bottom: 5px; font-weight: 600; letter-spacing: 1px; }
        p { color: #aaaaaa; font-size: 14px; margin-top: 0; }
        .btn { background-color: #00ff00; color: black; font-weight: bold; border: none; padding: 14px 28px; font-size: 15px; border-radius: 6px; cursor: pointer; margin-top: 15px; margin-right: 10px; transition: 0.2s; box-shadow: 0px 4px 6px rgba(0,255,0,0.2); }
        .btn:hover { background-color: #00cc00; transform: scale(1.02); }
        .btn-reg { background-color: #ffffff; color: black; box-shadow: 0px 4px 6px rgba(255,255,255,0.1); }
        .btn-reg:hover { background-color: #dddddd; }
        #statusLog { margin-top: 20px; font-size: 20px; color: #00ff00; font-weight: bold; min-height: 30px; letter-spacing: 0.5px; }
        .footer-note { margin-top: 25px; font-size: 11px; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <h1>=== BIOMETRIC CLOUD INTERFACE ===</h1>
        <p>Browser-to-Server Realtime Verification Hub | Secure Connection Required</p>
        
        <video id="webcam" autoplay playsinline muted></video>
        <canvas id="photoCanvas" style="display:none;"></canvas>
        
        <div id="statusLog">System Status: Armed & Ready</div>
        
        <button class="btn" onclick="processBiometrics('verify')">📸 Verify My Face Identity</button>
        <button class="btn btn-reg" onclick="processBiometrics('register')">👤 Register Fresh Profile</button>
        
        <p class="footer-note">Cybersecurity Lab Practical Environment. All entry checks report dynamically to remote cloud trails.</p>
    </div>

    <script>
        const video = document.getElementById('webcam');
        const canvas = document.getElementById('photoCanvas');
        const context = canvas.getContext('2d');
        const statusLog = document.getElementById('statusLog');

        navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } })
            .then(stream => { video.srcObject = stream; })
            .catch(err => { 
                statusLog.style.color = "#ff0000";
                statusLog.innerText = "Camera Error: SSL Certificate (HTTPS://) encryption required by browser settings."; 
            });

        function processBiometrics(actionType) {
            statusLog.style.color = "#00ff00";
            statusLog.innerText = actionType === 'register' ? "Syncing data matrix to cloud registry..." : "Analyzing structural facial vectors...";
            
            canvas.width = 640;
            canvas.height = 480;
            context.drawImage(video, 0, 0, 640, 480);
            const dataUrl = canvas.toDataURL('image/jpeg');

            fetch('/process_image', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image: dataUrl, action: actionType })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'granted' || data.status === 'success') {
                    statusLog.style.color = "#00ff00";
                } else {
                    statusLog.style.color = "#ff0000";
                }
                statusLog.innerText = data.message;
            })
            .catch(() => {
                statusLog.style.color = "#ff0000";
                statusLog.innerText = "Server communication failure.";
            });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/process_image', methods=['POST'])
def process_image():
    data = request.get_json()
    image_data = data.get('image').split(',')[1]
    action = data.get('action')
    
    img_bytes = base64.b64decode(image_data)
    np_array = np.frombuffer(img_bytes, dtype=np.uint8)
    frame = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
    
    # Convert BGR (OpenCV format) to RGB (Face Recognition format)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    if action == 'register':
        try:
            for f in os.listdir(DATABASE_DIR):
                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                    os.remove(os.path.join(DATABASE_DIR, f))
        except Exception:
            pass
            
        img_path = os.path.join(DATABASE_DIR, "User_Registered.jpg")
        cv2.imwrite(img_path, frame)
        
        log_security_event("NEW_USER_REGISTRATION_SUCCESS")
        return jsonify({"status": "success", "message": "Biometric registration successfully locked into cloud registry!"})
        
    elif action == 'verify':
        img_path = os.path.join(DATABASE_DIR, "User_Registered.jpg")
        if not os.path.exists(img_path):
            log_security_event("ACCESS_REJECTED_EMPTY_DATABASE")
            return jsonify({"status": "denied", "message": "ACCESS DENIED: Database empty. Register profile first."})
            
        try:
            # Load registered reference image and extract landmarks
            registered_image = face_recognition.load_image_file(img_path)
            registered_encodings = face_recognition.face_encodings(registered_image)
            
            if len(registered_encodings) == 0:
                return jsonify({"status": "denied", "message": "VERIFICATION ERROR: Stored reference photo lacks clear facial points."})
                
            # Extract landmarks from current camera frame
            current_encodings = face_recognition.face_encodings(rgb_frame)
            if len(current_encodings) == 0:
                return jsonify({"status": "denied", "message": "ACCESS DENIED: No clear face detected in view window."})
                
            # Perform lightning-fast structural vector matching
            matches = face_recognition.compare_faces([registered_encodings[0]], current_encodings[0], tolerance=0.6)
            
            if matches[0]:
                log_security_event("ACCESS_GRANTED_USER_REGISTERED")
                return jsonify({"status": "granted", "message": "ACCESS GRANTED: Welcome back!"})
            else:
                log_security_event("ACCESS_REJECTED_UNKNOWN_THREAT")
                return jsonify({"status": "denied", "message": "ACCESS DENIED: Facial signature verification failed."})
                
        except Exception as e:
            return jsonify({"status": "denied", "message": f"VERIFICATION ERROR: {str(e)}"})

port = int(os.environ.get("PORT", 10000))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, debug=False)
