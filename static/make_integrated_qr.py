import qrcode
from PIL import Image, ImageDraw, ImageFont

# --- CONFIGURATION ---
LOGO_FILENAME = 'logo.jpg'
URL = "https://www.thelittlespanishenglishschool.com/guide"
TEXT_CONTENT = "Escanea para ver la guía móvil"
OUTPUT_FILENAME = "LeerMexico_Integrated_QR.png"

# Colors
MEXICO_GREEN = (0, 104, 71)  # Matching the logo's green
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

def create_integrated_qr():
    # 1. Load the Logo
    try:
        logo = Image.open(LOGO_FILENAME)
    except FileNotFoundError:
        print(f"Error: Could not find {LOGO_FILENAME}")
        return

    # 2. Generate QR Code with HIGH Error Correction
    # This is crucial: 'ERROR_CORRECT_H' allows us to cover the center 
    # with the logo and the code will still scan perfectly.
    qr = qrcode.QRCode(
        version=None, # Auto-size
        error_correction=qrcode.constants.ERROR_CORRECT_H, 
        box_size=10,
        border=4,
    )
    qr.add_data(URL)
    qr.make(fit=True)

    # Create the base QR image (Green pixels, White background)
    qr_img = qr.make_image(fill_color=MEXICO_GREEN, back_color=WHITE).convert('RGB')

    # 3. Calculate Logo Size (Integrated Style)
    # We want the logo to take up about 25% of the QR code width.
    # This is the "safe zone" for scannability.
    logo_size = int(qr_img.width * 0.25)
    
    # Resize the logo while maintaining quality
    logo_resized = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

    # 4. Paste Logo into Center of QR
    # Calculate exact center position
    pos_x = (qr_img.width - logo_size) // 2
    pos_y = (qr_img.height - logo_size) // 2
    
    # Paste!
    qr_img.paste(logo_resized, (pos_x, pos_y))

    # 5. Create the Final Poster Canvas
    # Now we put this "Integrated QR" onto a nice white background with text.
    canvas_width = qr_img.width + 100
    canvas_height = qr_img.height + 150 # Room for text at top/bottom
    
    poster = Image.new('RGB', (canvas_width, canvas_height), WHITE)
    draw = ImageDraw.Draw(poster)

    # Paste the QR Code (Centered)
    qr_x = (canvas_width - qr_img.width) // 2
    poster.paste(qr_img, (qr_x, 50)) # 50px padding from top

    # Add the Text (Centered below QR)
    try:
        font = ImageFont.truetype("arial.ttf", 30)
    except IOError:
        font = ImageFont.load_default()

    text_bbox = draw.textbbox((0, 0), TEXT_CONTENT, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_x = (canvas_width - text_width) // 2
    text_y = qr_img.height + 60 # Position below QR
    
    draw.text((text_x, text_y), TEXT_CONTENT, fill=BLACK, font=font)

    # 6. Save
    poster.save(OUTPUT_FILENAME)
    print(f"Success! Integrated QR saved as {OUTPUT_FILENAME}")

if __name__ == "__main__":
    create_integrated_qr()