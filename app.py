import os
import subprocess
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify, send_file
import yt_dlp
import tempfile

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

# 임시 작업 디렉토리 생성
TEMP_DIR = tempfile.mkdtemp()

HTML_TEMPLATE = """
""" # 위에서 주신 기존 HTML 내용을 그대로 유지하세요.

def download_youtube_video(url, output_dir):
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': os.path.join(output_dir, 'input_video.%(ext)s'),
        'quiet': False,
        # 봇 탐지 방지 강화
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'referer': 'https://www.youtube.com/',
        'geo_bypass': True,
        'nocheckcertificate': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
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
        result = subprocess.run(probe_cmd, shell=True, capture_output=True, text=True, timeout=60)
        
        duration_str = result.stdout.strip()
        total_duration = float(duration_str) if duration_str else 600
        
        segment_duration = int(segment_duration)
        segment_count = max(1, int(total_duration / segment_duration) + 1)
        
        for i in range(segment_count):
            start_time = i * segment_duration
            if start_time >= total_duration: break
            
            output_name = f"segment_{i:02d}.mp4"
            output_path = os.path.join(output_dir, output_name)
            
            # FFmpeg 처리
            cmd = f'ffmpeg -i "{input_file}" -ss {start_time} -t {segment_duration} -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2" -c:v libx264 -preset fast -c:a aac -y "{output_path}" -loglevel error'
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=600)
            
            if result.returncode == 0:
                output_files.append(output_name)
        return output_files
    except Exception as e:
        print(f"❌ 영상 처리 오류: {e}")
        return []

@app.route('/convert', methods=['POST'])
def convert():
    data = request.json
    youtube_url = data.get('youtube_url')
    segment_duration = data.get('segment_duration', 180)
    work_dir = tempfile.mkdtemp()
    
    if not download_youtube_video(youtube_url, work_dir):
        return jsonify({"success": False, "error": "다운로드 실패. 일반 공개 영상을 시도해 보세요."})
    
    input_file = next(Path(work_dir).glob('input_video.*'), None)
    if not input_file:
        return jsonify({"success": False, "error": "파일을 찾을 수 없습니다."})
        
    output_files = split_video_into_shorts(str(input_file), work_dir, segment_duration)
    return jsonify({"success": True, "files": output_files, "work_dir": work_dir})

@app.route('/download/<filename>')
def download_file(filename):
    # work_dir을 쿼리 스트링에서 가져오도록 수정
    work_dir = request.args.get('dir')
    file_path = os.path.join(work_dir, filename)
    return send_file(file_path, as_attachment=True) if os.path.exists(file_path) else "파일 없음", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
