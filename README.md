# 🎥 Video Generator for YouTube Shorts

A powerful Flask-based API for generating YouTube Shorts with perfectly synchronized subtitles using Whisper AI and MoviePy/FFmpeg.

## ✨ Features

- 🎤 **Whisper AI Integration**: Real-time audio transcription with word-level timestamps
- 📱 **Mobile-Optimized Subtitles**: Vertical subtitle layout perfect for portrait videos
- 🎬 **Dual Rendering**: MoviePy and FFmpeg support for maximum compatibility
- 🔊 **High-Quality Audio**: 48kHz, 192k bitrate with automatic volume optimization
- 📝 **Smart Segmentation**: 2-3 words per subtitle for optimal readability
- 🎯 **Perfect Sync**: Word-level timestamp accuracy for flawless audio-subtitle sync
- 🌐 **n8n Compatible**: Ready for workflow automation

## 🚀 Quick Start

### Prerequisites

- Python 3.13+
- FFmpeg installed
- Virtual environment recommended

### Installation

1. Clone the repository:
```bash
git clone https://github.com/head-prog/video-generator-yt-shorts.git
cd video-generator-yt-shorts
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the server:
```bash
python main_fixed.py
```

Server will start at `http://localhost:5009`

## 📋 API Endpoints

### Health Check
```bash
GET /health
```

### Transcription Only
```bash
POST /transcribe-whisper
Content-Type: multipart/form-data

Parameters:
- audio: Audio file (wav, mp3, etc.)
- model: Whisper model (default: "base")
- language: Target language (optional)
```

### Video Generation with Subtitles
```bash
POST /generate-video-with-synced-subtitles
Content-Type: multipart/form-data

Parameters:
- video: Video file (mp4, etc.)
- audio: Audio file (wav, mp3, etc.)
- model: Whisper model (default: "base")
- max_words: Words per subtitle (default: 3)
- use_moviepy: Use MoviePy instead of FFmpeg (default: false)
```

## 💡 Usage Examples

### Basic Video Generation
```bash
curl -X POST \
  -F "video=@input.mp4" \
  -F "audio=@voiceover.wav" \
  http://localhost:5009/generate-video-with-synced-subtitles \
  -o output_with_subtitles.mp4
```

### Custom Settings
```bash
curl -X POST \
  -F "video=@input.mp4" \
  -F "audio=@voiceover.wav" \
  -F "model=small" \
  -F "max_words=2" \
  http://localhost:5009/generate-video-with-synced-subtitles \
  -o output_custom.mp4
```

## 🎨 Subtitle Features

### Vertical Layout for Mobile
- Each word appears on a separate line
- Perfect for 9:16 aspect ratio videos
- Automatically detects video orientation

### Visual Style
- **Font**: System-optimized with fallbacks
- **Size**: Auto-calculated based on video dimensions
- **Position**: Centered horizontally, lower third vertically
- **Style**: White text with black outline, capitalized
- **Background**: Semi-transparent for readability

### Smart Positioning
- **Vertical videos**: 80% width, positioned low
- **Horizontal videos**: Traditional centered layout
- **Bounds checking**: Never extends outside screen

## 🔧 Technical Details

### Audio Processing
- **Sample Rate**: 48kHz
- **Bitrate**: 192k
- **Channels**: Stereo
- **Codec**: AAC
- **Volume**: Auto-boost for quiet audio

### Video Processing
- **Codec**: H.264 (libx264)
- **CRF**: 23 (high quality)
- **Preset**: Medium (balanced speed/quality)
- **Frame Rate**: 24fps

### Whisper Models
- `tiny`: Fastest, least accurate
- `base`: Balanced (default)
- `small`: Better accuracy
- `medium`: High accuracy
- `large`: Best accuracy (slower)

## 📁 File Structure

```
video-api/
├── main_fixed.py              # Main Flask application
├── requirements.txt           # Python dependencies
├── audioop_compat_clean.py    # Python 3.13 compatibility
├── Dockerfile                 # Container configuration
├── .gitignore                # Git ignore rules
└── README.md                 # This file
```

## 🔄 n8n Integration

The API is designed for seamless integration with n8n workflows:

1. **HTTP Request Node**: Configure with endpoint URLs
2. **File Handling**: Binary data support for video/audio files
3. **Response Processing**: Direct video file output
4. **Error Handling**: Comprehensive error responses

## 🛠️ Development

### Dependencies
- **Flask**: Web framework
- **MoviePy**: Video processing
- **FFmpeg**: Video/audio manipulation
- **Faster-Whisper**: AI transcription
- **Pydub**: Audio processing

### Python 3.13 Compatibility
- Custom audioop compatibility layer
- Updated MoviePy imports
- Modern Python features supported

## 📊 Performance

- **Transcription**: Real-time for short clips
- **Video Generation**: ~1-2x real-time processing
- **Memory Usage**: Optimized for efficiency
- **Concurrent Requests**: Thread-safe processing

## 🔧 Configuration

### Environment Variables
```bash
# Optional: Custom Whisper model path
WHISPER_MODEL_PATH=/path/to/models

# Optional: Custom port
PORT=5009
```

### FFmpeg Requirements
Ensure FFmpeg is installed and accessible:
```bash
ffmpeg -version
```

## 🐛 Troubleshooting

### Common Issues

1. **Audio not audible**: Check audio file format and bitrate
2. **Subtitles cut off**: Verify video dimensions and font sizing
3. **Import errors**: Ensure all dependencies are installed
4. **FFmpeg errors**: Check FFmpeg installation and font availability

### Debug Mode
Run with debug logging:
```bash
python main_fixed.py --debug
```

## 📄 License

This project is open source. See individual dependencies for their respective licenses.

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Make changes
4. Test thoroughly
5. Submit pull request

## 📞 Support

For issues and questions:
- Create GitHub issue
- Check troubleshooting section
- Review logs for detailed error information

---

**Built with ❤️ for creating amazing YouTube Shorts content!**
