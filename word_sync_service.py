#!/usr/bin/env python3
"""
Enhanced Word-by-Word Synchronization using Captacity
Provides frame-accurate subtitle synchronization for every word
"""

import os
import json
import tempfile
import shutil
from typing import List, Dict, Any
from captacity import add_captions
from whisper_service import transcribe_with_whisper

def create_word_level_subtitles(voiceover_path: str, cta_path: str = None, timing_info: Dict = None) -> List[Dict]:
    """
    Create word-level synchronized subtitles using Captacity
    
    Args:
        voiceover_path: Path to voiceover audio file
        cta_path: Optional path to CTA audio file
        timing_info: Timing information for CTA placement
    
    Returns:
        List of word-level subtitle segments with precise timing
    """
    print("🎯 Creating WORD-LEVEL synchronized subtitles with Captacity...")
    
    # Transcription cache directory
    cache_dir = "transcription_cache"
    os.makedirs(cache_dir, exist_ok=True)
    
    # Get detailed word-level transcription for voiceover
    word_segments = []
    
    # Voiceover word-level transcription
    print("🎤 Generating word-level transcription for voiceover...")
    voiceover_mtime = os.path.getmtime(voiceover_path)
    cache_key = f"{os.path.basename(voiceover_path)}_{voiceover_mtime}_wordlevel"
    cache_file = os.path.join(cache_dir, f"{cache_key}.json")
    
    if os.path.exists(cache_file):
        print("⚡ Using cached word-level voiceover transcription...")
        with open(cache_file, 'r') as f:
            voiceover_result = json.load(f)
    else:
        print("🤖 Transcribing voiceover with word-level precision...")
        voiceover_result = transcribe_with_whisper(voiceover_path)
        with open(cache_file, 'w') as f:
            json.dump(voiceover_result, f)
        print("💾 Word-level transcription cached")
    
    # Extract word-level segments from voiceover
    if voiceover_result and 'segments' in voiceover_result:
        for segment in voiceover_result['segments']:
            if 'words' in segment and segment['words']:
                for word_info in segment['words']:
                    if word_info.get('word', '').strip():
                        word_segments.append({
                            'text': word_info['word'].strip(),
                            'start': word_info['start'],
                            'end': word_info['end'],
                            'type': 'voiceover',
                            'confidence': word_info.get('probability', 1.0)
                        })
    
    # CTA word-level transcription if provided
    if cta_path and timing_info:
        print("📢 Generating word-level transcription for CTA...")
        cta_mtime = os.path.getmtime(cta_path)
        cta_cache_key = f"{os.path.basename(cta_path)}_{cta_mtime}_wordlevel"
        cta_cache_file = os.path.join(cache_dir, f"{cta_cache_key}.json")
        
        if os.path.exists(cta_cache_file):
            print("⚡ Using cached word-level CTA transcription...")
            with open(cta_cache_file, 'r') as f:
                cta_result = json.load(f)
        else:
            print("🤖 Transcribing CTA with word-level precision...")
            cta_result = transcribe_with_whisper(cta_path)
            with open(cta_cache_file, 'w') as f:
                json.dump(cta_result, f)
            print("💾 CTA word-level transcription cached")
        
        # Extract word-level segments from CTA and adjust timing
        if cta_result and 'segments' in cta_result:
            cta_start_time = timing_info.get('cta_start', 0)
            for segment in cta_result['segments']:
                if 'words' in segment and segment['words']:
                    for word_info in segment['words']:
                        if word_info.get('word', '').strip():
                            word_segments.append({
                                'text': word_info['word'].strip(),
                                'start': word_info['start'] + cta_start_time,
                                'end': word_info['end'] + cta_start_time,
                                'type': 'cta',
                                'confidence': word_info.get('probability', 1.0)
                            })
    
    # Sort all word segments by start time
    word_segments.sort(key=lambda x: x['start'])
    
    print(f"✅ Generated {len(word_segments)} word-level segments")
    
    return word_segments

