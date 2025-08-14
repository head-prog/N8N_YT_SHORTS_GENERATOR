#!/usr/bin/env python3

# Suppress common deprecation warnings for cleaner output
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message="pkg_resources is deprecated")
warnings.filterwarnings("ignore", message=".*audioop.*", category=DeprecationWarning)

import os
import sys
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

# Global configuration
# Note: These are moved to whisper_service.py to avoid circular imports
# WHISPER_MODEL = None
# WHISPER_MODEL_NAME = "base"

# API Configuration (fallback)
A4F_API_KEY = "ddc-a4f-cc235b79cf914f809db73076609704cc"
A4F_API_URL = "https://api.a4f.co/v1/audio/transcriptions"

# Global configuration
SUBTITLE_SIZE_MULTIPLIER = 0.6  # Medium font size for balanced readability
