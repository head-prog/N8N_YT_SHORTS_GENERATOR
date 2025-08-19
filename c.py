"""
TTS Script Cleaner for N8N Integration
=====================================

This module provides functions to clean and normalize text scripts for TTS (Text-to-Speech) models.
It removes or replaces problematic characters that can cause misunderstandings or poor pronunciation.

Usage in N8N:
1. Copy this entire code block
2. Paste it into a "Code" node in N8N
3. Set the language to "Python"
4. Use the clean_script_for_tts() function

Author: N8N YouTube Shorts Generator
Repository: https://github.com/head-prog/N8N_YT_SHORTS_GENERATOR
"""

import re
import string

def clean_script_for_tts(text):
    """
    Clean and normalize text for TTS processing.
    
    This function removes or replaces characters that can cause TTS models to:
    - Mispronounce words
    - Create unnatural pauses
    - Generate unexpected sounds
    - Fail to process certain punctuation
    
    Args:
        text (str): Raw script text to be cleaned
        
    Returns:
        str: Cleaned text optimized for TTS processing
        
    Example:
        >>> raw_script = "John 3:16 says: 'For God so loved...' — it's amazing!"
        >>> clean_script = clean_script_for_tts(raw_script)
        >>> print(clean_script)
        "John 3 16 says, For God so loved, it's amazing!"
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Step 1: Replace colons with spaces (Bible verses, time references, etc.)
    text = text.replace(":", " ")
    
    # Step 2: Replace problematic punctuation with TTS-friendly alternatives
    replacements = {
        "—": ",",           # Em dash to comma
        "–": ",",           # En dash to comma  
        "…": ",",           # Ellipsis to comma
        ";": ",",           # Semicolon to comma
        '"': "",            # Remove double quotes
        "'": "'",           # Normalize single quotes
        """: "",            # Remove smart quotes
        """: "",            # Remove smart quotes
        "'": "'",           # Normalize smart apostrophe
        "'": "'",           # Normalize smart apostrophe
        "(": ",",           # Replace parentheses with commas
        ")": ",",
        "[": ",",           # Replace brackets with commas
        "]": ",",
        "{": ",",           # Replace braces with commas
        "}": ",",
        "/": " or ",        # Replace slash with "or"
        "\\": " ",          # Replace backslash with space
        "*": "",            # Remove asterisks
        "#": "",            # Remove hashtags
        "@": " at ",        # Replace @ with "at"
        "&": " and ",       # Replace ampersand with "and"
        "%": " percent ",   # Replace percent with word
        "$": " dollars ",   # Replace dollar sign with word
        "€": " euros ",     # Replace euro sign with word
        "£": " pounds ",    # Replace pound sign with word
        "¥": " yen ",       # Replace yen sign with word
        "©": "",            # Remove copyright symbol
        "®": "",            # Remove registered trademark
        "™": "",            # Remove trademark symbol
        "§": " section ",   # Replace section symbol
        "¶": "",            # Remove paragraph symbol
        "†": "",            # Remove dagger
        "‡": "",            # Remove double dagger
        "•": ",",           # Replace bullet with comma
        "◦": ",",           # Replace bullet with comma
        "▪": ",",           # Replace bullet with comma
        "▫": ",",           # Replace bullet with comma
        "‣": ",",           # Replace bullet with comma
        "⁃": ",",           # Replace bullet with comma
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    # Step 3: Handle numbers and special cases
    # Replace standalone numbers followed by colons (verse references)
    text = re.sub(r'\b(\d+)\s*:\s*(\d+)\b', r'\1 \2', text)
    
    # Step 4: Normalize whitespace and punctuation
    # Remove multiple consecutive commas
    text = re.sub(r',+', ',', text)
    
    # Remove comma at the beginning of sentences
    text = re.sub(r'^\s*,+\s*', '', text)
    text = re.sub(r'\.\s*,+\s*', '. ', text)
    
    # Ensure proper spacing around punctuation
    text = re.sub(r'\s*,\s*', ', ', text)
    text = re.sub(r'\s*\.\s*', '. ', text)
    text = re.sub(r'\s*\?\s*', '? ', text)
    text = re.sub(r'\s*!\s*', '! ', text)
    
    # Step 5: Clean up whitespace
    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    # Remove trailing commas before punctuation
    text = re.sub(r',+\s*([.!?])', r'\1', text)
    
    # Step 6: Final cleanup for common TTS issues
    # Ensure sentences end properly
    if text and text[-1] not in '.!?':
        text += '.'
    
    return text

def extract_and_clean_script(data, script_field='voice_script'):
    """
    Extract and clean script from N8N data structure.
    
    This is a helper function specifically designed for N8N workflows
    that extracts the script text from the data structure and cleans it.
    
    Args:
        data (dict): N8N data object containing the script
        script_field (str): Field name containing the script text
        
    Returns:
        str: Cleaned script text ready for TTS
        
    Example N8N usage:
        ```python
        # In N8N Code node:
        cleaned_script = extract_and_clean_script($json, 'voice_script')
        return {"cleaned_script": cleaned_script}
        ```
    """
    try:
        # Handle different N8N data structures
        if isinstance(data, dict):
            # Try to get the script from various possible locations
            script_text = (
                data.get(script_field) or 
                data.get('script_text') or 
                data.get('text') or 
                data.get('content') or
                ""
            )
        elif isinstance(data, str):
            script_text = data
        else:
            script_text = str(data)
        
        return clean_script_for_tts(script_text)
    
    except Exception as e:
        print(f"Error processing script: {str(e)}")
        return ""

def validate_cleaned_script(text, min_length=10, max_length=1000):
    """
    Validate that the cleaned script is suitable for TTS processing.
    
    Args:
        text (str): Cleaned script text
        min_length (int): Minimum acceptable length
        max_length (int): Maximum acceptable length
        
    Returns:
        dict: Validation result with status and message
        
    Example:
        >>> result = validate_cleaned_script("This is a test script.")
        >>> print(result)
        {"valid": True, "message": "Script is valid for TTS processing"}
    """
    if not text or not isinstance(text, str):
        return {"valid": False, "message": "Script is empty or invalid"}
    
    text_length = len(text.strip())
    
    if text_length < min_length:
        return {"valid": False, "message": f"Script too short ({text_length} chars, minimum {min_length})"}
    
    if text_length > max_length:
        return {"valid": False, "message": f"Script too long ({text_length} chars, maximum {max_length})"}
    
    # Check for problematic patterns that might still exist
    problematic_patterns = [
        (r'[^\w\s\.,!?\'-]', "Contains special characters that may cause TTS issues"),
        (r'\d+:\d+', "Contains time/verse references with colons"),
        (r'["""]', "Contains smart quotes that may not be pronounced correctly"),
        (r'\s{3,}', "Contains excessive whitespace"),
    ]
    
    for pattern, message in problematic_patterns:
        if re.search(pattern, text):
            return {"valid": False, "message": message}
    
    return {"valid": True, "message": "Script is valid for TTS processing"}

