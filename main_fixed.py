#!/usr/bin/env python3

# Suppress common deprecation warnings for cleaner output
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message="pkg_resources is deprecated")
warnings.filterwarnings("ignore", message=".*audioop.*", category=DeprecationWarning)

from flask import Flask, request, jsonify, send_file
import requests
import os
import tempfile
import subprocess
import shutil
import json
import traceback
import uuid
import re
import sys
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Remove local moviepy directory from Python's search path
if os.path.dirname(os.path.abspath(__file__)) in sys.path:
    sys.path.remove(os.path.dirname(os.path.abspath(__file__)))

# Import MoviePy components with better error handling
try:
    from moviepy.editor import (
        VideoFileClip, AudioFileClip, TextClip, 
        CompositeVideoClip, concatenate_audioclips,
        ColorClip
    )
    MOVIEPY_AVAILABLE = True
    print("✅ MoviePy imported successfully")
except ImportError as e:
    print(f"❌ MoviePy import failed: {e}")
    MOVIEPY_AVAILABLE = False

# Python 3.13 audioop compatibility
sys.path.insert(0, '.')
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    try:
        import audioop
        print("✅ Using system audioop module")
    except ImportError:
        try:
            import audioop_compat_clean as audioop_compat
            sys.modules['audioop'] = audioop_compat
            print("✅ Using audioop compatibility layer (from audioop_compat_clean)")
        except ImportError:
            try:
                import audioop_compat
                sys.modules['audioop'] = audioop_compat
                print("✅ Using audioop compatibility layer (from audioop_compat)")
            except ImportError:
                print("⚠️ No audioop compatibility layer available")

# OpenAI Whisper import (using faster-whisper)
try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
    print("✅ Faster-Whisper available")
except ImportError:
    WHISPER_AVAILABLE = False
    WhisperModel = None
    print("⚠️ Faster-Whisper not available, falling back to A4F API")

# Optional imports with better error handling
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
    print("✅ Pydub available")
except ImportError:
    PYDUB_AVAILABLE = False
    AudioSegment = None
    print("⚠️ Pydub not available")

# Captacity import with multiple fallback strategies
CAPTACITY_AVAILABLE = False
try:
    captacity_path = os.path.join(os.path.dirname(__file__), 'captacity')
    if os.path.exists(captacity_path):
        sys.path.insert(0, captacity_path)
    from captacity import add_captions
    CAPTACITY_AVAILABLE = True
    print("✅ Captacity available (MoviePy 2.x compatible)")
except ImportError as e:
    print(f"⚠️ Captacity import error: {e}")
    try:
        from captacity.captacity import add_captions
        CAPTACITY_AVAILABLE = True
        print("✅ Captacity available (fallback import)")
    except ImportError:
        try:
            # Alternative import method
            import captacity as cap
            add_captions = cap.add_captions
            CAPTACITY_AVAILABLE = True
            print("✅ Captacity available (alternative import)")
        except ImportError:
            CAPTACITY_AVAILABLE = False
            add_captions = None
            print("❌ Captacity not available")

app = Flask(__name__)

# Global Whisper model for efficiency
WHISPER_MODEL = None
WHISPER_MODEL_NAME = "base"

# API Configuration (fallback)
A4F_API_KEY = "ddc-a4f-cc235b79cf914f809db73076609704cc"
A4F_API_URL = "https://api.a4f.co/v1/audio/transcriptions"

SUBTITLE_SIZE_MULTIPLIER = 0.7  # Global size reduction factor

def load_whisper_model(model_name="base"):
    """Load Whisper model once and reuse for efficiency"""
    global WHISPER_MODEL, WHISPER_MODEL_NAME
    if not WHISPER_AVAILABLE:
        return None
    if WHISPER_MODEL is None or WHISPER_MODEL_NAME != model_name:
        print(f"🤖 Loading Faster-Whisper model: {model_name}")
        try:
            WHISPER_MODEL = WhisperModel(model_name, device="cpu", compute_type="int8")
            WHISPER_MODEL_NAME = model_name
            print(f"✅ Faster-Whisper {model_name} model loaded successfully")
            return WHISPER_MODEL
        except Exception as e:
            print(f"❌ Failed to load Faster-Whisper model {model_name}: {e}")
            if model_name != "base":
                print("🔄 Falling back to base model...")
                try:
                    WHISPER_MODEL = WhisperModel("base", device="cpu", compute_type="int8")
                    WHISPER_MODEL_NAME = "base"
                    return WHISPER_MODEL
                except Exception as fallback_error:
                    print(f"❌ Fallback to base model also failed: {fallback_error}")
                    return None
            return None
    return WHISPER_MODEL

