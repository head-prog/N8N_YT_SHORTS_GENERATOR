import os
import uuid
import json
import tempfile
import traceback
from config import MOVIEPY_AVAILABLE, SUBTITLE_SIZE_MULTIPLIER
from audio_service import safe_load_audio, mix_audio_with_bgm_and_cta, transcribe_cta_audio
from utils import run_cmd, get_available_font, calculate_optimal_font_size, get_ffmpeg_font
from subtitle_service import segments_to_srt


def safe_load_video(path):
    """Safely load video with multiple fallback attempts and frame access validation"""
    if not MOVIEPY_AVAILABLE:
        raise Exception("MoviePy not available")
    
    from moviepy.editor import VideoFileClip
        
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


def create_video_with_subtitles_moviepy(video_path, audio_path, subtitle_segments=None, output_path=None, bgm_path=None, cta_path=None, bgm_volume=0.3, cta_volume=0.8):
    """Create video with audio, subtitles, BGM and CTA using MoviePy 2.2.1"""
    if not MOVIEPY_AVAILABLE:
        raise Exception("MoviePy not available")
    
    from moviepy.editor import TextClip, CompositeVideoClip, concatenate_audioclips, concatenate_videoclips
    
    try:
        print("📂 Loading video and audio files...")
        video = safe_load_video(video_path)
        
        # Mix audio with BGM and CTA if provided
        timing_info = None
        if bgm_path or cta_path:
            mixed_audio_path, final_duration, timing_info = mix_audio_with_bgm_and_cta(
                audio_path, bgm_path, cta_path, bgm_volume, cta_volume
            )
            audio = safe_load_audio(mixed_audio_path)
            print(f"🎵 Using mixed audio with BGM/CTA: {final_duration:.2f}s")
            
            # Generate CTA subtitles if CTA is present
            cta_segments = []
            if cta_path and timing_info and timing_info['cta_start'] is not None:
                print(f"📝 Generating CTA subtitles...")
                cta_segments = transcribe_cta_audio(cta_path, timing_info['cta_start'])
        else:
            audio = safe_load_audio(audio_path)
            final_duration = audio.duration
            cta_segments = []
        
        video_width = video.w
        video_height = video.h
        print(f"📐 Video dimensions: {video_width}x{video_height}")
        
        # Combine video and audio with improved audio processing
        print("🎵 Combining video and audio...")
        
        # Get audio and video durations
        audio_duration = audio.duration
        video_duration = video.duration
        print(f"📊 Audio: {audio_duration:.2f}s, Video: {video_duration:.2f}s")
        
        # If audio is longer than video (e.g., voice + CTA), extend video by looping
        if audio_duration > video_duration:
            print(f"🔄 Extending video to match audio duration ({audio_duration:.2f}s)")
            loops_needed = int(audio_duration / video_duration) + 1
            video_clips = [video] * loops_needed
            video = concatenate_videoclips(video_clips).subclip(0, audio_duration)
        elif audio_duration < video_duration:
            print("✂️ Trimming video to match audio duration")
            video = video.subclip(0, audio_duration)
        
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
        
        # Use the exact audio duration as final duration (includes CTA if present)
        final_duration = audio.duration
        
        print(f"📊 Final video duration: {final_duration:.2f}s")
        
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
                    
                    # Calculate font size for horizontal subtitle layout
                    text_length = len(text)
                    base_font_size = calculate_optimal_font_size(video_width, video_height, text_length)
                    font_size = int(base_font_size * 0.6 * SUBTITLE_SIZE_MULTIPLIER)  # Medium multiplier for balanced readability
                    font_size = max(12, min(font_size, 24))  # Medium bounds (12-24px) for balanced visibility
                    
                    # FORCE horizontal layout - always use horizontal text for better readability
                    words = text.split()
                    # Always use horizontal layout regardless of video orientation - CAPITALIZED
                    horizontal_text = text.upper()  # Capitalize the text
                    max_subtitle_width = int(video_width * 0.9)  # 90% of width for good coverage
                    max_subtitle_height = int(video_height * 0.15)  # 15% of height for visibility
                    print(f"🔄 Using CAPITALIZED horizontal layout: '{text}' -> '{horizontal_text}'")
                    
                    txt_clip = TextClip(
                        horizontal_text,
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


def create_video_with_subtitles_ffmpeg(video_path, audio_path, subtitle_segments=None, output_path=None, bgm_path=None, cta_path=None, bgm_volume=0.3, cta_volume=0.8):
    """Create video using FFmpeg with burned-in subtitles, BGM and CTA for maximum compatibility"""
    try:
        if not output_path:
            output_path = f"output_ffmpeg_{uuid.uuid4().hex[:8]}.mp4"
        
        # Mix audio with BGM and CTA if provided
        final_audio_path = audio_path
        timing_info = None
        if bgm_path or cta_path:
            mixed_audio_path, total_duration, timing_info = mix_audio_with_bgm_and_cta(
                audio_path, bgm_path, cta_path, bgm_volume, cta_volume
            )
            final_audio_path = mixed_audio_path
            print(f"🎵 Using mixed audio with BGM/CTA for FFmpeg: {total_duration:.2f}s")
        
        if not subtitle_segments:
            # Simple video + audio combination with explicit stream mapping
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', final_audio_path,  # Use mixed audio
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
            # Generate CTA subtitles if CTA audio is provided
            if cta_path and timing_info and timing_info.get('cta_start') is not None:
                print("🎤 Generating CTA subtitles...")
                cta_start = timing_info['cta_start']
                cta_subtitle_segments = transcribe_cta_audio(cta_path, cta_start)
                if cta_subtitle_segments:
                    print(f"📝 Adding {len(cta_subtitle_segments)} CTA subtitle segments")
                    subtitle_segments.extend(cta_subtitle_segments)
            
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
                        optimal_font_size = max(14, int(video_width * 0.04 * SUBTITLE_SIZE_MULTIPLIER))  # Medium font for vertical videos
                        margin_v = max(40, int(video_height * 0.05))  # Bottom margin (lower position)
                        margin_lr = max(30, int(video_width * 0.08))  # Side margins
                    else:
                        optimal_font_size = max(12, int(video_height * 0.03 * SUBTITLE_SIZE_MULTIPLIER))  # Medium font for horizontal
                        margin_v = max(30, int(video_height * 0.05))  # Lower position for horizontal too
                        margin_lr = max(80, int(video_width * 0.15))
                else:
                    optimal_font_size = int(18 * SUBTITLE_SIZE_MULTIPLIER)  # Medium default size
                    margin_v = 80
                    margin_lr = 60
            else:
                optimal_font_size = int(20 * SUBTITLE_SIZE_MULTIPLIER)  # Medium fallback font size
                margin_v = 100
                margin_lr = 50
            
            ffmpeg_font = get_ffmpeg_font()
            
            # FFmpeg command with subtitle burning optimized for vertical videos
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', final_audio_path,  # Use mixed audio
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
