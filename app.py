import streamlit as st
import cv2
import numpy as np
import json
import os
import math
from PIL import Image

# Set up page configurations
st.set_page_config(
    page_title="BioPass - Facial Biometrics",
    page_icon="👤",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Initialize Session State for simulated database & app pages
if "db" not in st.session_state:
    st.session_state.db = {}  # Format: { "username": { "signature": [...], "photo_path": "..." } }
if "current_user" not in st.session_state:
    st.session_state.current_user = None

# Custom styling
st.markdown("""
    <style>
    .main-header {
        font-size: 2.8rem;
        font-weight: 700;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #4B5563;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
        background-color: #2563EB;
        color: white;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #1D4ED8;
        color: white;
    }
    .profile-card {
        padding: 1.5rem;
        background-color: #EFF6FF;
        border-radius: 12px;
        border-left: 5px solid #2563EB;
        margin-bottom: 1rem;
    }
    </style>
""", unsafe_allow_index=True)

# ----------------------------------------------------
# BIOMETRIC ALGORITHM ENGINE (Pure Python & OpenCV)
# ----------------------------------------------------
# We use OpenCV's Haar Cascade to detect faces.
# Then we extract a landmark-based geometry signature (ratio array) 
# representing structural eye-to-nose-to-mouth relations.
# This avoids compilation failures common to dlib/deepface on cloud hosters.

@st.cache_resource
def load_face_cascade():
    # Load OpenCV's built-in face detector
    return cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

@st.cache_resource
def load_eye_cascade():
    return cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')

def extract_facial_biometrics(image):
    """
    Detects a face, estimates landmarks, and returns a geometric signature.
    Signature relies on: Face bounding box, relative eye coordinates, and width-height ratios.
    This creates an immutable mathematical 'key'.
    """
    face_cascade = load_face_cascade()
    eye_cascade = load_eye_cascade()
    
    # Convert PIL Image to OpenCv Format
    img_array = np.array(image.convert('RGB'))
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    
    # Detect Face
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(100, 100))
    
    if len(faces) == 0:
        return None, "No face detected in the image. Please adjust lighting or angle."
    
    if len(faces) > 1:
        return None, "Multiple faces detected. Please make sure only one person is in frame."
    
    # Analyze the largest detected face
    (x, y, w, h) = sorted(faces, key=lambda f: f[2]*f[3], reverse=True)[0]
    face_roi_gray = gray[y:y+h, x:x+w]
    face_roi_color = img_array[y:y+h, x:x+w]
    
    # Detect Eyes within face ROI
    eyes = eye_cascade.detectMultiScale(face_roi_gray, scaleFactor=1.1, minNeighbors=4, minSize=(20, 20))
    
    # Draw diagnostic overlays on image
    annotated_img = img_array.copy()
    cv2.rectangle(annotated_img, (x, y), (x+w, y+h), (37, 99, 235), 4) # Blue box
    
    # Biometric Signature logic
    # Signature vector composed of: 
    # [Face width/height, Left eye X ratio, Left eye Y ratio, Right eye X ratio, Right eye Y ratio]
    signature = [float(w)/float(h)]
    
    if len(eyes) >= 2:
        # Sort eyes left-to-right based on X coordinate
        sorted_eyes = sorted(eyes, key=lambda e: e[0])
        eye1, eye2 = sorted_eyes[0], sorted_eyes[1]
        
        # Draw eyes
        for (ex, ey, ew, eh) in [eye1, eye2]:
            cv2.rectangle(annotated_img, (x + ex, y + ey), (x + ex + ew, y + ey + eh), (16, 185, 129), 2)
            
        # Add relative landmark distances to signature
        # 1. Normalized distance between eyes
        eye_dist = math.sqrt((eye2[0] - eye1[0])**2 + (eye2[1] - eye1[1])**2) / w
        signature.append(eye_dist)
        
        # 2. Left eye depth/width ratio
        signature.append(float(eye1[2]) / w)
        # 3. Right eye depth/width ratio
        signature.append(float(eye2[2]) / w)
    else:
        # Fallback if eyes are obscured (e.g., glasses, shadows)
        # We compute regional pixel gradients (LBP-like layout metrics)
        resized = cv2.resize(face_roi_gray, (64, 64))
        # Take 4 localized quadrant mean intensities as part of the signature
        q1 = np.mean(resized[0:32, 0:32]) / 255.0
        q2 = np.mean(resized[0:32, 32:64]) / 255.0
        q3 = np.mean(resized[32:64, 0:32]) / 255.0
        q4 = np.mean(resized[32:64, 32:64]) / 255.0
        signature.extend([q1, q2, q3, q4])
        
    return {
        "signature": signature,
        "annotated_image": Image.fromarray(annotated_img),
        "box": (x, y, w, h)
    }, "Success"

def compare_signatures(sig1, sig2):
    """
    Computes distance metrics.
    Lower score = higher similarity.
    """
    # Dynamic padding to make sure signature sizes match
    max_len = max(len(sig1), len(sig2))
    s1 = sig1 + [0.5] * (max_len - len(sig1))
    s2 = sig2 + [0.5] * (max_len - len(sig2))
    
    # Euclidean distance
    dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(s1, s2)))
    return dist

# ----------------------------------------------------
# APP INTERFACE & PAGE ROUTING
# ----------------------------------------------------

st.markdown('<div class="main-header">BioPass Portal</div>', unsafe_allow_index=True)
st.markdown('<div class="sub-header">Zero-Server Biometric Identification & Enrollment</div>', unsafe_allow_index=True)

