"""
Skin processing utilities for Player Models plugin.

Handles skin validation, 3D skin detection, and texture saving.
"""

import re
from pathlib import Path
from typing import Set, Tuple

import numpy as np
from PIL import Image


def is_3d_skin(image: np.ndarray) -> bool:
    """
    Check if the skin is a 3D/custom skin that should be skipped.
    
    Standard Bedrock skins are:
    - 64x32 (legacy format)
    - 64x64 (modern format)
    - 128x128 (high-res Bedrock format)
    - 128x64 (some Bedrock skins)
    
    3D/Custom skins are typically:
    - 256x256 or larger
    - Non-standard dimensions
    
    Args:
        image: Numpy array representing the skin image (RGBA)
        
    Returns:
        True if this is a 3D/custom skin that should be skipped
    """
    if image is None:
        return True
    
    shape = image.shape
    if len(shape) < 2:
        return True
    
    height, width = shape[0], shape[1]
    
    # Valid standard skin sizes (height, width) - numpy array format
    valid_sizes = [
        (32, 64),    # Legacy 64x32 format
        (64, 64),    # Modern 64x64 format
        (64, 128),   # Some Bedrock skins
        (128, 128),  # High-res Bedrock format
    ]
    
    # Accept any of the valid sizes
    if (height, width) in valid_sizes:
        return False
    
    # Also accept if width is 64 and height is reasonable (32-128)
    if width == 64 and 32 <= height <= 128:
        return False
    
    # Reject very large skins (likely 3D custom skins)
    if width >= 256 or height >= 256:
        return True
    
    # Be permissive for other sizes - don't skip
    return False


def sanitize_player_name(name: str) -> str:
    """
    Convert a player name to a valid entity ID component.
    
    Rules:
    - Lowercase all characters
    - Replace spaces with underscores
    - Remove any characters that aren't alphanumeric or underscore
    
    Args:
        name: The player's display name
        
    Returns:
        A sanitized string suitable for use in entity identifiers
    """
    # Lowercase
    result = name.lower()
    
    # Replace spaces with underscores
    result = result.replace(" ", "_")
    
    # Remove invalid characters (keep only alphanumeric and underscore)
    result = re.sub(r'[^a-z0-9_]', '', result)
    
    # Ensure it doesn't start with a number
    if result and result[0].isdigit():
        result = "_" + result
    
    # Ensure we have something
    if not result:
        result = "unknown_player"
    
    return result


def get_next_version(base_entity_id: str, existing_ids: Set[str]) -> str:
    """
    Get the next available version of an entity ID.
    
    If "playername" exists, returns "playername2", then "playername3", etc.
    If "playername" doesn't exist, returns "playername" (no version suffix).
    
    Args:
        base_entity_id: The base entity ID (sanitized player name)
        existing_ids: Set of existing entity IDs (without namespace)
        
    Returns:
        The next available entity ID
    """
    if base_entity_id not in existing_ids:
        return base_entity_id
    
    # Find the next available version number
    version = 2
    while f"{base_entity_id}{version}" in existing_ids:
        version += 1
    
    return f"{base_entity_id}{version}"


def save_skin_texture(image: np.ndarray, texture_path: Path, logger=None) -> bool:
    """
    Save a skin image as a PNG texture file.
    
    Args:
        image: Numpy array representing the skin (RGBA format)
        texture_path: Path where the texture should be saved
        logger: Optional logger for error messages
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Validate image data
        if image is None:
            if logger:
                logger.error("Cannot save texture: image is None")
            return False
        
        if len(image.shape) < 2:
            if logger:
                logger.error(f"Cannot save texture: invalid image shape {image.shape}")
            return False
        
        height, width = image.shape[0], image.shape[1]
        
        # Validate minimum dimensions (at least 64x32 for skins)
        if width < 32 or height < 32:
            if logger:
                logger.error(f"Cannot save texture: image too small ({width}x{height})")
            return False
        
        # Check if image has any non-zero data
        if np.all(image == 0):
            if logger:
                logger.error("Cannot save texture: image is completely black/empty")
            return False
        
        # Ensure parent directory exists
        texture_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert numpy array to PIL Image
        # Endstone provides RGBA image data as numpy array
        if len(image.shape) == 3 and image.shape[2] == 4:
            # RGBA image
            pil_image = Image.fromarray(image.astype(np.uint8), mode='RGBA')
        elif len(image.shape) == 3 and image.shape[2] == 3:
            # RGB image (no alpha) - convert to RGBA
            pil_image = Image.fromarray(image.astype(np.uint8), mode='RGB').convert('RGBA')
        elif len(image.shape) == 2:
            # Grayscale - convert to RGBA
            pil_image = Image.fromarray(image.astype(np.uint8), mode='L').convert('RGBA')
        else:
            if logger:
                logger.error(f"Cannot save texture: unexpected image format {image.shape}")
            return False
        
        # Save as PNG with optimization
        pil_image.save(texture_path, 'PNG', optimize=True)
        
        # Verify saved file exists and has reasonable size
        if not texture_path.exists():
            if logger:
                logger.error(f"Texture save failed: file not created at {texture_path}")
            return False
        
        file_size = texture_path.stat().st_size
        min_size = 500  # Minimum expected size for a valid skin texture
        
        if file_size < min_size:
            if logger:
                logger.warning(f"Saved texture may be corrupt: only {file_size} bytes (expected >{min_size})")
            # Don't fail, just warn - some small valid skins exist
        
        return True
        
    except Exception as e:
        if logger:
            logger.error(f"Failed to save texture: {e}")
        return False


def get_skin_dimensions(image: np.ndarray) -> Tuple[int, int]:
    """
    Get the dimensions of a skin image.
    
    Args:
        image: Numpy array representing the skin
        
    Returns:
        Tuple of (width, height)
    """
    if image is None or len(image.shape) < 2:
        return (0, 0)
    
    return (image.shape[1], image.shape[0])
