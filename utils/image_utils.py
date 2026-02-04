from PIL import ImageDraw, ImageFont
import time
import os

def overlay_timestamp(image, camera_id=None):
    """
    Draws a timestamp and Camera ID on the PIL image.
    Automatically scales font size based on image height.
    """
    if image is None:
        return None

    draw = ImageDraw.Draw(image)
    width, height = image.size
    
    # Dynamic font size: ~3% of image height
    font_size = int(height * 0.03) 
    if font_size < 20: font_size = 20
    
    # Try to load a nice font, fallback to default
    try:
        # Windows usually has arial.ttf
        font = ImageFont.truetype("arial.ttf", font_size)
    except IOError:
        font = ImageFont.load_default()

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    text = f"{timestamp}"
    if camera_id:
        text = f"CAM {camera_id} | {text}"

    # Draw text with outline for better visibility
    x, y = int(width * 0.02), int(height * 0.02)
    
    # Outline/Shadow
    outline_color = "black"
    text_color = "#00FF00" # Green
    
    # draw.text((x, y), text, font=font, fill=text_color, stroke_width=stroke_width, stroke_fill=outline_color)
    # Fallback to simple text due to "raster overflow" error in some PIL versions with large images
    draw.text((x, y), text, font=font, fill=text_color)

    return image
