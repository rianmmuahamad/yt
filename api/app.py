# api/index.py
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
import yt_dlp
import os
from werkzeug.utils import secure_filename
import logging

app = Flask(__name__)
# Configure CORS with specific options
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DOWNLOAD_FOLDER = '/tmp/downloads'

# Ensure necessary directories exist
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

def get_video_info(url):
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': False,
            # Remove cookies file dependency
            'cookiefile': None
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []
            resolutions_found = set()
            
            for f in info.get('formats', []):
                height = f.get('height', 0)
                if (f['ext'] == 'mp4' and 
                    f['vcodec'] != 'none' and 
                    height not in resolutions_found and 
                    height > 0):
                    formats.append({
                        'height': height,
                        'filesize': get_size_str(f.get('filesize', 0)),
                        'format_id': f['format_id']
                    })
                    resolutions_found.add(height)
            
            formats.sort(key=lambda x: x['height'], reverse=True)
            
            return {
                'title': info.get('title', ''),
                'duration': info.get('duration', 0),
                'formats': formats,
                'thumbnail': info.get('thumbnail', '')
            }
    except Exception as e:
        logger.error(f"Error extracting video info: {str(e)}")
        return {'error': str(e)}

def get_size_str(bytes):
    """Convert file size to readable format"""
    if bytes is None:
        return "Unknown size"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024
    return f"{bytes:.2f} GB"

@app.route('/api/info', methods=['POST', 'OPTIONS'])
def get_info():
    if request.method == 'OPTIONS':
        return '', 204
        
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data received'}), 400
            
        url = data.get('url')
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        info = get_video_info(url)
        if 'error' in info:
            return jsonify(info), 400
        return jsonify(info)
    except Exception as e:
        logger.error(f"Error in get_info: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['POST', 'OPTIONS'])
def download():
    if request.method == 'OPTIONS':
        return '', 204
        
    try:
        data = request.get_json()
        url = data.get('url')
        format_type = data.get('type')
        resolution = data.get('resolution')
        
        if not url or not format_type:
            return jsonify({'error': 'Missing parameters'}), 400

        ydl_opts = {
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
        }

        if format_type == 'video':
            ydl_opts.update({
                'format': f'bestvideo[height<={resolution}]+bestaudio/best',
                'merge_output_format': 'mp4',
            })
        else:  # audio
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if format_type == 'audio':
                filename = os.path.splitext(filename)[0] + '.mp3'
            
            return jsonify({
                'success': True,
                'message': 'Download completed',
                'filename': os.path.basename(filename)
            })
            
    except Exception as e:
        logger.error(f"Unexpected error during download: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    return send_file('../index.html')

@app.route('/downloads/<filename>')
def download_file(filename):
    return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
