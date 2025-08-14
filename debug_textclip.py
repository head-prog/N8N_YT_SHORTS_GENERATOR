#!/usr/bin/env python3

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from moviepy import TextClip
import inspect

def check_textclip_parameters():
    """Check what parameters TextClip actually accepts in this MoviePy version"""
    try:
        sig = inspect.signature(TextClip.__init__)
        print("✅ TextClip accepted parameters:")
        for param_name, param in sig.parameters.items():
            if param_name != 'self':
                print(f"  - {param_name}: {param.default}")
        print()
    except Exception as e:
        print(f"❌ Could not inspect TextClip parameters: {e}")

def test_simple_textclip():
    """Test creating a simple TextClip"""
    try:
        print("🔍 Testing simple TextClip creation...")
        
        # Test 1: Basic TextClip
        clip = TextClip("Hello World", fontsize=48, color='white')
        print("✅ Basic TextClip works!")
        print(f"   Duration: {clip.duration}")
        print(f"   Size: {clip.size}")
        clip.close()
        
        # Test 2: TextClip with stroke
        clip = TextClip("Hello World", fontsize=48, color='white', stroke_color='black', stroke_width=2)
        print("✅ TextClip with stroke works!")
        clip.close()
        
        # Test 3: TextClip with method='caption'
        clip = TextClip("Hello World", fontsize=48, color='white', method='caption', size=(400, None))
        print("✅ TextClip with caption method works!")
        clip.close()
        
        return True
        
    except Exception as e:
        print(f"❌ TextClip creation failed: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

def test_textclip_with_font_size():
    """Test TextClip with font_size parameter (MoviePy 2.x style)"""
    try:
        print("🔍 Testing TextClip with font_size parameter...")
        
        clip = TextClip("Hello World", font_size=48, color='white')
        print("✅ TextClip with font_size works!")
        clip.close()
        return True
        
    except Exception as e:
        print(f"❌ TextClip with font_size failed: {e}")
        print("   This suggests MoviePy version issue")
        return False

if __name__ == "__main__":
    print("🚀 MoviePy TextClip Debug Test")
    print("=" * 50)
    
    # Check MoviePy version
    try:
        import moviepy
        print(f"📦 MoviePy version: {moviepy.__version__}")
    except:
        print("❌ Could not get MoviePy version")
    
    print()
    
    # Check TextClip parameters
    check_textclip_parameters()
    
    # Test basic functionality
    basic_works = test_simple_textclip()
    print()
    
    # Test MoviePy 2.x style parameters
    font_size_works = test_textclip_with_font_size()
    print()
    
    if basic_works:
        print("✅ Basic TextClip functionality works")
    else:
        print("❌ Basic TextClip functionality broken")
    
    if font_size_works:
        print("✅ MoviePy 2.x style parameters work")
    else:
        print("❌ MoviePy 2.x style parameters don't work - use fontsize instead")