def get_ffmpeg_font():
    """Get available font for FFmpeg with fallbacks."""
    # Updated font list with more common system fonts
    default_fonts = [
        "Arial", "Helvetica", "DejaVu Sans", "Liberation Sans", 
        "Ubuntu", "Roboto", "Times New Roman", "Verdana", 
        "Tahoma", "Calibri", "Georgia"
    ]
    
    for font in default_fonts:
        test_cmd = [
            'ffmpeg', '-y', '-v', 'quiet',
            '-f', 'lavfi', '-i', 'color=c=black:s=320x240:d=0.1',
            '-vf', f"drawtext=text='Test':font='{font}':fontsize=20:fontcolor=white:x=10:y=10",
            '-frames:v', '1', '-f', 'null', '-'
        ]
        result = run_cmd(test_cmd, check=False)
        if result.returncode == 0:
            print(f"✅ FFmpeg font '{font}' is available")
            return font
    
    # Fallback to system default
    print("⚠️ No suitable FFmpeg font found, using system default")
    return "Arial"  # This will fallback to system default if not found

def get_available_font():
    """Find an available font with robust fallbacks for MoviePy TextClip."""
    if not MOVIEPY_AVAILABLE:
        return "Arial"
        
    # Extended font list with better coverage
    default_fonts = [
        "Arial", "Helvetica", "DejaVu Sans", "Liberation Sans", 
        "Ubuntu", "Roboto", "Times New Roman", "Verdana", 
        "Tahoma", "Calibri", "Georgia", "Open Sans"
    ]
    
    for font in default_fonts:
        try:
            # Test with a minimal TextClip
            test_clip = TextClip("T", font=font, fontsize=20, color='white')
            if hasattr(test_clip, 'size') and test_clip.size:
                test_clip.close()
                print(f"✅ Font '{font}' is available for TextClip")
                return font
            test_clip.close()
        except Exception as e:
            print(f"⚠️ Font '{font}' test failed: {e}")
            continue
    
    # Try system fonts using matplotlib if available
    try:
        import matplotlib.font_manager as fm
        system_fonts = [f.name for f in fm.fontManager.ttflist]
        common_system_fonts = [font for font in system_fonts if any(
            common in font.lower() for common in ['arial', 'helvetica', 'sans', 'ubuntu', 'roboto']
        )]
        
        for font in common_system_fonts[:10]:  # Try top 10 matches
            try:
                test_clip = TextClip("T", font=font, fontsize=20, color='white')
                if hasattr(test_clip, 'size') and test_clip.size:
                    test_clip.close()
                    print(f"✅ System font '{font}' is available")
                    return font
                test_clip.close()
            except Exception:
                continue
    except ImportError:
        print("⚠️ Matplotlib not available for font detection")
    
    # Final fallback - return None to use MoviePy default
    print("⚠️ Using MoviePy default font")
    return None

def run_cmd(cmd, check=True):
    """Run subprocess command with error handling"""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=check)
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {' '.join(cmd)}\nError: {e.stderr}")
        return e
    except FileNotFoundError as e:
        print(f"Command not found: {' '.join(cmd)}\nError: {e}")
        return subprocess.CompletedProcess(cmd, 127, '', str(e))

def calculate_optimal_font_size(video_width, video_height, text_length):
    """Calculate optimal font size based on video dimensions and text length - optimized for small, clean subtitles"""
    base_size = min(video_width, video_height) // 80  # Much smaller base for clean subtitles
    if text_length < 10:
        multiplier = 0.5  # Small multipliers for clean look
    elif text_length < 20:
        multiplier = 0.4
    elif text_length < 30:
        multiplier = 0.3
    else:
        multiplier = 0.25
    
    # Small bounds for clean, readable subtitles that don't dominate the screen
    optimal_size = max(10, min(20, int(base_size * multiplier)))  # Range: 10-20px for clean subtitles
    return optimal_size

def calculate_subtitle_position(video_width, video_height, text_height):
    """Calculate smart positioning with bounds checking"""
    bottom_margin = max(60, int(video_height * 0.12))
    y_position = video_height - text_height - bottom_margin
    max_y = int(video_height * 0.85)
    y_position = min(y_position, max_y)
    return ('center', y_position)

def safe_load_video(path):
    """Safely load video with multiple fallback attempts and frame access validation"""
    if not MOVIEPY_AVAILABLE:
        raise Exception("MoviePy not available")
        
    for attempt in range(3):
        try:
            if attempt == 0:
                # Standard load
                video = VideoFileClip(path)
            elif attempt == 1:
                # Try fixing with FFmpeg first
                fixed_path = f'{path}_fixed.mp4'
                result = run_cmd(['ffmpeg', '-i', path, '-c', 'copy', fixed_path, '-y'], check=False)
                if result.returncode == 0 and os.path.exists(fixed_path):
                    video = VideoFileClip(fixed_path)
                else:
                    continue
            else:
                # Load without audio as last resort
                video = VideoFileClip(path, audio=False)
            
            # Validate video
            if video and hasattr(video, 'duration') and video.duration > 0:
                try:
                    # Test frame access
                    test_frame = video.get_frame(min(0.1, video.duration/2))
                    if test_frame is not None and test_frame.size > 0:
                        print(f"✅ Video loaded successfully on attempt {attempt + 1}")
                        return video
                    else:
                        raise ValueError("Cannot access video frames")
                except Exception as frame_error:
                    print(f"Frame access test failed: {frame_error}")
                    if hasattr(video, 'close'):
                        video.close()
                    continue
        except Exception as e:
            print(f"Video load attempt {attempt+1} failed: {e}")
            if 'video' in locals() and hasattr(video, 'close'):
                video.close()
    
    raise Exception("Failed to load video after all attempts")

