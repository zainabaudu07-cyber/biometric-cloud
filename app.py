from flask import Flask, render_template_string, request, jsonify
import cv2
import numpy as np
import base64
import os
import sys
import time
from insightface.app import FaceAnalysis

app = Flask(__name__)

# Initialize InsightFace (using the lightweight 'buffalo_l' default face analysis group)
# 'ctx_id=-1' forces it to use the CPU, preventing crashes on free cloud servers without GPUs
face_app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
face_app.prepare(ctx_id=-1, det_size=(640, 640))

def get_base_path():
    if hasattr(sys, '_MEIPASS'):
        return os.path.dirname(sys.executable)
    return os.path.abspath(".")

BASE_DIR = get_base_path()
DATABASE_DIR = os.path.join(BASE_DIR, "database")
LOG_FILE_PATH = os.path.join(BASE_DIR, "security_log.txt")

if not os.path.exists(DATABASE_DIR):
    os.makedirs(DATABASE_DIR)

# In-memory caches for the extracted embedding vectors
known_face_embeddings = []
known_face_names = []

def log_security_event(name_status):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_FILE_PATH, "a") as log_file:
            log_file.write(f"[{timestamp}] CLOUD_AUTH: {name_status}\n")
    except Exception as e:
        print(f"[LOG ERROR] File-system write failure: {e}")

def load_database():
    """Scans the database folder and extracts embedding maps using InsightFace."""
    global known_face_embeddings, known_face_names
    known_face_embeddings = []
    known_face_names = []

    if not os.path.exists(DATABASE_DIR):
        return

    for file_name in os.listdir(DATABASE_DIR):
        if file_name.lower().endswith(('.jpg', '.jpeg', '.png')):
            name_key = os.path.splitext(file_name)[0].split('_')[0].capitalize()
            photo_path = os.path.join(DATABASE_DIR, file_name)
            
            try:
                img = cv2.imread(photo_path)
                if img is None:
                    continue
                
                # Extract face features
                faces = face_app.get(img)
                if len(faces) > 0:
                    # Save the 512-dimension floating-point vector mapping the face
                    known_face_embeddings.append(faces[0].normed_embedding)
                    known_face_names.append(name_key)
                    print(f"[SYSTEM] Armed signature for: {name_key}")
            except Exception as e:
                print(f"[ERR] Failed processing {file_name}: {e}")

load_database()

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
    
    if action == 'register':
        try:
            for f in os.listdir(DATABASE_DIR):
                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                    os.remove(os.path.join(DATABASE_DIR, f))
        except Exception:
            pass
            
        img_path = os.path.join(DATABASE_DIR, "User_Registered.jpg")
        cv2.imwrite(img_path, frame)
        load_database()
        
        log_security_event("NEW_USER_REGISTRATION_SUCCESS")
        return jsonify({"status": "success", "message": "Biometric registration successfully locked into cloud registry!"})
        
    elif action == 'verify':
        if not known_face_embeddings:
            log_security_event("ACCESS_REJECTED_EMPTY_DATABASE")
            return jsonify({"status": "denied", "message": "ACCESS DENIED: Database empty. Register profile first."})
            
        # Detect faces in the current webcam frame
        faces = face_app.get(frame)
        
        if not faces:
            return jsonify({"status": "denied", "message": "VERIFICATION FAILED: Frame layout blank or face obscured."})
            
        # Extract vector from the first detected face
        current_embedding = faces[0].normed_embedding
        
        # Calculate the mathematical match using dot product cosine similarity
        for index, target_embedding in enumerate(known_face_embeddings):
            similarity = np.dot(current_embedding, target_embedding)
            
            # InsightFace similarity threshold usually sits safely around 0.40 - 0.50 for verification
            if similarity > 0.45:
                name = known_face_names[index]
                log_security_event(f"ACCESS_GRANTED_USER_{name.upper()}")
                return jsonify({"status": "granted", "message": f"ACCESS GRANTED: Welcome {name}!"})
                
        log_security_event("ACCESS_REJECTED_UNKNOWN_THREAT")
        return jsonify({"status": "denied", "message": "ACCESS DENIED: Facial signature verification failed."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
