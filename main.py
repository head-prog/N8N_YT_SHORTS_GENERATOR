#!/usr/bin/env python3

# Suppress common deprecation warnings for cleaner output
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message="pkg_resources is deprecated")
warnings.filterwarnings("ignore", message=".*audioop.*", category=DeprecationWarning)

from flask import Flask, request, jsonify, send_file
import requests, os, tempfile, subprocess, shutil, json, traceback, uuid, re, sys, time

# Remove local moviepy directory from Python's search path
if os.path.dirname(os.path.abspath(__file__)) in sys.path:
    sys.path.remove(os.path.dirname(os.path.abspath(__file__)))

# Import MoviePy components from installed package
from moviepy import (
    VideoFileClip, AudioFileClip, TextClip, 
    CompositeVideoClip, CompositeAudioClip, concatenate_audioclips
)

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

# Optional imports
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    AudioSegment = None

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
                WHISPER_MODEL = WhisperModel("base", device="cpu", compute_type="int8")
                WHISPER_MODEL_NAME = "base"
                return WHISPER_MODEL
            raise
    return WHISPER_MODEL

def get_ffmpeg_font():
    """Get available font for FFmpeg with fallbacks."""
    default_fonts = ["Arial", "Helvetica", "DejaVu Sans", "Liberation Sans", "Times New Roman"]
    for font in default_fonts:
        test_cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi', '-i', 'color=c=black:s=320x240',
            '-vf', f"drawtext=text='Test':fontfile='{font}':fontsize=20",
            '-frames:v', '1', '-f', 'null', '-'
        ]
        result = run_cmd(test_cmd, check=False)
        if result.returncode == 0:
            print(f"✅ FFmpeg font '{font}' is available")
            return font
    print("⚠️ No suitable FFmpeg font found, using Arial")
    return "Arial"

def get_available_font():
    """Find an available font with robust fallbacks."""
    default_fonts = ["Helvetica", "Arial", "DejaVu Sans", "Liberation Sans", "Times New Roman"]
    for font in default_fonts:
        try:
            test_clip = TextClip("test", font=font, font_size=20, color='white')
            test_clip.close()
            print(f"✅ Font '{font}' is available")
            return font
        except:
            continue
    try:
        import matplotlib.font_manager as fm
        system_fonts = [f.name for f in fm.fontManager.ttflist]
        for font in system_fonts[:10]:
            try:
                test_clip = TextClip("test", font=font, font_size=20, color='white')
                test_clip.close()
                print(f"✅ System font '{font}' is available")
                return font
            except:
                continue
    except ImportError:
        pass
    print("⚠️ No suitable font found, using system default")
    return None

def run_cmd(cmd, check=True):
    """Run subprocess command with error handling"""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=check)
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {' '.join(cmd)}\nError: {e.stderr}")
        return e

def calculate_optimal_font_size(video_width, video_height, text_length):
    """Calculate optimal font size based on video dimensions and text length"""
    base_size = min(video_width, video_height) // 25
    if text_length < 10:
        multiplier = 1.2
    elif text_length < 20:
        multiplier = 1.0
    else:
        multiplier = 0.8
    return max(16, int(base_size * multiplier))

def calculate_subtitle_position(video_width, video_height, text_height):
    """Calculate smart positioning with bounds checking"""
    bottom_margin = max(50, int(video_height * 0.1))
    y_position = video_height - text_height - bottom_margin
    max_y = int(video_height * 0.8)
    y_position = min(y_position, max_y)
    return ('center', y_position)

def safe_load_video(path):
    """Safely load video with multiple fallback attempts and frame access validation"""
    for attempt in range(3):
        try:
            if attempt == 0:
                video = VideoFileClip(path)
            elif attempt == 1:
                result = run_cmd(['ffmpeg', '-i', path, '-c', 'copy', f'{path}_fixed.mp4'])
                if result.returncode == 0:
                    video = VideoFileClip(f'{path}_fixed.mp4')
                else:
                    continue
            else:
                video = VideoFileClip(path, audio=False)
            if video and hasattr(video, 'duration') and video.duration > 0:
                try:
                    test_frame = video.get_frame(0)
                    if test_frame is not None:
                        return video
                    else:
                        raise ValueError("Cannot access video frames")
                except Exception as frame_error:
                    print(f"Frame access test failed: {frame_error}")
                    video.close()
                    continue
        except Exception as e:
            print(f"Video load attempt {attempt+1} failed: {e}")
            if 'video' in locals():
                video.close()
    raise Exception("Failed to load video after all attempts")

def safe_load_audio(path):
    """Safely load audio with fallback methods and frame access validation"""
    try:
        audio = AudioFileClip(path)
        if audio and hasattr(audio, 'duration') and audio.duration > 0:
            try:
                test_frame = audio.get_frame(0)
                if test_frame is not None:
                    return audio
                else:
                    raise ValueError("Cannot access audio frames")
            except Exception as frame_error:
                print(f"Audio frame access failed: {frame_error}")
                audio.close()
                raise
        else:
            raise ValueError("Invalid audio duration")
    except Exception as e:
        print(f"AudioFileClip failed: {e}, trying repair...")
        temp_path = f"{path}_repaired.wav"
        result = run_cmd(['ffmpeg', '-i', path, '-ar', '44100', '-ac', '2', temp_path])
        if result.returncode == 0:
            repaired_audio = AudioFileClip(temp_path)
            try:
                test_frame = repaired_audio.get_frame(0)
                if test_frame is not None:
                    return repaired_audio
                else:
                    repaired_audio.close()
                    raise ValueError("Cannot access repaired audio frames")
            except:
                repaired_audio.close()
                raise
        raise Exception(f"Failed to load audio: {e}")

def compress_audio(input_path, max_size_mb=0.5):
    """Compress audio for API compatibility"""
    output_path = input_path.replace('.', '_compressed.')
    target_bitrate = max(8, int((max_size_mb * 8 * 1024) / (AudioFileClip(input_path).duration)))
    cmd = ['ffmpeg', '-i', input_path, '-b:a', f'{target_bitrate}k', '-ar', '8000', '-ac', '1', output_path, '-y']
    result = run_cmd(cmd, check=False)
    if result.returncode == 0 and os.path.exists(output_path):
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"Compressed audio: {size_mb:.2f}MB")
        return output_path
    return input_path