def safe_load_audio(path):
    """Safely load audio with fallback methods and frame access validation"""
    if not MOVIEPY_AVAILABLE:
        raise Exception("MoviePy not available")
    
    # First, try to normalize the audio file using FFmpeg for better compatibility
    normalized_path = f"{path}_normalized.wav"
    normalize_cmd = [
        'ffmpeg', '-y', '-i', path,
        '-ar', '48000',    # Standard sample rate
        '-ac', '2',        # Stereo
        '-c:a', 'pcm_s16le',  # Uncompressed audio for better quality
        '-filter:a', 'volume=2.0',  # Boost volume
        normalized_path
    ]
    
    normalize_result = run_cmd(normalize_cmd, check=False)
    audio_to_load = normalized_path if normalize_result.returncode == 0 and os.path.exists(normalized_path) else path
    
    try:
        audio = AudioFileClip(audio_to_load)
        if audio and hasattr(audio, 'duration') and audio.duration > 0:
            try:
                # Test audio frame access
                test_frame = audio.get_frame(min(0.1, audio.duration/2))
                if test_frame is not None:
                    print(f"✅ Audio loaded and validated successfully from {audio_to_load}")
                    return audio
                else:
                    raise ValueError("Cannot access audio frames")
            except Exception as frame_error:
                print(f"Audio frame access failed: {frame_error}")
                if hasattr(audio, 'close'):
                    audio.close()
                raise
        else:
            raise ValueError("Invalid audio duration")
    except Exception as e:
        print(f"AudioFileClip failed: {e}, trying repair...")
        temp_path = f"{path}_repaired.wav"
        result = run_cmd(['ffmpeg', '-i', audio_to_load, '-ar', '44100', '-ac', '2', temp_path, '-y'], check=False)
        if result.returncode == 0 and os.path.exists(temp_path):
            try:
                repaired_audio = AudioFileClip(temp_path)
                test_frame = repaired_audio.get_frame(0)
                if test_frame is not None:
                    print("✅ Audio repaired and loaded successfully")
                    return repaired_audio
                else:
                    if hasattr(repaired_audio, 'close'):
                        repaired_audio.close()
                    raise ValueError("Cannot access repaired audio frames")
            except Exception as repair_error:
                print(f"Repaired audio failed: {repair_error}")
                if 'repaired_audio' in locals() and hasattr(repaired_audio, 'close'):
                    repaired_audio.close()
                raise
        raise Exception(f"Failed to load audio: {e}")

def compress_audio(input_path, max_size_mb=0.5):
    """Compress audio for API compatibility"""
    try:
        # Get audio info first
        probe_cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', input_path]
        probe_result = run_cmd(probe_cmd, check=False)
        
        if probe_result.returncode != 0:
            return input_path
            
        audio_info = json.loads(probe_result.stdout)
        duration = float(audio_info['format']['duration'])
        
        output_path = input_path.replace('.', '_compressed.')
        target_bitrate = max(8, int((max_size_mb * 8 * 1024) / duration))
        
        cmd = [
            'ffmpeg', '-i', input_path, 
            '-b:a', f'{target_bitrate}k', 
            '-ar', '16000',  # Better quality than 8000
            '-ac', '1', 
            output_path, '-y'
        ]
        
        result = run_cmd(cmd, check=False)
        if result.returncode == 0 and os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"✅ Compressed audio: {size_mb:.2f}MB")
            return output_path
    except Exception as e:
        print(f"⚠️ Audio compression failed: {e}")
    
    return input_path

