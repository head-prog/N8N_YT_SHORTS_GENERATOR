#!/usr/bin/env python3
"""
Enhanced Subtitle Synchronization with Pause Detection
Creates subtitles that respect natural speech pauses and punctuation
"""

import os
import json
import re
from typing import List, Dict, Any

def detect_natural_pauses(segments: List[Dict], min_pause_duration: float = 0.3) -> List[Dict]:
    """
    Detect natural pauses in speech and split segments accordingly
    
    Args:
        segments: Original segments from Whisper
        min_pause_duration: Minimum pause duration to consider (seconds)
    
    Returns:
        Enhanced segments with pause-aware splitting
    """
    print(f"🔍 Detecting natural pauses (minimum {min_pause_duration}s)...")
    
    enhanced_segments = []
    
    for segment in segments:
        if 'words' not in segment or not segment['words']:
            enhanced_segments.append(segment)
            continue
        
        words = segment['words']
        current_group = []
        
        for i, word in enumerate(words):
            current_group.append(word)
            
            # Check for pause after this word
            pause_detected = False
            
            # 1. Check gap to next word
            if i < len(words) - 1:
                next_word = words[i + 1]
                gap = next_word['start'] - word['end']
                if gap >= min_pause_duration:
                    pause_detected = True
                    print(f"   📍 Pause detected: {gap:.2f}s after '{word['word']}'")
            
            # 2. Check punctuation indicating pause
            word_text = word['word'].strip()
            if re.search(r'[,.!?;:]$', word_text):
                pause_detected = True
                print(f"   📝 Punctuation pause: '{word_text}'")
            
            # 3. End of segment
            if i == len(words) - 1:
                pause_detected = True
            
            # Create new segment at pause
            if pause_detected and current_group:
                enhanced_segment = {
                    'start': current_group[0]['start'],
                    'end': current_group[-1]['end'],
                    'text': ' '.join([w['word'].strip() for w in current_group]),
                    'words': current_group.copy(),
                    'type': segment.get('type', 'voiceover'),
                    'pause_after': i < len(words) - 1  # True if there's a pause after
                }
                enhanced_segments.append(enhanced_segment)
                current_group = []
    
    print(f"✅ Enhanced segments: {len(segments)} → {len(enhanced_segments)} (with pause detection)")
    return enhanced_segments

def chunk_segments_into_words(segments: List[Dict], max_words: int = 3) -> List[Dict]:
    """
    Chunk pause-aware segments into smaller 2-3 word groups for dynamic subtitles
    
    Args:
        segments: Pause-aware segments
        max_words: Maximum words per subtitle (default: 3)
    
    Returns:
        List of chunked segments with 2-3 words each
    """
    print(f"📝 Chunking segments into {max_words}-word groups for dynamic subtitles...")
    
    chunked_segments = []
    
    for segment in segments:
        if 'words' not in segment or not segment['words']:
            # If no words, keep the segment as is
            chunked_segments.append(segment)
            continue
        
        words = segment['words']
        
        # Split into chunks of 2-3 words
        for i in range(0, len(words), max_words):
            chunk_words = words[i:i + max_words]
            
            if chunk_words:
                chunked_segment = {
                    'start': chunk_words[0]['start'],
                    'end': chunk_words[-1]['end'],
                    'text': ' '.join([w['word'].strip() for w in chunk_words]),
                    'words': chunk_words,
                    'type': segment.get('type', 'voiceover'),
                    'pause_after': (i + max_words >= len(words)) and segment.get('pause_after', False)
                }
                chunked_segments.append(chunked_segment)
    
    print(f"✅ Chunked into {len(chunked_segments)} dynamic subtitle segments ({max_words} words max)")
    return chunked_segments

