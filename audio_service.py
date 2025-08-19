import os
import json
import traceback
import tempfile
from utils import run_cmd
from config import PYDUB_AVAILABLE


def mix_audio_with_bgm_and_cta(voice_audio_path, bgm_path=None, cta_path=None, bgm_volume=0.6, cta_volume=1.5):
    """Mix voice audio with background music and call-to-action audio"""
    from config import MOVIEPY_AVAILABLE
    
    if not MOVIEPY_AVAILABLE:
        raise Exception("MoviePy not available")
    
    from moviepy.editor import AudioFileClip, CompositeAudioClip, concatenate_audioclips
    
    print(f"🎵 Mixing audio with BGM and CTA...")
    print(f"   Voice: {voice_audio_path}")
    print(f"   BGM: {bgm_path} (volume: {bgm_volume})")
    print(f"   CTA: {cta_path} (volume: {cta_volume})")
    
    try:
        # Load voice audio
        voice_audio = safe_load_audio(voice_audio_path)
        voice_duration = voice_audio.duration
        
        audio_clips = [voice_audio]
        
        # Add background music if provided
        if bgm_path and os.path.exists(bgm_path):
            try:
                bgm_audio = AudioFileClip(bgm_path)
                # Loop BGM to match voice duration if needed
                if bgm_audio.duration < voice_duration:
                    loops_needed = int(voice_duration / bgm_audio.duration) + 1
                    bgm_looped = concatenate_audioclips([bgm_audio] * loops_needed)
                    bgm_final = bgm_looped.subclip(0, voice_duration)
                else:
                    bgm_final = bgm_audio.subclip(0, voice_duration)
                
                # Reduce BGM volume
                bgm_final = bgm_final.volumex(bgm_volume)
                audio_clips.append(bgm_final)
                print(f"✅ BGM added: {bgm_audio.duration:.2f}s, looped to {voice_duration:.2f}s")
                
            except Exception as bgm_error:
                print(f"⚠️ BGM loading failed: {bgm_error}")
        
        # Create composite audio with voice and BGM
        if len(audio_clips) > 1:
            composite_audio = CompositeAudioClip(audio_clips)
            # Ensure fps is properly set for composite audio
            try:
                # Set fps based on voice audio
                if hasattr(voice_audio, 'fps') and voice_audio.fps:
                    composite_audio.fps = voice_audio.fps
                else:
                    composite_audio.fps = 44100  # Standard audio fps
            except Exception as fps_error:
                print(f"⚠️ Setting fps for composite audio: {fps_error}")
                composite_audio.fps = 44100
        else:
            composite_audio = voice_audio
        
        # Add CTA at the end if provided
        if cta_path and os.path.exists(cta_path):
            try:
                cta_audio = AudioFileClip(cta_path)
                cta_audio = cta_audio.volumex(cta_volume)
                
                # Concatenate composite audio with CTA
                final_audio = concatenate_audioclips([composite_audio, cta_audio])
                # Ensure fps is set for concatenated audio
                try:
                    if hasattr(voice_audio, 'fps') and voice_audio.fps:
                        final_audio.fps = voice_audio.fps
                    else:
                        final_audio.fps = 44100
                except Exception as fps_error:
                    print(f"⚠️ Setting fps for final audio: {fps_error}")
                    final_audio.fps = 44100
                    
                print(f"✅ CTA added: {cta_audio.duration:.2f}s at the end")
                
            except Exception as cta_error:
                print(f"⚠️ CTA loading failed: {cta_error}")
                final_audio = composite_audio
        else:
            final_audio = composite_audio
        
        # Final fps check and fallback
        try:
            if not hasattr(final_audio, 'fps') or final_audio.fps is None:
                if hasattr(voice_audio, 'fps') and voice_audio.fps:
                    final_audio.fps = voice_audio.fps
                else:
                    final_audio.fps = 44100
        except Exception as fps_error:
            print(f"⚠️ Final fps check failed: {fps_error}")
            final_audio.fps = 44100
        
        # Save the mixed audio
        temp_mixed = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        temp_mixed.close()
        
        final_audio.write_audiofile(temp_mixed.name, verbose=False, logger=None)
        print(f"✅ Mixed audio saved: {temp_mixed.name}")
        print(f"   Final duration: {final_audio.duration:.2f}s")
        
        # Return additional timing information for subtitle generation
        timing_info = {
            'voice_duration': voice_duration,
            'cta_start': voice_duration if cta_path and os.path.exists(cta_path) else None,
            'cta_duration': cta_audio.duration if 'cta_audio' in locals() and cta_audio else 0,
            'total_duration': final_audio.duration
        }
        
        return temp_mixed.name, final_audio.duration, timing_info
        
    except Exception as e:
        print(f"❌ Audio mixing failed: {e}")
        traceback.print_exc()
        
        # Try to provide a working fallback - just use the original voice audio
        try:
            print("🔄 Using fallback: original voice audio only")
            fallback_audio = safe_load_audio(voice_audio_path)
            
            # Create a temporary file with just the voice audio
            temp_fallback = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            temp_fallback.close()
            fallback_audio.write_audiofile(temp_fallback.name, verbose=False, logger=None)
            
            voice_duration = fallback_audio.duration
            timing_info = {
                'voice_duration': voice_duration,
                'cta_start': None,
                'cta_duration': 0,
                'total_duration': voice_duration
            }
            
            print(f"✅ Fallback audio created: {temp_fallback.name} ({voice_duration:.2f}s)")
            return temp_fallback.name, voice_duration, timing_info
            
        except Exception as fallback_error:
            print(f"❌ Fallback audio creation also failed: {fallback_error}")
            # Last resort - return original file path
            voice_duration = 0
            try:
                fallback_audio = safe_load_audio(voice_audio_path)
                voice_duration = fallback_audio.duration
            except:
                voice_duration = 40.0  # Default fallback
                
            timing_info = {
                'voice_duration': voice_duration,
                'cta_start': None,
                'cta_duration': 0,
                'total_duration': voice_duration
            }
            return voice_audio_path, voice_duration, timing_info