def group_words_for_display(word_segments: List[Dict], max_words: int = 2, max_duration: float = 2.0) -> List[Dict]:
    """
    Group individual words into readable subtitle chunks while maintaining precise timing
    
    Args:
        word_segments: List of individual word segments
        max_words: Maximum words per subtitle (default: 2 for better mobile readability)
        max_duration: Maximum duration per subtitle in seconds
    
    Returns:
        List of grouped subtitle segments with embedded word timing
    """
    print(f"🔧 Grouping words into {max_words}-word subtitles for optimal readability...")
    
    grouped_segments = []
    current_group = []
    current_type = None
    
    for word in word_segments:
        # Start new group if type changes or max words reached
        if (current_type != word['type'] or 
            len(current_group) >= max_words or
            (current_group and word['start'] - current_group[0]['start'] > max_duration)):
            
            if current_group:
                # Create subtitle from current group with embedded word timing
                subtitle = {
                    'text': ' '.join([w['text'] for w in current_group]),
                    'start': current_group[0]['start'],
                    'end': current_group[-1]['end'],
                    'type': current_type,
                    'word_count': len(current_group),
                    'confidence': sum([w['confidence'] for w in current_group]) / len(current_group),
                    'words': current_group  # Keep original word timing for Captacity
                }
                grouped_segments.append(subtitle)
                current_group = []
        
        current_group.append(word)
        current_type = word['type']
    
    # Add final group
    if current_group:
        subtitle = {
            'text': ' '.join([w['text'] for w in current_group]),
            'start': current_group[0]['start'],
            'end': current_group[-1]['end'],
            'type': current_type,
            'word_count': len(current_group),
            'confidence': sum([w['confidence'] for w in current_group]) / len(current_group),
            'words': current_group  # Keep original word timing for Captacity
        }
        grouped_segments.append(subtitle)
    
    print(f"✅ Created {len(grouped_segments)} optimized subtitle groups")
    return grouped_segments

def create_enhanced_subtitle_video(video_path: str, subtitle_segments: List[Dict], output_path: str) -> str:
    """
    Create video with word-level synchronized subtitles using Captacity
    
    Args:
        video_path: Path to input video
        subtitle_segments: List of subtitle segments with precise timing
        output_path: Path for output video
    
    Returns:
        Path to output video with subtitles
    """
    print("🎬 Adding word-level synchronized subtitles with Captacity...")
    
    # Create subtitle segments for Captacity with proper word-level format
    captacity_segments = []
    
    for segment in subtitle_segments:
        subtitle_type = segment.get('type', 'voiceover')
        
        # Use the embedded word timing from our grouped segments
        words_array = []
        if 'words' in segment and segment['words']:
            # Use the precise word timing from Whisper
            for word_data in segment['words']:
                words_array.append({
                    'word': word_data['text'],
                    'start': word_data['start'],
                    'end': word_data['end']
                })
        else:
            # Fallback: split text and estimate timing
            words = segment['text'].split()
            segment_duration = segment['end'] - segment['start']
            word_duration = segment_duration / len(words) if words else 0
            
            current_time = segment['start']
            for word in words:
                word_end = current_time + word_duration
                words_array.append({
                    'word': word,
                    'start': current_time,
                    'end': word_end
                })
                current_time = word_end
        
        captacity_segment = {
            'start': segment['start'],
            'end': segment['end'],
            'text': segment['text'].upper(),
            'words': words_array  # Precise word timing for Captacity
        }
        captacity_segments.append(captacity_segment)
    
    print(f"🎯 Processing {len(captacity_segments)} subtitle segments with Captacity...")
    
    try:
        # Use Captacity to add captions with correct parameters
        print(f"🎥 Using Captacity with {len(captacity_segments)} segments...")
        print(f"📝 Sample segment: {captacity_segments[0]['text'][:50]}...")
        
        result_video = add_captions(
            video_file=video_path,
            output_file=output_path,
            font='PoetsenOne-Regular.ttf',  
            font_size=20,  # Smaller font size to fit better
            font_color='white',
            stroke_width=2,
            stroke_color='black',
            highlight_current_word=False,
            line_count=1,
            padding=60,
            position=('center', 'center'),
            shadow_strength=0.8,
            shadow_blur=0.1,
            segments=captacity_segments,
            use_local_whisper=False,
            print_info=False  # Disable verbose output
        )
        
        print("✅ Captacity subtitle processing completed successfully!")
        return output_path
        
    except Exception as e:
        print(f"❌ Captacity processing error: {e}")
        print("🔄 Falling back to FFmpeg ASS subtitle method...")
        return None

