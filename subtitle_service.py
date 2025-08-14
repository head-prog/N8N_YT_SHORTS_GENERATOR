import traceback


def create_segments_from_whisper_result(whisper_result, max_chars_per_segment=45, max_duration=5.0, max_words=3):
    """Create subtitle segments from Whisper transcription result with real timestamps"""
    if not whisper_result:
        print("❌ No Whisper result provided")
        return []
    
    whisper_segments = whisper_result.get('segments', [])
    if whisper_segments:
        return create_segments_from_whisper_timestamps(whisper_result, max_chars_per_segment, max_duration, max_words)
    else:
        print("⚠️ No segments in result, using text-based timing")
        return create_segments_from_a4f_result(whisper_result, max_chars_per_segment, max_words)


def create_segments_from_whisper_timestamps(whisper_result, max_chars_per_segment=45, max_duration=5.0, max_words=3):
    """Create subtitle segments from Whisper result with real timestamps"""
    whisper_segments = whisper_result.get('segments', [])
    if not whisper_segments:
        print("❌ No segments in Whisper result")
        return []
    
    subtitle_segments = []
    print(f"🎬 Processing {len(whisper_segments)} Whisper segments...")
    
    for i, segment in enumerate(whisper_segments):
        start_time = segment.get('start', 0)
        end_time = segment.get('end', start_time + 3)
        text = segment.get('text', '').strip()
        
        if not text:
            continue
        
        words = segment.get('words', [])
        if words and len(words) > 0:
            # Use word-level timestamps for better accuracy
            sub_segments = split_segment_by_words(words, max_chars_per_segment, max_duration, max_words)
            subtitle_segments.extend(sub_segments)
        else:
            # Fallback to sentence-level splitting
            sub_segments = split_long_segment(text, start_time, end_time, max_chars_per_segment, max_words)
            subtitle_segments.extend(sub_segments)
    
    print(f"✅ Created {len(subtitle_segments)} subtitle segments from Whisper timestamps")
    for i, seg in enumerate(subtitle_segments[:3]):
        duration = seg['end'] - seg['start']
        print(f"  Segment {i+1}: '{seg['text'][:40]}...' ({seg['start']:.2f}s-{seg['end']:.2f}s, {duration:.2f}s)")
    
    return subtitle_segments


def split_segment_by_words(words, max_chars, max_duration, max_words=3):
    """Split segment using word-level timestamps"""
    segments = []
    current_text = ""
    current_start = None
    current_end = None
    word_count = 0
    
    for word_data in words:
        word = word_data.get('word', '').strip()
        word_start = word_data.get('start', 0)
        word_end = word_data.get('end', word_start + 0.5)
        
        if not word:
            continue
        
        if current_start is None:
            current_start = word_start
            current_text = word
            current_end = word_end
            word_count = 1
            continue
        
        test_text = current_text + " " + word
        test_duration = word_end - current_start
        
        # Check if we should end current segment
        should_end = (
            word_count >= max_words or 
            len(test_text) > max_chars or 
            test_duration > max_duration
        )
        
        if should_end:
            if current_text.strip():
                segments.append({
                    'start': current_start,
                    'end': current_end,
                    'text': current_text.strip()
                })
            # Start new segment
            current_start = word_start
            current_text = word
            current_end = word_end
            word_count = 1
        else:
            # Continue current segment
            current_text = test_text
            current_end = word_end
            word_count += 1
    
    # Add final segment
    if current_text.strip():
        segments.append({
            'start': current_start,
            'end': current_end,
            'text': current_text.strip()
        })
    
    return segments


