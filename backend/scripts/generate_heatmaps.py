import os
import rasterio
import numpy as np
from PIL import Image

# Path configurations
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
PUBLIC_DIR = os.path.join(BASE_DIR, "frontend", "public")

GHI_PATH = os.path.join(DATA_DIR, "GHI.tif")
WIND_PATH = os.path.join(DATA_DIR, "WIND.tif")

SOLAR_OUTPUT = os.path.join(PUBLIC_DIR, "solar_heatmap.png")
WIND_OUTPUT = os.path.join(PUBLIC_DIR, "wind_heatmap.png")

def generate_heatmap(input_path, output_path, type="solar"):
    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found.")
        return

    with rasterio.open(input_path) as src:
        data = src.read(1)
        nodata = src.nodata
        
        # Prepare RGBA array
        h, w = data.shape
        rgba = np.zeros((h, w, 4), dtype=np.uint8)

        # Alpha value for transparency
        alpha = 160

        if type == "solar":
            # "Kırmızılı tema" - Solar: Yellow to Deep Red
            mask_nodata = (data == nodata) | (data <= 0)
            mask1 = (data > 0) & (data < 1400)      # Low
            mask2 = (data >= 1400) & (data < 1600) # Medium
            mask3 = (data >= 1600) & (data < 1800) # High
            mask4 = (data >= 1800)                 # Very High

            rgba[mask1] = [254, 240, 190, alpha] # Light Yellow
            rgba[mask2] = [251, 191, 36, alpha]  # Amber
            rgba[mask3] = [234, 88, 12, alpha]   # Orange/Red
            rgba[mask4] = [185, 28, 28, alpha]   # Deep Red
            rgba[mask_nodata] = [0, 0, 0, 0]

        else:
            # "Mavili tema" - Wind: Light Blue to Deep Blue
            mask_nodata = (data == nodata) | (data < 0)
            mask1 = (data >= 0) & (data < 4) # Low
            mask2 = (data >= 4) & (data < 6) # Medium
            mask3 = (data >= 6) & (data < 8) # High
            mask4 = (data >= 8)             # Very High

            rgba[mask1] = [219, 234, 254, alpha] # Very Light Blue
            rgba[mask2] = [96, 165, 250, alpha]  # Sky Blue
            rgba[mask3] = [37, 99, 235, alpha]   # Royal Blue
            rgba[mask4] = [30, 58, 138, alpha]   # Navy Blue
            rgba[mask_nodata] = [0, 0, 0, 0]

        # Save using Pillow
        img = Image.fromarray(rgba, 'RGBA')
        img.save(output_path)
        
        bounds = src.bounds
        leaflet_bounds = [bounds.bottom, bounds.left, bounds.top, bounds.right]
        print(f"Generated {type} heatmap. Bounds: {leaflet_bounds}")

if __name__ == "__main__":
    os.makedirs(PUBLIC_DIR, exist_ok=True)
    generate_heatmap(GHI_PATH, SOLAR_OUTPUT, "solar")
    generate_heatmap(WIND_PATH, WIND_OUTPUT, "wind")
