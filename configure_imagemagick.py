#!/usr/bin/env python3
"""
Configure MoviePy to use ImageMagick properly
"""

import os
import sys

def configure_moviepy_imagemagick():
    """Configure MoviePy to use the correct ImageMagick binary"""
    
    # Find MoviePy config file location
    try:
        import moviepy.config as config
        print(f"MoviePy config location: {config.__file__}")
        
        # Check current ImageMagick binary setting
        print(f"Current ImageMagick binary: {config.IMAGEMAGICK_BINARY}")
        
        # Set the correct path
        imagemagick_path = "/usr/local/bin/convert"
        if os.path.exists(imagemagick_path):
            print(f"✅ Found ImageMagick at: {imagemagick_path}")
            
            # Update the config
            config.change_settings({"IMAGEMAGICK_BINARY": imagemagick_path})
            print(f"✅ Updated MoviePy config to use: {imagemagick_path}")
            
            # Test if it works
            try:
                from moviepy.editor import TextClip
                test_clip = TextClip("TEST", fontsize=20, color='white', font='Arial')
                if test_clip:
                    print("✅ ImageMagick configuration successful!")
                    test_clip.close()
                    return True
            except Exception as e:
                print(f"⚠️ Test failed: {e}")
                return False
        else:
            print(f"❌ ImageMagick not found at: {imagemagick_path}")
            return False
            
    except Exception as e:
        print(f"❌ Failed to configure MoviePy: {e}")
        return False

def create_moviepy_config():
    """Create a local MoviePy config file"""
    config_content = '''# MoviePy Configuration
import os

# ImageMagick binary location
IMAGEMAGICK_BINARY = "/usr/local/bin/convert"

# Set environment variable
os.environ["IMAGEMAGICK_BINARY"] = IMAGEMAGICK_BINARY
'''
    
    config_path = "moviepy_config.py"
    with open(config_path, 'w') as f:
        f.write(config_content)
    
    print(f"✅ Created MoviePy config: {config_path}")

if __name__ == "__main__":
    print("🔧 Configuring MoviePy with ImageMagick...")
    
    # Create local config
    create_moviepy_config()
    
    # Try to configure MoviePy
    success = configure_moviepy_imagemagick()
    
    if success:
        print("✅ MoviePy ImageMagick configuration complete!")
    else:
        print("⚠️ Configuration may need manual adjustment")
