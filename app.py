import os
import subprocess
import tempfile
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify, send_file
import yt_dlp

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024 # 500MB 제한

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8"><title>설교 쇼츠 메이커</title>
    <style>
        body { font-family: sans-serif; background: #f4f4f9; display: flex; justify-content: center; padding: 20px; }
        .container { background: white; padding: 30px; border-radius: 15px; width: 100%; max-width: 500px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
        input, button { width: 100%; padding: 12px; margin: 8px 0; border: 1px solid #ccc; border-radius: 8px; }
        button { background: #6c5ce7; color: white; border: none; cursor: pointer; }
    </style>
</head>
<body>
    <div class="container">
        <h2>⛪ 설교 쇼츠 메이커</h2>
        <form id="urlForm">
            <input type="text" id="url" placeholder="유튜브 링크 입력" required>
            <input type="number" id="dur1" value="180">
            <button type="submit">유튜브 변환</button>
        </form>
        <hr>
        <form id="fileForm">
            <input type="file" id="file" accept="video/mp4" required>
            <input type="number" id="dur2" value="180">
            <button type="submit">파일 업로드 변환</button>
        </form>
        <div id="status" style="margin-top:15px; text-align:center;"></div>
        <div id="links"></div>
    </div>
    <script>
        async function sendReq(formData, isFile) {
            const status = document.getElementById('status');
            status.innerText = "처리 중...";
            const res = await fetch(isFile ? '/upload' : '/convert', { method: 'POST', body: formData });
            const data = await res.json();
            if(data.success) {
                status.innerText = "✅ 완료!";
                data.files.forEach(f => document.getElementById('links').innerHTML += `<div><a href="/download/${f}?dir=${data.work_dir}">다운로드: ${f}</a></div>`);
            } else { status.innerText = "❌ 오류: " + data.error; }
        }
        document.getElementById('urlForm').onsubmit = (e) => { e.preventDefault(); sendReq(JSON.stringify({url: document.getElementById('url').value, dur: document.getElementById('dur1').value}), false); };
        document.getElementById('fileForm').onsubmit = (e) => { e.preventDefault(); const fd = new FormData(); fd.append('file', document.getElementById('file').files[0]); fd.append('dur', document.getElementById('dur2').value); sendReq(fd, true); };
    </script>
</body>
</html>
"""

def split_video(input_file, output_dir, segment_duration):
    files = []
    # 간단한 분할 로직 (ffmpeg)
    cmd = f'ffmpeg -i "{input_file}" -c:v libx264 -c:a aac -f segment -segment_time {segment_duration} -reset_timestamps 1 "{os.path.join(output_dir, "segment_%03d.mp4")}"'
    subprocess.run(cmd, shell=True)
    for f in Path(output_dir).glob("segment_*.mp4"):
        files.append(f.name)
    return files

@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)

@app.route('/convert', methods=['POST'])
def convert():
    data = request.json
    work_dir = tempfile.mkdtemp()
    ydl_opts = {'outtmpl': os.path.join(work_dir, 'input.mp4'), 'format': 'best[ext=mp4]'}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([data['url']])
        files = split_video(os.path.join(work_dir, 'input.mp4'), work_dir, data['dur'])
        return jsonify({"success": True, "files": files, "work_dir": work_dir})
    except: return jsonify({"success": False, "error": "다운로드 실패"})

@app.route('/upload', methods=['POST'])
def upload():
    work_dir = tempfile.mkdtemp()
    path = os.path.join(work_dir, "input.mp4")
    request.files['file'].save(path)
    files = split_video(path, work_dir, request.form['dur'])
    return jsonify({"success": True, "files": files, "work_dir": work_dir})

@app.route('/download/<filename>')
def download(filename): return send_file(os.path.join(request.args.get('dir'), filename), as_attachment=True)

if __name__ == '__main__': app.run(host='0.0.0.0', port=5000)