def transcribe_with_whisper(audio_path, model_name="base", language=None, task="transcribe"):
    """Transcribe audio using OpenAI Whisper with real timestamps"""
    if not WHISPER_AVAILABLE:
        print("⚠️ Whisper not available, falling back to A4F API")
        return transcribe_audio_with_a4f(audio_path)
    
    try:
        model = load_whisper_model(model_name)
        if not model:
            print("⚠️ Whisper model loading failed, falling back to A4F API")
            return transcribe_audio_with_a4f(audio_path)
        
        print(f"🎤 Transcribing audio with Whisper {model_name} model...")
        print(f"📁 Audio file: {audio_path}")
        print(f"🌍 Language: {language or 'auto-detect'}")
        print(f"🎯 Task: {task}")
        
        segments, info = model.transcribe(
            audio_path,
            language=language,
            task=task,
            word_timestamps=True,
            vad_filter=True,  # Voice Activity Detection
            vad_parameters=dict(min_silence_duration_ms=500)
        )
        
        print(f"✅ Faster-Whisper transcription completed!")
        print(f"🔤 Detected language: {info.language}")
        
        segment_list = list(segments)
        full_text = " ".join([segment.text for segment in segment_list])
        print(f"📝 Text: {full_text[:100]}...")
        
        result = {
            'text': full_text,
            'language': info.language,
            'segments': []
        }
        
        for segment in segment_list:
            segment_dict = {
                'start': segment.start,
                'end': segment.end,
                'text': segment.text.strip(),
                'words': []
            }
            
            if hasattr(segment, 'words') and segment.words:
                for word in segment.words:
                    segment_dict['words'].append({
                        'word': word.word.strip(),
                        'start': word.start,
                        'end': word.end
                    })
            
            result['segments'].append(segment_dict)
        
        print(f"📊 Generated {len(result['segments'])} segments with timestamps")
        for i, segment in enumerate(result['segments'][:3]):
            start = segment.get('start', 0)
            end = segment.get('end', 0)
            text = segment.get('text', '').strip()
            print(f"  Segment {i+1}: '{text[:50]}...' ({start:.2f}s - {end:.2f}s)")
            words = segment.get('words', [])
            if words:
                print(f"    Words: {len(words)} word-level timestamps available")
        
        return result
        
    except Exception as e:
        print(f"❌ Whisper transcription failed: {e}")
        print("🔄 Falling back to A4F API...")
        return transcribe_audio_with_a4f(audio_path)

def transcribe_audio_with_a4f(audio_path, max_file_size_mb=0.5):
    """Transcribe audio using A4F API (fallback method)"""
    try:
        # Check file size and compress if needed
        size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        if size_mb > max_file_size_mb:
            print(f"📉 Compressing audio: {size_mb:.2f}MB -> target: {max_file_size_mb}MB")
            audio_path = compress_audio(audio_path, max_file_size_mb)
        
        print(f"📤 Uploading to A4F API: {audio_path}")
        with open(audio_path, 'rb') as f:
            response = requests.post(
                A4F_API_URL,
                headers={'Authorization': f'Bearer {A4F_API_KEY}'},
                files={'file': f},
                data={'model': 'provider-3/whisper-1'},
                timeout=120
            )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ A4F API successful! Response keys: {list(result.keys())}")
            print(f"📝 Response type: {type(result)}")
            
            if isinstance(result, dict):
                if 'text' in result:
                    print(f"📄 Text content: '{result['text'][:100]}...'")
                if 'segments' in result:
                    print(f"🎬 Found {len(result['segments'])} segments")
                elif 'words' in result:
                    print(f"🔤 Found {len(result['words'])} words")
                else:
                    print(f"🔍 Other keys: {[k for k in result.keys() if k != 'text']}")
            
            return result
        else:
            print(f"❌ A4F API error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Transcription error: {e}")
        return None

def create_segments_from_whisper_result(whisper_result, max_chars_per_segment=45, max_duration=5.0, max_words=3):
    """Create subtitle segments from Whisper transcription result with real timestamps"""
    if not whisper_result:
        print("❌ No Whisper result provided")
        return []
    
    whisper_segments = whisper_result.get('segments', [])
    if whisper_segments:
        return create_segments_from_whisper_timestamps(whisper_result, max_chars_per_segment, max_duration, max_words)
    else:
        print("⚠️ No segments in result, using text-based timing")
        return create_segments_from_a4f_result(whisper_result, max_chars_per_segment, max_words)

def create_segments_from_whisper_timestamps(whisper_result, max_chars_per_segment=45, max_duration=5.0, max_words=3):
    """Create subtitle segments from Whisper result with real timestamps"""
    whisper_segments = whisper_result.get('segments', [])
    if not whisper_segments:
        print("❌ No segments in Whisper result")
        return []
    
    subtitle_segments = []
    print(f"🎬 Processing {len(whisper_segments)} Whisper segments...")
    
    for i, segment in enumerate(whisper_segments):
        start_time = segment.get('start', 0)
        end_time = segment.get('end', start_time + 3)
        text = segment.get('text', '').strip()
        
        if not text:
            continue
        
        words = segment.get('words', [])
        if words and len(words) > 0:
            # Use word-level timestamps for better accuracy
            sub_segments = split_segment_by_words(words, max_chars_per_segment, max_duration, max_words)
            subtitle_segments.extend(sub_segments)
        else:
            # Fallback to sentence-level splitting
            sub_segments = split_long_segment(text, start_time, end_time, max_chars_per_segment, max_words)
            subtitle_segments.extend(sub_segments)
    
    print(f"✅ Created {len(subtitle_segments)} subtitle segments from Whisper timestamps")
    for i, seg in enumerate(subtitle_segments[:3]):
        duration = seg['end'] - seg['start']
        print(f"  Segment {i+1}: '{seg['text'][:40]}...' ({seg['start']:.2f}s-{seg['end']:.2f}s, {duration:.2f}s)")
    
    return subtitle_segments

