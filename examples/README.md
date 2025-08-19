# Examples

This directory contains example outputs and configuration files for the N8N YouTube Shorts Generator.

## Files

### `test_final_volume_fix.mp4`
- **Description**: Sample generated video showcasing all features
- **Features Demonstrated**:
  - Random video clip compilation (4-second segments)
  - Voiceover integration with word-level subtitle synchronization
  - Background music at optimized volume (0.6)
  - Call-to-action audio at enhanced volume (1.5)
  - Perfectly centered subtitles using Bangers font (19px)
  - ASS format for mobile optimization
  - Crossfade transitions between clips
- **Generated With**: Latest volume-enhanced API (v2.0)
- **Size**: ~23MB
- **Duration**: Variable (based on voiceover length)

### `final_yt_shorts_workflow.json`
- **Description**: Complete N8N workflow configuration
- **Purpose**: Automated video generation pipeline
- **Features**:
  - Multi-file input handling (voiceover, BGM, CTA)
  - API integration with Flask server
  - Error handling and logging
  - Batch processing support
  - Custom parameter configuration
  - Output file management
- **Usage**: Import into N8N instance and configure endpoints

## How to Use

### Testing the Video Output
```bash
# Play the example video to see expected output quality
open examples/test_final_volume_fix.mp4
```

### Importing N8N Workflow
1. Open your N8N instance
2. Go to Workflows → Import
3. Select `examples/final_yt_shorts_workflow.json`
4. Configure the API endpoint URL (default: `http://localhost:5000`)
5. Set up input file sources
6. Activate the workflow

### Recreating the Example Video
```bash
# Use the same parameters that generated the example
curl -X POST "http://localhost:5000/generate-video-with-random-clips" \
  -F "voiceover=@TEST/VOICE_AUDIO.wav" \
  -F "bgm=@TEST/BGM.mp3" \
  -F "cta=@TEST/CTA.mp3" \
  -F "add_subtitles=true" \
  -F "bgm_volume=0.6" \
  -F "cta_volume=1.5" \
  --output my_generated_video.mp4
```

## Quality Expectations

The example video demonstrates:
- ✅ **Audio Quality**: Clear voiceover with balanced BGM and prominent CTA
- ✅ **Subtitle Quality**: Perfect centering, readable font, accurate timing
- ✅ **Video Quality**: Smooth transitions, maintained resolution
- ✅ **Mobile Optimization**: Designed for vertical viewing on mobile devices
- ✅ **Professional Output**: Ready for social media platforms

## Technical Specifications

- **Video Format**: MP4 (H.264)
- **Audio**: Mixed stereo (voiceover + BGM + CTA)
- **Subtitle Format**: ASS (Advanced SubStation Alpha)
- **Font**: Bangers-Regular, 19px
- **Transitions**: Crossfade, 0.5s duration
- **Clip Duration**: 4 seconds per segment