def split_long_segment(text, start_time, end_time, max_chars, max_words=3):
    """Split a long text segment into smaller parts with proportional timing"""
    segments = []
    words = text.split()
    
    if not words:
        return []
    
    total_duration = end_time - start_time
    total_words = len(words)
    current_words = []
    word_count = 0
    words_processed = 0
    
    for i, word in enumerate(words):
        if word_count < max_words:
            current_words.append(word)
            word_count += 1
        else:
            # Calculate timing for current segment
            segment_text = ' '.join(current_words)
            segment_duration = (len(current_words) / total_words) * total_duration
            segment_start = start_time + (words_processed / total_words) * total_duration
            segment_end = segment_start + segment_duration
            
            segments.append({
                'start': segment_start,
                'end': segment_end,
                'text': segment_text
            })
            
            words_processed += len(current_words)
            current_words = [word]
            word_count = 1
    
    # Handle remaining words
    if current_words:
        segment_text = ' '.join(current_words)
        segment_start = start_time + (words_processed / total_words) * total_duration
        segments.append({
            'start': segment_start,
            'end': end_time,
            'text': segment_text
        })
    
    return segments


def create_segments_from_a4f_result(transcription_result, max_chars_per_segment=45, max_words=3):
    """Create subtitle segments from A4F API result"""
    try:
        segments = []
        if not transcription_result:
            print("❌ No transcription result provided")
            return []
        
        full_text = transcription_result.get('text', '').strip()
        if not full_text:
            print("❌ No text found in response")
            return []
        
        print(f"📝 Creating intelligent subtitle segments from text: '{full_text[:100]}...'")
        words = full_text.split()
        
        if not words:
            return [{
                'start': 0,
                'end': 10,
                'text': full_text
            }]
        
        print(f"📄 Split into {len(words)} words")
        
        # Improved timing calculation
        words_per_second = 2.2  # Average speaking rate
        current_time = 0
        current_words = []
        word_count = 0
        
        for i, word in enumerate(words):
            if word_count < max_words:
                current_words.append(word)
                word_count += 1
            else:
                # Create segment from current words
                segment_text = ' '.join(current_words)
                duration = max(1.5, len(current_words) / words_per_second) # Minimum 1.5s
                
                # Add small gap between segments
                if i > 0:
                    current_time += 0.2
                
                start_time = current_time
                end_time = current_time + duration
                
                segments.append({
                    'start': start_time,
                    'end': end_time,
                    'text': segment_text.strip()
                })
                
                current_time = end_time
                current_words = [word]
                word_count = 1
            
            # Handle last segment
            if i == len(words) - 1 and current_words:
                segment_text = ' '.join(current_words)
                duration = max(1.5, len(current_words) / words_per_second)
                
                if i > 0:
                    current_time += 0.2
                
                start_time = current_time
                end_time = current_time + duration
                
                segments.append({
                    'start': start_time,
                    'end': end_time,
                    'text': segment_text.strip()
                })
        
        print(f"✅ Created {len(segments)} intelligent subtitle segments")
        for i, seg in enumerate(segments[:3]):
            print(f"  Segment {i+1}: '{seg['text'][:40]}...' ({seg['start']:.2f}s - {seg['end']:.2f}s)")
        
        return segments
        
    except Exception as e:
        print(f"❌ Error processing text into segments: {e}")
        traceback.print_exc()
        return []


def segments_to_srt(segments):
    """Convert segments to SRT format with vertical formatting for mobile videos"""
    srt_content = ""
    for i, seg in enumerate(segments, 1):
        start_h, start_r = divmod(seg['start'], 3600)
        start_m, start_s = divmod(start_r, 60)
        start_ms = int((start_s % 1) * 1000)
        
        end_h, end_r = divmod(seg['end'], 3600)
        end_m, end_s = divmod(end_r, 60)
        end_ms = int((end_s % 1) * 1000)
        
        # FORCE vertical text layout - each word on its own line - CAPITALIZED
        original_text = seg['text'].strip().upper()  # Capitalize all text
        words = original_text.split()
        
        # Always create vertical layout for better mobile viewing - CAPITALIZED
        vertical_text = '\n'.join(words)  # Each word on separate line, already capitalized
        
        srt_content += f"{i}\n"
        srt_content += f"{int(start_h):02d}:{int(start_m):02d}:{int(start_s):02d},{start_ms:03d} --> "
        srt_content += f"{int(end_h):02d}:{int(end_m):02d}:{int(end_s):02d},{end_ms:03d}\n"
        srt_content += f"{vertical_text}\n\n"
    
    return srt_content