def create_comprehensive_word_sync_video(voiceover_path: str, output_path: str, 
                                       bgm_path: str = None, cta_path: str = None,
                                       video_clips: List = None) -> str:
    """
    Create a complete video with comprehensive word-by-word synchronization
    
    Args:
        voiceover_path: Path to voiceover audio
        output_path: Output video path
        bgm_path: Optional BGM path
        cta_path: Optional CTA path
        video_clips: Optional list of video clips
    
    Returns:
        Path to final video with word-synchronized subtitles
    """
    print("🚀 Creating comprehensive word-synchronized video...")
    
    # Import required video service functions
    from video_service import create_video_with_ffmpeg_subtitles, safe_load_audio
    
    # First create a standard video with ASS subtitles as a baseline
    print("🎬 Creating baseline video with standard subtitles...")
    standard_video_path = tempfile.mktemp(suffix='_standard.mp4')
    
    base_video_path = create_video_with_ffmpeg_subtitles(
        voiceover_path=voiceover_path,
        output_path=standard_video_path,
        bgm_path=bgm_path,
        cta_path=cta_path
    )
    
    if not base_video_path:
        print("❌ Base video creation failed")
        return None
    
    print("✅ Baseline video created, now enhancing with word-level subtitles...")
    
    # Get timing information for CTA
    timing_info = {}
    if cta_path:
        voiceover_audio = safe_load_audio(voiceover_path)
        timing_info['cta_start'] = voiceover_audio.duration
        cta_audio = safe_load_audio(cta_path)
        timing_info['cta_duration'] = cta_audio.duration
        voiceover_audio.close()
        cta_audio.close()
    
    # Create word-level subtitles
    word_segments = create_word_level_subtitles(voiceover_path, cta_path, timing_info)
    
    # Group words for optimal display
    subtitle_segments = group_words_for_display(word_segments, max_words=2)
    
    # Try to add enhanced subtitles with Captacity
    print("🎯 Attempting to enhance with Captacity word-level subtitles...")
    try:
        # Create a temporary video without the ASS subtitles for Captacity processing
        temp_no_subs_path = tempfile.mktemp(suffix='_no_subs.mp4')
        
        # Extract video without subtitles using FFmpeg
        import subprocess
        cmd = [
            'ffmpeg', '-y', '-i', base_video_path,
            '-c:v', 'copy', '-c:a', 'copy',
            '-an', temp_no_subs_path  # Copy without audio to isolate video
        ]
        
        print("🔧 Extracting video track for Captacity processing...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print("⚠️  Could not extract video track, using original video")
            temp_no_subs_path = base_video_path
        
        # Add subtitles with Captacity
        final_video_path = create_enhanced_subtitle_video(
            video_path=temp_no_subs_path,
            subtitle_segments=subtitle_segments,
            output_path=output_path
        )
        
        # Cleanup intermediate files
        for temp_file in [standard_video_path, temp_no_subs_path]:
            try:
                if temp_file != base_video_path and os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass
        
        if final_video_path:
            print("🎉 Comprehensive word-synchronized video created successfully!")
            return final_video_path
        else:
            print("⚠️  Captacity enhancement failed, returning baseline video")
            return base_video_path
    
    except Exception as e:
        print(f"⚠️  Word synchronization enhancement failed: {e}")
        print("🔄 Returning baseline video with standard subtitles")
        
        # Copy baseline to final output
        import shutil
        shutil.copy2(base_video_path, output_path)
        
        # Cleanup
        try:
            os.remove(base_video_path)
        except:
            pass
        
        return output_path

if __name__ == "__main__":
    print("🎯 Enhanced Word-by-Word Synchronization Module")
    print("✅ Captacity integration ready for frame-accurate subtitles")
