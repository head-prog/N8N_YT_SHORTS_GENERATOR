import subprocess
import json
import os
import random
import glob


def run_cmd(cmd, check=True):
    """Run subprocess command with error handling"""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=check)
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {' '.join(cmd)}\nError: {e.stderr}")
        return e
    except FileNotFoundError as e:
        print(f"Command not found: {' '.join(cmd)}\nError: {e}")
        return subprocess.CompletedProcess(cmd, 127, '', str(e))


def get_ffmpeg_font():
    """Get available font for FFmpeg with fallbacks."""
    # Updated font list with more common system fonts
    default_fonts = [
        "Arial", "Helvetica", "DejaVu Sans", "Liberation Sans", 
        "Ubuntu", "Roboto", "Times New Roman", "Verdana", 
        "Tahoma", "Calibri", "Georgia"
    ]
    
    for font in default_fonts:
        test_cmd = [
            'ffmpeg', '-y', '-v', 'quiet',
            '-f', 'lavfi', '-i', 'color=c=black:s=320x240:d=0.1',
            '-vf', f"drawtext=text='Test':font='{font}':fontsize=20:fontcolor=white:x=10:y=10",
            '-frames:v', '1', '-f', 'null', '-'
        ]
        result = run_cmd(test_cmd, check=False)
        if result.returncode == 0:
            print(f"✅ FFmpeg font '{font}' is available")
            return font
    
    # Fallback to system default
    print("⚠️ No suitable FFmpeg font found, using system default")
    return "Arial"  # This will fallback to system default if not found


def get_available_font():
    """Find an available font with robust fallbacks for MoviePy TextClip."""
    from config import MOVIEPY_AVAILABLE
    
    if not MOVIEPY_AVAILABLE:
        return "Arial"
        
    from moviepy.editor import TextClip
    
    # Extended font list with better coverage
    default_fonts = [
        "Arial", "Helvetica", "DejaVu Sans", "Liberation Sans", 
        "Ubuntu", "Roboto", "Times New Roman", "Verdana", 
        "Tahoma", "Calibri", "Georgia", "Open Sans"
    ]
    
    for font in default_fonts:
        try:
            # Test with a minimal TextClip
            test_clip = TextClip("T", font=font, fontsize=20, color='white')
            if hasattr(test_clip, 'size') and test_clip.size:
                test_clip.close()
                print(f"✅ Font '{font}' is available for TextClip")
                return font
            test_clip.close()
        except Exception as e:
            print(f"⚠️ Font '{font}' test failed: {e}")
            continue
    
    # Try system fonts using matplotlib if available
    try:
        import matplotlib.font_manager as fm
        system_fonts = [f.name for f in fm.fontManager.ttflist]
        common_system_fonts = [font for font in system_fonts if any(
            common in font.lower() for common in ['arial', 'helvetica', 'sans', 'ubuntu', 'roboto']
        )]
        
        for font in common_system_fonts[:10]:  # Try top 10 matches
            try:
                test_clip = TextClip("T", font=font, fontsize=20, color='white')
                if hasattr(test_clip, 'size') and test_clip.size:
                    test_clip.close()
                    print(f"✅ System font '{font}' is available")
                    return font
                test_clip.close()
            except Exception:
                continue
    except ImportError:
        print("⚠️ Matplotlib not available for font detection")
    
    # Final fallback - return None to use MoviePy default
    print("⚠️ Using MoviePy default font")
    return None


def calculate_optimal_font_size(video_width, video_height, text_length):
    """Calculate optimal font size based on video dimensions and text length - optimized for medium-sized horizontal subtitles"""
    base_size = min(video_width, video_height) // 80  # Medium base for balanced subtitles
    if text_length < 10:
        multiplier = 0.6  # Medium multipliers for balanced readability
    elif text_length < 20:
        multiplier = 0.5
    elif text_length < 30:
        multiplier = 0.4
    else:
        multiplier = 0.35
    
    # Medium bounds for clear, horizontal subtitles
    optimal_size = max(12, min(26, int(base_size * multiplier)))  # Range: 12-26px for medium subtitles
    return optimal_size


def calculate_subtitle_position(video_width, video_height, text_height):
    """Calculate smart positioning with bounds checking"""
    bottom_margin = max(60, int(video_height * 0.12))
    y_position = video_height - text_height - bottom_margin
    max_y = int(video_height * 0.85)
    y_position = min(y_position, max_y)
    return ('center', y_position)