# N8N Integration Examples:
"""
Example 1: Basic cleaning in N8N Code node
==========================================
```python
# Copy the clean_script_for_tts function above, then use:
raw_script = $json.selected_script.voice_script
cleaned_script = clean_script_for_tts(raw_script)

# N8N requires an array of dictionaries
return [{"cleaned_script": cleaned_script}]
```

Example 2: Full processing with validation
==========================================
```python
# Copy all functions above, then use:
data = $json.selected_script
cleaned_script = extract_and_clean_script(data, 'voice_script')
validation = validate_cleaned_script(cleaned_script)

# N8N requires an array of dictionaries
return [{
    "cleaned_script": cleaned_script,
    "validation": validation,
    "original_length": len(data.get('voice_script', '')),
    "cleaned_length": len(cleaned_script),
    "is_valid": validation['valid'],
    "validation_message": validation['message']
}]
```

Example 3: Processing multiple scripts
=====================================
```python
# Copy all functions above, then use:
scripts = $json.items  # Array of script objects
results = []

for item in scripts:
    cleaned = extract_and_clean_script(item, 'voice_script')
    validation = validate_cleaned_script(cleaned)
    
    results.append({
        "original": item.get('voice_script', ''),
        "cleaned": cleaned,
        "valid": validation['valid'],
        "message": validation['message']
    })

# N8N requires an array of dictionaries - return the results array directly
return results
```

Example 4: Simple single item processing (most common use case)
===============================================================
```python
# Copy the clean_script_for_tts function above, then use:
# For processing a single script from incoming data

# Get the script text from various possible field names
script_text = (
    $json.voice_script or 
    $json.script_text or 
    $json.text or 
    $json.content or 
    str($json)
)

# Clean the script
cleaned_script = clean_script_for_tts(script_text)

# Return as array for N8N
return [{
    "original_script": script_text,
    "cleaned_script": cleaned_script,
    "character_count": len(cleaned_script)
}]
```

Example 5: Processing from selected_script structure (like your data)
====================================================================
```python
# Copy the clean_script_for_tts function above, then use:
# This matches your data structure from the screenshot

# Extract script from the selected_script structure
script_data = $json.selected_script
voice_script = script_data.get('voice_script', '')

# Clean the script
cleaned_script = clean_script_for_tts(voice_script)

# Return all relevant data as array for N8N
return [{
    "title": script_data.get('title', ''),
    "theme": script_data.get('theme', ''),
    "original_voice_script": voice_script,
    "cleaned_voice_script": cleaned_script,
    "visual_tips": script_data.get('visual_tips', ''),
    "hook_strength": script_data.get('hook_strength', ''),
    "estimated_duration": script_data.get('estimated_duration', ''),
    "key_scripture": script_data.get('key_scripture', ''),
    "engagement_score": script_data.get('engagement_score', ''),
    "script_text": script_data.get('script_text', ''),
    "processing_info": {
        "script_length": len(voice_script),
        "cleaned_length": len(cleaned_script),
        "word_count": len(cleaned_script.split()),
        "timestamp": script_data.get('processing_info', {}).get('timestamp', '')
    }
}]
```
"""

if __name__ == "__main__":
    # Test the functions with sample data
    sample_script = """
    When you feel invisible and alone, like no one truly sees your heart... The Bible says, 
    "The Lord is close to the brokenhearted and saves those who are crushed in spirit." — Psalm 34:18. 
    Imagine sitting quietly in your room, the silence wrapping around you like a heavy blanket. 
    You reach out, but no one answers. Yet, right there, God's presence is near, quietly comforting 
    every ache and whispering peace to your soul. Even in moments when loneliness feels overwhelming, 
    His promise reminds us: you are never truly alone. His love is a constant, tender embrace. 
    So, when the world feels distant, re...
    """
    
    print("Original script:")
    print(sample_script)
    print("\n" + "="*50 + "\n")
    
    cleaned = clean_script_for_tts(sample_script)
    print("Cleaned script:")
    print(cleaned)
    print("\n" + "="*50 + "\n")
    
    validation = validate_cleaned_script(cleaned)
    print("Validation result:")
    print(validation)
