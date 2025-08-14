#!/usr/bin/env python3

from flask import Flask, request, jsonify, send_file
import os
import tempfile
import traceback

from config import MOVIEPY_AVAILABLE, WHISPER_AVAILABLE, PYDUB_AVAILABLE, CAPTACITY_AVAILABLE
from utils import run_cmd
from whisper_service import transcribe_with_whisper
from subtitle_service import create_segments_from_whisper_result, segments_to_srt
from video_service import create_video_with_subtitles_moviepy, create_video_with_subtitles_ffmpeg

app = Flask(__name__)

# Flask Routes
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "message": "Video API is running",
        "ffmpeg_available": run_cmd(['ffmpeg', '-version'], check=False).returncode == 0,
        "features": {
            "moviepy": MOVIEPY_AVAILABLE,
            "whisper": WHISPER_AVAILABLE,
            "pydub": PYDUB_AVAILABLE,
            "captacity": CAPTACITY_AVAILABLE
        }
    })

@app.route('/generate-subtitles', methods=['POST'])
def generate_subtitles():
    """Generate subtitles for audio using Whisper"""
    try:
        if 'audio' not in request.files:
            return jsonify({"error": "Missing audio file"}), 400
        
        audio_file = request.files['audio']
        if not audio_file.filename:
            return jsonify({"error": "No file selected"}), 400
        
        # Save uploaded file
        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        audio_file.save(temp_audio.name)
        temp_audio.close()
        
        try:
            model_name = request.form.get('model', 'base')
            language = request.form.get('language', None)
            max_words = int(request.form.get('max_words', 3))
            
            # Transcribe
            transcription = transcribe_with_whisper(temp_audio.name, model_name, language)
            segments = create_segments_from_whisper_result(transcription, max_words=max_words)
            
            if not segments:
                return jsonify({"error": "Failed to generate subtitle segments"}), 500
            
            # Create SRT
            srt_content = segments_to_srt(segments)
            temp_srt = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.srt', encoding='utf-8')
            temp_srt.write(srt_content)
            temp_srt.close()
            
            return send_file(temp_srt.name, as_attachment=True, download_name='subtitles.srt', mimetype='text/plain')
            
        finally:
            # Cleanup
            for temp_path in [temp_audio.name, temp_srt.name if 'temp_srt' in locals() else None]:
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
                        
    except Exception as e:
        print(f"Subtitle generation error: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/generate-video-with-synced-subtitles', methods=['POST'])
def generate_video_with_synced_subtitles():
    """Generate video with perfectly synchronized subtitles, BGM and CTA using Whisper"""
    try:
        if 'video' not in request.files or 'audio' not in request.files:
            return jsonify({"error": "Missing video or audio file"}), 400
        
        # Save uploaded files
        video_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        audio_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        
        request.files['video'].save(video_temp.name)
        request.files['audio'].save(audio_temp.name)
        video_temp.close()
        audio_temp.close()
        
        # Save optional BGM and CTA files
        bgm_temp = None
        cta_temp = None
        
        if 'bgm' in request.files and request.files['bgm'].filename:
            bgm_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            request.files['bgm'].save(bgm_temp.name)
            bgm_temp.close()
            print(f"🎵 BGM file uploaded: {bgm_temp.name}")
        else:
            # Use default BGM if available
            default_bgm = os.path.join('TEST', 'BGM.mp3')
            if os.path.exists(default_bgm):
                bgm_temp = type('temp', (), {'name': default_bgm})()
                print(f"🎵 Using default BGM: {default_bgm}")
        
        if 'cta' in request.files and request.files['cta'].filename:
            cta_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            request.files['cta'].save(cta_temp.name)
            cta_temp.close()
            print(f"📢 CTA file uploaded: {cta_temp.name}")
        else:
            # Use default CTA if available
            default_cta = os.path.join('TEST', 'CTA.mp3')
            if os.path.exists(default_cta):
                cta_temp = type('temp', (), {'name': default_cta})()
                print(f"📢 Using default CTA: {default_cta}")
        
        try:
            # Get parameters
            model_name = request.form.get('model', 'base')
            bgm_volume = float(request.form.get('bgm_volume', 0.3))  # BGM volume
            cta_volume = float(request.form.get('cta_volume', 0.8))  # CTA volume
            language = request.form.get('language', None)
            max_words = int(request.form.get('max_words', 3))
            use_moviepy = request.form.get('use_moviepy', 'false').lower() == 'true'
            
            # Transcribe
            print("🎤 Transcribing audio with Whisper...")
            transcription = transcribe_with_whisper(audio_temp.name, model_name, language)
            segments = create_segments_from_whisper_result(transcription, max_words=max_words)
            
            if not segments:
                return jsonify({"error": "Failed to generate subtitle segments"}), 500
            
            # Create video with BGM and CTA
            print(f"🎬 Creating video with {'MoviePy' if use_moviepy else 'FFmpeg'}...")
            
            bgm_path = bgm_temp.name if bgm_temp else None
            cta_path = cta_temp.name if cta_temp else None
            
            if use_moviepy and MOVIEPY_AVAILABLE:
                output_path = create_video_with_subtitles_moviepy(
                    video_temp.name, audio_temp.name, segments, 
                    bgm_path=bgm_path, cta_path=cta_path, 
                    bgm_volume=bgm_volume, cta_volume=cta_volume
                )
            else:
                output_path = create_video_with_subtitles_ffmpeg(
                    video_temp.name, audio_temp.name, segments,
                    bgm_path=bgm_path, cta_path=cta_path,
                    bgm_volume=bgm_volume, cta_volume=cta_volume
                )
            
            if not output_path or not os.path.exists(output_path):
                return jsonify({"error": "Video creation failed"}), 500
            
            return send_file(output_path, as_attachment=True, 
                           download_name='video_with_synced_subtitles.mp4', mimetype='video/mp4')
            
        finally:
            # Cleanup
            temp_files = [video_temp.name, audio_temp.name]
            if bgm_temp and hasattr(bgm_temp, 'name') and bgm_temp.name != os.path.join('TEST', 'BGM.mp3'):
                temp_files.append(bgm_temp.name)
            if cta_temp and hasattr(cta_temp, 'name') and cta_temp.name != os.path.join('TEST', 'CTA.mp3'):
                temp_files.append(cta_temp.name)
            if 'output_path' in locals() and output_path:
                temp_files.append(output_path)
            
            for temp_file in temp_files:
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.unlink(temp_file)
                    except:
                        pass
                        
    except Exception as e:
        print(f"Video generation error: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/transcribe-whisper', methods=['POST'])
def transcribe_whisper_endpoint():
    """Direct Whisper transcription endpoint"""
    try:
        if 'audio' not in request.files:
            return jsonify({"error": "Missing audio file"}), 400
        
        audio_file = request.files['audio']
        if not audio_file.filename:
            return jsonify({"error": "No file selected"}), 400
        
        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        audio_file.save(temp_audio.name)
        temp_audio.close()
        
        try:
            model_name = request.form.get('model', 'base')
            language = request.form.get('language', None)
            task = request.form.get('task', 'transcribe')
            
            result = transcribe_with_whisper(temp_audio.name, model_name, language, task)
            
            if result:
                return jsonify({
                    "success": True,
                    "transcription": result,
                    "model_used": model_name,
                    "language": result.get('language', 'unknown') if isinstance(result, dict) else 'unknown'
                })
            else:
                return jsonify({"error": "Transcription failed"}), 500
                
        finally:
            if os.path.exists(temp_audio.name):
                try:
                    os.unlink(temp_audio.name)
                except:
                    pass
                    
    except Exception as e:
        print(f"Whisper transcription error: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("🚀 Enhanced Video API with MoviePy 2.2.1 Compatibility")
    print("📝 Endpoints: /health, /generate-subtitles, /generate-video-with-synced-subtitles, /transcribe-whisper")
    print("🎯 Features: Whisper transcription, MoviePy & FFmpeg video processing, Perfect subtitle sync")
    print("🔧 Compatible with MoviePy 2.2.1 and Python 3.13")
    
    port = 5009
    print(f"🌐 Server starting at: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
