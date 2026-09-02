import os
from flask import Flask, request, send_file, jsonify
from werkzeug.utils import secure_filename
from services.video_translation_service import process_video_translation

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.route('/api/translate-video', methods=['POST'])
def translate_video_endpoint():
    if 'video' not in request.files:
        return jsonify({"error": "No video file provided"}), 400
    
    file = request.files['video']
    if file.filename == '':
        return jsonify({"error": "Selected file is invalid"}), 400
        
    filename = secure_filename(file.filename)
    video_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(video_path)
    
    try:
        # Run translation, video dubbing, and zip creation
        zip_file_path = process_video_translation(video_path, OUTPUT_FOLDER)
        return send_file(zip_file_path, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
        
