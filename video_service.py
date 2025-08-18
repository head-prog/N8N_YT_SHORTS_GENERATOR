import os
import uuid
import json
import tempfile
import traceback
from config import MOVIEPY_AVAILABLE, SUBTITLE_SIZE_MULTIPLIER, CLIPS_FOLDER, CLIP_DURATION
from audio_service import safe_load_audio, mix_audio_with_bgm_and_cta, transcribe_cta_audio, load_voiceover, load_bgm, load_cta, merge_audio
from utils import run_cmd, get_available_font, calculate_optimal_font_size, get_ffmpeg_font, get_random_clips
from subtitle_service import segments_to_srt


def safe_load_video(path):
    """Safely load video with multiple fallback         # Step 5: Create final video with audio and subtitles
        print("� Creating final video with audio mix...")
        
        # Create a temporary video file with just the clips (no audio)
        temp_video_path = f"/tmp/temp_random_clips_{uuid.uuid4().hex[:8]}.mp4"
        video_clip.write_videofile(
            temp_video_path,
            codec='libx264',
            audio=False,  # Explicitly no audio
            verbose=False,
            logger=None
        )rame access validation"""
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
        # Write video with MoviePy first
        temp_output = output_path.replace('.mp4', '_temp.mp4')
        final_video.write_videofile(
            temp_output,
            fps=24,
            codec='libx264',
            audio_codec='aac',
            audio_bitrate='192k',  # High quality audio bitrate
            preset='medium',       # Balance between speed and quality
            verbose=False,
            logger=None,
            temp_audiofile='temp-audio.wav',  # Use temporary audio file for better quality
            remove_temp=True
        )
        
        # Post-process with FFmpeg to fix audio encoding issues
        print("🛠️ Post-processing video with FFmpeg for proper audio encoding...")
        import subprocess
        ffmpeg_cmd = [
            'ffmpeg', '-y', '-i', temp_output,
            '-c:v', 'copy',  # Copy video stream as-is
            '-c:a', 'aac',   # Re-encode audio
            '-ar', '44100',  # Sample rate
            '-b:a', '128k',  # Audio bitrate (changed to 128k for better quality)
            '-ac', '2',      # Stereo
            '-avoid_negative_ts', 'make_zero',
            '-fflags', '+genpts',
            output_path
        ]
        
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        
        # Cleanup temp file
        if os.path.exists(temp_output):
            os.unlink(temp_output)
        
        if result.returncode != 0:
            print(f"⚠️ FFmpeg post-processing failed: {result.stderr}")
            print("Using original MoviePy output...")
            # If FFmpeg fails, rename temp to final output
            if os.path.exists(temp_output):
                os.rename(temp_output, output_path)
        else:
            print("✅ FFmpeg post-processing successful!")
        
        # Verify final output exists
        if not os.path.exists(output_path):
            print("❌ Final video output missing!")
            return None
        
        # Cleanup
        video.close()
        audio.close()
        final_video.close()
        
        # Clean up subtitle clips if they exist
        if 'subtitle_clips' in locals() and subtitle_clips:
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


def create_video_with_random_clips(voiceover_path, bgm_path, output_path, cta_path=None, add_subtitles=True):
    """
    Create a video from random clips matched to voiceover length, with BGM and optional CTA.
    
    Args:
        voiceover_path (str): Path to voiceover audio file
        bgm_path (str): Path to background music file  
        output_path (str): Path for output video
        cta_path (str, optional): Path to CTA audio file
        add_subtitles (bool): Whether to add subtitles from voiceover transcription
    
    Returns:
        str: Output video path if successful, None if failed
    """
    if not MOVIEPY_AVAILABLE:
        raise Exception("MoviePy not available")
    
    from moviepy.editor import concatenate_videoclips
    
    try:
        print("🎬 Creating video with random clips...")
        
        # Step 1: Load voiceover and get duration
        voiceover_clip = load_voiceover(voiceover_path)
        voiceover_duration = voiceover_clip.duration
        print(f"🎤 Voiceover duration: {voiceover_duration:.2f}s")
        
        # Step 2: Get random clips to match voiceover duration
        print("🎲 Selecting random video clips...")
        random_clips = get_random_clips(CLIPS_FOLDER, CLIP_DURATION, voiceover_duration)
        
        if not random_clips:
            print("❌ No random clips available")
            return None
        
        print(f"📹 Selected {len(random_clips)} clips")
        
        # Step 3: Concatenate clips and trim to exact duration
        print("🔗 Concatenating video clips...")
        
        # Remove audio from all clips to avoid conflicts
        random_clips_no_audio = [clip.without_audio() for clip in random_clips]
        video_clip = concatenate_videoclips(random_clips_no_audio)
        
        # Trim to exact voiceover duration
        if video_clip.duration > voiceover_duration:
            video_clip = video_clip.subclip(0, voiceover_duration)
        
        print(f"✂️ Final video duration: {video_clip.duration:.2f}s")
        
        # Step 4: Generate subtitles if requested
        subtitle_segments = None
        if add_subtitles:
            print("📝 Generating subtitles from voiceover...")
            try:
                from whisper_service import transcribe_with_whisper
                from subtitle_service import create_segments_from_whisper_result
                
                # Transcribe the voiceover
                transcription_result = transcribe_with_whisper(voiceover_path)
                
                if transcription_result:
                    # Create subtitle segments
                    subtitle_segments = create_segments_from_whisper_result(
                        transcription_result, 
                        max_chars_per_segment=45, 
                        max_duration=5.0, 
                        max_words=3
                    )
                    print(f"✅ Generated {len(subtitle_segments)} subtitle segments")
                else:
                    print("⚠️ Transcription failed, skipping subtitles")
            except Exception as subtitle_error:
                print(f"⚠️ Subtitle generation failed: {subtitle_error}")
                # Fallback to A4F transcription
                try:
                    from whisper_service import transcribe_audio_with_a4f
                    from subtitle_service import create_segments_from_a4f_result
                    
                    print("🔄 Trying A4F transcription as fallback...")
                    transcription_result = transcribe_audio_with_a4f(voiceover_path)
                    
                    if transcription_result:
                        subtitle_segments = create_segments_from_a4f_result(
                            transcription_result,
                            max_chars_per_segment=45,
                            max_words=3
                        )
                        print(f"✅ Generated {len(subtitle_segments)} subtitle segments with A4F")
                    else:
                        print("⚠️ A4F transcription also failed, creating video without subtitles")
                except Exception as a4f_error:
                    print(f"⚠️ A4F transcription failed: {a4f_error}, creating video without subtitles")
        
        # Step 5: Create final video with audio and subtitles
        print("� Creating final video with audio mix...")
        
        # Create a temporary video file with just the clips
        temp_video_path = f"/tmp/temp_random_clips_{uuid.uuid4().hex[:8]}.mp4"
        video_clip.write_videofile(
            temp_video_path,
            codec='libx264',
            audio_codec='aac',
            audio_bitrate='128k',  # Lower bitrate for temp file
            audio_fps=44100,       # Standard audio sample rate
            verbose=False,
            logger=None
        )
        
        # Use existing function to add audio and subtitles
        final_video_path = create_video_with_subtitles_moviepy(
            temp_video_path,
            voiceover_path,
            subtitle_segments=subtitle_segments,
            output_path=output_path,
            bgm_path=bgm_path,
            cta_path=cta_path,
            bgm_volume=0.2,
            cta_volume=0.8
        )
        
        # Cleanup temporary files
        video_clip.close()
        voiceover_clip.close()
        for clip in random_clips:
            clip.close()
        for clip in random_clips_no_audio:
            clip.close()
        
        if os.path.exists(temp_video_path):
            os.unlink(temp_video_path)
        
        print(f"✅ Random clips video created successfully: {final_video_path}")
        return final_video_path
        
    except Exception as e:
        print(f"❌ Error creating video with random clips: {e}")
        traceback.print_exc()
        return None