def transcribe_with_whisper(audio_path, model_name="base", language=None, task="transcribe"):
    """Transcribe audio using OpenAI Whisper with real timestamps"""
    if not WHISPER_AVAILABLE:
        print("⚠️ Whisper not available, falling back to A4F API")
        return transcribe_audio_with_a4f(audio_path)
    try:
        model = load_whisper_model(model_name)
        if not model:
            return transcribe_audio_with_a4f(audio_path)
        print(f"🎤 Transcribing audio with Whisper {model_name} model...")
        print(f"📁 Audio file: {audio_path}")
        print(f"🌍 Language: {language or 'auto-detect'}")
        print(f"🎯 Task: {task}")
        segments, info = model.transcribe(
            audio_path,
            language=language,
            task=task,
            word_timestamps=True
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
                'text': segment.text,
                'words': []
            }
            if hasattr(segment, 'words') and segment.words:
                for word in segment.words:
                    segment_dict['words'].append({
                        'word': word.word,
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
        size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        if size_mb > max_file_size_mb:
            audio_path = compress_audio(audio_path, max_file_size_mb)
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
        if words:
            sub_segments = split_segment_by_words(words, max_chars_per_segment, max_duration, max_words)
            subtitle_segments.extend(sub_segments)
        else:
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
        if word_count >= max_words or len(test_text) > max_chars or test_duration > max_duration:
            if current_text.strip():
                segments.append({
                    'start': current_start,
                    'end': current_end,
                    'text': current_text.strip()
                })
            current_start = word_start
            current_text = word
            current_end = word_end
            word_count = 1
        else:
            current_text = test_text
            current_end = word_end
            word_count += 1
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
    for i, word in enumerate(words):
        if word_count < max_words:
            current_words.append(word)
            word_count += 1
        else:
            segment_text = ' '.join(current_words)
            segment_duration = (len(current_words) / total_words) * total_duration
            segment_end = start_time + segment_duration
            segments.append({
                'start': start_time,
                'end': segment_end,
                'text': segment_text
            })
            start_time = segment_end
            current_words = [word]
            word_count = 1
    if current_words:
        segment_text = ' '.join(current_words)
        segments.append({
            'start': start_time,
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
        words_per_second = 2.2
        current_time = 0
        current_words = []
        word_count = 0
        for i, word in enumerate(words):
            if word_count < max_words:
                current_words.append(word)
                word_count += 1
            else:
                segment_text = ' '.join(current_words)
                duration = max(2.0, len(current_words) / words_per_second)
                if i > 0:
                    current_time += 0.3
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
            if i == len(words) - 1 and current_words:
                segment_text = ' '.join(current_words)
                duration = max(2.0, len(current_words) / words_per_second)
                if i > 0:
                    current_time += 0.3
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

def split_text_into_sentences(text):
    """Split text into natural subtitle segments"""
    import re
    sentences = re.split(r'[.!?]+\s+', text)
    cleaned_sentences = []
    for sentence in sentences:
        sentence = sentence.strip()
        if sentence:
            if len(sentence) > 80:
                sub_parts = re.split(r',\s+|;\s+|\s+but\s+|\s+and\s+|\s+or\s+', sentence)
                for part in sub_parts:
                    part = part.strip()
                    if part and len(part) > 10:
                        cleaned_sentences.append(part)
            else:
                cleaned_sentences.append(sentence)
    return cleaned_sentences

def create_word_level_synchronized_timing(text, duration, speaking_rate=2.5, max_words=3):
    """Create natural speech-synchronized timing"""
    try:
        segments = []
        if not text or not text.strip():
            print("No transcription text provided")
            return []
        full_text = text.strip()
        words = full_text.split()
        total_words = len(words)
        if total_words == 0:
            return []
        print(f"Creating natural speech timing for {total_words} words in {duration}s")
        actual_words_per_second = total_words / duration
        print(f"Actual speaking rate: {actual_words_per_second:.2f} words/second")
        target_segment_duration = 4.0
        words_per_segment = min(max_words, max(1, int(actual_words_per_second * target_segment_duration)))
        print(f"Target: {target_segment_duration}s per segment, ~{words_per_segment} words per segment")
        current_words = []
        current_start_time = 0.0
        word_count = 0
        for i, word in enumerate(words):
            current_words.append(word)
            word_count += 1
            words_so_far = i + 1
            expected_time = (words_so_far / total_words) * duration
            should_end_segment = False
            if word.endswith(('.', '!', '?')):
                should_end_segment = True
            elif word.endswith((',', ';', ':')) and len(current_words) >= 2:
                should_end_segment = True
            elif word_count >= words_per_segment:
                should_end_segment = True
            elif word_count >= 2 and word.lower() in ['and', 'but', 'or', 'so', 'then', 'now', 'when', 'if', 'because']:
                should_end_segment = True
            if expected_time - current_start_time >= target_segment_duration:
                should_end_segment = True
            if should_end_segment or i == len(words) - 1:
                segment_text = ' '.join(current_words)
                segment_end_time = min(expected_time, duration)
                if segment_end_time - current_start_time < 2.0:
                    segment_end_time = min(current_start_time + 2.0, duration)
                segments.append({
                    'start': current_start_time,
                    'end': segment_end_time,
                    'text': segment_text
                })
                current_words = []
                current_start_time = segment_end_time
                word_count = 0
        for i in range(len(segments) - 1):
            if segments[i]['end'] > segments[i + 1]['start']:
                segments[i]['end'] = segments[i + 1]['start']
        print(f"Created {len(segments)} natural speech segments")
        for i, seg in enumerate(segments[:5]):
            duration_seg = seg['end'] - seg['start']
            words_in_seg = len(seg['text'].split())
            print(f"  Segment {i+1}: '{seg['text'][:40]}...' ({seg['start']:.1f}s-{seg['end']:.1f}s, {duration_seg:.1f}s, {words_in_seg} words)")
        return segments
    except Exception as e:
        print(f"Error creating natural speech timing: {e}")
        traceback.print_exc()
        return []

def create_enhanced_subtitle_timing(text, duration, style='natural', max_words=3):
    """Create enhanced subtitle timing with improved synchronization"""
    try:
        segments = []
        if not text or not text.strip():
            print("No transcription text provided")
            return []
        full_text = text.strip()
        print(f"Creating enhanced timing ({style}) for: {full_text[:100]}...")
        if style == 'word_level':
            return create_word_level_synchronized_timing(text, duration, max_words=max_words)
        elif style == 'word_level_old':
            words = full_text.split()
            if words:
                word_duration = duration / len(words)
                current_words = []
                word_count = 0
                for i, word in enumerate(words):
                    if word_count < max_words:
                        current_words.append(word)
                        word_count += 1
                    else:
                        segment_text = ' '.join(current_words)
                        start_time = (i - len(current_words)) * word_duration
                        end_time = min(i * word_duration, duration)
                        segments.append({
                            'start': start_time,
                            'end': end_time,
                            'text': segment_text
                        })
                        current_words = [word]
                        word_count = 1
                if current_words:
                    segment_text = ' '.join(current_words)
                    start_time = (len(words) - len(current_words)) * word_duration
                    end_time = duration
                    segments.append({
                        'start': start_time,
                        'end': end_time,
                        'text': segment_text
                    })
        elif style == 'precise':
            phrases = []
            current_phrase = ""
            words = full_text.split()
            for word in words:
                current_phrase += word + " "
                word_count = len(current_phrase.split())
                if (word.endswith((',', '.', '!', '?', ';')) or 
                    word_count >= max_words or
                    word.lower() in ['and', 'but', 'or', 'so', 'then', 'now']):
                    phrases.append(current_phrase.strip())
                    current_phrase = ""
            if current_phrase.strip():
                phrases.append(current_phrase.strip())
            if phrases:
                phrase_duration = duration / len(phrases)
                for i, phrase in enumerate(phrases):
                    start_time = i * phrase_duration
                    end_time = min(start_time + phrase_duration, duration)
                    segments.append({
                        'start': start_time,
                        'end': end_time,
                        'text': phrase
                    })
        else:
            estimated_words = len(full_text.split())
            natural_segments = max(2, min(10, int(duration / 4)))
            sentences = []
            for delimiter in ['. ', '! ', '? ']:
                full_text = full_text.replace(delimiter, delimiter + '|SPLIT|')
            sentence_parts = [s.strip() for s in full_text.split('|SPLIT|') if s.strip()]
            if len(sentence_parts) > natural_segments:
                grouped_segments = []
                current_group = ""
                words_per_segment = min(max_words, estimated_words / natural_segments)
                for part in sentence_parts:
                    part_words = part.split()
                    for i in range(0, len(part_words), int(words_per_segment)):
                        chunk = ' '.join(part_words[i:i + int(words_per_segment)])
                        if chunk:
                            grouped_segments.append(chunk)
                sentence_parts = grouped_segments
            if sentence_parts:
                segment_duration = duration / len(sentence_parts)
                for i, segment_text in enumerate(sentence_parts):
                    start_time = i * segment_duration
                    end_time = min(start_time + segment_duration, duration)
                    segments.append({
                        'start': start_time,
                        'end': end_time,
                        'text': segment_text.strip()
                    })
            else:
                segments.append({
                    'start': 0,
                    'end': duration,
                    'text': ' '.join(full_text.split()[:max_words])
                })
        print(f"Created {len(segments)} enhanced subtitle segments with {style} timing")
        return segments
    except Exception as e:
        print(f"Error creating enhanced subtitle timing: {e}")
        return []

def add_captacity_subtitles(video_with_audio_path, output_path, openai_api_key=None):
    """Add subtitles using Captacity with YouTube Shorts optimized styling"""
    if not CAPTACITY_AVAILABLE:
        print("Captacity not available, cannot add professional subtitles")
        try:
            shutil.copy(video_with_audio_path, output_path)
            return True
        except:
            return False
    try:
        print("Adding subtitles using Captacity with optimized styling...")
        captacity_options = {
            "video_file": video_with_audio_path,
            "output_file": output_path,
            "font": "Helvetica",
            "font_size": 105,
            "font_color": "white",
            "stroke_width": 3,
            "stroke_color": "black",
            "shadow_strength": 1.0,
            "shadow_blur": 0.2,
            "highlight_current_word": False,
            "line_count": 2,
            "padding": 20,
            "use_local_whisper": True
        }
        if openai_api_key:
            os.environ['OPENAI_API_KEY'] = openai_api_key
            print("OpenAI API key configured for fallback transcription")
        print(f"Captacity options: {captacity_options}")
        add_captions(**captacity_options)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            print(f"Successfully added subtitles using Captacity: {output_path} ({os.path.getsize(output_path)} bytes)")
            return True
        else:
            print("Captacity output file is empty or missing, falling back to copy")
            shutil.copy(video_with_audio_path, output_path)
            return True
    except Exception as e:
        print(f"Error adding Captacity subtitles: {e}")
        if "local" in str(e).lower() or "whisper" in str(e).lower():
            print("Local Whisper failed, trying with OpenAI API...")
            try:
                captacity_fallback_options = {
                    "video_file": video_with_audio_path,
                    "output_file": output_path,
                    "font_size": 105,
                    "font_color": "white",
                    "stroke_width": 3,
                    "stroke_color": "black",
                    "line_count": 2,
                    "padding": 20,
                    "use_local_whisper": False
                }
                add_captions(**captacity_fallback_options)
                if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                    print("Successfully added subtitles using Captacity API fallback")
                    return True
            except Exception as fallback_error:
                print(f"Captacity API fallback also failed: {fallback_error}")
        try:
            shutil.copy(video_with_audio_path, output_path)
            return True
        except:
            return False

def create_synchronized_subtitles(voice_path, cta_path, timing_style='word_level', max_words=3):
    """Create properly synchronized subtitles for voice + CTA sequence"""
    try:
        segments = []
        voice_audio = safe_load_audio(voice_path)
        voice_duration = voice_audio.duration / 1.25  # Adjust for 1.25x speed
        voice_audio.close()
        print(f"📊 Creating synchronized subtitles for voice ({voice_duration}s) + CTA (max {max_words} words per subtitle)")
        voice_transcription = transcribe_with_whisper(voice_path)
        if voice_transcription:
            voice_segments = create_segments_from_whisper_result(voice_transcription, max_words=max_words)
            voice_segments = scale_segments_to_duration(voice_segments, voice_duration)
            for seg in voice_segments:
                seg['start'] = seg['start'] / 1.25
                seg['end'] = seg['end'] / 1.25
                if seg['end'] - seg['start'] < 0.5:
                    seg['end'] = seg['start'] + 0.5
            segments.extend(voice_segments)
            print(f"✅ Created {len(voice_segments)} voice subtitle segments scaled to {voice_duration}s")
        if cta_path and os.path.exists(cta_path):
            cta_audio = safe_load_audio(cta_path)
            cta_duration = cta_audio.duration / 1.25
            cta_audio.close()
            cta_start_time = voice_duration
            print(f"📊 CTA audio: {cta_duration}s, starting at {cta_start_time}s")
            cta_transcription = transcribe_with_whisper(cta_path)
            if cta_transcription:
                cta_segments = create_segments_from_whisper_result(cta_transcription, max_words=max_words)
                cta_segments = scale_segments_to_duration(cta_segments, cta_duration)
                for seg in cta_segments:
                    seg['start'] = (seg['start'] / 1.25) + cta_start_time
                    seg['end'] = (seg['end'] / 1.25) + cta_start_time
                    if seg['end'] - seg['start'] < 0.5:
                        seg['end'] = seg['start'] + 0.5
                segments.extend(cta_segments)
                print(f"✅ Created {len(cta_segments)} CTA subtitle segments, offset by {cta_start_time}s")
            else:
                segments.append({
                    'start': cta_start_time,
                    'end': cta_start_time + cta_duration,
                    'text': '[Call to Action]'
                })
        print(f"📋 Total synchronized subtitle segments: {len(segments)}")
        
        # Ensure all segments are within reasonable bounds
        total_audio_duration = voice_duration
        if cta_path and os.path.exists(cta_path):
            cta_audio = safe_load_audio(cta_path)
            total_audio_duration += cta_audio.duration / 1.25
            cta_audio.close()
        
        # Filter segments to ensure they don't exceed the total duration
        valid_segments = []
        for seg in segments:
            if seg['start'] < total_audio_duration:
                # Trim end time if it exceeds total duration
                if seg['end'] > total_audio_duration:
                    seg['end'] = total_audio_duration
                
                # Only keep segments with valid duration
                if seg['end'] > seg['start']:
                    valid_segments.append(seg)
                    
        print(f"📋 Valid subtitle segments within {total_audio_duration:.2f}s: {len(valid_segments)}")
        return valid_segments
    except Exception as e:
        print(f"❌ Error creating synchronized subtitles: {e}")
        traceback.print_exc()
        return []

def scale_segments_to_duration(segments, target_duration):
    """Scale subtitle segments to match the actual audio duration"""
    if not segments:
        return segments
    last_segment = segments[-1]
    estimated_duration = last_segment['end'] if segments else 0
    if estimated_duration <= 0:
        return segments
    scale_factor = target_duration / estimated_duration
    print(f"📐 Scaling subtitles: {estimated_duration:.2f}s → {target_duration:.2f}s (factor: {scale_factor:.2f})")
    scaled_segments = []
    for segment in segments:
        scaled_segments.append({
            'start': segment['start'] * scale_factor,
            'end': segment['end'] * scale_factor,
            'text': segment['text']
        })
    return scaled_segments

def create_subtitle_segments(transcription, duration, offset=0, max_words=3):
    """Create subtitle segments from transcription"""
    try:
        if transcription and 'text' in transcription:
            return create_enhanced_subtitle_timing(transcription['text'], duration, max_words=max_words)
        num_segments = max(1, int(duration / 6))
        segment_duration = duration / num_segments
        return [{'start': i * segment_duration + offset, 
                'end': min((i + 1) * segment_duration + offset, duration + offset),
                'text': '[Audio content - transcription unavailable]'} 
               for i in range(num_segments)]
    except Exception as e:
        print(f"Error creating segments: {e}")
        return []

def segments_to_srt(segments):
    """Convert segments to SRT format with enhanced formatting"""
    srt_content = ""
    for i, seg in enumerate(segments, 1):
        start_h, start_r = divmod(seg['start'], 3600)
        start_m, start_s = divmod(start_r, 60)
        start_ms = int((start_s % 1) * 1000)
        end_h, end_r = divmod(seg['end'], 3600)
        end_m, end_s = divmod(end_r, 60)
        end_ms = int((end_s % 1) * 1000)
        enhanced_text = seg['text'].upper().strip()
        print(f"📝 SRT Segment {i}: '{enhanced_text}' ({seg['start']:.2f}s-{seg['end']:.2f}s)")
        srt_content += f"{i}\n"
        srt_content += f"{int(start_h):02d}:{int(start_m):02d}:{int(start_s):02d},{start_ms:03d} --> "
        srt_content += f"{int(end_h):02d}:{int(end_m):02d}:{int(end_s):02d},{end_ms:03d}\n"
        srt_content += f"{enhanced_text}\n\n"
    return srt_content

def mix_audio_files(audio_paths, volumes, output_path, target_duration=None):
    """Mix multiple audio files with proper sequential positioning using FFmpeg"""
    try:
        print(f"Mixing audio files: {audio_paths}")
        print(f"Volumes: {volumes}")
        if not audio_paths or len(audio_paths) == 0:
            return False
        voice_audio = safe_load_audio(audio_paths[0])
        voice_duration = voice_audio.duration
        voice_audio.close()
        print(f"Voice duration: {voice_duration}s")
        temp_voice_cta_path = tempfile.NamedTemporaryFile(delete=False, suffix='.wav').name
        if len(audio_paths) > 1 and os.path.exists(audio_paths[1]):
            cta_audio = safe_load_audio(audio_paths[1])
            cta_duration = cta_audio.duration
            cta_audio.close()
            print(f"CTA duration: {cta_duration}s, will start at: {voice_duration}s")
            concat_cmd = [
                'ffmpeg', '-y',
                '-i', audio_paths[0],
                '-i', audio_paths[1],
                '-filter_complex', 
                f'[0]volume={volumes[0]}[v];[1]volume={volumes[1]}[c];[v][c]concat=n=2:v=0:a=1[out]',
                '-map', '[out]',
                '-c:a', 'pcm_s16le',
                '-ar', '44100',
                temp_voice_cta_path
            ]
            print(f"Running voice+CTA concatenation: {' '.join(concat_cmd)}")
            result = run_cmd(concat_cmd, check=False)
            if result.returncode != 0:
                print(f"Voice+CTA concatenation failed: {result.stderr}")
                return False
            voice_cta_duration = voice_duration + cta_duration
        else:
            volume_cmd = [
                'ffmpeg', '-y',
                '-i', audio_paths[0],
                '-filter:a', f'volume={volumes[0]}',
                '-c:a', 'pcm_s16le',
                '-ar', '44100',
                temp_voice_cta_path
            ]
            result = run_cmd(volume_cmd, check=False)
            if result.returncode != 0:
                print(f"Voice volume adjustment failed: {result.stderr}")
                return False
            voice_cta_duration = voice_duration
        print(f"Voice + CTA total duration: {voice_cta_duration}s")
        if len(audio_paths) > 2 and os.path.exists(audio_paths[2]):
            final_duration = target_duration if target_duration else voice_cta_duration
            print(f"Adding BGM, target duration: {final_duration}s")
            bgm_cmd = [
                'ffmpeg', '-y',
                '-i', temp_voice_cta_path,
                '-i', audio_paths[2],
                '-filter_complex',
                f'[0]apad[main];[1]volume={volumes[2]},aloop=loop=-1:size=2e+09[bgm];[main][bgm]amix=inputs=2:duration=first',
                '-t', str(final_duration),
                '-c:a', 'pcm_s16le',
                '-ar', '44100',
                output_path
            ]
            print(f"Running BGM mixing: {' '.join(bgm_cmd)}")
            result = run_cmd(bgm_cmd, check=False)
            if result.returncode != 0:
                print(f"BGM mixing failed: {result.stderr}")
                shutil.copy(temp_voice_cta_path, output_path)
        else:
            shutil.copy(temp_voice_cta_path, output_path)
        if os.path.exists(temp_voice_cta_path):
            os.unlink(temp_voice_cta_path)
        print(f"Successfully mixed audio to: {output_path}")
        return True
    except Exception as e:
        print(f"Audio mixing error: {e}")
        traceback.print_exc()
        return False

def create_video_with_subtitles(video_path, audio_path, subtitle_segments=None, output_path=None):
    """Create video with audio (1.25x speed) and properly centered subtitles"""
    try:
        video = safe_load_video(video_path)
        audio = safe_load_audio(audio_path)
        video_width = video.w
        video_height = video.h
        print(f"📐 Video dimensions: {video_width}x{video_height}")
        temp_audio_path = tempfile.mktemp(suffix='.wav')
        audio.write_audiofile(temp_audio_path, codec='pcm_s16le', logger=None)
        temp_processed_path = tempfile.mktemp(suffix='.wav')
        subprocess.call([
            'ffmpeg', '-y', 
            '-i', temp_audio_path,
            '-filter:a', 'atempo=1.25',
            '-c:a', 'pcm_s16le',
            temp_processed_path
        ])
        audio_speeded = AudioFileClip(temp_processed_path)
        # Simplified approach - just use original video without speed adjustment for now
        print("🎬 Using original video (speed adjustment disabled for compatibility)")
        video_speeded = video
        try:
            os.remove(temp_audio_path)
            os.remove(temp_processed_path)
        except:
            pass
        video_with_audio = video_speeded.with_audio(audio_speeded)
        
        # Check durations first before processing subtitles
        video_duration = video_speeded.duration
        audio_duration = audio_speeded.duration
        final_duration = min(video_duration, audio_duration)  # Use the shorter duration
        
        print(f"📊 Durations - Video: {video_duration:.2f}s, Audio: {audio_duration:.2f}s, Final: {final_duration:.2f}s")
        
        # Trim both video and audio to the shorter duration
        if video_duration > final_duration:
            print(f"🎬 Trimming video from {video_duration:.2f}s to {final_duration:.2f}s")
            video_speeded = video_speeded.subclip(0, final_duration)
        
        if audio_duration > final_duration:
            print(f"🎵 Trimming audio from {audio_duration:.2f}s to {final_duration:.2f}s")
            audio_speeded = audio_speeded.subclip(0, final_duration)
        
        # Re-create the video with properly trimmed components
        video_with_audio = video_speeded.with_audio(audio_speeded)
        
        if subtitle_segments:
            # Filter and adjust subtitle segments to fit within the final duration
            adjusted_segments = []
            for seg in subtitle_segments:
                seg_start = seg['start'] / 1.25
                seg_end = seg['end'] / 1.25
                
                # Skip segments that start after the final duration
                if seg_start >= final_duration:
                    print(f"⚠️ Skipping subtitle segment starting at {seg_start:.2f}s (beyond {final_duration:.2f}s)")
                    continue
                
                # Trim segments that extend beyond the final duration
                if seg_end > final_duration:
                    print(f"✂️ Trimming subtitle from {seg_end:.2f}s to {final_duration:.2f}s")
                    seg_end = final_duration
                
                # Ensure minimum duration
                if seg_end - seg_start < 0.5:
                    seg_end = min(seg_start + 0.5, final_duration)
                
                # Only add if there's still valid duration
                if seg_end > seg_start:
                    adjusted_segments.append({
                        'start': seg_start,
                        'end': seg_end,
                        'text': seg['text']
                    })
                else:
                    print(f"⚠️ Skipping subtitle segment with invalid duration: {seg_start:.2f}s-{seg_end:.2f}s")
            
            subtitle_segments = adjusted_segments
            print(f"📝 Adjusted {len(subtitle_segments)} subtitle segments to fit duration {final_duration:.2f}s")
        if subtitle_segments:
            print(f"📝 Creating {len(subtitle_segments)} subtitle clips with robust positioning...")
            subtitle_clips = []
            font_choice = get_available_font()
            for i, seg in enumerate(subtitle_segments):
                try:
                    text = seg['text'].strip()
                    if not text:
                        print(f"⚠️ Skipping empty subtitle segment {i+1}")
                        continue
                    
                    # Validate segment timing to prevent duration errors
                    segment_duration = seg['end'] - seg['start']
                    if segment_duration <= 0:
                        print(f"⚠️ Skipping subtitle {i+1} with invalid duration: {segment_duration:.2f}s")
                        continue
                    
                    if seg['start'] >= final_duration:
                        print(f"⚠️ Skipping subtitle {i+1} starting beyond video duration")
                        continue
                    
                    # Ensure end time doesn't exceed video duration
                    actual_end = min(seg['end'], final_duration)
                    actual_duration = actual_end - seg['start']
                    
                    if actual_duration <= 0:
                        print(f"⚠️ Skipping subtitle {i+1} with no valid duration after clipping")
                        continue
                    text_width = min(int(video_width * 0.8), max(400, len(text) * 20))
                    font_size = min(
                        int(video_height * 0.07),
                        int(text_width / max(len(text), 1) * 1.5),
                        70
                    )
                    font_size = max(24, font_size)
                    # Create MoviePy 2.2.1 compatible TextClip
                    try:
                        txt_clip = TextClip(
                            text,
                            font=font_choice,
                            fontsize=font_size,
                            color="white",
                            stroke_color="black",
                            stroke_width=max(3, font_size // 12),
                            method="caption",
                            size=(text_width, int(video_height * 0.3)),
                            align="center"
                        )
                    except Exception as textclip_error:
                        print(f"⚠️ Caption method failed, trying simple text: {textclip_error}")
                        txt_clip = TextClip(
                            text,
                            font=font_choice,
                            fontsize=font_size,
                            color="white",
                            stroke_color="black",
                            stroke_width=2
                        )
                    # Remove on_color for MoviePy 2.2.1 compatibility
                    # txt_clip = txt_clip.on_color(
                    #     size=(txt_clip.w + 40, txt_clip.h + 20),
                    #     color=(0, 0, 0),
                    #     col_opacity=0.7
                    # )
                    margin_bottom = int(video_height * 0.1)
                    y_pos = video_height - txt_clip.h - margin_bottom
                    y_pos = max(margin_bottom, min(y_pos, int(video_height * 0.9)))
                    txt_clip = txt_clip.with_position(("center", y_pos)).with_start(seg['start']).with_duration(actual_duration)
                    subtitle_clips.append(txt_clip)
                    print(f"✅ Subtitle {i+1}: '{text[:30]}...' - Font: {font_size}px, Y: {y_pos}px ({seg['start']:.2f}s-{actual_end:.2f}s)")
                except Exception as subtitle_error:
                    print(f"❌ Primary subtitle creation failed for {i+1}: {subtitle_error}")
                    try:
                        fallback_font_size = max(20, int(video_height * 0.05))
                        txt_clip = TextClip(
                            text,
                            fontsize=fallback_font_size,
                            color="white",
                            stroke_color="black",
                            stroke_width=2
                        )
                        # Remove on_color for MoviePy 2.2.1 compatibility
                        # txt_clip = txt_clip.on_color(
                        #     size=(txt_clip.w + 30, txt_clip.h + 15),
                        #     color=(0, 0, 0),
                        #     col_opacity=0.8
                        # )
                        y_pos = int(video_height * 0.8)
                        txt_clip = txt_clip.with_position(("center", y_pos)).with_start(seg['start']).with_duration(actual_duration)
                        subtitle_clips.append(txt_clip)
                        print(f"⚠️ Subtitle {i+1} added with fallback rendering")
                    except Exception as fallback_error:
                        print(f"❌ Fallback also failed for subtitle {i+1}: {fallback_error}")
                        try:
                            txt_clip = TextClip(
                                text,
                                fontsize=24,
                                color="white"
                            )
                            txt_clip = txt_clip.with_position(("center", int(video_height * 0.8))).with_start(seg['start']).with_duration(actual_duration)
                            subtitle_clips.append(txt_clip)
                            print(f"⚠️ Subtitle {i+1} added with minimal fallback")
                        except:
                            print(f"❌ All fallbacks failed for subtitle {i+1}")
                            continue
            if subtitle_clips:
                print(f"✅ Successfully created {len(subtitle_clips)} subtitle clips out of {len(subtitle_segments)} segments")
                final_video = CompositeVideoClip([video_with_audio] + subtitle_clips)
            else:
                print("❌ No subtitle clips created, proceeding without subtitles")
                final_video = video_with_audio
        else:
            print("ℹ️ No subtitle segments provided")
            final_video = video_with_audio
        if not output_path:
            output_path = f"output_{os.path.basename(video_path)}"
        try:
            final_video.write_videofile(output_path, fps=24, verbose=False)
        except Exception as write_error:
            print(f"Standard video write failed: {write_error}")
            try:
                final_video.write_videofile(output_path, fps=30, verbose=False, audio_codec='aac')
            except Exception as fallback_error:
                print(f"Fallback video write also failed: {fallback_error}")
                return None
        video.close()
        audio.close()
        final_video.close()
        return output_path
    except Exception as e:
        print(f"Video creation error: {e}")
        return None

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "message": "Video API is running",
        "ffmpeg_available": run_cmd(['ffmpeg', '-version'], check=False).returncode == 0,
        "features": {
            "pydub": PYDUB_AVAILABLE,
            "captacity": CAPTACITY_AVAILABLE,
            "enhanced_subtitles": True
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
        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        temp_audio_path = temp_audio.name
        audio_file.save(temp_audio_path)
        temp_audio.close()
        try:
            model_name = request.form.get('model', 'base')
            language = request.form.get('language', None)
            transcription = transcribe_with_whisper(temp_audio_path, model_name, language)
            segments = create_segments_from_whisper_result(transcription, max_words=4)
            if not segments:
                return jsonify({"error": "Failed to generate subtitle segments"}), 500
            srt_content = segments_to_srt(segments)
            temp_srt = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.srt', encoding='utf-8')
            temp_srt_path = temp_srt.name
            temp_srt.write(srt_content)
            temp_srt.close()
            return send_file(temp_srt_path, as_attachment=True, download_name='subtitles.srt', mimetype='text/plain')
        finally:
            for temp_path in [temp_audio_path, temp_srt_path if 'temp_srt_path' in locals() else None]:
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except PermissionError:
                        time.sleep(0.1)
                        try:
                            os.unlink(temp_path)
                        except PermissionError:
                            print(f"⚠️ Could not delete temporary file: {temp_path}")
    except Exception as e:
        print(f"Subtitle generation error: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/generate-enhanced-subtitles', methods=['POST'])
def generate_enhanced_subtitles():
    """Generate enhanced subtitles with timing options"""
    return generate_subtitles()

@app.route('/upload-files', methods=['POST'])
def upload_files():
    """Upload files for video processing"""
    try:
        files = {}
        video_keys = ['video']
        for key in video_keys:
            if key in request.files and request.files[key].filename:
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
                request.files[key].save(temp_file.name)
                files['video'] = temp_file.name
                break
        voice_keys = ['voiceover', 'voice_audio', 'voice']
        for key in voice_keys:
            if key in request.files and request.files[key].filename:
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                request.files[key].save(temp_file.name)
                files['voice'] = temp_file.name
                break
        cta_keys = ['cta_audio', 'cta', 'call_to_action']
        for key in cta_keys:
            if key in request.files and request.files[key].filename:
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                request.files[key].save(temp_file.name)
                files['cta'] = temp_file.name
                break
        bgm_keys = ['bgm_audio', 'bgm', 'background_music']
        for key in bgm_keys:
            if key in request.files and request.files[key].filename:
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                request.files[key].save(temp_file.name)
                files['bgm'] = temp_file.name
                break
        if 'video' not in files or 'voice' not in files:
            return jsonify({"error": "Missing required files: video and voice audio"}), 400
        try:
            audio_paths = [files['voice']]
            volumes = [float(request.form.get('voice_volume', request.form.get('voiceover_volume', 1.0)))]
            if 'cta' in files:
                audio_paths.append(files['cta'])
                volumes.append(float(request.form.get('cta_volume', 0.9)))
            if 'bgm' in files:
                audio_paths.append(files['bgm'])
                volumes.append(float(request.form.get('bgm_volume', 0.3)))
            video = safe_load_video(files['video'])
            video_duration = video.duration
            video.close()
            mixed_audio_path = tempfile.NamedTemporaryFile(delete=False, suffix='.wav').name
            if not mix_audio_files(audio_paths, volumes, mixed_audio_path, video_duration):
                return jsonify({"error": "Audio mixing failed"}), 500
            subtitle_segments = None
            if request.form.get('enable_subtitles', 'true').lower() == 'true':
                print("Generating word-level synchronized subtitles for voice + CTA...")
                subtitle_segments = create_synchronized_subtitles(
                    files['voice'], 
                    files.get('cta'),
                    timing_style='word_level',
                    max_words=3
                )
            output_path = create_video_with_subtitles(files['video'], mixed_audio_path, subtitle_segments)
            if output_path and os.path.exists(output_path):
                return send_file(output_path, as_attachment=True, download_name='final_video.mp4', mimetype='video/mp4')
            else:
                return jsonify({"error": "Video creation failed"}), 500
        finally:
            all_temp_files = list(files.values())
            if 'mixed_audio_path' in locals():
                all_temp_files.append(mixed_audio_path)
            if 'output_path' in locals() and output_path:
                all_temp_files.append(output_path)
            for temp_path in all_temp_files:
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except PermissionError:
                        time.sleep(0.1)
                        try:
                            os.unlink(temp_path)
                        except PermissionError:
                            print(f"⚠️ Could not delete temporary file: {temp_path}")
    except Exception as e:
        print(f"Upload processing error: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/generate-video-with-synced-subtitles', methods=['POST'])
def generate_video_with_synced_subtitles():
    """Generate video with perfectly synchronized subtitles using Whisper"""
    try:
        if 'video' not in request.files or 'audio' not in request.files:
            return jsonify({"error": "Missing video or audio file"}), 400
        video_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        audio_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        video_temp_path = video_temp.name
        audio_temp_path = audio_temp.name
        request.files['video'].save(video_temp_path)
        request.files['audio'].save(audio_temp_path)
        video_temp.close()
        audio_temp.close()
        try:
            model_name = request.form.get('model', 'base')
            language = request.form.get('language', None)
            subtitle_size = int(request.form.get('subtitle_size', 84))
            subtitle_color = request.form.get('subtitle_color', 'white')
            transcription = transcribe_with_whisper(audio_temp_path, model_name, language)
            segments = create_segments_from_whisper_result(transcription, max_words=3)
            if not segments:
                return jsonify({"error": "Failed to generate subtitle segments"}), 500
            print("🎬 Using MoviePy for subtitle generation with improved positioning...")
            try:
                output_path = create_video_with_subtitles(video_temp_path, audio_temp_path, segments)
                if not output_path or not os.path.exists(output_path):
                    return jsonify({"error": "Video creation failed - output file not generated"}), 500
                return send_file(output_path, as_attachment=True, 
                               download_name=f'video_whisper_synced.mp4', mimetype='video/mp4')
            except Exception as video_error:
                print(f"❌ Video creation error: {video_error}")
                traceback.print_exc()
                return jsonify({"error": f"Video creation failed: {str(video_error)}"}), 500
        finally:
            temp_files = [video_temp_path, audio_temp_path]
            for temp_file in temp_files:
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.unlink(temp_file)
                    except PermissionError:
                        time.sleep(0.1)
                        try:
                            os.unlink(temp_file)
                        except PermissionError:
                            print(f"⚠️ Could not delete temporary file: {temp_file}")
    except Exception as e:
        print(f"Synced video generation error: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/upload-files-captacity', methods=['POST'])
def upload_files_with_captacity():
    """Enhanced file upload with Captacity subtitle generation"""
    try:
        print("Processing file uploads with Captacity subtitles...")
        required_files = ['video', 'voiceover', 'cta_audio', 'bgm']
        for file_key in required_files:
            if file_key not in request.files:
                return jsonify({"error": f"Missing file: {file_key}"}), 400
            file = request.files[file_key]
            if file.filename == '':
                return jsonify({"error": f"No file selected for: {file_key}"}), 400
        openai_api_key = request.form.get('openai_api_key')
        if not openai_api_key:
            print("No OpenAI API key provided, will try to use environment variable")
        temp_files = {}
        try:
            for file_key in required_files:
                file = request.files[file_key]
                if file_key == 'video':
                    suffix = '.mp4'
                else:
                    suffix = '.mp3'
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                file.save(temp_file.name)
                temp_files[file_key] = temp_file.name
                print(f"Saved {file_key}: {temp_file.name} ({os.path.getsize(temp_file.name)} bytes)")
            video_path = temp_files['video']
            voice_path = temp_files['voiceover'] 
            cta_path = temp_files['cta_audio']
            bgm_path = temp_files['bgm']
            print("Loading video to get duration...")
            video_temp = safe_load_video(video_path)
            video_duration = video_temp.duration
            video_temp.close()
            print(f"Video duration: {video_duration}s")
            print("Merging audio tracks with synchronized positioning...")
            merged_audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
            audio_paths = [voice_path, cta_path]
            volumes = [1.5, 2.5]
            if bgm_path:
                audio_paths.append(bgm_path)
                volumes.append(0.3)
            audio_success = mix_audio_files(audio_paths, volumes, merged_audio_path, video_duration)
            if not audio_success:
                return jsonify({"error": "Audio merging failed"}), 500
            print("Applying merged audio to video...")
            video = safe_load_video(video_path)
            final_audio = safe_load_audio(merged_audio_path)
            if abs(final_audio.duration - video.duration) > 0.1:
                print("Adjusting audio duration to match video...")
                if final_audio.duration > video.duration:
                    final_audio_adjusted = final_audio.subclip(0, video.duration)
                    final_audio.close()
                    final_audio = final_audio_adjusted
                else:
                    print(f"Audio ({final_audio.duration}s) shorter than video ({video.duration}s)")
                print(f"Adjusted audio duration: {final_audio.duration}s")
            video_with_audio = video.with_audio(final_audio)
            print("Exporting intermediate video...")
            output_dir = "temp"
            os.makedirs(output_dir, exist_ok=True)
            intermediate_path = os.path.join(output_dir, f"intermediate_{uuid.uuid4().hex}.mp4")
            video_with_audio.write_videofile(
                intermediate_path,
                fps=24,
                verbose=False,
                threads=4,
                audio_codec="aac",
                audio_bitrate="320k",
                bitrate="8000k"
            )
            video.close()
            final_audio.close()
            video_with_audio.close()
            print("Adding subtitles using Captacity...")
            final_output_path = os.path.join(output_dir, f"final_captacity_{uuid.uuid4().hex}.mp4")
            subtitle_success = add_captacity_subtitles(intermediate_path, final_output_path, openai_api_key)
            if not subtitle_success:
                print("Captacity subtitles failed, returning video without subtitles")
                final_output_path = intermediate_path
            for f in list(temp_files.values()) + [merged_audio_path]:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except:
                        pass
            if final_output_path != intermediate_path and os.path.exists(intermediate_path):
                try:
                    os.remove(intermediate_path)
                except:
                    pass
            if os.path.exists(final_output_path) and os.path.getsize(final_output_path) > 1000:
                print(f"Successfully created video with Captacity subtitles: {final_output_path} ({os.path.getsize(final_output_path)} bytes)")
                return send_file(final_output_path, mimetype="video/mp4", as_attachment=True, download_name="final_video_captacity.mp4")
            else:
                return jsonify({"error": "Video rendering failed - output file is empty"}), 500
        except Exception as e:
            for temp_file in temp_files.values():
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass
            raise e
    except Exception as e:
        print(f"Captacity upload processing error: {e}")
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
                except PermissionError:
                    time.sleep(0.1)
                    try:
                        os.unlink(temp_audio.name)
                    except PermissionError:
                        print(f"⚠️ Could not delete temporary file: {temp_audio.name}")
                except Exception as e:
                    print(f"⚠️ Error deleting temp file: {e}")
    except Exception as e:
        print(f"Whisper transcription error: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/upload-files-whisper', methods=['POST'])
def upload_files_whisper():
    """Upload files and process with Whisper for perfect subtitle synchronization"""
    try:
        print("Processing files with Whisper integration...")
        required_files = ['video', 'voiceover', 'cta_audio', 'bgm']
        for file_key in required_files:
            if file_key not in request.files:
                return jsonify({"error": f"Missing file: {file_key}"}), 400
        temp_video = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_voiceover = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        temp_cta = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        temp_bgm = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        request.files['video'].save(temp_video.name)
        request.files['voiceover'].save(temp_voiceover.name)
        request.files['cta_audio'].save(temp_cta.name)
        request.files['bgm'].save(temp_bgm.name)
        temp_video.close()
        temp_voiceover.close()
        temp_cta.close()
        temp_bgm.close()
        try:
            font_size = int(request.form.get('font_size', 24))
            subtitle_color = request.form.get('subtitle_color', 'white')
            print("🎤 Transcribing voiceover with Whisper...")
            voiceover_transcription = transcribe_with_whisper(temp_voiceover.name)
            print("🎤 Transcribing CTA with Whisper...")
            cta_transcription = transcribe_with_whisper(temp_cta.name)
            print("📝 Creating subtitle segments...")
            subtitle_segments = create_synchronized_subtitles(
                temp_voiceover.name, 
                temp_cta.name,
                timing_style='word_level',
                max_words=3
            )
            if not subtitle_segments:
                return jsonify({"error": "Failed to create subtitle segments"}), 500
            srt_content = segments_to_srt(subtitle_segments)
            print("📝 Generated SRT content:\n", srt_content[:500], "...")
            srt_temp = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.srt', encoding='utf-8')
            srt_temp.write(srt_content)
            srt_temp.close()
            print("🎵 Processing audio with enhanced volume and tempo adjustment...")
            mixed_audio_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            mixed_audio_temp.close()
            cmd = [
                'ffmpeg', '-y',
                '-i', temp_voiceover.name,
                '-i', temp_cta.name, 
                '-i', temp_bgm.name,
                '-filter_complex', '[0:a]volume=2.0,atempo=1.25[v];[1:a]volume=3.0,atempo=1.25[c];[2:a]volume=1.2[b];[v][c][b]amix=inputs=3:duration=longest:normalize=0[out]',
                '-map', '[out]',
                '-c:a', 'aac',
                '-b:a', '192k',
                mixed_audio_temp.name
            ]
            result = run_cmd(cmd, check=False)
            if result.returncode != 0:
                print("⚠️ Audio mixing failed, using voiceover only")
                mixed_audio_temp.name = temp_voiceover.name
            print("🎬 Creating final video with burned-in subtitles...")
            output_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
            output_temp.close()
            probe_cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', temp_video.name]
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
            video_info = json.loads(probe_result.stdout)
            video_stream = next((s for s in video_info['streams'] if s['codec_type'] == 'video'), None)
            if video_stream:
                video_width = int(video_stream['width'])
                video_height = int(video_stream['height'])
                optimal_font_size = max(24, int(video_height * 0.06))
                margin_v = max(80, int(video_height * 0.12))
                margin_lr = max(50, int(video_width * 0.08))
            else:
                optimal_font_size = font_size
                margin_v = 80
                margin_lr = 50
            font_choice = get_ffmpeg_font()
            simple_srt_path = "temp_subtitles.srt"
            shutil.copy(srt_temp.name, simple_srt_path)
            simple_srt_path = re.sub(r'([\\ ])', r'\\\1', simple_srt_path)
            cmd = [
                'ffmpeg', '-y',
                '-i', temp_video.name,
                '-i', mixed_audio_temp.name,
                '-filter_complex', f"""[0:v]setpts=PTS/1.25[v];
                [v]subtitles='{simple_srt_path}':force_style='
                FontName={font_choice},
                FontSize={optimal_font_size},
                PrimaryColour=&Hffffff,
                OutlineColour=&H000000,
                Outline=3,
                BackColour=&Hcc000000,
                BorderStyle=3,
                Alignment=2,
                MarginV={margin_v},
                MarginL={margin_lr},
                MarginR={margin_lr},
                Bold=1,
                WrapStyle=2,
                ScaleX=100,
                ScaleY=100'[vout]""",
                '-map', '[vout]',
                '-map', '1:a',
                '-c:v', 'libx264',
                '-c:a', 'copy',
                '-shortest', output_temp.name
            ]
            result = run_cmd(cmd, check=False)
            if os.path.exists(simple_srt_path):
                try:
                    os.unlink(simple_srt_path)
                except:
                    pass
            if result.returncode == 0:
                print("✅ Video created successfully!")
                probe_cmd = ['ffprobe', '-v', 'quiet', '-show_streams', '-select_streams', 's', output_temp.name]
                probe_result = run_cmd(probe_cmd, check=False)
                if probe_result.returncode == 0 and probe_result.stdout:
                    print("✅ Subtitles detected in output video")
                else:
                    print("❌ No subtitles detected in output video")
                return send_file(output_temp.name, as_attachment=True, 
                               download_name='video_whisper_perfect_sync.mp4', mimetype='video/mp4')
            else:
                print(f"❌ FFmpeg video creation failed with return code: {result.returncode}")
                print(f"❌ FFmpeg stderr: {result.stderr}")
                print(f"📄 FFmpeg stdout: {result.stdout}")
                print("⚠️ Falling back to MoviePy for subtitle rendering...")
                output_path = create_video_with_subtitles(temp_video.name, mixed_audio_temp.name, subtitle_segments)
                if output_path and os.path.exists(output_path):
                    return send_file(output_path, as_attachment=True, 
                                   download_name='video_whisper_perfect_sync.mp4', mimetype='video/mp4')
                return jsonify({"error": f"Video creation failed: {result.stderr}"}), 500
        
        finally:
            temp_files = [temp_video.name, temp_voiceover.name, temp_cta.name, temp_bgm.name]
            if 'srt_temp' in locals():
                temp_files.append(srt_temp.name)
            if 'mixed_audio_temp' in locals():
                temp_files.append(mixed_audio_temp.name)
            if 'output_temp' in locals():
                temp_files.append(output_temp.name)
            for temp_file in temp_files:
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.unlink(temp_file)
                    except PermissionError:
                        print(f"⚠️ Could not delete temporary file: {temp_file}")
                    except Exception as e:
                        print(f"⚠️ Error deleting temp file: {e}")
    
    except Exception as e:
            print(f"❌ Whisper video processing error: {e}")
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500
if __name__ == "__main__":
    print("🚀 Minimized Video API with Whisper Integration")
    print("📝 Endpoints: /health, /generate-subtitles, /upload-files, /generate-video-with-synced-subtitles")
    print("� New Whisper endpoints: /transcribe-whisper, /upload-files-whisper")
    print("🎯 Features: Real timestamp-based subtitles with OpenAI Whisper (A4F fallback)")
    print("💡 Perfect subtitle synchronization using word-level timestamps")
    print("🔧 MoviePy 2.x compatible with robust error handling")
    port = 5009
    print(f"🌐 Server starting at: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)