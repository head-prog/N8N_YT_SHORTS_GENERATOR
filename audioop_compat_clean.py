"""
Compatibility layer for audioop module (removed in Python 3.13)
Provides basic functionality needed by PyDub
"""

import array
import struct
import math

def mul(fragment, width, factor):
    """Multiply all samples in a fragment by a factor."""
    if width == 1:
        fmt = 'b'
        min_val, max_val = -128, 127
    elif width == 2:
        fmt = 'h'
        min_val, max_val = -32768, 32767
    elif width == 4:
        fmt = 'i'
        min_val, max_val = -2147483648, 2147483647
    else:
        raise ValueError("Unsupported sample width")
    
    samples = array.array(fmt, fragment)
    for i in range(len(samples)):
        # Handle overflow/underflow by clamping
        val = int(samples[i] * factor)
        if val > max_val:
            val = max_val
        elif val < min_val:
            val = min_val
        samples[i] = val
    
    return samples.tobytes()

def add(fragment1, fragment2, width):
    """Add two audio fragments sample by sample."""
    if width == 1:
        fmt = 'b'
        min_val, max_val = -128, 127
    elif width == 2:
        fmt = 'h'
        min_val, max_val = -32768, 32767
    elif width == 4:
        fmt = 'i'
        min_val, max_val = -2147483648, 2147483647
    else:
        raise ValueError("Unsupported sample width")
    
    samples1 = array.array(fmt, fragment1)
    samples2 = array.array(fmt, fragment2)
    
    # Make sure both fragments have the same length
    min_len = min(len(samples1), len(samples2))
    result = array.array(fmt)
    
    for i in range(min_len):
        # Handle overflow/underflow by clamping
        sum_val = samples1[i] + samples2[i]
        if sum_val > max_val:
            sum_val = max_val
        elif sum_val < min_val:
            sum_val = min_val
        result.append(sum_val)
    
    return result.tobytes()

def lin2lin(fragment, width, newwidth):
    """Convert between different sample widths."""
    if width == newwidth:
        return fragment
    
    if width == 1:
        samples = array.array('b', fragment)
    elif width == 2:
        samples = array.array('h', fragment)
    elif width == 4:
        samples = array.array('i', fragment)
    else:
        raise ValueError("Unsupported input sample width")
    
    if newwidth == 1:
        result = array.array('b')
        for sample in samples:
            result.append(sample >> (8 * (width - 1)))
    elif newwidth == 2:
        result = array.array('h')
        if width == 1:
            for sample in samples:
                result.append(sample << 8)
        else:  # width == 4
            for sample in samples:
                result.append(sample >> 16)
    elif newwidth == 4:
        result = array.array('i')
        for sample in samples:
            result.append(sample << (8 * (4 - width)))
    else:
        raise ValueError("Unsupported output sample width")
    
    return result.tobytes()

def minmax(fragment, width):
    """Return the minimum and maximum values of the samples."""
    if width == 1:
        fmt = 'b'
    elif width == 2:
        fmt = 'h'
    elif width == 4:
        fmt = 'i'
    else:
        raise ValueError("Unsupported sample width")
    
    samples = array.array(fmt, fragment)
    if not samples:
        return 0, 0
    
    return __builtins__['min'](samples), __builtins__['max'](samples)

def maxabs(fragment, width):
    """Return the maximum absolute value of the samples."""
    min_val, max_val = minmax(fragment, width)
    return __builtins__['max'](abs(min_val), abs(max_val))

def avg(fragment, width):
    """Return the average value of the samples."""
    if width == 1:
        fmt = 'b'
    elif width == 2:
        fmt = 'h'
    elif width == 4:
        fmt = 'i'
    else:
        raise ValueError("Unsupported sample width")
    
    samples = array.array(fmt, fragment)
    if not samples:
        return 0
    
    return sum(samples) // len(samples)

def rms(fragment, width):
    """Return the root-mean-square of the samples."""
    if width == 1:
        fmt = 'b'
    elif width == 2:
        fmt = 'h'
    elif width == 4:
        fmt = 'i'
    else:
        raise ValueError("Unsupported sample width")
    
    samples = array.array(fmt, fragment)
    if not samples:
        return 0
    
    sum_squares = sum(sample * sample for sample in samples)
    mean_square = sum_squares / len(samples)
    return int(math.sqrt(mean_square))