def transcribe_cta_audio(cta_path, cta_start_time, model_name='base', language='en'):
    """Transcribe CTA audio and create subtitle segments with proper timing offset"""
    if not cta_path or not os.path.exists(cta_path):
        return []
    
    try:
        # Import whisper service here to avoid circular imports
        from whisper_service import transcribe_with_whisper
        from subtitle_service import create_segments_from_whisper_result
        
        print(f"🎤 Transcribing CTA audio: {cta_path}")
        print(f"   CTA starts at: {cta_start_time:.2f}s")
        
        # Transcribe the CTA audio
        cta_result = transcribe_with_whisper(cta_path, model_name=model_name, language=language)
        
        if not cta_result:
            print("❌ CTA transcription failed")
            return []
        
        # Create subtitle segments from CTA transcription
        cta_segments = create_segments_from_whisper_result(cta_result, max_chars_per_segment=45, max_duration=5.0, max_words=3)
        
        if not cta_segments:
            print("❌ No CTA subtitle segments created")
            return []
        
        # Adjust timing - offset all CTA segments by the voice audio duration
        adjusted_cta_segments = []
        for segment in cta_segments:
            adjusted_segment = segment.copy()
            adjusted_segment['start'] = segment['start'] + cta_start_time
            adjusted_segment['end'] = segment['end'] + cta_start_time
            # Mark as CTA for styling if needed
            adjusted_segment['type'] = 'cta'
            adjusted_cta_segments.append(adjusted_segment)
        
        print(f"✅ CTA subtitles created: {len(adjusted_cta_segments)} segments")
        print(f"   First CTA subtitle: '{adjusted_cta_segments[0]['text']}' ({adjusted_cta_segments[0]['start']:.2f}s-{adjusted_cta_segments[0]['end']:.2f}s)")
        
        return adjusted_cta_segments
        
    except Exception as e:
        print(f"❌ CTA transcription error: {e}")
        traceback.print_exc()
        return []


