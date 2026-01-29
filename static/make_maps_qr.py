import qrcode
from PIL import Image

# --- CONFIGURATION ---
# 1. The Image to put in the center (Your Logo OR a Google Maps Pin icon)
LOGO_FILENAME = 'logo.jpg' 

# 2. The Google Maps Link
# (Double check this link is the correct one for your location)
URL = "https://www.google.com/maps?q=Leer+Mexico+Read,+Av.+Canal+Nacional,+Zona+Urbana+Ejidal+Estrella+Culhuacan,+Iztapalapa,+09800+Ciudad+de+M%C3%A9xico,+CDMX,+Mexico&ftid=0x85d1f92bf87de397:0x70618a4c58454d13&entry=gps&shh=CAE&lucs=,94297699,94275415,94284511,94231188,94280568,47071704,94218641,94282134,94286869&g_ep=CAISEjI2LjAzLjEuODU1MjUwMDQwMBgAIIgnKlEsOTQyOTc2OTksOTQyNzU0MTUsOTQyODQ1MTEsOTQyMzExODgsOTQyODA1NjgsNDcwNzE3MDQsOTQyMTg2NDEsOTQyODIxMzQsOTQyODY4NjlCAlVT&skid=31715b6b-0931-4c6a-9391-9213a6e88442&g_st=ic"

# 3. Output Filename
OUTPUT_FILENAME = "GoogleMaps_QR.png"

# --- COLORS ---
# Google Maps Red (Approximate): (234, 67, 53)
QR_COLOR = (234, 67, 53)
WHITE = (255, 255, 255)

def create_maps_qr():
    try:
        logo = Image.open(LOGO_FILENAME)
    except FileNotFoundError:
        print(f"Error: Could not find {LOGO_FILENAME}. Please ensure the file is in this folder.")
        return

    # 1. Generate QR Code (High Error Correction)
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H, 
        box_size=10,
        border=2,
    )
    qr.add_data(URL)
    qr.make(fit=True)

    # 2. Create Image with Google Red
    qr_img = qr.make_image(fill_color=QR_COLOR, back_color=WHITE).convert('RGB')

    # 3. Resize and Paste Center Logo
    # Use 25% of the QR width for the logo
    logo_size = int(qr_img.width * 0.25)
    logo_resized = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

    # Calculate center position
    pos_x = (qr_img.width - logo_size) // 2
    pos_y = (qr_img.height - logo_size) // 2
    
    # Paste the logo
    qr_img.paste(logo_resized, (pos_x, pos_y))

    # 4. Save
    qr_img.save(OUTPUT_FILENAME)
    print(f"Success! Created {OUTPUT_FILENAME}")

if __name__ == "__main__":
    create_maps_qr()