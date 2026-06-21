import os
import subprocess
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify, send_file
import yt_dlp
import tempfile
import shutil

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

# 임시 폴더 설정
TEMP_DIR = tempfile.mkdtemp()

# 사용자님이 처음에 주셨던 HTML 원본입니다
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>설교 쇼츠 메이커</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; justify-content: center; align-items: center; padding: 20px; }
        .container { background: white; border-radius: 20px; padding: 40px; max-width: 500px; width: 100%; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
        h1 { color: #333; margin-bottom: 10px; font-size: 28px; }
        .subtitle { color: #666; margin-bottom: 30px; font-size: 14px; }
        .input-group { margin-bottom: 20px; }
        label { display: block; color: #333; font-weight: 600; margin-bottom: 8px; font-size: 14px; }
        input[type="text"], input[type="number"] { width: 100%; padding: 12px; border: 2px solid #e0e0e0; border-radius: 10px; font-size: 14px; }
        button { width: 100%; padding: 14px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 10px; font-size: 16px; cursor: pointer; }
        .status { margin-top: 20px; padding: 15px; background: #f5f5f5; border-radius: 10px; text-align: center; }
        .download-item { padding: 10px; background: #f5f5f5; border-radius: 8px; margin-bottom: 8px; display: flex; justify-content: space-between; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⛪ 설교 쇼츠 메이커</h1>
        <form id="uploadForm">
            <div class="input-group">
                <label for="youtubeUrl">유튜브 링크</label>
                <input type="text" id="youtubeUrl" placeholder="https://www.youtube.com/watch?v=..." required>
            </div>
            <div class="input-group">
                <label for="segmentDuration">각 쇼츠 길이 (초)</label>
                <input type="number" id="segmentDuration" value="180">
            </div>
            <button type="submit" id="submitBtn">변환 시작</button>
        </form>
        <div class="status" id="status"></div>
        <div class="downloads" id="downloads"></div>
    </div>
    <script>
        document.getElementById('uploadForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const url = document.getElementById('youtubeUrl').value;
            const duration = document.getElementById('segmentDuration').value;
            const statusDiv = document.getElementById('status');
            statusDiv.innerHTML = '변환 중...';
            
            const response = await fetch('/convert', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({youtube_url: url, segment_duration: parseInt(duration)})
            });
            const data = await response.json();
            if (data.success) {
                statusDiv.innerHTML = `✅ 완료!`;
                data.files.forEach((file, idx) => {
                    document.getElementById('downloads').innerHTML += `<div class="download-item">쇼츠 ${idx + 1} <a href="/download/${file}?dir=${data.work_dir}">다운로드</a></div>`;
                });
            } else {
                statusDiv.innerHTML = `❌ 오류: ${data.error}`;
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
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'geo_bypass': True,
        'nocheckcertificate': True
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
        return True
    except:
        return False

def split_video_into_shorts(input_file, output_dir, segment_duration=180):
    output_files = []
    # 영상 길이를 ffprobe로 확인
    cmd_probe = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{input_file}"'
    try:
        duration = float(subprocess.check_output(cmd_probe, shell=True))
        num_segments = int(duration / segment_duration) + 1
        for i in range(num_segments):
            out_name = f"segment_{i}.mp4"
            cmd = f'ffmpeg -i "{input_file}" -ss {i*segment_duration} -t {segment_duration} -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2" -c:v libx264 -c:a aac -y "{os.path.join(output_dir, out_name)}"'
            subprocess.run(cmd, shell=True)
            output_files.append(out_name)
    except: pass
    return output_files

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/convert', methods=['POST'])
def convert():
    data = request.json
    work_dir = tempfile.mkdtemp()
    if download_youtube_video(data['youtube_url'], work_dir):
        input_file = list(Path(work_dir).glob('input_video.*'))[0]
        files = split_video_into_shorts(str(input_file), work_dir, data['segment_duration'])
        return jsonify({"success": True, "files": files, "work_dir": work_dir})
    return jsonify({"success": False, "error": "다운로드 실패"})

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(request.args.get('dir'), filename), as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