def safe_load_audio(path):
    """Safely load audio with fallback methods and frame access validation"""
    from config import MOVIEPY_AVAILABLE
    
    if not MOVIEPY_AVAILABLE:
        raise Exception("MoviePy not available")
    
    from moviepy.editor import AudioFileClip
    
    # First, try to normalize the audio file using FFmpeg for better compatibility
    normalized_path = f"{path}_normalized.wav"
    normalize_cmd = [
        'ffmpeg', '-y', '-i', path,
        '-ar', '44100',    # Standard sample rate (matching video output)
        '-ac', '2',        # Stereo
        '-c:a', 'pcm_s16le',  # Uncompressed audio for better quality
        '-filter:a', 'volume=2.0',  # Boost volume
        normalized_path
    ]
    
    normalize_result = run_cmd(normalize_cmd, check=False)
    audio_to_load = normalized_path if normalize_result.returncode == 0 and os.path.exists(normalized_path) else path
    
    try:
        audio = AudioFileClip(audio_to_load)
        if audio and hasattr(audio, 'duration') and audio.duration > 0:
            try:
                # Test audio frame access
                test_frame = audio.get_frame(min(0.1, audio.duration/2))
                if test_frame is not None:
                    print(f"✅ Audio loaded and validated successfully from {audio_to_load}")
                    return audio
                else:
                    raise ValueError("Cannot access audio frames")
            except Exception as frame_error:
                print(f"Audio frame access failed: {frame_error}")
                if hasattr(audio, 'close'):
                    audio.close()
                raise
        else:
            raise ValueError("Invalid audio duration")
    except Exception as e:
        print(f"AudioFileClip failed: {e}, trying repair...")
        temp_path = f"{path}_repaired.wav"
        result = run_cmd(['ffmpeg', '-i', audio_to_load, '-ar', '44100', '-ac', '2', temp_path, '-y'], check=False)
        if result.returncode == 0 and os.path.exists(temp_path):
            try:
                repaired_audio = AudioFileClip(temp_path)
                test_frame = repaired_audio.get_frame(0)
                if test_frame is not None:
                    print("✅ Audio repaired and loaded successfully")
                    return repaired_audio
                else:
                    if hasattr(repaired_audio, 'close'):
                        repaired_audio.close()
                    raise ValueError("Cannot access repaired audio frames")
            except Exception as repair_error:
                print(f"Repaired audio failed: {repair_error}")
                if 'repaired_audio' in locals() and hasattr(repaired_audio, 'close'):
                    repaired_audio.close()
                raise
        raise Exception(f"Failed to load audio: {e}")


def compress_audio(input_path, max_size_mb=0.5):
    """Compress audio for API compatibility"""
    try:
        # Get audio info first
        probe_cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', input_path]
        probe_result = run_cmd(probe_cmd, check=False)
        
        if probe_result.returncode != 0:
            return input_path
            
        audio_info = json.loads(probe_result.stdout)
        duration = float(audio_info['format']['duration'])
        
        output_path = input_path.replace('.', '_compressed.')
        target_bitrate = max(8, int((max_size_mb * 8 * 1024) / duration))
        
        cmd = [
            'ffmpeg', '-i', input_path, 
            '-b:a', f'{target_bitrate}k', 
            '-ar', '16000',  # Better quality than 8000
            '-ac', '1', 
            output_path, '-y'
        ]
        
        result = run_cmd(cmd, check=False)
        if result.returncode == 0 and os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"✅ Compressed audio: {size_mb:.2f}MB")
            return output_path
    except Exception as e:
        print(f"⚠️ Audio compression failed: {e}")
    
    return input_path


def load_voiceover(path):
    """Load voiceover audio file"""
    from config import MOVIEPY_AVAILABLE
    
    if not MOVIEPY_AVAILABLE:
        raise Exception("MoviePy not available")
    
    from moviepy.editor import AudioFileClip
    
    try:
        voiceover = safe_load_audio(path)
        print(f"✅ Voiceover loaded: {voiceover.duration:.2f}s")
        return voiceover
    except Exception as e:
        print(f"❌ Failed to load voiceover: {e}")
        raise


