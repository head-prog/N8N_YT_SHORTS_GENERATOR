import subprocess
import json
import os


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