def get_random_clips(folder, clip_duration, total_duration):
    """
    Get random video clips from a folder to cover the specified duration.
    
    Args:
        folder (str): Path to folder containing video clips
        clip_duration (float): Duration of each clip in seconds
        total_duration (float): Total duration to cover
    
    Returns:
        list: List of MoviePy VideoFileClip objects
    """
    import random
    from config import MOVIEPY_AVAILABLE
    
    if not MOVIEPY_AVAILABLE:
        print("❌ MoviePy not available for video processing")
        return []
    
    try:
        from moviepy.editor import VideoFileClip
    except ImportError:
        print("❌ Could not import VideoFileClip from moviepy")
        return []
    
    # Get all video files in the folder (.mp4, .mov, .avi, .mkv)
    video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.m4v']
    clip_files = [f for f in os.listdir(folder) 
                  if any(f.lower().endswith(ext) for ext in video_extensions)]
    
    if not clip_files:
        print(f"❌ No video files found in {folder}")
        return []
    
    print(f"📁 Found {len(clip_files)} video files in clips folder")
    
    # Shuffle the files for randomness
    random.shuffle(clip_files)
    
    # Calculate how many clips we need
    clips_needed = int(total_duration / clip_duration) + 1  # +1 to ensure we have enough
    
    print(f"🎲 Selecting {clips_needed} random clips for {total_duration}s duration")
    
    video_clips = []
    selected_files = clip_files[:clips_needed] if len(clip_files) >= clips_needed else clip_files * (clips_needed // len(clip_files) + 1)
    
    for i, filename in enumerate(selected_files[:clips_needed]):
        try:
            file_path = os.path.join(folder, filename)
            print(f"   Loading clip {i+1}/{clips_needed}: {filename}")
            
            # Load the video clip with safer reading
            clip = VideoFileClip(file_path)
            
            # Validate the clip loaded properly
            if clip.reader is None:
                print(f"   ⚠️ Clip {filename} failed to load reader, skipping")
                clip.close()
                continue
            
            # Get the clip duration
            try:
                clip_full_duration = clip.duration
            except Exception as e:
                print(f"   ⚠️ Clip {filename} duration error: {e}, skipping")
                clip.close()
                continue
            
            if clip_full_duration is None or clip_full_duration <= 0:
                print(f"   ⚠️ Clip {filename} invalid duration, skipping")
                clip.close()
                continue
            
            # Safety buffer to avoid reading beyond file bounds
            safety_buffer = 0.3  # 0.3 seconds buffer
            safe_duration = max(0.5, clip_full_duration - safety_buffer)
            
            # If the clip is shorter than our desired clip_duration, use safe duration
            actual_clip_duration = min(clip_duration, safe_duration)
            
            if actual_clip_duration <= 0.5:
                print(f"   ⚠️ Clip {filename} too short ({clip_full_duration:.2f}s), skipping")
                clip.close()
                continue
            
            # Trim the clip to the desired duration (starting from random point if clip is longer)
            if safe_duration > clip_duration:
                # Choose random start time, ensuring we don't go beyond safe bounds
                max_start = safe_duration - clip_duration
                start_time = random.uniform(0, max(0, max_start))
                end_time = min(start_time + clip_duration, safe_duration)
                try:
                    trimmed_clip = clip.subclip(start_time, end_time)
                    # Test if the trimmed clip is valid
                    test_frame = trimmed_clip.get_frame(0)
                    if test_frame is None:
                        raise Exception("Invalid frame data")
                except Exception as e:
                    print(f"   ⚠️ Clip {filename} subclip error: {e}, skipping")
                    clip.close()
                    continue
            else:
                # Use the safe portion of the clip
                try:
                    trimmed_clip = clip.subclip(0, actual_clip_duration)
                    # Test if the trimmed clip is valid
                    test_frame = trimmed_clip.get_frame(0)
                    if test_frame is None:
                        raise Exception("Invalid frame data")
                except Exception as e:
                    print(f"   ⚠️ Clip {filename} subclip error: {e}, skipping")
                    clip.close()
                    continue
            
            video_clips.append(trimmed_clip)
            print(f"   ✅ Clip {filename} loaded successfully ({actual_clip_duration:.2f}s)")
            
            # DON'T close the original clip - this invalidates the trimmed clip's reader
            # We'll let Python's garbage collection handle this
            
        except Exception as e:
            print(f"   ⚠️ Error loading {filename}: {e}")
            continue
    
    print(f"✅ Successfully loaded {len(video_clips)} video clips")
    
    # Check if we have enough clips
    if len(video_clips) == 0:
        print("❌ No valid video clips loaded!")
        return None
    
    if len(video_clips) < clips_needed:
        print(f"⚠️ Only loaded {len(video_clips)} clips, need {clips_needed}. Will repeat clips.")
        # Repeat clips to fill the required duration
        while len(video_clips) < clips_needed:
            video_clips.extend(video_clips[:min(clips_needed - len(video_clips), len(video_clips))])
    
    return video_clips[:clips_needed]
