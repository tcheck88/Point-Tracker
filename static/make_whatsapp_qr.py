import qrcode
from PIL import Image

# --- CONFIGURATION ---
# 1. The Image to put in the center (Your Logo OR a WhatsApp Icon)
LOGO_FILENAME = 'logo.jpg' 

# 2. The WhatsApp Link
URL = "https://chat.whatsapp.com/Jcy7oTLUkqI5rcOFhAXDN4"

# 3. Output Filename
OUTPUT_FILENAME = "WhatsApp_QR.png"

# --- COLORS ---
# WhatsApp Official Green: (37, 211, 102)
# Your Logo Dark Green:    (0, 104, 71)
QR_COLOR = (37, 211, 102) 
WHITE = (255, 255, 255)

def create_whatsapp_qr():
    try:
        logo = Image.open(LOGO_FILENAME)
    except FileNotFoundError:
        print(f"Error: Could not find {LOGO_FILENAME}. Please ensure the file is in this folder.")
        return

    # 1. Generate QR Code (High Error Correction is key)
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H, 
        box_size=10,
        border=2,
    )
    qr.add_data(URL)
    qr.make(fit=True)

    # 2. Create Image with WhatsApp Green
    qr_img = qr.make_image(fill_color=QR_COLOR, back_color=WHITE).convert('RGB')

    # 3. Resize and Paste Center Logo
    # We take 25% of the QR width for the logo
    logo_size = int(qr_img.width * 0.25)
    logo_resized = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

    # Calculate center position
    pos_x = (qr_img.width - logo_size) // 2
    pos_y = (qr_img.height - logo_size) // 2
    
    # Paste the logo into the middle
    qr_img.paste(logo_resized, (pos_x, pos_y))

    # 4. Save
    qr_img.save(OUTPUT_FILENAME)
    print(f"Success! Created {OUTPUT_FILENAME}")

if __name__ == "__main__":
    create_whatsapp_qr()