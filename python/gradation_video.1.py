import os
import shutil
import subprocess
import json
from PIL import Image, ImageDraw, ImageFilter
from tqdm import tqdm
import glob

#pip install pillow tqdm
def feather_video_edges_with_ffmpeg(
    video_path: str, 
    output_path: str, 
    border_width: int,
    ffmpeg_path: str = "ffmpeg", # 시스템 PATH에 없으면 "C:/path/to/ffmpeg.exe" 형식으로 지정
    ffprobe_path: str = "ffprobe" # 시스템 PATH에 없으면 "C:/path/to/ffprobe.exe" 형식으로 지정
):
    """
    ffmpeg.exe를 직접 호출하여 동영상의 경계에 페더링 효과를 적용합니다.
    """
    # --- 1. 사전 검사 및 임시 폴더 설정 ---
    if not os.path.exists(video_path):
        print(f"오류: 원본 동영상 '{video_path}'을(를) 찾을 수 없습니다.")
        return
    if shutil.which(ffmpeg_path) is None or shutil.which(ffprobe_path) is None:
        print("오류: ffmpeg 또는 ffprobe를 찾을 수 없습니다.")
        print("시스템 환경변수 PATH에 ffmpeg 경로를 추가하거나, 코드 내의 경로 변수를 직접 지정해주세요.")
        return

    temp_dir = "temp_video_processing"
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)
    
    print(f"임시 작업 폴더 '{temp_dir}'을(를) 생성했습니다.")

    try:
        # --- 2. FFprobe로 동영상 정보 가져오기 (FPS) ---
        print("원본 동영상 정보를 분석합니다...")
        cmd_probe = [
            ffprobe_path, "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate",
            "-of", "json", video_path
        ]
        result = subprocess.run(cmd_probe, capture_output=True, text=True, check=True)
        video_info = json.loads(result.stdout)["streams"][0]
        
        width = video_info["width"]
        height = video_info["height"]
        frame_rate = video_info["r_frame_rate"] # e.g., "30/1"
        print(f"정보: {width}x{height}, FPS: {frame_rate}")

        # --- 3. FFmpeg로 프레임 추출 ---
        print("동영상 프레임을 이미지로 추출합니다... (시간이 걸릴 수 있습니다)")
        cmd_extract_frames = [
            ffmpeg_path, "-i", video_path, "-y",
            os.path.join(temp_dir, "frame_%06d.png")
        ]
        subprocess.run(cmd_extract_frames, check=True, capture_output=True)

        # --- 4. FFmpeg로 오디오 추출 ---
        print("오디오를 추출합니다...")
        audio_output_path = os.path.join(temp_dir, "audio.aac")
        cmd_extract_audio = [
            ffmpeg_path, "-i", video_path, "-vn", "-acodec", "copy", "-y", audio_output_path
        ]
        # 오디오 스트림이 없는 경우를 대비하여 예외 처리
        try:
            subprocess.run(cmd_extract_audio, check=True, capture_output=True)
            has_audio = True
        except subprocess.CalledProcessError:
            print("경고: 원본 동영상에 오디오 스트림이 없거나 추출에 실패했습니다.")
            has_audio = False

        # --- 5. Python(Pillow)으로 마스크 생성 및 프레임 처리 ---
        print("알파 마스크를 생성하고 각 프레임에 적용합니다...")
        mask = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(mask)
        draw.rectangle(
            (border_width, border_width, width - border_width, height - border_width),
            fill=255
        )
        blur_radius = border_width / 2
        mask_blurred = mask.filter(ImageFilter.GaussianBlur(radius=blur_radius))

        frame_files = sorted(glob.glob(os.path.join(temp_dir, "frame_*.png")))
        for frame_path in tqdm(frame_files, desc="프레임 처리 중"):
            frame_img = Image.open(frame_path).convert("RGBA")
            frame_img.putalpha(mask_blurred)
            frame_img.save(frame_path)

        # --- 6. FFmpeg로 최종 동영상 합성 ---
        print("처리된 프레임과 오디오를 최종 동영상으로 합성합니다...")
        cmd_compose = [
            ffmpeg_path, "-framerate", frame_rate, "-i", os.path.join(temp_dir, "frame_%06d.png"),
        ]
        if has_audio:
            cmd_compose.extend(["-i", audio_output_path])
        
        cmd_compose.extend([
            "-c:v", "png",  # 투명도 지원 코덱
            "-c:a", "aac",  # 오디오 코덱
            "-shortest", "-y", output_path
        ])
        subprocess.run(cmd_compose, check=True, capture_output=True)
        print(f"작업 완료! 결과 파일: '{output_path}'")

    except Exception as e:
        print(f"작업 중 오류가 발생했습니다: {e}")
    
    finally:
        # --- 7. 임시 폴더 삭제 ---
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"임시 작업 폴더 '{temp_dir}'을(를) 삭제했습니다.")


# --- 코드 실행 ---
input_video = "만년필.mp4"
output_video = "output_feathered_ffmpeg.mov"
border_size = 30

feather_video_edges_with_ffmpeg(input_video, output_video, border_size)