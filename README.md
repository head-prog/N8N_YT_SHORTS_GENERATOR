# N8N YouTube Shorts Generator

A powerful, modular Flask API for generating YouTube Shorts videos with random clips, voiceover, background music (BGM), call-to-action (CTA), and perfectly centered subtitles.

## ✨ Features

- **🎬 Random Video Clips**: Automatically selects and concatenates random 4-second video clips
- **🎤 Voiceover Integration**: Seamless audio mixing with voiceover
- **🎵 Background Music**: Adjustable BGM volume for perfect audio balance
- **📢 Call-to-Action**: CTA audio with customizable volume levels
- **📝 Dynamic Subtitles**: 
  - Word-level synchronization using Faster-Whisper
  - ASS format for perfect centering
  - Custom Bangers font (19px) for mobile optimization
  - Pause-aware subtitle timing
- **🔄 Transitions**: Optional crossfade transitions between clips
- **⚡ Performance**: FFmpeg-optimized subtitle rendering for 10x speed improvement

## 🚀 Quick Start

### Prerequisites

```bash
# Install system dependencies (macOS)
brew install ffmpeg
brew install --cask font-bangers

# Install Python dependencies
pip install -r requirements.txt
```

### Installation

1. Clone the repository:
```bash
git clone https://github.com/head-prog/N8N_YT_SHORTS_GENERATOR.git
cd N8N_YT_SHORTS_GENERATOR
```

2. Set up virtual environment:
```bash
chmod +x run_with_venv.sh
./run_with_venv.sh
```

3. Configure your video clips folder in `config.py`:
```python
CLIPS_FOLDER = "/path/to/your/video/clips"
```

### Usage

#### Start the API Server
```bash
python app.py
```
The server will start on `http://localhost:5000`

#### Generate Video via API
```bash
curl -X POST "http://localhost:5000/generate-video-with-random-clips" \
  -F "voiceover=@path/to/voiceover.wav" \
  -F "bgm=@path/to/background-music.mp3" \
  -F "cta=@path/to/call-to-action.mp3" \
  -F "add_subtitles=true" \
  -F "bgm_volume=0.6" \
  -F "cta_volume=1.5" \
  --output generated_video.mp4
```

## 🔧 Configuration

### Audio Volume Settings
- **BGM Volume**: `0.6` (default) - Background music level
- **CTA Volume**: `1.5` (default) - Call-to-action audio level  
- **Voiceover Volume**: `1.0` (fixed) - Main voice level

### Subtitle Settings
- **Font**: Bangers-Regular.ttf (19px)
- **Format**: ASS (Advanced SubStation Alpha) for perfect centering
- **Alignment**: Center-aligned for mobile optimization
- **Timing**: Word-level synchronization with pause awareness

### Video Settings
- **Clip Duration**: 4 seconds per clip
- **Transitions**: Optional crossfade (0.5s default)
- **Quality**: Maintains original clip resolution

## 📁 Project Structure

```
video-api/
├── app.py                     # Flask API server
├── video_service.py           # Core video generation logic
├── audio_service.py           # Audio mixing and processing
├── subtitle_service.py        # Subtitle generation
├── enhanced_subtitle_service.py # Advanced subtitle features
├── whisper_service.py         # Speech-to-text transcription
├── word_sync_service.py       # Word-level timing synchronization
├── config.py                  # Configuration settings
├── utils.py                   # Utility functions
├── requirements.txt           # Python dependencies
├── run_with_venv.sh          # Virtual environment setup script
├── Bangers/                   # Custom font files
│   ├── Bangers-Regular.ttf
│   └── OFL.txt
└── TEST/                      # Sample test files
    ├── VOICE_AUDIO.wav
    ├── BGM.mp3
    └── CTA.mp3
├── examples/                  # Example outputs and workflows
│   ├── test_final_volume_fix.mp4      # Example generated video
│   └── final_yt_shorts_workflow.json  # N8N workflow configuration
```

## 🔄 API Endpoints

### POST `/generate-video-with-random-clips`

Generate a video with random clips, subtitles, and audio mixing.

