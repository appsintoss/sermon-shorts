import os
import subprocess
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify, send_file
import yt_dlp
import tempfile
import shutil

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB

# 임시 폴더 설정
TEMP_DIR = tempfile.mkdtemp()

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
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
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
            max-width: 500px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }
        .input-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            color: #333;
            font-weight: 600;
            margin-bottom: 8px;
            font-size: 14px;
        }
        input[type="text"], input[type="number"] {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 14px;
            transition: border-color 0.3s;
        }
        input[type="text"]:focus, input[type="number"]:focus {
            outline: none;
            border-color: #667eea;
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
            transition: transform 0.2s, box-shadow 0.2s;
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.4);
        }
        button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        .status {
            margin-top: 20px;
            padding: 15px;
            background: #f5f5f5;
            border-radius: 10px;
            text-align: center;
            min-height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .status.working {
            background: #e3f2fd;
            color: #1976d2;
        }
        .status.success {
            background: #e8f5e9;
            color: #388e3c;
        }
        .status.error {
            background: #ffebee;
            color: #d32f2f;
        }
        .downloads {
            margin-top: 20px;
        }
        .download-item {
            padding: 10px;
            background: #f5f5f5;
            border-radius: 8px;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .download-item a {
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
            font-size: 13px;
        }
        .info {
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 12px;
            border-radius: 4px;
            margin-bottom: 20px;
            font-size: 13px;
            color: #856404;
        }
        .spinner {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid #f3f3f3;
            border-top: 2px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 8px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>⛪ 설교 쇼츠 메이커</h1>
        <p class="subtitle">유튜브 설교 영상을 자동으로 쇼츠로 나눠드립니다</p>
        
        <div class="info">
            💡 유튜브 설교 영상 링크를 붙여넣으면 자동으로 여러 개의 쇼츠(9:16)로 분할됩니다
        </div>
        
        <form id="uploadForm">
            <div class="input-group">
                <label for="youtubeUrl">유튜브 링크</label>
                <input type="text" id="youtubeUrl" placeholder="https://www.youtube.com/watch?v=..." required>
            </div>
            
            <div class="input-group">
                <label for="segmentDuration">각 쇼츠 길이 (초, 기본값: 180)</label>
                <input type="number" id="segmentDuration" value="180" min="60" max="600">
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
            const submitBtn = document.getElementById('submitBtn');
            const downloadsDiv = document.getElementById('downloads');
            
            submitBtn.disabled = true;
            statusDiv.className = 'status working';
            statusDiv.innerHTML = '<span class="spinner"></span>변환 중... (3-15분 소요)';
            downloadsDiv.innerHTML = '';
            
            try {
                const response = await fetch('/convert', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({youtube_url: url, segment_duration: parseInt(duration)})
                });
                
                const data = await response.json();
                
                if (data.success) {
                    statusDiv.className = 'status success';
                    statusDiv.innerHTML = `✅ 변환 완료! ${data.files.length}개의 쇼츠가 생성되었습니다.`;
                    
                    downloadsDiv.innerHTML = '<h3 style="margin-bottom: 10px; font-size: 14px;">📥 다운로드</h3>';
                    data.files.forEach((file, idx) => {
                        downloadsDiv.innerHTML += `
                            <div class="download-item">
                                <span>쇼츠 ${idx + 1}</span>
                                <a href="/download/${file}" download>다운로드</a>
                            </div>
                        `;
                    });
                } else {
                    statusDiv.className = 'status error';
                    statusDiv.innerHTML = `❌ 오류: ${data.error}`;
                }
            } catch (error) {
                statusDiv.className = 'status error';
                statusDiv.innerHTML = `❌ 오류 발생: ${error.message}`;
            } finally {
                submitBtn.disabled = false;
            }
        });
    </script>
</body>
</html>
"""

def download_youtube_video(url, output_dir):
    """유튜브 영상 다운로드"""
    ydl_opts = {
        'format': 'best[ext=mp4]',
        'outtmpl': os.path.join(output_dir, 'input_video.%(ext)s'),
        'quiet': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return True
    except Exception as e:
        print(f"❌ 다운로드 오류: {e}")
        return False

def split_video_into_shorts(input_file, output_dir, segment_duration=180):
    """영상을 일정 시간 단위로 분할"""
    output_files = []
    
    try:
        # 영상 길이 확인
        probe_cmd = f'ffprobe -v error -show_entries format=duration -of csv=p=0 "{input_file}"'
        result = subprocess.run(probe_cmd, shell=True, capture_output=True, text=True, timeout=30)
        
        duration_str = result.stdout.strip()
        if not duration_str:
            print("⚠️ 영상 길이를 읽을 수 없습니다. 600초로 진행합니다.")
            total_duration = 600
        else:
            total_duration = float(duration_str)
        
        segment_duration = int(segment_duration)
        segment_count = max(1, int(total_duration / segment_duration) + 1)
        
        print(f"📹 영상 길이: {int(total_duration)}초, 분할 개수: {segment_count}개")
        
        for i in range(segment_count):
            start_time = i * segment_duration
            if start_time >= total_duration:
                break
                
            output_name = f"segment_{i:02d}.mp4"
            output_path = os.path.join(output_dir, output_name)
            
            # ffmpeg로 영상 자르기 및 9:16 변환
            cmd = f'ffmpeg -i "{input_file}" -ss {start_time} -t {segment_duration} -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2" -c:v libx264 -preset fast -c:a aac -y "{output_path}" -loglevel error'
            
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=300)
            
            if result.returncode == 0:
                output_files.append(output_name)
                print(f"✅ {output_name} 생성 완료")
            else:
                print(f"⚠️ {output_name} 생성 실패")
        
        return output_files
    
    except Exception as e:
        print(f"❌ 영상 처리 오류: {e}")
        return []

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/convert', methods=['POST'])
def convert():
    data = request.json
    youtube_url = data.get('youtube_url')
    segment_duration = data.get('segment_duration', 180)
    
    # 작업용 임시 폴더 생성
    work_dir = tempfile.mkdtemp()
    
    try:
        # 다운로드
        if not download_youtube_video(youtube_url, work_dir):
            return jsonify({"success": False, "error": "영상 다운로드 실패. 유튜브 링크를 확인해주세요."})
        
        # 입력 파일 찾기
        input_file = None
        for f in Path(work_dir).glob('input_video.*'):
            input_file = str(f)
            break
        
        if not input_file:
            return jsonify({"success": False, "error": "다운로드된 파일을 찾을 수 없습니다."})
        
        # 분할
        output_files = split_video_into_shorts(input_file, work_dir, segment_duration)
        
        if not output_files:
            return jsonify({"success": False, "error": "영상 분할 실패. 영상을 확인해주세요."})
        
        return jsonify({"success": True, "files": output_files, "work_dir": work_dir})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
    finally:
        # 정리는 나중에 (다운로드 후)
        pass

@app.route('/download/<filename>')
def download_file(filename):
    work_dir = request.args.get('dir', TEMP_DIR)
    file_path = os.path.join(work_dir, filename)
    
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return "파일을 찾을 수 없습니다.", 404

if __name__ == '__main__':
    app.run(debug=False)
