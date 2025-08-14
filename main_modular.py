#!/usr/bin/env python3
"""
Main application file - now using modular structure
This file imports from the separate service modules for better maintainability
"""

# Import the modular Flask application
from app import app

# Import all service modules to ensure they're properly loaded
import config
import utils
import whisper_service
import subtitle_service
import audio_service
import video_service

if __name__ == "__main__":
    print("🚀 Enhanced Video API with Modular Structure")
    print("📝 Endpoints: /health, /generate-subtitles, /generate-video-with-synced-subtitles, /transcribe-whisper")
    print("🎯 Features: Whisper transcription, MoviePy & FFmpeg video processing, Perfect subtitle sync")
    print("🔧 Compatible with MoviePy 2.2.1 and Python 3.13")
    print("📁 Architecture: Modular design with separate service files")
    
    port = 5009
    print(f"🌐 Server starting at: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
