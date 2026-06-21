import os
import subprocess
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify, send_file
import yt_dlp
import tempfile

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

# HTML 템플릿 (기존 전체 내용 복구)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>설교 쇼츠 메이커</title>
    <style>
        body { font-family: sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; justify-content: center; align-items: center; padding: 20px; }
        .container { background: white; border-radius: 20px; padding: 40px; max-width: 500px; width: 100%; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
        input, button { width: 100%; padding: 12px; margin: 10px 0; border-radius: 10px; border: 2px solid #ddd; }
        button { background: #764ba2; color: white; border: none; cursor: pointer; }
        .status { margin-top: 20px; padding: 15px; border-radius: 10px; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⛪ 설교 쇼츠 메이커</h1>
        <form id="uploadForm">
            <input type="text" id="youtubeUrl" placeholder="유튜브 링크 입력" required>
            <input type="number" id="segmentDuration" value="180">
            <button type="submit" id="submitBtn">변환 시작</button>
        </form>
        <div id="status" class="status"></div>
        <div id="downloads"></div>
    </div>
    <script>
        document.getElementById('uploadForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const url = document.getElementById('youtubeUrl').value;
            const duration = document.getElementById('segmentDuration').value;
            const statusDiv = document.getElementById('status');
            statusDiv.innerText = '변환 중...';
            const response = await fetch('/convert', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({youtube_url: url, segment_duration: parseInt(duration)})
            });
            const data = await response.json();
            if (data.success) {
                statusDiv.innerText = '✅ 완료!';
                const dlDiv = document.getElementById('downloads');
                data.files.forEach(f => {
                    dlDiv.innerHTML += `<div class="download-item"><a href="/download/${f}?dir=${data.work_dir}">다운로드 ${f}</a></div>`;
                });
            } else {
                statusDiv.innerText = '❌ 오류: ' + data.error;
            }
        });
    </script>
</body>
</html>
"""

def download_youtube_video(url, output_dir):
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': os.path.join(output_dir, 'input_video.%(ext)s'),
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'geo_bypass': True,
        'nocheckcertificate': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
        return True
    except: return False

def split_video_into_shorts(input_file, output_dir, segment_duration):
    output_files = []
    # ... (기존 분할 로직)
    return output_files

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/convert', methods=['POST'])
def convert():
    data = request.json
    work_dir = tempfile.mkdtemp()
    if download_youtube_video(data['youtube_url'], work_dir):
        files = split_video_into_shorts(list(Path(work_dir).glob('input_video.*'))[0], work_dir, data['segment_duration'])
        return jsonify({"success": True, "files": files, "work_dir": work_dir})
    return jsonify({"success": False, "error": "다운로드 실패"})

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(request.args.get('dir'), filename), as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
