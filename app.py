from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
import face_recognition
import cv2
import os
import datetime

# Flask app setup
app = Flask(__name__)
app.secret_key = "g38_1912"

# Configure folder paths
ACCESS_FOLDER = "access_persons"  # Folder containing images of known persons
UPLOAD_FOLDER = "static/images"  # Folder to save uploaded images
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(ACCESS_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# User model
class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

# Dummy user data (use a database in production)
users = {
    "admin": User(id=1, username="admin38", password="g38123"),
}

@login_manager.user_loader
def load_user(user_id):
    for user in users.values():
        if user.id == int(user_id):
            return user
    return None

# Helper function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Helper function to load known faces
def load_known_faces(folder):
    known_face_encodings = []
    known_face_names = []
    for filename in os.listdir(folder):
        if filename.endswith(('png', 'jpg', 'jpeg')):
            image_path = os.path.join(folder, filename)
            image = face_recognition.load_image_file(image_path)
            encoding = face_recognition.face_encodings(image)[0]  # Get the first face encoding
            known_face_encodings.append(encoding)
            known_face_names.append(os.path.splitext(filename)[0])  # Use file name (without extension) as the person's name
    return known_face_encodings, known_face_names

# Load known faces from the access folder
known_face_encodings, known_face_names = load_known_faces(ACCESS_FOLDER)

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = users.get(username)
        if user and user.password == password:
            flash('Login successful!', 'success')
            login_user(user)
            return redirect(url_for('access'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('login.html')

# Logout route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Access management endpoint (for adding known faces)
@app.route('/access', methods=['GET', 'POST'])
@login_required
def access():
    if request.method == 'POST':
        if 'image' not in request.files or 'name' not in request.form:
            return jsonify({"error": "Image and name required"}), 400
        file = request.files['image']
        name = request.form['name']
        if file and allowed_file(file.filename):
            filepath = os.path.join(ACCESS_FOLDER, f"{name}.jpg")
            file.save(filepath)
            flash('Face added successfully!', 'success')
            return redirect(url_for('access'))
    return render_template('access.html')

# Face recognition upload and processing
@app.route('/upload', methods=['POST'])
def upload():
    if 'image' not in request.files:
        return jsonify({"error": "No image uploaded"}), 400
    file = request.files['image']
    if file and allowed_file(file.filename):
        # Secure the filename
        base_filename = secure_filename(file.filename)
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{base_filename}_{timestamp}.jpg"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # Save the uploaded image temporarily
        file.save(filepath)

        # Process the uploaded image for face recognition
        uploaded_image = face_recognition.load_image_file(filepath)
        face_locations = face_recognition.face_locations(uploaded_image)
        face_encodings = face_recognition.face_encodings(uploaded_image, face_locations)

        # OpenCV image for drawing
        cv2_image = cv2.imread(filepath)

        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            # Compare the uploaded face to known faces
            matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
            name = "Unknown"

            if True in matches:
                match_index = matches.index(True)
                name = known_face_names[match_index]

            # Draw a rectangle around the face
            cv2.rectangle(cv2_image, (left, top), (right, bottom), (0, 255, 0), 2)
            # Add a label with the name
            cv2.putText(cv2_image, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        # Save the processed image with the detected faces
        processed_filename = f"processed_{timestamp}.jpg"
        processed_filepath = os.path.join(app.config['UPLOAD_FOLDER'], processed_filename)
        cv2.imwrite(processed_filepath, cv2_image)

        return jsonify({"message": "Image processed successfully", "processed_image_link": f"/{processed_filepath}"})
    return jsonify({"error": "Invalid file type"}), 400

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
