from flask import Flask, render_template_string, request, jsonify
import cv2
import numpy as np
import base64
import os
import sys
import time
from deepface import DeepFace

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

# (Keep your HTML_PAGE string definition exactly here as it was)

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
    
    # Save current frame to a temp file for DeepFace to read
    temp_frame_path = os.path.join(BASE_DIR, "temp_current_frame.jpg")
    cv2.imwrite(temp_frame_path, frame)
    
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
            # DeepFace verification using the lightning-fast, lightweight 'VGG-Face' model
            result = DeepFace.verify(
                img1_path=temp_frame_path, 
                img2_path=img_path, 
                model_name="VGG-Face", 
                enforce_detection=False
            )
            
            if result["verified"]:
                log_security_event("ACCESS_GRANTED_USER_REGISTERED")
                return jsonify({"status": "granted", "message": "ACCESS GRANTED: Welcome back!"})
            else:
                log_security_event("ACCESS_REJECTED_UNKNOWN_THREAT")
                return jsonify({"status": "denied", "message": "ACCESS DENIED: Facial signature verification failed."})
                
        except Exception as e:
            return jsonify({"status": "denied", "message": f"VERIFICATION ERROR: {str(e)}"})
        finally:
            if os.path.exists(temp_frame_path):
                os.remove(temp_frame_path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