def load_bgm(path, duration, volume=0.6):
    """
    Load background music, loop/trim to duration, and adjust volume
    
    Args:
        path (str): Path to BGM file
        duration (float): Target duration in seconds
        volume (float): Volume multiplier (default 0.2 for medium volume)
        
    Returns:
        AudioFileClip: Processed BGM audio clip
    """
    from config import MOVIEPY_AVAILABLE
    
    if not MOVIEPY_AVAILABLE:
        raise Exception("MoviePy not available")
    
    from moviepy.editor import AudioFileClip, concatenate_audioclips
    
    try:
        bgm_audio = AudioFileClip(path)
        
        # Loop BGM to match target duration if needed
        if bgm_audio.duration < duration:
            loops_needed = int(duration / bgm_audio.duration) + 1
            bgm_looped = concatenate_audioclips([bgm_audio] * loops_needed)
            bgm_final = bgm_looped.subclip(0, duration)
        else:
            bgm_final = bgm_audio.subclip(0, duration)
        
        # Adjust volume for medium background level
        bgm_final = bgm_final.volumex(volume)
        
        print(f"✅ BGM loaded and processed: {bgm_audio.duration:.2f}s -> {duration:.2f}s, volume: {volume}")
        return bgm_final
        
    except Exception as e:
        print(f"❌ Failed to load BGM: {e}")
        raise


def load_cta(path):
    """Load call-to-action audio file"""
    from config import MOVIEPY_AVAILABLE
    
    if not MOVIEPY_AVAILABLE:
        raise Exception("MoviePy not available")
    
    from moviepy.editor import AudioFileClip
    
    try:
        cta = safe_load_audio(path)
        print(f"✅ CTA loaded: {cta.duration:.2f}s")
        return cta
    except Exception as e:
        print(f"❌ Failed to load CTA: {e}")
        raise


def merge_audio(voiceover_clip, bgm_clip, cta_clip=None):
    """
    Merge voiceover + BGM, optionally append CTA after voiceover
    
    Args:
        voiceover_clip: AudioFileClip with voiceover audio
        bgm_clip: AudioFileClip with background music
        cta_clip: Optional AudioFileClip with call-to-action audio
        
    Returns:
        tuple: (final_audio_clip, timing_info)
    """
    from config import MOVIEPY_AVAILABLE
    
    if not MOVIEPY_AVAILABLE:
        raise Exception("MoviePy not available")
    
    from moviepy.editor import CompositeAudioClip, concatenate_audioclips
    
    try:
        voiceover_duration = voiceover_clip.duration
        
        # Create composite of voiceover and BGM
        composite_audio = CompositeAudioClip([voiceover_clip, bgm_clip])
        # Ensure fps is properly set for composite audio
        try:
            if hasattr(voiceover_clip, 'fps') and voiceover_clip.fps:
                composite_audio.fps = voiceover_clip.fps
            else:
                composite_audio.fps = 44100
        except Exception as fps_error:
            print(f"⚠️ Setting fps for composite audio: {fps_error}")
            composite_audio.fps = 44100
        
        # Add CTA at the end if provided
        if cta_clip:
            final_audio = concatenate_audioclips([composite_audio, cta_clip])
            # Ensure fps is set for concatenated audio
            try:
                if hasattr(voiceover_clip, 'fps') and voiceover_clip.fps:
                    final_audio.fps = voiceover_clip.fps
                else:
                    final_audio.fps = 44100
            except Exception as fps_error:
                print(f"⚠️ Setting fps for final audio: {fps_error}")
                final_audio.fps = 44100
                
            cta_start = voiceover_duration
            total_duration = final_audio.duration
            print(f"✅ Audio merged: {voiceover_duration:.2f}s voice + BGM + {cta_clip.duration:.2f}s CTA = {total_duration:.2f}s total")
        else:
            final_audio = composite_audio
            cta_start = None
            total_duration = final_audio.duration
            print(f"✅ Audio merged: {voiceover_duration:.2f}s voice + BGM = {total_duration:.2f}s total")
        
        # Create timing info
        timing_info = {
            'voice_duration': voiceover_duration,
            'cta_start': cta_start,
            'cta_duration': cta_clip.duration if cta_clip else 0,
            'total_duration': total_duration
        }
        
        return final_audio, timing_info
        
    except Exception as e:
        print(f"❌ Failed to merge audio: {e}")
        raise