def create_pause_aware_subtitles(voiceover_path: str, cta_path: str = None, timing_info: Dict = None) -> List[Dict]:
    """
    Create subtitles that respect natural speech pauses and punctuation with 2-3 words per segment
    """
    print("🎯 Creating PAUSE-AWARE subtitles with 2-3 words per segment...")
    
    from whisper_service import transcribe_with_whisper
    
    # Transcription cache
    cache_dir = "transcription_cache"
    os.makedirs(cache_dir, exist_ok=True)
    
    all_segments = []
    
    # Process voiceover with pause detection
    print("🎤 Processing voiceover with pause detection...")
    voiceover_mtime = os.path.getmtime(voiceover_path)
    cache_key = f"{os.path.basename(voiceover_path)}_{voiceover_mtime}_pauses"
    cache_file = os.path.join(cache_dir, f"{cache_key}.json")
    
    if os.path.exists(cache_file):
        print("⚡ Using cached pause-aware transcription...")
        with open(cache_file, 'r') as f:
            voiceover_result = json.load(f)
    else:
        print("🤖 Transcribing with pause detection...")
        voiceover_result = transcribe_with_whisper(voiceover_path)
        
        if voiceover_result and 'segments' in voiceover_result:
            # Enhance segments with pause detection
            enhanced_segments = detect_natural_pauses(voiceover_result['segments'])
            voiceover_result['enhanced_segments'] = enhanced_segments
        
        with open(cache_file, 'w') as f:
            json.dump(voiceover_result, f)
        print("💾 Pause-aware transcription cached")
    
    # Use enhanced segments if available
    if 'enhanced_segments' in voiceover_result:
        segments = voiceover_result['enhanced_segments']
    else:
        segments = voiceover_result.get('segments', [])
    
    # Chunk pause-aware segments into 2-3 word groups
    chunked_voiceover_segments = chunk_segments_into_words(segments, max_words=3)
    
    # Add voiceover segments
    for segment in chunked_voiceover_segments:
        segment['type'] = 'voiceover'
        all_segments.append(segment)
    
    # Process CTA if provided
    if cta_path and timing_info:
        print("📢 Processing CTA with pause detection...")
        cta_mtime = os.path.getmtime(cta_path)
        cta_cache_key = f"{os.path.basename(cta_path)}_{cta_mtime}_pauses"
        cta_cache_file = os.path.join(cache_dir, f"{cta_cache_key}.json")
        
        if os.path.exists(cta_cache_file):
            print("⚡ Using cached CTA pause-aware transcription...")
            with open(cta_cache_file, 'r') as f:
                cta_result = json.load(f)
        else:
            print("🤖 Transcribing CTA with pause detection...")
            cta_result = transcribe_with_whisper(cta_path)
            
            if cta_result and 'segments' in cta_result:
                enhanced_segments = detect_natural_pauses(cta_result['segments'])
                cta_result['enhanced_segments'] = enhanced_segments
            
            with open(cta_cache_file, 'w') as f:
                json.dump(cta_result, f)
            print("💾 CTA pause-aware transcription cached")
        
        # Use enhanced segments and adjust timing
        if 'enhanced_segments' in cta_result:
            cta_segments = cta_result['enhanced_segments']
        else:
            cta_segments = cta_result.get('segments', [])
        
        # Chunk CTA segments into 2-3 word groups
        chunked_cta_segments = chunk_segments_into_words(cta_segments, max_words=3)
        
        cta_start_time = timing_info.get('cta_start', 0)
        for segment in chunked_cta_segments:
            segment['start'] += cta_start_time
            segment['end'] += cta_start_time
            segment['type'] = 'cta'
            all_segments.append(segment)
    
    # Sort by start time
    all_segments.sort(key=lambda x: x['start'])
    
    print(f"✅ Created {len(all_segments)} dynamic subtitle segments (2-3 words each)")
    return all_segments

def create_enhanced_ass_subtitles_with_pauses(voiceover_path: str, cta_path: str = None) -> str:
    """
    Create ASS subtitles that respect natural pauses and punctuation with 2-3 words per segment
    """
    print("🎨 Creating pause-aware ASS subtitles with 2-3 words per segment...")
    
    # Get timing info for CTA
    timing_info = {}
    if cta_path:
        from video_service import safe_load_audio
        voiceover_audio = safe_load_audio(voiceover_path)
        timing_info['cta_start'] = voiceover_audio.duration
        voiceover_audio.close()
    
    # Get pause-aware segments
    segments = create_pause_aware_subtitles(voiceover_path, cta_path, timing_info)
    
    if not segments:
        print("❌ No subtitle segments generated")
        return None
    
    # Create ASS subtitle content with pause awareness
    ass_content = """[Script Info]
Title: Pause-Aware Subtitles
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: VoiceOver,Bangers,19,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,0,5,0,0,50,1
Style: CTA,Bangers,19,&H0000FFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,0,5,0,0,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    def format_ass_time(seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:05.2f}"
    
    for segment in segments:
        start_time = format_ass_time(segment['start'])
        end_time = format_ass_time(segment['end'])
        
        # Choose style based on type
        style = "CTA" if segment.get('type') == 'cta' else "VoiceOver"
        
        # Clean and format text
        text = segment['text'].strip().upper()
        
        # Add natural pause indication if this segment has a pause after
        if segment.get('pause_after', False):
            # Add slight visual spacing for pauses
            text += "..."
        
        ass_content += f"Dialogue: 0,{start_time},{end_time},{style},,0,0,0,,{text}\n"
    
    # Save ASS file
    ass_file_path = "enhanced_pause_aware_subtitles.ass"
    with open(ass_file_path, 'w', encoding='utf-8') as f:
        f.write(ass_content)
    
    print(f"✅ Created pause-aware ASS subtitle file: {ass_file_path}")
    print(f"📊 Total segments: {len(segments)}")
    
    return ass_file_path

if __name__ == "__main__":
    print("🎯 Enhanced Pause-Aware Subtitle System")
    print("✅ Respects natural speech pauses and punctuation")
