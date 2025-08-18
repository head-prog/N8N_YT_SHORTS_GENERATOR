import requests
import json
import traceback
from config import WHISPER_AVAILABLE, WhisperModel, A4F_API_KEY, A4F_API_URL, FORCE_LOCAL_WHISPER
from audio_service import compress_audio

# Global variables for this module
WHISPER_MODEL = None
WHISPER_MODEL_NAME = "base"

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


def transcribe_with_whisper(audio_path, model_name="base", language=None, task="transcribe"):
    """Transcribe audio using OpenAI Whisper with real timestamps"""
    if not WHISPER_AVAILABLE:
        if FORCE_LOCAL_WHISPER:
            print("❌ Local Whisper forced but not available. Please install faster-whisper.")
            return None
        else:
            print("⚠️ Whisper not available, falling back to A4F API")
            return transcribe_audio_with_a4f(audio_path)
    
    try:
        # Check for environment variable override for model size
        import os
        env_model = os.environ.get('WHISPER_MODEL_SIZE', model_name)
        if env_model != model_name:
            print(f"🔧 Using environment override model: {env_model}")
            model_name = env_model
        
        model = load_whisper_model(model_name)
        if not model:
            if FORCE_LOCAL_WHISPER:
                print("❌ Local Whisper forced but model loading failed.")
                return None
            else:
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
        if FORCE_LOCAL_WHISPER:
            print("❌ Local Whisper forced - not falling back to A4F API")
            return None
        else:
            print("🔄 Falling back to A4F API...")
            return transcribe_audio_with_a4f(audio_path)


def transcribe_audio_with_a4f(audio_path, max_file_size_mb=0.5):
    """Transcribe audio using A4F API (fallback method)"""
    try:
        # Check file size and compress if needed
        import os
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