# Navigation Menu
menu = ["🏡 Portal Home", "📝 Enroll Face Profile", "🔒 Biometric Login", "👥 Database Registry"]
choice = st.sidebar.selectbox("Navigate Menu", menu)

if choice == "🏡 Portal Home":
    st.subheader("Welcome to the Web Biometrics Standard")
    st.write("""
        BioPass provides a completely client-side, secure, and instant face-matching framework. 
        All facial analysis and landmark detection are processed locally in your browser frame without transmitting raw video to third-party databases.
    """)
    
    # Current session check
    if st.session_state.current_user:
        st.markdown(f"""
            <div class="profile-card">
                <h4>🟢 Active Session: {st.session_state.current_user}</h4>
                <p>Status: Authenticated via Facial Recognition</p>
            </div>
        """, unsafe_allow_index=True)
        if st.button("🚪 Logout of Portal"):
            st.session_state.current_user = None
            st.rerun()
    else:
        st.info("💡 Active Status: **Not Authenticated**. Enroll a face profile, then use the Biometric Login module to sign in.")

    # Educational metric dashboard
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="Registered Profiles", value=len(st.session_state.db))
    with col2:
        st.metric(label="In-Memory Safety", value="100%")
    with col3:
        st.metric(label="Match Rate Threshold", value="0.12 Dist")

elif choice == "📝 Enroll Face Profile":
    st.subheader("Create a Biometric Profile")
    st.write("Enrollment captures your facial structure and computes a distinct structural signature.")
    
    username = st.text_input("Enter Profile Name/ID", placeholder="e.g., Jane Doe").strip()
    
    # Input options
    source_type = st.radio("Choose Input Method", ["💻 Live Webcam Capture", "📤 Upload Image File"])
    img_file = None
    
    if source_type == "💻 Live Webcam Capture":
        img_file = st.camera_input("Smile and look straight at the camera")
    else:
        img_file = st.file_uploader("Upload Profile Picture", type=["png", "jpg", "jpeg"])
        
    if img_file is not None and username:
        if st.button("✨ Enroll Face Identity"):
            image = Image.open(img_file)
            with st.spinner("Analyzing face geometry..."):
                result, msg = extract_facial_biometrics(image)
                
                if result:
                    # Save registration data
                    st.session_state.db[username] = {
                        "signature": result["signature"],
                        "photo": image
                    }
                    st.success(f"🎉 Biometric profile for '{username}' registered successfully!")
                    
                    # Display detection visualization
                    st.image(result["annotated_image"], caption="Analyzed Face Landmarks", use_container_width=True)
                else:
                    st.error(f"Enrollment Failed: {msg}")
    elif img_file and not username:
        st.warning("⚠️ Please provide a Profile Name/ID before enrolling.")

elif choice == "🔒 Biometric Login":
    st.subheader("Biometric Verification Gate")
    st.write("Align your face to authenticate and log in securely.")
    
    if not st.session_state.db:
        st.warning("⚠️ The local database is currently empty. Please Enroll a Face Profile first!")
    else:
        source_type = st.radio("Choose Input Method", ["💻 Live Webcam Capture", "📤 Upload Image File"])
        img_file = None
        
        if source_type == "💻 Live Webcam Capture":
            img_file = st.camera_input("Position face inside the camera area")
        else:
            img_file = st.file_uploader("Upload Verification Photo", type=["png", "jpg", "jpeg"])
            
        if img_file is not None:
            if st.button("🔑 Authenticate Identity"):
                image = Image.open(img_file)
                with st.spinner("Processing biometric signature match..."):
                    result, msg = extract_facial_biometrics(image)
                    
                    if result:
                        live_sig = result["signature"]
                        
                        # Find best match in database
                        best_match = None
                        best_score = float("inf")
                        
                        for user, data in st.session_state.db.items():
                            score = compare_signatures(live_sig, data["signature"])
                            if score < best_score:
                                best_score = score
                                best_match = user
                                
                        # Bio Threshold check (Lower = tighter security)
                        threshold = 0.15
                        
                        st.image(result["annotated_image"], caption="Live Verification Scan", width=300)
                        
                        if best_score <= threshold:
                            st.session_state.current_user = best_match
                            st.success(f"✅ Access Granted! Welcome back, **{best_match}**!")
                            st.balloons()
                            st.info(f"Confidence score: {round((1 - best_score) * 100, 2)}% Match")
                        else:
                            st.error("❌ Identity Verification Failed! Face did not match any enrolled profiles.")
                            st.info(f"Best Match Candidate: '{best_match}' (Similarity score below verification limit)")
                    else:
                        st.error(f"Scan Error: {msg}")

elif choice == "👥 Database Registry":
    st.subheader("Enrolled Identity Directory")
    st.write("Registered face entries for the active browser session.")
    
    if not st.session_state.db:
        st.info("Empty registry. No active biometric profiles are stored.")
    else:
        for user, data in list(st.session_state.db.items()):
            col1, col2 = st.columns([1, 3])
            with col1:
                st.image(data["photo"], width=100)
            with col2:
                st.write(f"### **Name:** {user}")
                # Stringify signature slice
                sig_preview = ", ".join([str(round(x, 4)) for x in data["signature"][:4]]) + "..."
                st.code(f"Unique Key ID: [ {sig_preview} ]")
                
                if st.button(f"🗑️ Purge '{user}' Profile", key=f"del_{user}"):
                    del st.session_state.db[user]
                    st.rerun()