def split_segment_by_words(words, max_chars, max_duration, max_words=3):
    """Split segment using word-level timestamps"""
    segments = []
    current_text = ""
    current_start = None
    current_end = None
    word_count = 0
    
    for word_data in words:
        word = word_data.get('word', '').strip()
        word_start = word_data.get('start', 0)
        word_end = word_data.get('end', word_start + 0.5)
        
        if not word:
            continue
        
        if current_start is None:
            current_start = word_start
            current_text = word
            current_end = word_end
            word_count = 1
            continue
        
        test_text = current_text + " " + word
        test_duration = word_end - current_start
        
        # Check if we should end current segment
        should_end = (
            word_count >= max_words or 
            len(test_text) > max_chars or 
            test_duration > max_duration
        )
        
        if should_end:
            if current_text.strip():
                segments.append({
                    'start': current_start,
                    'end': current_end,
                    'text': current_text.strip()
                })
            # Start new segment
            current_start = word_start
            current_text = word
            current_end = word_end
            word_count = 1
        else:
            # Continue current segment
            current_text = test_text
            current_end = word_end
            word_count += 1
    
    # Add final segment
    if current_text.strip():
        segments.append({
            'start': current_start,
            'end': current_end,
            'text': current_text.strip()
        })
    
    return segments

def split_long_segment(text, start_time, end_time, max_chars, max_words=3):
    """Split a long text segment into smaller parts with proportional timing"""
    segments = []
    words = text.split()
    
    if not words:
        return []
    
    total_duration = end_time - start_time
    total_words = len(words)
    current_words = []
    word_count = 0
    words_processed = 0
    
    for i, word in enumerate(words):
        if word_count < max_words:
            current_words.append(word)
            word_count += 1
        else:
            # Calculate timing for current segment
            segment_text = ' '.join(current_words)
            segment_duration = (len(current_words) / total_words) * total_duration
            segment_start = start_time + (words_processed / total_words) * total_duration
            segment_end = segment_start + segment_duration
            
            segments.append({
                'start': segment_start,
                'end': segment_end,
                'text': segment_text
            })
            
            words_processed += len(current_words)
            current_words = [word]
            word_count = 1
    
    # Handle remaining words
    if current_words:
        segment_text = ' '.join(current_words)
        segment_start = start_time + (words_processed / total_words) * total_duration
        segments.append({
            'start': segment_start,
            'end': end_time,
            'text': segment_text
        })
    
    return segments

def create_segments_from_a4f_result(transcription_result, max_chars_per_segment=45, max_words=3):
    """Create subtitle segments from A4F API result"""
    try:
        segments = []
        if not transcription_result:
            print("❌ No transcription result provided")
            return []
        
        full_text = transcription_result.get('text', '').strip()
        if not full_text:
            print("❌ No text found in response")
            return []
        
        print(f"📝 Creating intelligent subtitle segments from text: '{full_text[:100]}...'")
        words = full_text.split()
        
        if not words:
            return [{
                'start': 0,
                'end': 10,
                'text': full_text
            }]
        
        print(f"📄 Split into {len(words)} words")
        
        # Improved timing calculation
        words_per_second = 2.2  # Average speaking rate
        current_time = 0
        current_words = []
        word_count = 0
        
        for i, word in enumerate(words):
            if word_count < max_words:
                current_words.append(word)
                word_count += 1
            else:
                # Create segment from current words
                segment_text = ' '.join(current_words)
                duration = max(1.5, len(current_words) / words_per_second) # Minimum 1.5s
                
                # Add small gap between segments
                if i > 0:
                    current_time += 0.2
                
                start_time = current_time
                end_time = current_time + duration
                
                segments.append({
                    'start': start_time,
                    'end': end_time,
                    'text': segment_text.strip()
                })
                
                current_time = end_time
                current_words = [word]
                word_count = 1
            
            # Handle last segment
            if i == len(words) - 1 and current_words:
                segment_text = ' '.join(current_words)
                duration = max(1.5, len(current_words) / words_per_second)
                
                if i > 0:
                    current_time += 0.2
                
                start_time = current_time
                end_time = current_time + duration
                
                segments.append({
                    'start': start_time,
                    'end': end_time,
                    'text': segment_text.strip()
                })
        
        print(f"✅ Created {len(segments)} intelligent subtitle segments")
        for i, seg in enumerate(segments[:3]):
            print(f"  Segment {i+1}: '{seg['text'][:40]}...' ({seg['start']:.2f}s - {seg['end']:.2f}s)")
        
        return segments
        
    except Exception as e:
        print(f"❌ Error processing text into segments: {e}")
        traceback.print_exc()
        return []

