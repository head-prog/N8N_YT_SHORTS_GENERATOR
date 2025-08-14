# Video API Modular Structure

This document explains the new modular structure of the video API after dividing `main_fixed.py` into smaller, manageable files.

## File Structure

```
video-api/
├── config.py              # Configuration, imports, and global variables
├── utils.py               # Utility functions (fonts, calculations, command execution)
├── audio_service.py       # Audio processing utilities 
├── whisper_service.py     # Whisper transcription functionality
├── subtitle_service.py    # Subtitle generation and formatting
├── video_service.py       # Video processing with MoviePy and FFmpeg
├── app.py                 # Flask routes and main application
└── main_fixed.py          # Original monolithic file (backup)
```

## Module Responsibilities

### config.py
- Import all required libraries with error handling
- Global configuration variables
- Library availability flags (MOVIEPY_AVAILABLE, WHISPER_AVAILABLE, etc.)
- API keys and configuration constants

### utils.py
- Command execution (`run_cmd`)
- Font detection for MoviePy and FFmpeg
- Font size and positioning calculations
- General utility functions

### audio_service.py
- Audio file loading and validation (`safe_load_audio`)
- Audio compression for API compatibility
- Audio processing utilities

### whisper_service.py
- Whisper model loading and management
- Audio transcription using Whisper or A4F API fallback
- Transcription result processing

### subtitle_service.py
- Subtitle segment creation from transcription results
- Word-level and sentence-level timing generation
- SRT format conversion
- Vertical subtitle formatting for mobile videos

### video_service.py
- Video file loading and validation (`safe_load_video`)
- MoviePy-based video creation with subtitles
- FFmpeg-based video creation with subtitles
- Video and audio synchronization

### app.py
- Flask application setup
- API route definitions
- Request/response handling
- Main application entry point

## Key Features Preserved

1. **MoviePy 2.2.1 Compatibility**: All MoviePy imports and usage remain compatible
2. **Vertical Subtitle Layout**: Capitalized, lower-positioned subtitles for mobile videos
3. **Audio Quality**: 48kHz, 192k bitrate audio processing
4. **Whisper Integration**: Real-time transcription with word-level timestamps
5. **Fallback Systems**: Multiple fallback strategies for all components

## Usage

To run the modular API:

```bash
python app.py
```

## Benefits of Modular Structure

1. **Maintainability**: Each module has a single responsibility
2. **Testability**: Individual components can be tested in isolation
3. **Reusability**: Services can be used independently
4. **Debugging**: Easier to locate and fix issues
5. **Scalability**: New features can be added to specific modules

## Import Dependencies

- `app.py` imports from all service modules
- Service modules import from `config.py` and `utils.py`
- Minimal circular dependencies with clear separation of concerns

## API Endpoints (Unchanged)

- `GET /health` - Health check with feature availability
- `POST /generate-subtitles` - Generate SRT subtitles from audio
- `POST /generate-video-with-synced-subtitles` - Create video with synced subtitles
- `POST /transcribe-whisper` - Direct Whisper transcription

All endpoints maintain the same interface and functionality as the original monolithic version.
