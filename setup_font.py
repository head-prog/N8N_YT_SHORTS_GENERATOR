#!/usr/bin/env python3
"""
Font Setup for Bangers Font
Ensures Bangers font is available for all subtitle rendering methods
"""

import os
import shutil
from pathlib import Path

def setup_bangers_font():
    """Setup Bangers font for system-wide availability"""
    
    # Current font file path
    current_dir = Path(__file__).parent
    bangers_source = current_dir / "Bangers" / "Bangers-Regular.ttf"
    
    if not bangers_source.exists():
        print(f"❌ Bangers font not found at: {bangers_source}")
        return False
    
    print(f"📁 Found Bangers font at: {bangers_source}")
    
    # Install to macOS user fonts directory
    user_fonts_dir = Path.home() / "Library" / "Fonts"
    user_fonts_dir.mkdir(exist_ok=True)
    
    bangers_dest = user_fonts_dir / "Bangers-Regular.ttf"
    
    try:
        if bangers_dest.exists():
            print(f"✅ Bangers font already installed in user fonts")
        else:
            shutil.copy2(bangers_source, bangers_dest)
            print(f"✅ Bangers font installed to: {bangers_dest}")
        
        # Also copy to system temp for FFmpeg access
        temp_font = Path("/tmp") / "Bangers-Regular.ttf"
        shutil.copy2(bangers_source, temp_font)
        print(f"✅ Bangers font copied to temp: {temp_font}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to install Bangers font: {e}")
        return False

def get_bangers_font_path():
    """Get the best available path for Bangers font"""
    
    # Check user fonts first
    user_font = Path.home() / "Library" / "Fonts" / "Bangers-Regular.ttf"
    if user_font.exists():
        return str(user_font)
    
    # Check local font
    current_dir = Path(__file__).parent
    local_font = current_dir / "Bangers" / "Bangers-Regular.ttf"
    if local_font.exists():
        return str(local_font)
    
    # Check temp
    temp_font = Path("/tmp") / "Bangers-Regular.ttf"
    if temp_font.exists():
        return str(temp_font)
    
    return None

if __name__ == "__main__":
    success = setup_bangers_font()
    if success:
        font_path = get_bangers_font_path()
        print(f"🎨 Bangers font available at: {font_path}")
    else:
        print("❌ Failed to setup Bangers font")
