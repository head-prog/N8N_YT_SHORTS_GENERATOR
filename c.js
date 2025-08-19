/**
 * TTS Script Cleaner for N8N Integration (JavaScript Version)
 * ===========================================================
 * 
 * This module provides functions to clean and normalize text scripts for TTS (Text-to-Speech) models.
 * It removes or replaces problematic characters that can cause misunderstandings or poor pronunciation.
 * 
 * Usage in N8N:
 * 1. Copy this entire code block
 * 2. Paste it into a "Code" node in N8N
 * 3. Set the language to "JavaScript"
 * 4. Use the cleanScriptForTTS() function
 * 
 * Author: N8N YouTube Shorts Generator
 * Repository: https://github.com/head-prog/N8N_YT_SHORTS_GENERATOR
 */

/**
 * Clean and normalize text for TTS processing.
 * 
 * This function removes or replaces characters that can cause TTS models to:
 * - Mispronounce words
 * - Create unnatural pauses
 * - Generate unexpected sounds
 * - Fail to process certain punctuation
 * 
 * @param {string} text - Raw script text to be cleaned
 * @returns {string} Cleaned text optimized for TTS processing
 * 
 * @example
 * const rawScript = "John 3:16 says: 'For God so loved...' — it's amazing!";
 * const cleanScript = cleanScriptForTTS(rawScript);
 * console.log(cleanScript); // "John 3 16 says, For God so loved, it's amazing!"
 */
