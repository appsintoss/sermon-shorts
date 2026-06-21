import os
import subprocess
import tempfile
import json
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify, send_file
import yt_dlp
import whisper

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024 # 500MB 제한

# Whisper 모델 로드 (처음 한 번만)
WHISPER_MODEL = None

def get_whisper_model():
    global WHISPER_MODEL
    if WHISPER_MODEL is None:
        print("🎵 Whisper 모델 로딩 중...")
        WHISPER_MODEL = whisper.load_model("base", device="cpu")
    return WHISPER_MODEL

def find_korean_font():
    """한국어 폰트 찾기"""
    possible_fonts = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttf",
        "/System/Library/Fonts/PingFang.ttc",  # macOS
        "C:\\Windows\\Fonts\\arial.ttf",  # Windows
    ]
    for font_path in possible_fonts:
        if os.path.exists(font_path):
            print(f"✅ 폰트 찾음: {font_path}")
            return font_path
    print("⚠️  한국어 폰트 없음. 기본 폰트 사용")
    return None

def extract_subtitles(audio_path, output_dir):
    """Whisper로 자막 추출"""
    print(f"🎙️  Whisper로 자막 추출 중... ({audio_path})")
    model = get_whisper_model()
    result = model.transcribe(audio_path, language="ko")
    
    # SRT 형식으로 변환
    srt_path = os.path.join(output_dir, "subtitles.srt")
    with open(srt_path, 'w', encoding='utf-8') as f:
        for idx, segment in enumerate(result['segments'], 1):
            start = format_timestamp(segment['start'])
            end = format_timestamp(segment['end'])
            text = segment['text']
            f.write(f"{idx}\n{start} --> {end}\n{text}\n\n")
    
    print(f"✅ 자막 생성 완료: {srt_path}")
    return srt_path

def format_timestamp(seconds):
    """초를 SRT 형식(HH:MM:SS,mmm)으로 변환"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def add_subtitles_to_video(input_video, subtitle_file, output_video, font_path=None):
    """비디오에 자막 추가"""
    print(f"📝 자막 추가 중... ({output_video})")
    
    if font_path:
        # 폰트 경로를 escaping (Windows 경로 대비)
        font_path = font_path.replace('\\', '/')
        subtitle_filter = f"subtitles={subtitle_file}:fontfile={font_path}:fontsize=24:font_color=white:borderw=2:bordercolor=black"
    else:
        subtitle_filter = f"subtitles={subtitle_file}:fontsize=24:font_color=white"
    
    cmd = [
        'ffmpeg', '-i', input_video,
        '-vf', subtitle_filter,
        '-c:a', 'aac',
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-y',
        output_video
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f"❌ 자막 추가 오류: {result.stderr}")
        raise Exception(f"ffmpeg 오류: {result.stderr}")
    
    print(f"✅ 자막 추가 완료: {output_video}")
    return output_video

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>설교 쇼츠 메이커</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 40px;
            width: 100%;
            max-width: 600px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        h2 {
            color: #333;
            margin-bottom: 30px;
            text-align: center;
            font-size: 28px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            color: #555;
            margin-bottom: 8px;
            font-weight: 500;
            font-size: 14px;
        }
        input[type="text"],
        input[type="number"],
        input[type="file"] {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 15px;
            transition: border-color 0.3s;
        }
        input[type="text"]:focus,
        input[type="number"]:focus,
        input[type="file"]:focus {
            outline: none;
            border-color: #667eea;
        }
        .checkbox-group {
            display: flex;
            align-items: center;
            gap: 10px;
            margin: 15px 0;
        }
        input[type="checkbox"] {
            width: 20px;
            height: 20px;
            cursor: pointer;
        }
        button {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
        }
        button:hover {
            transform: translateY(-2px);
        }
        button:active {
            transform: translateY(0);
        }
        hr {
            margin: 30px 0;
            border: none;
            border-top: 2px solid #e0e0e0;
        }
        #status {
            margin-top: 20px;
            text-align: center;
            font-size: 16px;
            padding: 15px;
            border-radius: 10px;
        }
        #status.loading {
            background: #e3f2fd;
            color: #1976d2;
        }
        #status.success {
            background: #e8f5e9;
            color: #388e3c;
        }
        #status.error {
            background: #ffebee;
            color: #c62828;
        }
        #links {
            margin-top: 15px;
        }
        .download-link {
            display: block;
            padding: 12px;
            background: #f5f5f5;
            border-radius: 8px;
            text-decoration: none;
            color: #667eea;
            margin: 8px 0;
            font-weight: 500;
            text-align: center;
            transition: background 0.2s;
        }
        .download-link:hover {
            background: #e0e0e0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h2>⛪ 설교 쇼츠 메이커</h2>
        
        <div>
            <h3 style="color: #666; margin: 20px 0 15px 0; font-size: 18px;">1️⃣ 유튜브 영상</h3>
            <form id="urlForm">
                <div class="form-group">
                    <label>유튜브 링크</label>
                    <input type="text" id="url" placeholder="https://youtube.com/..." required>
                </div>
                <div class="form-group">
                    <label>세그먼트 길이 (초)</label>
                    <input type="number" id="dur1" value="180" min="30" max="600">
                </div>
                <div class="checkbox-group">
                    <input type="checkbox" id="addSubs1" checked>
                    <label for="addSubs1" style="margin: 0;">자막 자동 추가 (Whisper)</label>
                </div>
                <button type="submit">🚀 유튜브 변환</button>
            </form>
        </div>
        
        <hr>
        
        <div>
            <h3 style="color: #666; margin: 20px 0 15px 0; font-size: 18px;">2️⃣ 파일 업로드</h3>
            <form id="fileForm">
                <div class="form-group">
                    <label>MP4 파일 선택</label>
                    <input type="file" id="file" accept="video/mp4" required>
                </div>
                <div class="form-group">
                    <label>세그먼트 길이 (초)</label>
                    <input type="number" id="dur2" value="180" min="30" max="600">
                </div>
                <div class="checkbox-group">
                    <input type="checkbox" id="addSubs2" checked>
                    <label for="addSubs2" style="margin: 0;">자막 자동 추가 (Whisper)</label>
                </div>
                <button type="submit">📤 파일 변환</button>
            </form>
        </div>
        
        <div id="status"></div>
        <div id="links"></div>
    </div>
    
    <script>
        async function sendReq(formData, isFile) {
            const status = document.getElementById('status');
            const links = document.getElementById('links');
            status.textContent = "⏳ 처리 중... (이 과정에 2-5분이 걸릴 수 있습니다)";
            status.className = "loading";
            links.innerHTML = "";
            
            try {
                const endpoint = isFile ? '/upload' : '/convert';
                const res = await fetch(endpoint, { method: 'POST', body: formData });
                const data = await res.json();
                
                if(data.success) {
                    status.textContent = "✅ 완료! 아래에서 다운로드하세요.";
                    status.className = "success";
                    data.files.forEach(f => {
                        const link = document.createElement('a');
                        link.href = `/download/${f}?dir=${data.work_dir}`;
                        link.className = 'download-link';
                        link.textContent = `📥 다운로드: ${f}`;
                        links.appendChild(link);
                    });
                } else {
                    status.textContent = "❌ 오류: " + data.error;
                    status.className = "error";
                }
            } catch(err) {
                status.textContent = "❌ 요청 실패: " + err.message;
                status.className = "error";
            }
        }
        
        document.getElementById('urlForm').onsubmit = (e) => {
            e.preventDefault();
            const formData = JSON.stringify({
                url: document.getElementById('url').value,
                dur: document.getElementById('dur1').value,
                add_subs: document.getElementById('addSubs1').checked
            });
            sendReq(formData, false);
        };
        
        document.getElementById('fileForm').onsubmit = (e) => {
            e.preventDefault();
            const fd = new FormData();
            fd.append('file', document.getElementById('file').files[0]);
            fd.append('dur', document.getElementById('dur2').value);
            fd.append('add_subs', document.getElementById('addSubs2').checked ? 'true' : 'false');
            sendReq(fd, true);
        };
    </script>
</body>
</html>
"""

