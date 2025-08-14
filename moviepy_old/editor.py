"""
Compatibility module for moviepy.editor for older code that depends on it.
This module imports from MoviePy 2.1.1 and re-exports with the old structure.
"""

# Re-export everything from moviepy 2.1.1
from moviepy import (
    VideoFileClip,
    AudioFileClip,
    CompositeVideoClip,
    CompositeAudioClip,
    TextClip,
    VideoClip,
    ImageClip,
    ColorClip,
    ImageSequenceClip
)

# Make these available for older imports
from moviepy import concatenate_audioclips, concatenate_videoclips

# Make all exported names available
__all__ = [
    'VideoFileClip',
    'AudioFileClip',
    'CompositeVideoClip',
    'CompositeAudioClip',
    'TextClip',
    'VideoClip',
    'ImageClip',
    'ColorClip',
    'ImageSequenceClip',
    'concatenate_audioclips',
    'concatenate_videoclips',
]