def segments_to_srt(segments):
    """Convert segments to SRT format with vertical formatting for mobile videos"""
    srt_content = ""
    for i, seg in enumerate(segments, 1):
        start_h, start_r = divmod(seg['start'], 3600)
        start_m, start_s = divmod(start_r, 60)
        start_ms = int((start_s % 1) * 1000)
        
        end_h, end_r = divmod(seg['end'], 3600)
        end_m, end_s = divmod(end_r, 60)
        end_ms = int((end_s % 1) * 1000)
        
        # FORCE vertical text layout - each word on its own line - CAPITALIZED
        original_text = seg['text'].strip().upper()  # Capitalize all text
        words = original_text.split()
        
        # Always create vertical layout for better mobile viewing - CAPITALIZED
        vertical_text = '\n'.join(words)  # Each word on separate line, already capitalized
        
        srt_content += f"{i}\n"
        srt_content += f"{int(start_h):02d}:{int(start_m):02d}:{int(start_s):02d},{start_ms:03d} --> "
        srt_content += f"{int(end_h):02d}:{int(end_m):02d}:{int(end_s):02d},{end_ms:03d}\n"
        srt_content += f"{vertical_text}\n\n"
    
    return srt_content

def create_video_with_subtitles_moviepy(video_path, audio_path, subtitle_segments=None, output_path=None):
    """Create video with audio and MoviePy 2.2.1 compatible subtitles"""
    if not MOVIEPY_AVAILABLE:
        raise Exception("MoviePy not available")
    
    try:
        print("📂 Loading video and audio files...")
        video = safe_load_video(video_path)
        audio = safe_load_audio(audio_path)
        
        video_width = video.w
        video_height = video.h
        print(f"📐 Video dimensions: {video_width}x{video_height}")
        
        # Combine video and audio with improved audio processing
        print("🎵 Combining video and audio...")
        
        # Ensure audio duration matches video or is properly handled
        audio_duration = audio.duration
        video_duration = video.duration
        print(f"📊 Audio: {audio_duration:.2f}s, Video: {video_duration:.2f}s")
        
        # If audio is shorter than video, loop it; if longer, trim it
        if audio_duration < video_duration:
            print("🔄 Looping audio to match video duration")
            loops_needed = int(video_duration / audio_duration) + 1
            audio_clips = [audio] * loops_needed
            audio = concatenate_audioclips(audio_clips).subclip(0, video_duration)
        elif audio_duration > video_duration:
            print("✂️ Trimming audio to match video duration")
            audio = audio.subclip(0, video_duration)
        
        # Ensure audio has proper volume and format
        try:
            # Check if audio has proper volume levels
            if hasattr(audio, 'max_volume'):
                max_vol = audio.max_volume()
                if max_vol < 0.3:  # If audio is too quiet
                    print(f"🔊 Boosting audio volume (current max: {max_vol:.2f})")
                    audio = audio.volumex(3.0)  # Triple the volume for very quiet audio
                elif max_vol < 0.5:
                    print(f"🔊 Boosting audio volume (current max: {max_vol:.2f})")
                    audio = audio.volumex(2.0)  # Double the volume
        except Exception as vol_error:
            print(f"⚠️ Volume adjustment failed: {vol_error}, using original audio")
        
        video_with_audio = video.set_audio(audio)
        
        # Ensure durations match
        video_duration = video.duration
        audio_duration = audio.duration
        final_duration = min(video_duration, audio_duration)
        
        print(f"📊 Durations - Video: {video_duration:.2f}s, Audio: {audio_duration:.2f}s, Final: {final_duration:.2f}s")
        
        if video_duration > final_duration:
            print(f"🎬 Trimming video to {final_duration:.2f}s")
            video_with_audio = video_with_audio.subclip(0, final_duration)
        
        if subtitle_segments:
            print(f"📝 Creating {len(subtitle_segments)} subtitle clips...")
            subtitle_clips = []
            font_choice = get_available_font()
            
            for i, seg in enumerate(subtitle_segments):
                try:
                    text = seg['text'].strip()
                    if not text:
                        continue
                    
                    # Validate timing
                    if seg['start'] >= final_duration:
                        continue
                    
                    actual_end = min(seg['end'], final_duration)
                    actual_duration = actual_end - seg['start']
                    
                    if actual_duration <= 0:
                        continue
                    
                    # Calculate smaller font size for clean vertical subtitle layout
                    text_length = len(text)
                    base_font_size = calculate_optimal_font_size(video_width, video_height, text_length)
                    font_size = int(base_font_size * 0.5)  # Much smaller for cleaner look
                    font_size = max(12, min(font_size, 24))  # Smaller bounds (12-24px) for clear visibility
                    
                    # FORCE vertical layout - each word on its own line for vertical videos
                    words = text.split()
                    if video_height > video_width:  # Vertical video detected
                        # Create true vertical subtitle layout (each word on separate line) - CAPITALIZED
                        vertical_text = '\n'.join([word.upper() for word in words])  # Capitalize each word
                        max_subtitle_width = int(video_width * 0.8)  # 80% of width for smaller footprint
                        max_subtitle_height = int(video_height * 0.25)  # Max 25% of height
                        print(f"🔄 Converting to CAPITALIZED vertical layout: '{text}' -> '{vertical_text.replace(chr(10), ' | ')}'")
                    else:
                        # Horizontal layout for landscape videos - CAPITALIZED
                        vertical_text = text.upper()  # Capitalize the text
                        max_subtitle_width = int(video_width * 0.9)
                        max_subtitle_height = int(video_height * 0.12)
                    
                    txt_clip = TextClip(
                        vertical_text,
                        font=font_choice,
                        fontsize=font_size,
                        color='white',
                        stroke_color='black',
                        stroke_width=1,  # Thinner stroke for smaller text
                        size=(max_subtitle_width, max_subtitle_height),
                        method='caption',
                        align='center',  # Center each line
                        interline=-8    # Tighter line spacing for compact vertical layout
                    )
                    
                    # Ensure subtitle clip fits within video bounds
                    actual_width = min(txt_clip.w, max_subtitle_width)
                    actual_height = min(txt_clip.h, max_subtitle_height)
                    
                    # Position subtitle in center horizontally and MUCH LOWER vertically
                    x_pos = (video_width - actual_width) // 2  # Center horizontally
                    margin_bottom = int(video_height * 0.03)  # Only 3% from bottom (much lower)
                    y_pos = video_height - actual_height - margin_bottom
                    
                    # Ensure y_pos doesn't go too high up the screen but allow it to be very low
                    y_pos = max(int(video_height * 0.8), min(y_pos, video_height - actual_height - 10))
                    
                    # Apply timing and positioning - use absolute positioning for better control
                    txt_clip = txt_clip.set_position((x_pos, y_pos)).set_start(seg['start']).set_duration(actual_duration)
                    subtitle_clips.append(txt_clip)
                    
                    print(f"✅ Subtitle {i+1}: '{text[:30]}...' ({seg['start']:.2f}s-{actual_end:.2f}s) pos:({x_pos},{y_pos}) size:({actual_width}x{actual_height})")
                    
                except Exception as subtitle_error:
                    print(f"❌ Subtitle {i+1} failed: {subtitle_error}")
                    continue
            
            if subtitle_clips:
                print(f"✅ Created {len(subtitle_clips)} subtitle clips")
                final_video = CompositeVideoClip([video_with_audio] + subtitle_clips)
            else:
                print("⚠️ No subtitle clips created, using video without subtitles")
                final_video = video_with_audio
        else:
            print("ℹ️ No subtitle segments provided")
            final_video = video_with_audio
        
        # Set output path
        if not output_path:
            output_path = f"output_moviepy_{uuid.uuid4().hex[:8]}.mp4"
        
        print(f"🎬 Writing final video to {output_path}...")
        final_video.write_videofile(
            output_path,
            fps=24,
            codec='libx264',
            audio_codec='aac',
            audio_bitrate='192k',  # High quality audio bitrate as per your requirement
            audio_fps=48000,       # 48kHz audio sample rate
            verbose=False,
            logger=None,
            temp_audiofile='temp-audio.wav',  # Use temporary audio file for better quality
            remove_temp=True
        )
        
        # Cleanup
        video.close()
        audio.close()
        final_video.close()
        if subtitle_clips:
            for clip in subtitle_clips:
                clip.close()
        
        print(f"✅ Video created successfully: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"❌ Video creation error: {e}")
        traceback.print_exc()
        return None

def create_video_with_subtitles_ffmpeg(video_path, audio_path, subtitle_segments=None, output_path=None):
    """Create video using FFmpeg with burned-in subtitles for maximum compatibility"""
    try:
        if not output_path:
            output_path = f"output_ffmpeg_{uuid.uuid4().hex[:8]}.mp4"
        
        if not subtitle_segments:
            # Simple video + audio combination with explicit stream mapping
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', audio_path,
                '-map', '0:v:0',    # Map first video stream from first input
                '-map', '1:a:0',    # Map first audio stream from second input
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-ar', '48000',
                '-b:a', '192k',
                '-ac', '2',
                '-shortest',
                output_path
            ]
        else:
            # Create SRT file
            srt_content = segments_to_srt(subtitle_segments)
            srt_temp = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.srt', encoding='utf-8')
            srt_temp.write(srt_content)
            srt_temp.close()
            
            # Get video info for font sizing
            probe_cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', video_path]
            probe_result = run_cmd(probe_cmd, check=False)
            
            if probe_result.returncode == 0:
                video_info = json.loads(probe_result.stdout)
                video_stream = next((s for s in video_info['streams'] if s['codec_type'] == 'video'), None)
                
                if video_stream:
                    video_width = int(video_stream['width'])
                    video_height = int(video_stream['height'])
                    
                    # Detect if it's a vertical video and adjust font sizing accordingly
                    is_vertical = video_height > video_width
                    if is_vertical:
                        optimal_font_size = max(14, int(video_width * 0.04))  # Smaller font for cleaner vertical videos
                        margin_v = max(40, int(video_height * 0.05))  # Much smaller bottom margin (lower position)
                        margin_lr = max(30, int(video_width * 0.08))  # Side margins
                    else:
                        optimal_font_size = max(12, int(video_height * 0.025))  # Smaller for horizontal
                        margin_v = max(30, int(video_height * 0.05))  # Lower position for horizontal too
                        margin_lr = max(80, int(video_width * 0.15))
                else:
                    optimal_font_size = 16  # Default size
                    margin_v = 80
                    margin_lr = 60
            else:
                optimal_font_size = 24  # Reduced from 32
                margin_v = 100
                margin_lr = 50
            
            ffmpeg_font = get_ffmpeg_font()
            
            # FFmpeg command with subtitle burning optimized for vertical videos
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', audio_path,
                '-map', '0:v:0',    # Explicitly map video from first input
                '-map', '1:a:0',    # Explicitly map audio from second input
                '-vf', f"subtitles={srt_temp.name}:force_style='FontName={ffmpeg_font},FontSize={optimal_font_size},PrimaryColour=&Hffffff,OutlineColour=&H000000,Outline=2,BackColour=&H80000000,BorderStyle=1,Alignment=2,MarginV={margin_v},MarginL={margin_lr},MarginR={margin_lr},Bold=1,WrapStyle=2,Spacing=2'",
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-ar', '48000',  # 48kHz audio sample rate as per your requirement
                '-b:a', '192k',  # 192k audio bitrate for high quality
                '-ac', '2',      # Stereo audio (2 channels)
                '-preset', 'medium',
                '-crf', '23',
                '-shortest',
                output_path
            ]
        
        print(f"🎬 Running FFmpeg: {' '.join(cmd[:10])}...")
        result = run_cmd(cmd, check=False)
        
        # Cleanup
        if 'srt_temp' in locals():
            try:
                os.unlink(srt_temp.name)
            except:
                pass
        
        if result.returncode == 0:
            print(f"✅ FFmpeg video created successfully: {output_path}")
            
            # Additional audio processing for better compatibility
            final_output = output_path.replace('.mp4', '_qt_safe.mp4')
            audio_fix_cmd = [
                'ffmpeg', '-y',
                '-i', output_path,
                '-c:v', 'copy',  # Copy video without re-encoding
                '-c:a', 'aac',
                '-ar', '48000',  # 48kHz as per your requirement
                '-b:a', '192k',  # 192k bitrate for high quality
                '-ac', '2',      # Stereo
                final_output
            ]
            
            print("🔧 Post-processing audio for better compatibility...")
            audio_result = run_cmd(audio_fix_cmd, check=False)
            
            if audio_result.returncode == 0 and os.path.exists(final_output):
                print(f"✅ Audio post-processing successful: {final_output}")
                # Replace original with audio-fixed version
                try:
                    os.remove(output_path)
                    os.rename(final_output, output_path)
                    print(f"✅ Replaced with audio-optimized version")
                except Exception as rename_error:
                    print(f"⚠️ Could not replace original: {rename_error}")
                    return final_output
            else:
                print(f"⚠️ Audio post-processing failed, using original")
            
            return output_path
        else:
            print(f"❌ FFmpeg failed: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"❌ FFmpeg video creation error: {e}")
        traceback.print_exc()
        return None

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
    """Generate video with perfectly synchronized subtitles using Whisper"""
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
        
        try:
            # Get parameters
            model_name = request.form.get('model', 'base')
            language = request.form.get('language', None)
            max_words = int(request.form.get('max_words', 3))
            use_moviepy = request.form.get('use_moviepy', 'false').lower() == 'true'
            
            # Transcribe
            print("🎤 Transcribing audio with Whisper...")
            transcription = transcribe_with_whisper(audio_temp.name, model_name, language)
            segments = create_segments_from_whisper_result(transcription, max_words=max_words)
            
            if not segments:
                return jsonify({"error": "Failed to generate subtitle segments"}), 500
            
            # Create video
            print(f"🎬 Creating video with {'MoviePy' if use_moviepy else 'FFmpeg'}...")
            
            if use_moviepy and MOVIEPY_AVAILABLE:
                output_path = create_video_with_subtitles_moviepy(video_temp.name, audio_temp.name, segments)
            else:
                output_path = create_video_with_subtitles_ffmpeg(video_temp.name, audio_temp.name, segments)
            
            if not output_path or not os.path.exists(output_path):
                return jsonify({"error": "Video creation failed"}), 500
            
            return send_file(output_path, as_attachment=True, 
                           download_name='video_with_synced_subtitles.mp4', mimetype='video/mp4')
            
        finally:
            # Cleanup
            temp_files = [video_temp.name, audio_temp.name]
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