def create_video_with_random_clips_fixed(voiceover_path, output_path, bgm_path=None, cta_path=None):
    """
    Create video with random clips using the proven direct MoviePy approach.
    This function replaces the problematic create_video_with_random_clips function.
    """
    try:
        print("🎬 Creating video with random clips (FIXED APPROACH)...")
        
        # Load voiceover to get duration
        voiceover = safe_load_audio(voiceover_path)
        voiceover_duration = voiceover.duration
        print(f"🎤 Voiceover duration: {voiceover_duration:.2f}s")
        
        # Get random clips (returns VideoFileClip objects)
        print(f"🎞️ Getting random clips from {CLIPS_FOLDER}...")
        video_clips = get_random_clips(CLIPS_FOLDER, CLIP_DURATION, voiceover_duration)
        
        if not video_clips:
            raise Exception("No valid video clips loaded")
        
        print(f"📂 Selected {len(video_clips)} clips")
        
        # Remove audio from clips and ensure proper duration
        print("🔄 Processing video clips...")
        processed_clips = []
        for i, clip in enumerate(video_clips):
            try:
                # Remove audio and ensure duration
                clip_no_audio = clip.without_audio()
                if clip_no_audio.duration >= CLIP_DURATION:
                    clip_no_audio = clip_no_audio.subclip(0, CLIP_DURATION)
                processed_clips.append(clip_no_audio)
                print(f"✅ Processed clip {i+1}: {clip_no_audio.duration:.2f}s")
            except Exception as e:
                print(f"❌ Failed to process clip {i+1}: {e}")
                continue
        
        # Concatenate video clips
        print("🔗 Concatenating video clips...")
        if not MOVIEPY_AVAILABLE:
            raise Exception("MoviePy not available")
        
        from moviepy.editor import concatenate_videoclips
        video_clip = concatenate_videoclips(processed_clips)
        print(f"📹 Total video duration: {video_clip.duration:.2f}s")
        
        # Handle audio mixing
        if bgm_path or cta_path:
            print("🎵 Mixing audio with BGM/CTA...")
            mixed_audio_path, final_duration, timing_info = mix_audio_with_bgm_and_cta(
                voiceover_path, bgm_path, cta_path, 0.2, 0.8
            )
            audio = safe_load_audio(mixed_audio_path)
            print(f"🎵 Mixed audio duration: {final_duration:.2f}s")
        else:
            audio = voiceover
            final_duration = voiceover_duration
        
        # Extend video to match audio duration if needed
        if video_clip.duration < final_duration:
            print(f"🔄 Extending video to match audio duration ({final_duration:.2f}s)")
            loops_needed = int(final_duration / video_clip.duration) + 1
            video_clips_extended = [video_clip] * loops_needed
            video_clip = concatenate_videoclips(video_clips_extended).subclip(0, final_duration)
        elif video_clip.duration > final_duration:
            video_clip = video_clip.subclip(0, final_duration)
        
        # Combine video and audio
        final_video = video_clip.set_audio(audio)
        print(f"📊 Final video: {final_video.duration:.2f}s")
        
        # Write video
        print(f"🎬 Writing video to {output_path}...")
        final_video.write_videofile(
            output_path,
            fps=24,
            codec='libx264',
            audio_codec='aac',
            audio_bitrate='128k',
            verbose=False,
            logger=None
        )
        
        # Cleanup
        for clip in video_clips:
            clip.close()
        for clip in processed_clips:
            clip.close()
        video_clip.close()
        final_video.close()
        audio.close()
        if bgm_path or cta_path:
            voiceover.close()
        
        print(f"✅ Video created successfully: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"❌ Error creating video: {e}")
        traceback.print_exc()
        return None


def create_video_with_random_clips_and_subtitles(voiceover_path, output_path, bgm_path=None, cta_path=None):
    """
    Create video with random clips, audio mixing, and dynamic subtitles for voiceover and CTA.
    Subtitles are timed so CTA subtitles start exactly when voiceover ends.
    """
    try:
        print("🎬 Creating video with random clips and DYNAMIC SUBTITLES...")
        
        # Import required modules
        if not MOVIEPY_AVAILABLE:
            raise Exception("MoviePy not available")
        
        from moviepy.editor import concatenate_videoclips, CompositeVideoClip, TextClip
        from whisper_service import transcribe_with_whisper
        
        # Load voiceover to get duration
        voiceover = safe_load_audio(voiceover_path)
        voiceover_duration = voiceover.duration
        print(f"🎤 Voiceover duration: {voiceover_duration:.2f}s")
        
        # Get random clips (returns VideoFileClip objects)
        print(f"🎞️ Getting random clips from {CLIPS_FOLDER}...")
        video_clips = get_random_clips(CLIPS_FOLDER, CLIP_DURATION, voiceover_duration)
        
        if not video_clips:
            raise Exception("No valid video clips loaded")
        
        print(f"📂 Selected {len(video_clips)} clips")
        
        # Remove audio from clips and ensure proper duration
        print("🔄 Processing video clips...")
        processed_clips = []
        for i, clip in enumerate(video_clips):
            try:
                # Remove audio and ensure duration
                clip_no_audio = clip.without_audio()
                if clip_no_audio.duration >= CLIP_DURATION:
                    clip_no_audio = clip_no_audio.subclip(0, CLIP_DURATION)
                processed_clips.append(clip_no_audio)
                print(f"✅ Processed clip {i+1}: {clip_no_audio.duration:.2f}s")
            except Exception as e:
                print(f"❌ Failed to process clip {i+1}: {e}")
                continue
        
        # Concatenate video clips
        print("🔗 Concatenating video clips...")
        video_clip = concatenate_videoclips(processed_clips)
        print(f"📹 Total video duration: {video_clip.duration:.2f}s")
        
        # Handle audio mixing and get timing info
        timing_info = {'voiceover_duration': voiceover_duration, 'cta_start': voiceover_duration, 'cta_duration': 0}
        
        if bgm_path or cta_path:
            print("🎵 Mixing audio with BGM/CTA...")
            mixed_audio_path, final_duration, timing_info = mix_audio_with_bgm_and_cta(
                voiceover_path, bgm_path, cta_path, 0.2, 0.8
            )
            audio = safe_load_audio(mixed_audio_path)
            print(f"🎵 Mixed audio duration: {final_duration:.2f}s")
            
            # Update timing info if CTA is present
            if cta_path:
                cta_audio = safe_load_audio(cta_path)
                timing_info['cta_duration'] = cta_audio.duration
                timing_info['cta_start'] = voiceover_duration
                print(f"📢 CTA timing: starts at {timing_info['cta_start']:.2f}s, duration {timing_info['cta_duration']:.2f}s")
                cta_audio.close()
        else:
            audio = voiceover
            final_duration = voiceover_duration
        
        # Extend video to match audio duration if needed
        if video_clip.duration < final_duration:
            print(f"🔄 Extending video to match audio duration ({final_duration:.2f}s)")
            loops_needed = int(final_duration / video_clip.duration) + 1
            video_clips_extended = [video_clip] * loops_needed
            video_clip = concatenate_videoclips(video_clips_extended).subclip(0, final_duration)
        elif video_clip.duration > final_duration:
            video_clip = video_clip.subclip(0, final_duration)
        
        # Generate subtitles for voiceover
        print("📝 Generating subtitles for voiceover...")
        voiceover_result = transcribe_with_whisper(voiceover_path)
        voiceover_segments = voiceover_result['segments'] if voiceover_result and 'segments' in voiceover_result else []
        
        # Generate subtitles for CTA if present
        cta_segments = []
        if cta_path and timing_info['cta_duration'] > 0:
            print("📝 Generating subtitles for CTA...")
            cta_result = transcribe_with_whisper(cta_path)
            cta_segments = cta_result['segments'] if cta_result and 'segments' in cta_result else []
            if cta_segments:
                # Adjust CTA segment timings to start after voiceover
                for segment in cta_segments:
                    segment['start'] += timing_info['cta_start']
                    segment['end'] += timing_info['cta_start']
                print(f"✅ Adjusted {len(cta_segments)} CTA subtitle segments to start at {timing_info['cta_start']:.2f}s")
        
        # Create subtitle clips
        subtitle_clips = []
        video_width = video_clip.w
        video_height = video_clip.h
        
        # Add voiceover subtitles
        if voiceover_segments:
            print(f"🎬 Creating {len(voiceover_segments)} voiceover subtitle clips...")
            for i, segment in enumerate(voiceover_segments):
                try:
                    text = segment['text'].strip()
                    if not text:
                        continue
                    
                    start_time = segment['start']
                    end_time = segment['end']
                    duration = end_time - start_time
                    
                    # Create text clip for voiceover (white text with black outline)
                    font_size = max(int(video_height * 0.06), 24)  # Dynamic font size
                    txt_clip = TextClip(
                        text.upper(),
                        fontsize=font_size,
                        color='white',
                        stroke_color='black',
                        stroke_width=2,
                        size=(int(video_width * 0.9), None),
                        method='caption',
                        align='center'
                    )
                    
                    # Position at bottom of screen
                    margin_bottom = int(video_height * 0.1)
                    x_pos = (video_width - txt_clip.w) // 2
                    y_pos = video_height - txt_clip.h - margin_bottom
                    
                    txt_clip = txt_clip.set_position((x_pos, y_pos)).set_start(start_time).set_duration(duration)
                    subtitle_clips.append(txt_clip)
                    
                    print(f"✅ Voiceover subtitle {i+1}: '{text[:30]}...' ({start_time:.2f}s-{end_time:.2f}s)")
                    
                except Exception as e:
                    print(f"❌ Failed to create voiceover subtitle {i+1}: {e}")
                    continue
        
        # Add CTA subtitles
        if cta_segments:
            print(f"🎬 Creating {len(cta_segments)} CTA subtitle clips...")
            for i, segment in enumerate(cta_segments):
                try:
                    text = segment['text'].strip()
                    if not text:
                        continue
                    
                    start_time = segment['start']
                    end_time = segment['end']
                    duration = end_time - start_time
                    
                    # Create text clip for CTA (yellow text with black outline for distinction)
                    font_size = max(int(video_height * 0.07), 26)  # Slightly larger for CTA
                    txt_clip = TextClip(
                        text.upper(),
                        fontsize=font_size,
                        color='yellow',
                        stroke_color='black',
                        stroke_width=3,
                        size=(int(video_width * 0.9), None),
                        method='caption',
                        align='center'
                    )
                    
                    # Position at bottom of screen (same as voiceover)
                    margin_bottom = int(video_height * 0.1)
                    x_pos = (video_width - txt_clip.w) // 2
                    y_pos = video_height - txt_clip.h - margin_bottom
                    
                    txt_clip = txt_clip.set_position((x_pos, y_pos)).set_start(start_time).set_duration(duration)
                    subtitle_clips.append(txt_clip)
                    
                    print(f"✅ CTA subtitle {i+1}: '{text[:30]}...' ({start_time:.2f}s-{end_time:.2f}s)")
                    
                except Exception as e:
                    print(f"❌ Failed to create CTA subtitle {i+1}: {e}")
                    continue
        
        # Combine video with audio and subtitles
        print("🎬 Combining video, audio, and subtitles...")
        video_with_audio = video_clip.set_audio(audio)
        
        if subtitle_clips:
            final_video = CompositeVideoClip([video_with_audio] + subtitle_clips)
            print(f"✅ Added {len(subtitle_clips)} subtitle clips to video")
        else:
            final_video = video_with_audio
            print("⚠️ No subtitles added")
        
        print(f"📊 Final video: {final_video.duration:.2f}s")
        
        # Write video
        print(f"🎬 Writing video to {output_path}...")
        final_video.write_videofile(
            output_path,
            fps=24,
            codec='libx264',
            audio_codec='aac',
            audio_bitrate='128k',
            verbose=False,
            logger=None
        )
        
        # Cleanup
        for clip in video_clips:
            clip.close()
        for clip in processed_clips:
            clip.close()
        for clip in subtitle_clips:
            clip.close()
        video_clip.close()
        final_video.close()
        audio.close()
        if bgm_path or cta_path:
            voiceover.close()
        
        print(f"✅ Video with dynamic subtitles created successfully: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"❌ Error creating video with subtitles: {e}")
        traceback.print_exc()
        return None


def create_video_with_random_clips_and_subtitles_optimized(voiceover_path, output_path, bgm_path=None, cta_path=None):
    """
    OPTIMIZED version: Create video with random clips and dynamic subtitles.
    Performance improvements:
    - Reduced subtitle clip count by merging nearby segments
    - Lower subtitle resolution for faster processing
    - Simplified text rendering
    - Faster video writing settings
    """
    try:
        print("🎬 Creating video with random clips and OPTIMIZED SUBTITLES...")
        
        # Import required modules
        if not MOVIEPY_AVAILABLE:
            raise Exception("MoviePy not available")
        
        from moviepy.editor import concatenate_videoclips, CompositeVideoClip, TextClip
        from whisper_service import transcribe_with_whisper
        
        # Load voiceover to get duration
        voiceover = safe_load_audio(voiceover_path)
        voiceover_duration = voiceover.duration
        print(f"🎤 Voiceover duration: {voiceover_duration:.2f}s")
        
        # Get random clips (returns VideoFileClip objects)
        print(f"🎞️ Getting random clips from {CLIPS_FOLDER}...")
        video_clips = get_random_clips(CLIPS_FOLDER, CLIP_DURATION, voiceover_duration)
        
        if not video_clips:
            raise Exception("No valid video clips loaded")
        
        print(f"📂 Selected {len(video_clips)} clips")
        
        # Remove audio from clips and ensure proper duration
        print("🔄 Processing video clips...")
        processed_clips = []
        for i, clip in enumerate(video_clips):
            try:
                # Remove audio and ensure duration
                clip_no_audio = clip.without_audio()
                if clip_no_audio.duration >= CLIP_DURATION:
                    clip_no_audio = clip_no_audio.subclip(0, CLIP_DURATION)
                processed_clips.append(clip_no_audio)
                print(f"✅ Processed clip {i+1}: {clip_no_audio.duration:.2f}s")
            except Exception as e:
                print(f"❌ Failed to process clip {i+1}: {e}")
                continue
        
        # Concatenate video clips
        print("🔗 Concatenating video clips...")
        video_clip = concatenate_videoclips(processed_clips)
        print(f"📹 Total video duration: {video_clip.duration:.2f}s")
        
        # Handle audio mixing and get timing info
        timing_info = {'voiceover_duration': voiceover_duration, 'cta_start': voiceover_duration, 'cta_duration': 0}
        
        if bgm_path or cta_path:
            print("🎵 Mixing audio with BGM/CTA...")
            mixed_audio_path, final_duration, timing_info = mix_audio_with_bgm_and_cta(
                voiceover_path, bgm_path, cta_path, 0.2, 0.8
            )
            audio = safe_load_audio(mixed_audio_path)
            print(f"🎵 Mixed audio duration: {final_duration:.2f}s")
            
            # Update timing info if CTA is present
            if cta_path:
                cta_audio = safe_load_audio(cta_path)
                timing_info['cta_duration'] = cta_audio.duration
                timing_info['cta_start'] = voiceover_duration
                print(f"📢 CTA timing: starts at {timing_info['cta_start']:.2f}s, duration {timing_info['cta_duration']:.2f}s")
                cta_audio.close()
        else:
            audio = voiceover
            final_duration = voiceover_duration
        
        # Extend video to match audio duration if needed
        if video_clip.duration < final_duration:
            print(f"🔄 Extending video to match audio duration ({final_duration:.2f}s)")
            loops_needed = int(final_duration / video_clip.duration) + 1
            video_clips_extended = [video_clip] * loops_needed
            video_clip = concatenate_videoclips(video_clips_extended).subclip(0, final_duration)
        elif video_clip.duration > final_duration:
            video_clip = video_clip.subclip(0, final_duration)
        
        # OPTIMIZATION: Combine video and audio first, then add subtitles
        print("🎬 Combining video and audio...")
        video_with_audio = video_clip.set_audio(audio)
        
        # Generate subtitles for voiceover
        print("📝 Generating subtitles for voiceover...")
        voiceover_result = transcribe_with_whisper(voiceover_path)
        voiceover_segments = voiceover_result['segments'] if voiceover_result and 'segments' in voiceover_result else []
        
        # OPTIMIZATION: Merge nearby segments to reduce subtitle clip count
        def merge_nearby_segments(segments, max_gap=1.0, max_duration=5.0):
            if not segments:
                return []
            
            merged = []
            current = segments[0].copy()
            
            for seg in segments[1:]:
                gap = seg['start'] - current['end']
                combined_duration = seg['end'] - current['start']
                
                # Merge if gap is small and combined duration is reasonable
                if gap <= max_gap and combined_duration <= max_duration:
                    current['end'] = seg['end']
                    current['text'] += " " + seg['text'].strip()
                else:
                    merged.append(current)
                    current = seg.copy()
            
            merged.append(current)
            return merged
        
        # Apply optimization to voiceover segments
        if voiceover_segments:
            original_count = len(voiceover_segments)
            voiceover_segments = merge_nearby_segments(voiceover_segments)
            print(f"🔧 Optimized: {original_count} → {len(voiceover_segments)} voiceover segments")
        
        # Generate subtitles for CTA if present
        cta_segments = []
        if cta_path and timing_info['cta_duration'] > 0:
            print("📝 Generating subtitles for CTA...")
            cta_result = transcribe_with_whisper(cta_path)
            cta_segments = cta_result['segments'] if cta_result and 'segments' in cta_result else []
            if cta_segments:
                # Adjust CTA segment timings to start after voiceover
                for segment in cta_segments:
                    segment['start'] += timing_info['cta_start']
                    segment['end'] += timing_info['cta_start']
                
                # Apply optimization to CTA segments
                original_count = len(cta_segments)
                cta_segments = merge_nearby_segments(cta_segments)
                print(f"🔧 Optimized: {original_count} → {len(cta_segments)} CTA segments")
                print(f"✅ Adjusted {len(cta_segments)} CTA subtitle segments to start at {timing_info['cta_start']:.2f}s")
        
        # Create subtitle clips with optimizations
        subtitle_clips = []
        video_width = video_clip.w
        video_height = video_clip.h
        
        # OPTIMIZATION: Use smaller font and simpler styling for faster rendering
        base_font_size = max(int(video_height * 0.04), 18)  # Smaller font
        
        # Add voiceover subtitles
        if voiceover_segments:
            print(f"🎬 Creating {len(voiceover_segments)} optimized voiceover subtitle clips...")
            for i, segment in enumerate(voiceover_segments):
                try:
                    text = segment['text'].strip()
                    if not text:
                        continue
                    
                    start_time = segment['start']
                    end_time = segment['end']
                    duration = end_time - start_time
                    
                    # OPTIMIZATION: Simpler text clip creation
                    txt_clip = TextClip(
                        text.upper()[:100],  # Limit text length
                        fontsize=base_font_size,
                        color='white',
                        stroke_color='black',
                        stroke_width=1,  # Thinner stroke
                        method='caption',
                        align='center'
                    )
                    
                    # OPTIMIZATION: Fixed positioning to avoid calculations
                    margin_bottom = int(video_height * 0.08)
                    x_pos = (video_width - txt_clip.w) // 2
                    y_pos = video_height - txt_clip.h - margin_bottom
                    
                    txt_clip = txt_clip.set_position((x_pos, y_pos)).set_start(start_time).set_duration(duration)
                    subtitle_clips.append(txt_clip)
                    
                    print(f"✅ Voiceover subtitle {i+1}: '{text[:30]}...' ({start_time:.2f}s-{end_time:.2f}s)")
                    
                except Exception as e:
                    print(f"❌ Failed to create voiceover subtitle {i+1}: {e}")
                    continue
        
        # Add CTA subtitles
        if cta_segments:
            print(f"🎬 Creating {len(cta_segments)} optimized CTA subtitle clips...")
            for i, segment in enumerate(cta_segments):
                try:
                    text = segment['text'].strip()
                    if not text:
                        continue
                    
                    start_time = segment['start']
                    end_time = segment['end']
                    duration = end_time - start_time
                    
                    # OPTIMIZATION: Simpler CTA text clip
                    txt_clip = TextClip(
                        text.upper()[:100],  # Limit text length
                        fontsize=base_font_size + 2,  # Slightly larger for CTA
                        color='yellow',
                        stroke_color='black',
                        stroke_width=1,
                        method='caption',
                        align='center'
                    )
                    
                    margin_bottom = int(video_height * 0.08)
                    x_pos = (video_width - txt_clip.w) // 2
                    y_pos = video_height - txt_clip.h - margin_bottom
                    
                    txt_clip = txt_clip.set_position((x_pos, y_pos)).set_start(start_time).set_duration(duration)
                    subtitle_clips.append(txt_clip)
                    
                    print(f"✅ CTA subtitle {i+1}: '{text[:30]}...' ({start_time:.2f}s-{end_time:.2f}s)")
                    
                except Exception as e:
                    print(f"❌ Failed to create CTA subtitle {i+1}: {e}")
                    continue
        
        # Combine everything
        if subtitle_clips:
            print(f"🎬 Combining video with {len(subtitle_clips)} subtitle clips...")
            final_video = CompositeVideoClip([video_with_audio] + subtitle_clips)
            print(f"✅ Added {len(subtitle_clips)} subtitle clips to video")
        else:
            final_video = video_with_audio
            print("⚠️ No subtitles added")
        
        print(f"📊 Final video: {final_video.duration:.2f}s")
        
        # OPTIMIZATION: Faster video writing settings
        print(f"🎬 Writing video to {output_path} with optimized settings...")
        final_video.write_videofile(
            output_path,
            fps=24,
            codec='libx264',
            audio_codec='aac',
            audio_bitrate='128k',
            preset='fast',  # Faster encoding preset
            verbose=False,
            logger=None,
            threads=4  # Use multiple threads
        )
        
        # Cleanup
        for clip in video_clips:
            clip.close()
        for clip in processed_clips:
            clip.close()
        for clip in subtitle_clips:
            clip.close()
        video_clip.close()
        video_with_audio.close()
        final_video.close()
        audio.close()
        if bgm_path or cta_path:
            voiceover.close()
        
        print(f"✅ Optimized video with dynamic subtitles created: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"❌ Error creating optimized video with subtitles: {e}")
        traceback.print_exc()
        return None


def create_video_with_ffmpeg_subtitles(voiceover_path, output_path, bgm_path=None, cta_path=None):
    """
    FFMPEG-based ultra-fast subtitle generation.
    Uses FFmpeg subtitle filter instead of MoviePy TextClip for 10x speed improvement.
    """
    import subprocess
    import json
    import tempfile
    
    try:
        print("🚀 Creating video with FFmpeg-based ULTRA FAST subtitles...")
        
        # Import required modules
        if not MOVIEPY_AVAILABLE:
            raise Exception("MoviePy not available")
        
        from moviepy.editor import concatenate_videoclips
        from whisper_service import transcribe_with_whisper
        
        # Load voiceover to get duration
        voiceover = safe_load_audio(voiceover_path)
        voiceover_duration = voiceover.duration
        print(f"🎤 Voiceover duration: {voiceover_duration:.2f}s")
        
        # Get random clips at LOWER RESOLUTION for speed
        print(f"🎞️ Getting random clips from {CLIPS_FOLDER}...")
        video_clips = get_random_clips(CLIPS_FOLDER, CLIP_DURATION, voiceover_duration)
        
        if not video_clips:
            raise Exception("No valid video clips loaded")
        
        print(f"📂 Selected {len(video_clips)} clips")
        
        # Process clips at original resolution (as requested)
        print("🔄 Processing video clips at original resolution...")
        processed_clips = []
        for i, clip in enumerate(video_clips):
            try:
                # Keep original resolution and remove audio only
                clip_no_audio = clip.without_audio()
                if clip_no_audio.duration >= CLIP_DURATION:
                    clip_no_audio = clip_no_audio.subclip(0, CLIP_DURATION)
                processed_clips.append(clip_no_audio)
                print(f"✅ Processed clip {i+1}: {clip_no_audio.duration:.2f}s ({clip_no_audio.w}x{clip_no_audio.h})")
            except Exception as e:
                print(f"❌ Failed to process clip {i+1}: {e}")
                continue
        
        # Concatenate video clips
        print("🔗 Concatenating video clips...")
        video_clip = concatenate_videoclips(processed_clips)
        print(f"📹 Total video duration: {video_clip.duration:.2f}s")
        
        # Handle audio mixing
        timing_info = {'voiceover_duration': voiceover_duration, 'cta_start': voiceover_duration, 'cta_duration': 0}
        
        if bgm_path or cta_path:
            print("🎵 Mixing audio with BGM/CTA...")
            mixed_audio_path, final_duration, timing_info = mix_audio_with_bgm_and_cta(
                voiceover_path, bgm_path, cta_path, 0.4, 0.8
            )
            audio = safe_load_audio(mixed_audio_path)
            print(f"🎵 Mixed audio duration: {final_duration:.2f}s")
            
            if cta_path:
                cta_audio = safe_load_audio(cta_path)
                timing_info['cta_duration'] = cta_audio.duration
                timing_info['cta_start'] = voiceover_duration
                print(f"📢 CTA timing: starts at {timing_info['cta_start']:.2f}s, duration {timing_info['cta_duration']:.2f}s")
                cta_audio.close()
        else:
            audio = voiceover
            final_duration = voiceover_duration
        
        # Extend video to match audio duration if needed
        if video_clip.duration < final_duration:
            print(f"🔄 Extending video to match audio duration ({final_duration:.2f}s)")
            loops_needed = int(final_duration / video_clip.duration) + 1
            video_clips_extended = [video_clip] * loops_needed
            video_clip = concatenate_videoclips(video_clips_extended).subclip(0, final_duration)
        elif video_clip.duration > final_duration:
            video_clip = video_clip.subclip(0, final_duration)
        
        # Create intermediate video without subtitles first
        temp_video_path = tempfile.mktemp(suffix='.mp4')
        print("🎬 Creating intermediate video without subtitles...")
        
        video_with_audio = video_clip.set_audio(audio)
        video_with_audio.write_videofile(
            temp_video_path,
            fps=24,
            codec='libx264',
            audio_codec='aac',
            preset='fast',
            verbose=False,
            logger=None
        )
        
        # ENHANCED: Generate pause-aware subtitles that respect natural speech patterns
        print("📝 Generating PAUSE-AWARE subtitles that respect natural speech timing...")
        
        # Try enhanced pause-aware subtitles first
        try:
            from enhanced_subtitle_service import create_enhanced_ass_subtitles_with_pauses
            
            print("🎯 Using ENHANCED pause-aware subtitle system...")
            ass_file_path = create_enhanced_ass_subtitles_with_pauses(voiceover_path, cta_path)
            
            if ass_file_path and os.path.exists(ass_file_path):
                print("✅ Enhanced pause-aware subtitles created successfully!")
                
                # Apply enhanced ASS subtitles with FFmpeg
                final_output_path = temp_video_path.replace('.mp4', '_with_enhanced_subs.mp4')
                
                ffmpeg_cmd = [
                    'ffmpeg', '-y',
                    '-i', temp_video_path,
                    '-vf', f"ass={ass_file_path}",
                    '-c:a', 'copy',
                    '-c:v', 'libx264',
                    '-preset', 'fast',
                    final_output_path
                ]
                
                print("🎬 Adding enhanced pause-aware subtitles with FFmpeg...")
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    print("✅ Enhanced pause-aware subtitles applied successfully!")
                    # Move to final output
                    import shutil
                    shutil.move(final_output_path, output_path)
                    return output_path
                else:
                    print(f"⚠️  Enhanced subtitle processing failed: {result.stderr}")
                    print("🔄 Falling back to standard subtitles...")
            
        except Exception as e:
            print(f"⚠️  Enhanced pause-aware subtitles failed: {e}")
            print("🔄 Using standard subtitle system...")
        
        # ACCURACY OPTIMIZATION: Use large-v3-turbo Whisper model for precise synchronization
        print("📝 Generating standard subtitles with LARGE-V3-TURBO Whisper model...")
        os.environ['WHISPER_MODEL_SIZE'] = 'large-v3-turbo'
        
        # Generate transcriptions with caching
        cache_dir = "transcription_cache"
        os.makedirs(cache_dir, exist_ok=True)
        
        # Cache key based on file modification time
        voiceover_mtime = os.path.getmtime(voiceover_path)
        cache_key = f"{os.path.basename(voiceover_path)}_{voiceover_mtime}"
        cache_file = os.path.join(cache_dir, f"{cache_key}.json")
        
        if os.path.exists(cache_file):
            print("⚡ Using cached voiceover transcription...")
            with open(cache_file, 'r') as f:
                voiceover_result = json.load(f)
        else:
            print("🤖 Transcribing voiceover with large-v3-turbo model for precise timing...")
            voiceover_result = transcribe_with_whisper(voiceover_path)
            # Cache the result
            with open(cache_file, 'w') as f:
                json.dump(voiceover_result, f)
            print("💾 Transcription cached for future use")
        
        voiceover_segments = voiceover_result['segments'] if voiceover_result and 'segments' in voiceover_result else []
        
        # OPTIMIZATION: Split segments into 2-3 word chunks
        def split_into_word_chunks(segments, max_words=3):
            """Split segments into smaller chunks of 2-3 words each"""
            chunked_segments = []
            
            for segment in segments:
                text = segment['text'].strip()
                words = text.split()
                
                if len(words) <= max_words:
                    # Keep as is if already small enough
                    chunked_segments.append(segment)
                else:
                    # Split into chunks
                    start_time = segment['start']
                    end_time = segment['end']
                    duration = end_time - start_time
                    
                    # Calculate time per word
                    time_per_word = duration / len(words)
                    
                    for i in range(0, len(words), max_words):
                        chunk_words = words[i:i + max_words]
                        chunk_text = ' '.join(chunk_words)
                        
                        # Calculate timing for this chunk
                        chunk_start = start_time + (i * time_per_word)
                        chunk_end = start_time + ((i + len(chunk_words)) * time_per_word)
                        
                        chunk_segment = {
                            'text': chunk_text,
                            'start': chunk_start,
                            'end': min(chunk_end, end_time)  # Don't exceed original end time
                        }
                        chunked_segments.append(chunk_segment)
            
            return chunked_segments
        
        # Apply word chunking to voiceover segments
        if voiceover_segments:
            original_count = len(voiceover_segments)
            voiceover_segments = split_into_word_chunks(voiceover_segments, max_words=3)
            print(f"🔧 Split into word chunks: {original_count} → {len(voiceover_segments)} segments (2-3 words each)")
        
        # Generate CTA transcription if needed
        cta_segments = []
        if cta_path and timing_info['cta_duration'] > 0:
            print("📝 Generating CTA subtitles...")
            cta_mtime = os.path.getmtime(cta_path)
            cta_cache_key = f"{os.path.basename(cta_path)}_{cta_mtime}"
            cta_cache_file = os.path.join(cache_dir, f"{cta_cache_key}.json")
            
            if os.path.exists(cta_cache_file):
                print("⚡ Using cached CTA transcription...")
                with open(cta_cache_file, 'r') as f:
                    cta_result = json.load(f)
            else:
                print("🤖 Transcribing CTA with large-v3-turbo model for precise timing...")
                cta_result = transcribe_with_whisper(cta_path)
                with open(cta_cache_file, 'w') as f:
                    json.dump(cta_result, f)
                print("💾 CTA transcription cached")
            
            cta_segments = cta_result['segments'] if cta_result and 'segments' in cta_result else []
            if cta_segments:
                # Adjust CTA timings first
                for segment in cta_segments:
                    segment['start'] += timing_info['cta_start']
                    segment['end'] += timing_info['cta_start']
                
                # Apply word chunking to CTA segments as well
                original_cta_count = len(cta_segments)
                cta_segments = split_into_word_chunks(cta_segments, max_words=3)
                print(f"🔧 Split CTA into word chunks: {original_cta_count} → {len(cta_segments)} segments (2-3 words each)")
                print(f"✅ Adjusted {len(cta_segments)} CTA segments")
        
        # Create SRT subtitle file for FFmpeg
        srt_file = tempfile.mktemp(suffix='.srt')
        print("📝 Creating SRT subtitle file...")
        
        with open(srt_file, 'w', encoding='utf-8') as f:
            subtitle_index = 1
            
            # Add voiceover subtitles
            for segment in voiceover_segments:
                text = segment['text'].strip()
                if not text:
                    continue
                
                start_time = segment['start']
                end_time = segment['end']
                
                # Convert to SRT time format
                start_srt = f"{int(start_time//3600):02d}:{int((start_time%3600)//60):02d}:{int(start_time%60):02d},{int((start_time%1)*1000):03d}"
                end_srt = f"{int(end_time//3600):02d}:{int((end_time%3600)//60):02d}:{int(end_time%60):02d},{int((end_time%1)*1000):03d}"
                
                f.write(f"{subtitle_index}\n")
                f.write(f"{start_srt} --> {end_srt}\n")
                f.write(f"{text.upper()}\n\n")
                subtitle_index += 1
            
            # Add CTA subtitles in yellow
            for segment in cta_segments:
                text = segment['text'].strip()
                if not text:
                    continue
                
                start_time = segment['start']
                end_time = segment['end']
                
                start_srt = f"{int(start_time//3600):02d}:{int((start_time%3600)//60):02d}:{int(start_time%60):02d},{int((start_time%1)*1000):03d}"
                end_srt = f"{int(end_time//3600):02d}:{int((end_time%3600)//60):02d}:{int(end_time%60):02d},{int((end_time%1)*1000):03d}"
                
                f.write(f"{subtitle_index}\n")
                f.write(f"{start_srt} --> {end_srt}\n")
                f.write(f"<font color='yellow'>{text.upper()}</font>\n\n")
                subtitle_index += 1
        
        print(f"✅ Created SRT file with {subtitle_index-1} subtitles")
        
        # Use FFmpeg to add subtitles with ASS/SRT file for better performance
        print("🎯 Adding PERFECTLY CENTERED subtitles with ASS format...")
        
        # Create ASS subtitle file for better positioning control
        ass_file = tempfile.mktemp(suffix='.ass')
        
        with open(ass_file, 'w', encoding='utf-8') as f:
            # ASS format header with large font and perfect centering
            f.write("[Script Info]\n")
            f.write("Title: Video Subtitles\n")
            f.write("ScriptType: v4.00+\n\n")
            
            f.write("[V4+ Styles]\n")
            f.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
            # Style for voiceover - white text, medium font (18px), TRUE CENTER (alignment=5 = middle center)
            f.write("Style: Voiceover,Arial,18,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,2,0,5,0,0,0,1\n")
            # Style for CTA - yellow text, medium font (18px), TRUE CENTER (alignment=5 = middle center)  
            f.write("Style: CTA,Arial,18,&H0000FFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,2,0,5,0,0,0,1\n\n")
            
            f.write("[Events]\n")
            f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
            
            # Add voiceover subtitles
            for segment in voiceover_segments:
                text = segment['text'].strip()
                if not text:
                    continue
                    
                start_time = segment['start']
                end_time = segment['end']
                
                # Convert to ASS time format (h:mm:ss.cc)
                start_ass = f"{int(start_time//3600)}:{int((start_time%3600)//60):02d}:{start_time%60:05.2f}"
                end_ass = f"{int(end_time//3600)}:{int((end_time%3600)//60):02d}:{end_time%60:05.2f}"
                
                f.write(f"Dialogue: 0,{start_ass},{end_ass},Voiceover,,0,0,0,,{text.upper()}\n")
            
            # Add CTA subtitles
            for segment in cta_segments:
                text = segment['text'].strip()
                if not text:
                    continue
                    
                start_time = segment['start']
                end_time = segment['end']
                
                # Convert to ASS time format
                start_ass = f"{int(start_time//3600)}:{int((start_time%3600)//60):02d}:{start_time%60:05.2f}"
                end_ass = f"{int(end_time//3600)}:{int((end_time%3600)//60):02d}:{end_time%60:05.2f}"
                
                f.write(f"Dialogue: 0,{start_ass},{end_ass},CTA,,0,0,0,,{text.upper()}\n")
        
        print(f"✅ Created ASS subtitle file with {len(voiceover_segments) + len(cta_segments)} subtitles")
        
        ffmpeg_cmd = [
            'ffmpeg', '-y',
            '-i', temp_video_path,
            '-vf', f"ass={ass_file}",
            '-c:a', 'copy',  # Copy audio without re-encoding
            '-preset', 'ultrafast',
            output_path
        ]
        
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ FFmpeg subtitle processing completed successfully!")
        else:
            print(f"❌ FFmpeg error: {result.stderr}")
            raise Exception(f"FFmpeg failed: {result.stderr}")
        
        # Cleanup
        for clip in video_clips:
            clip.close()
        for clip in processed_clips:
            clip.close()
        video_clip.close()
        video_with_audio.close()
        audio.close()
        if bgm_path or cta_path:
            voiceover.close()
        
        # Remove temporary files
        try:
            os.remove(temp_video_path)
            os.remove(srt_file)
            os.remove(ass_file)
        except:
            pass
        
        print(f"🚀 Ultra-fast FFmpeg video with subtitles created: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"❌ Error creating FFmpeg video with subtitles: {e}")
        traceback.print_exc()
        return None