def split_video(input_file, output_dir, segment_duration, add_subs=True):
    """비디오 분할 및 자막 추가"""
    files = []
    
    # 1단계: 오디오 추출 (자막 생성용)
    audio_path = os.path.join(output_dir, "audio.wav")
    print(f"🎵 오디오 추출 중...")
    cmd_audio = [
        'ffmpeg', '-i', input_file,
        '-q:a', '9', '-n',
        audio_path
    ]
    subprocess.run(cmd_audio, capture_output=True, timeout=120)
    
    # 2단계: Whisper로 자막 생성
    subtitle_file = None
    font_path = None
    if add_subs:
        try:
            subtitle_file = extract_subtitles(audio_path, output_dir)
            font_path = find_korean_font()
        except Exception as e:
            print(f"⚠️  자막 생성 실패: {e}")
            subtitle_file = None
    
    # 3단계: 비디오 분할
    print(f"✂️  비디오 분할 중 ({segment_duration}초)...")
    cmd = [
        'ffmpeg', '-i', input_file,
        '-c:v', 'libx264', '-c:a', 'aac',
        '-f', 'segment',
        '-segment_time', str(segment_duration),
        '-reset_timestamps', '1',
        '-y',
        os.path.join(output_dir, "segment_%03d.mp4")
    ]
    subprocess.run(cmd, capture_output=True, timeout=300)
    
    # 4단계: 각 세그먼트에 자막 추가
    for f in sorted(Path(output_dir).glob("segment_*.mp4")):
        if subtitle_file and os.path.exists(subtitle_file):
            output_with_subs = os.path.join(output_dir, f"sub_{f.name}")
            try:
                add_subtitles_to_video(str(f), subtitle_file, output_with_subs, font_path)
                os.remove(f)  # 원본 삭제
                os.rename(output_with_subs, f)
                print(f"✅ 자막 추가됨: {f.name}")
            except Exception as e:
                print(f"⚠️  자막 추가 실패 ({f.name}): {e}")
        
        files.append(f.name)
    
    # 정리
    if os.path.exists(audio_path):
        os.remove(audio_path)
    
    return files

@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)

@app.route('/convert', methods=['POST'])
def convert():
    data = request.json
    work_dir = tempfile.mkdtemp()
    add_subs = data.get('add_subs', True)
    
    ydl_opts = {'outtmpl': os.path.join(work_dir, 'input.mp4'), 'format': 'best[ext=mp4]'}
    try:
        print(f"📥 유튜브에서 다운로드 중...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([data['url']])
        
        files = split_video(os.path.join(work_dir, 'input.mp4'), work_dir, int(data['dur']), add_subs=add_subs)
        return jsonify({"success": True, "files": files, "work_dir": work_dir})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/upload', methods=['POST'])
def upload():
    work_dir = tempfile.mkdtemp()
    path = os.path.join(work_dir, "input.mp4")
    add_subs = request.form.get('add_subs', 'true').lower() == 'true'
    
    try:
        request.files['file'].save(path)
        files = split_video(path, work_dir, int(request.form['dur']), add_subs=add_subs)
        return jsonify({"success": True, "files": files, "work_dir": work_dir})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/download/<filename>')
def download(filename): return send_file(os.path.join(request.args.get('dir'), filename), as_attachment=True)

if __name__ == '__main__': app.run(host='0.0.0.0', port=5000)
