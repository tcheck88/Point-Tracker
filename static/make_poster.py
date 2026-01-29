import qrcode
from PIL import Image, ImageDraw, ImageFont

# --- CONFIGURATION ---
LOGO_FILENAME = 'logo.jpg'  # Your file
URL = "https://www.thelittlespanishenglishschool.com/guide"
TEXT_CONTENT = "Escanea para ver la guía móvil"
OUTPUT_FILENAME = "LeerMexico_QR_Poster.png"

# Colors (Approximated from your logo)
MEXICO_GREEN = (0, 104, 71)  # Dark Green
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

def create_poster():
    # 1. Open the Logo
    try:
        logo = Image.open(LOGO_FILENAME)
    except FileNotFoundError:
        print(f"Error: Could not find {LOGO_FILENAME}. Make sure it is in the same folder.")
        return

    # resize logo if it's huge, to keep file size manageable (e.g. max 800px wide)
    max_width = 800
    if logo.width > max_width:
        ratio = max_width / logo.width
        new_height = int(logo.height * ratio)
        logo = logo.resize((max_width, new_height), Image.Resampling.LANCZOS)

    # 2. Generate the QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H, # High error correction
        box_size=10,
        border=2,
    )
    qr.add_data(URL)
    qr.make(fit=True)

    # Create the QR image (Green pixels, White background)
    qr_img = qr.make_image(fill_color=MEXICO_GREEN, back_color=WHITE).convert('RGB')
    
    # 3. Add the book icon to the center of the QR code (Optional, but matches your request)
    # We will resize a tiny version of the main logo or just leave it clean. 
    # For now, let's keep it clean to ensure scanability, or we can paste a tiny logo in the middle.
    # (Uncomment the block below to add a logo center)
    """
    center_size = int(qr_img.width / 4)
    center_icon = logo.resize((center_size, center_size))
    pos = ((qr_img.width - center_size) // 2, (qr_img.height - center_size) // 2)
    qr_img.paste(center_icon, pos)
    """

    # 4. Create the Canvas
    # Width = max(logo width, qr width) + margins
    canvas_width = max(logo.width, qr_img.width) + 100
    # Height = Logo + Padding + QR + Padding + Text + Padding
    canvas_height = logo.height + qr_img.height + 150 
    
    poster = Image.new('RGB', (canvas_width, canvas_height), WHITE)
    draw = ImageDraw.Draw(poster)

    # 5. Paste Elements
    # Paste Logo (Centered at top)
    logo_x = (canvas_width - logo.width) // 2
    poster.paste(logo, (logo_x, 20))

    # Paste Text (Below Logo)
    # Note: Loading fonts is tricky on different OSs. We'll use the default font but try to scale it.
    # Ideally, download a .ttf file (like Arial or a specific brand font) and use ImageFont.truetype("arial.ttf", 40)
    try:
        # Try to load a standard font
        font = ImageFont.truetype("arial.ttf", 40) 
    except IOError:
        font = ImageFont.load_default()
    
    # Calculate text position
    # We can't easily center text with default font, so we estimate
    text_bbox = draw.textbbox((0, 0), TEXT_CONTENT, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_x = (canvas_width - text_width) // 2
    text_y = logo.height + 50
    
    draw.text((text_x, text_y), TEXT_CONTENT, fill=BLACK, font=font)

    # Paste QR Code (Below Text)
    qr_x = (canvas_width - qr_img.width) // 2
    qr_y = text_y + 60
    poster.paste(qr_img, (qr_x, qr_y))

    # 6. Save
    poster.save(OUTPUT_FILENAME)
    print(f"Success! Poster saved as {OUTPUT_FILENAME}")

if __name__ == "__main__":
    create_poster()