function cleanScriptForTTS(text) {
    if (!text || typeof text !== 'string') {
        return '';
    }
    
    // Step 1: Replace colons with spaces (Bible verses, time references, etc.)
    text = text.replace(/:/g, ' ');
    
    // Step 2: Replace problematic punctuation with TTS-friendly alternatives
    const replacements = {
        '—': ',',           // Em dash to comma
        '–': ',',           // En dash to comma  
        '…': ',',           // Ellipsis to comma
        ';': ',',           // Semicolon to comma
        '"': '',            // Remove double quotes
        ''': "'",           // Normalize single quotes
        '"': '',            // Remove smart quotes
        '"': '',            // Remove smart quotes
        ''': "'",           // Normalize smart apostrophe
        ''': "'",           // Normalize smart apostrophe
        '(': ',',           // Replace parentheses with commas
        ')': ',',
        '[': ',',           // Replace brackets with commas
        ']': ',',
        '{': ',',           // Replace braces with commas
        '}': ',',
        '/': ' or ',        // Replace slash with "or"
        '\\': ' ',          // Replace backslash with space
        '*': '',            // Remove asterisks
        '#': '',            // Remove hashtags
        '@': ' at ',        // Replace @ with "at"
        '&': ' and ',       // Replace ampersand with "and"
        '%': ' percent ',   // Replace percent with word
        '$': ' dollars ',   // Replace dollar sign with word
        '€': ' euros ',     // Replace euro sign with word
        '£': ' pounds ',    // Replace pound sign with word
        '¥': ' yen ',       // Replace yen sign with word
        '©': '',            // Remove copyright symbol
        '®': '',            // Remove registered trademark
        '™': '',            // Remove trademark symbol
        '§': ' section ',   // Replace section symbol
        '¶': '',            // Remove paragraph symbol
        '†': '',            // Remove dagger
        '‡': '',            // Remove double dagger
        '•': ',',           // Replace bullet with comma
        '◦': ',',           // Replace bullet with comma
        '▪': ',',           // Replace bullet with comma
        '▫': ',',           // Replace bullet with comma
        '‣': ',',           // Replace bullet with comma
        '⁃': ',',           // Replace bullet with comma
    };
    
    // Apply all replacements
    for (const [oldChar, newChar] of Object.entries(replacements)) {
        text = text.replace(new RegExp(oldChar.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), newChar);
    }
    
    // Step 3: Handle numbers and special cases
    // Replace standalone numbers followed by colons (verse references)
    text = text.replace(/\b(\d+)\s*:\s*(\d+)\b/g, '$1 $2');
    
    // Step 4: Normalize whitespace and punctuation
    // Remove multiple consecutive commas
    text = text.replace(/,+/g, ',');
    
    // Remove comma at the beginning of sentences
    text = text.replace(/^\s*,+\s*/, '');
    text = text.replace(/\.\s*,+\s*/g, '. ');
    
    // Ensure proper spacing around punctuation
    text = text.replace(/\s*,\s*/g, ', ');
    text = text.replace(/\s*\.\s*/g, '. ');
    text = text.replace(/\s*\?\s*/g, '? ');
    text = text.replace(/\s*!\s*/g, '! ');
    
    // Step 5: Clean up whitespace
    // Replace multiple spaces with single space
    text = text.replace(/\s+/g, ' ');
    
    // Remove leading/trailing whitespace
    text = text.trim();
    
    // Remove trailing commas before punctuation
    text = text.replace(/,+\s*([.!?])/g, '$1');
    
    // Step 6: Final cleanup for common TTS issues
    // Ensure sentences end properly
    if (text && !text.match(/[.!?]$/)) {
        text += '.';
    }
    
    return text;
}

/**
 * Extract and clean script from N8N data structure.
 * 
 * This is a helper function specifically designed for N8N workflows
 * that extracts the script text from the data structure and cleans it.
 * 
 * @param {Object} data - N8N data object containing the script
 * @param {string} scriptField - Field name containing the script text
 * @returns {string} Cleaned script text ready for TTS
 */
function extractAndCleanScript(data, scriptField = 'voice_script') {
    try {
        let scriptText = '';
        
        if (typeof data === 'object' && data !== null) {
            // Try to get the script from various possible locations
            scriptText = data[scriptField] || 
                        data.script_text || 
                        data.text || 
                        data.content || 
                        '';
        } else if (typeof data === 'string') {
            scriptText = data;
        } else {
            scriptText = String(data);
        }
        
        return cleanScriptForTTS(scriptText);
    } catch (error) {
        console.log(`Error processing script: ${error.message}`);
        return '';
    }
}

/**
 * Validate that the cleaned script is suitable for TTS processing.
 * 
 * @param {string} text - Cleaned script text
 * @param {number} minLength - Minimum acceptable length
 * @param {number} maxLength - Maximum acceptable length
 * @returns {Object} Validation result with status and message
 */
function validateCleanedScript(text, minLength = 10, maxLength = 1000) {
    if (!text || typeof text !== 'string') {
        return { valid: false, message: 'Script is empty or invalid' };
    }
    
    const textLength = text.trim().length;
    
    if (textLength < minLength) {
        return { 
            valid: false, 
            message: `Script too short (${textLength} chars, minimum ${minLength})` 
        };
    }
    
    if (textLength > maxLength) {
        return { 
            valid: false, 
            message: `Script too long (${textLength} chars, maximum ${maxLength})` 
        };
    }
    
    // Check for problematic patterns that might still exist
    const problematicPatterns = [
        { pattern: /[^\w\s\.,!?\'-]/g, message: 'Contains special characters that may cause TTS issues' },
        { pattern: /\d+:\d+/g, message: 'Contains time/verse references with colons' },
        { pattern: /["""]/g, message: 'Contains smart quotes that may not be pronounced correctly' },
        { pattern: /\s{3,}/g, message: 'Contains excessive whitespace' },
    ];
    
    for (const { pattern, message } of problematicPatterns) {
        if (pattern.test(text)) {
            return { valid: false, message };
        }
    }
    
    return { valid: true, message: 'Script is valid for TTS processing' };
}

// N8N Integration Examples - Copy the code you need:

/* 
Example 1: Basic cleaning for your data structure
================================================
// Copy the cleanScriptForTTS function above, then use:
const voiceScript = $input.first().json.selected_script.voice_script;
const cleanedScript = cleanScriptForTTS(voiceScript);

return [{ cleaned_script: cleanedScript }];
*/

/* 
Example 2: Full processing with validation for your data structure
================================================================
// Copy all functions above, then use:
const scriptData = $input.first().json.selected_script;
const voiceScript = scriptData.voice_script || '';
const cleanedScript = cleanScriptForTTS(voiceScript);
const validation = validateCleanedScript(cleanedScript);

return [{
    cleaned_script: cleanedScript,
    validation: validation,
    original_length: voiceScript.length,
    cleaned_length: cleanedScript.length,
    is_valid: validation.valid,
    validation_message: validation.message
}];
*/

/* 
Example 3: Complete data passthrough with cleaning
=================================================
// Copy all functions above, then use:
const inputData = $input.first().json;
const scriptData = inputData.selected_script;
const voiceScript = scriptData.voice_script || '';
const cleanedScript = cleanScriptForTTS(voiceScript);

return [{
    title: scriptData.title || '',
    theme: scriptData.theme || '',
    original_voice_script: voiceScript,
    cleaned_voice_script: cleanedScript,
    visual_tips: scriptData.visual_tips || '',
    hook_strength: scriptData.hook_strength || '',
    estimated_duration: scriptData.estimated_duration || '',
    key_scripture: scriptData.key_scripture || '',
    engagement_score: scriptData.engagement_score || '',
    script_text: scriptData.script_text || '',
    processing_info: {
        script_length: voiceScript.length,
        cleaned_length: cleanedScript.length,
        word_count: cleanedScript.split(' ').length,
        timestamp: scriptData.processing_info?.timestamp || new Date().toISOString()
    }
}];
*/

/* 
Example 4: Simple one-liner for quick use
========================================
// Copy the cleanScriptForTTS function above, then use:
return [{ 
    cleaned_script: cleanScriptForTTS($input.first().json.selected_script.voice_script || '') 
}];
*/

/* 
Example 5: Error-safe processing with fallbacks
==============================================
// Copy all functions above, then use:
try {
    const inputData = $input.first().json;
    const scriptData = inputData.selected_script || {};
    const voiceScript = scriptData.voice_script || scriptData.script_text || '';
    
    if (!voiceScript) {
        return [{ error: 'No voice script found in input data', cleaned_script: '' }];
    }
    
    const cleanedScript = cleanScriptForTTS(voiceScript);
    const validation = validateCleanedScript(cleanedScript);
    
    return [{
        success: true,
        original_script: voiceScript,
        cleaned_script: cleanedScript,
        character_count: cleanedScript.length,
        word_count: cleanedScript.split(' ').filter(word => word.length > 0).length,
        validation: validation,
        timestamp: new Date().toISOString()
    }];
    
} catch (error) {
    return [{
        success: false,
        error: error.message,
        cleaned_script: '',
        timestamp: new Date().toISOString()
    }];
}
*/

// Test function (for development/debugging)
function testCleanScript() {
    const sampleScript = `
    When you feel invisible and alone, like no one truly sees your heart... The Bible says, 
    "The Lord is close to the brokenhearted and saves those who are crushed in spirit." — Psalm 34:18. 
    Imagine sitting quietly in your room, the silence wrapping around you like a heavy blanket. 
    You reach out, but no one answers. Yet, right there, God's presence is near, quietly comforting 
    every ache and whispering peace to your soul. Even in moments when loneliness feels overwhelming, 
    His promise reminds us: you are never truly alone. His love is a constant, tender embrace. 
    So, when the world feels distant, re...
    `;
    
    console.log('Original script:');
    console.log(sampleScript);
    console.log('\n' + '='.repeat(50) + '\n');
    
    const cleaned = cleanScriptForTTS(sampleScript);
    console.log('Cleaned script:');
    console.log(cleaned);
    console.log('\n' + '='.repeat(50) + '\n');
    
    const validation = validateCleanedScript(cleaned);
    console.log('Validation result:');
    console.log(validation);
    
    return {
        original: sampleScript,
        cleaned: cleaned,
        validation: validation
    };
}

// Export functions for Node.js environments (if needed)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        cleanScriptForTTS,
        extractAndCleanScript,
        validateCleanedScript,
        testCleanScript
    };
}
