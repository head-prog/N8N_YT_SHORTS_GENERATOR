#!/usr/bin/env python3
"""
MoviePy Editor compatibility layer for MoviePy 2.1.x
"""

# This module creates a fake "moviepy.editor" module that can be imported
# by legacy code that was written for MoviePy 1.x

# First, make sure this file is in Python's path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Create a fake moviepy.editor module
import types
import moviepy as real_moviepy

# Create the moviepy.editor module
if 'moviepy.editor' not in sys.modules:
    editor_module = types.ModuleType('moviepy.editor')
    sys.modules['moviepy.editor'] = editor_module
    
    # Expose the classes from moviepy 2.1.x
    editor_module.VideoFileClip = real_moviepy.VideoFileClip
    editor_module.AudioFileClip = real_moviepy.AudioFileClip
    editor_module.TextClip = real_moviepy.TextClip
    editor_module.CompositeVideoClip = real_moviepy.CompositeVideoClip
    editor_module.CompositeAudioClip = real_moviepy.CompositeAudioClip
    editor_module.concatenate_audioclips = real_moviepy.concatenate_audioclips
    editor_module.concatenate_videoclips = real_moviepy.concatenate_videoclips
    editor_module.ImageClip = real_moviepy.ImageClip
    editor_module.ColorClip = real_moviepy.ColorClip
    editor_module.VideoClip = real_moviepy.VideoClip
    editor_module.ImageSequenceClip = real_moviepy.ImageSequenceClip

# Add all exports here to match moviepy.editor from MoviePy 1.x
__all__ = [
    'VideoFileClip',
    'AudioFileClip',
    'CompositeVideoClip',
    'CompositeAudioClip',
    'TextClip',
    'concatenate_videoclips',
    'concatenate_audioclips',
    'ImageSequenceClip',
    'ColorClip',
    'ImageClip'
]