**Parameters:**
- `voiceover` (file): Voice audio file (WAV/MP3)
- `bgm` (file): Background music file (MP3)
- `cta` (file, optional): Call-to-action audio file (MP3)
- `add_subtitles` (bool): Enable subtitle generation (default: true)
- `bgm_volume` (float): BGM volume level (default: 0.6)
- `cta_volume` (float): CTA volume level (default: 1.5)
- `enable_transitions` (bool): Enable clip transitions (default: true)
- `transition_duration` (float): Transition duration in seconds (default: 0.5)
- `transition_type` (string): Transition type (default: "crossfade")

**Response:** Generated MP4 video file

### POST `/transcribe`

Transcribe audio using Faster-Whisper.

**Parameters:**
- `audio` (file): Audio file to transcribe
- `model` (string): Whisper model size (default: "base")
- `language` (string, optional): Target language
- `task` (string): Task type - "transcribe" or "translate"

## 🎯 Performance Optimizations

- **FFmpeg Integration**: Direct subtitle rendering bypasses MoviePy for 10x speed improvement
- **Caching**: Transcription results cached to avoid re-processing
- **Memory Management**: Proper cleanup of video/audio objects
- **Async Processing**: Background video generation support

## 🛠️ Advanced Features

### Custom Font Integration
The system uses the Bangers font for YouTube Shorts optimization:
- Automatically detects system font installation
- Falls back to system fonts if unavailable
- Perfect mobile readability at 19px size

### Word-Level Synchronization
Advanced subtitle timing features:
- Individual word timestamps
- Pause detection and respect
- Punctuation-aware line breaks
- Dynamic subtitle chunking

### Audio Processing
Sophisticated audio mixing:
- Multiple format support (WAV, MP3, FLAC)
- Volume normalization
- Crossfade transitions
- CTA timing synchronization

## 📊 Recent Updates

### v2.0 - Volume Enhancement Update
- ✅ Increased BGM volume from 0.2 to 0.6 (3x louder)
- ✅ Increased CTA volume from 0.8 to 1.5 (nearly 2x louder) 
- ✅ Updated all audio mixing functions consistently
- ✅ Fixed hardcoded volume values across all code paths
- ✅ Enhanced FFmpeg filter_complex for better audio balance

### v1.9 - Font & Subtitle Improvements
- ✅ Upgraded to Bangers font (19px) for better readability
- ✅ Implemented ASS format for perfect subtitle centering
- ✅ Added pause-aware subtitle timing
- ✅ Enhanced word-level synchronization

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

For issues and questions:
- Create an issue on GitHub
- Check the [Wiki](https://github.com/head-prog/N8N_YT_SHORTS_GENERATOR/wiki) for detailed documentation
- Review the test files in the `TEST/` directory for examples

## 🎬 Demo & Examples

### Example Output Video
Check out `examples/test_final_volume_fix.mp4` for a sample generated video showcasing:
- ✅ Perfect subtitle centering for mobile viewing
- ✅ Balanced audio mixing (voice, BGM, CTA)
- ✅ Smooth transitions between random clips
- ✅ Word-perfect synchronization
- ✅ High-quality output optimized for social media

### N8N Workflow Integration

![N8N Workflow](examples/n8n_workflow_screenshot.png)

The repository includes a complete N8N workflow (`examples/final_yt_shorts_workflow.json`) that demonstrates:
- **Form Trigger**: Collects user input for video generation
- **Content Validation**: Validates uploaded audio files
- **AI Script Generation**: Uses OpenAI to enhance content
- **TTS Conversion**: Converts text to speech
- **Video Generation**: Calls the API to create the final video
- **Error Handling**: Robust error management throughout the process

**Import the workflow:**
1. Copy the content of `examples/final_yt_shorts_workflow.json`
2. In N8N, go to Workflows → Import from JSON
3. Paste the workflow and configure your API endpoints
4. Set up your OpenAI API key and other credentials
5. Test with the form trigger

The workflow automates the entire video creation process from content input to final video output, making it perfect for content creators and agencies.

## 🔧 N8N Integration

The included N8N workflow (`examples/final_yt_shorts_workflow.json`) provides:
- Automated video generation triggers
- File upload handling
- API integration with the Flask server
- Error handling and notifications
- Batch processing capabilities

To use the N8N workflow:
1. Import `examples/final_yt_shorts_workflow.json` into your N8N instance
2. Configure the API endpoint URL
3. Set up your file input sources
4. Activate the workflow

---

**Made with ❤️ for content creators and N8N automation workflows**
