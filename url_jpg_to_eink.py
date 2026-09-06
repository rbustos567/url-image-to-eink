import argparse
import importlib
from io import BytesIO
import os
import urllib.parse
import urllib.request
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def load_image_bytes(source):
    """Loads raw image bytes from either a remote HTTP/HTTPS URL or a local file path."""
    parsed = urllib.parse.urlparse(source)

    # Check if the source argument is an HTTP or HTTPS URL
    if parsed.scheme in ("http", "https"):
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        req = urllib.request.Request(source, headers=headers)
        print(f"Downloading image from URL: {source}...")
        with urllib.request.urlopen(req) as response:
            return response.read()
    else:
        # Otherwise, treat it as a local file path
        expanded_path = os.path.expanduser(source)
        if not os.path.exists(expanded_path):
            raise FileNotFoundError(
                f"Local image file not found: {expanded_path}"
            )

        print(f"Reading local image file: {expanded_path}...")
        with open(expanded_path, "rb") as f:
            return f.read()


def process_jpg_for_eink(
    image_bytes,
    target_width,
    target_height,
    contrast=1.6,
    gamma=1.4,
    sharpness=2.5,
    white_threshold=200,
    no_dither=False,
):
    """Processes raw image bytes with granular controls for e-Paper displays."""
    with Image.open(BytesIO(image_bytes)) as img:
        # 1. Resize and crop to fill exact e-Paper dimensions (e.g., 800x480)
        img_fit = ImageOps.fit(
            img, (target_width, target_height), method=Image.Resampling.LANCZOS
        )

        # 2. Convert to 8-bit Grayscale
        img_gray = img_fit.convert("L")

        # 3. White clipping + Gamma adjustment via point lookup table
        lookup_table = []
        for i in range(256):
            if i >= white_threshold:
                lookup_table.append(255)
            else:
                val = int(((i / float(white_threshold)) ** (1.0 / gamma)) * 255)
                lookup_table.append(min(255, max(0, val)))

        img_gamma = img_gray.point(lookup_table)

        # 4. Unsharp Masking to define geometric edges
        if sharpness > 0:
            img_sharp = img_gamma.filter(
                ImageFilter.UnsharpMask(
                    radius=2.0, percent=int(sharpness * 100), threshold=2
                )
            )
        else:
            img_sharp = img_gamma

        # 5. Contrast Enhancement
        img_contrast = ImageEnhance.Contrast(img_sharp).enhance(contrast)

        # 6. Convert to 1-bit monochrome (Floyd-Steinberg or thresholding)
        if no_dither:
            img_bw = img_contrast.convert("1", dither=Image.Dither.NONE)
        else:
            img_bw = img_contrast.convert("1", dither=Image.FLOYDSTEINBERG)

        return img_bw


def render_to_waveshare(bw_image, display_model):
    """Sends the processed image buffer to the Waveshare display via SPI."""
    try:
        epd_module = importlib.import_module(f"waveshare_epd.{display_model}")
        epd = epd_module.EPD()
        print(f"Initializing Waveshare display ({display_model})...")
        epd.init()
        epd.display(epd.getbuffer(bw_image))
        epd.sleep()
        print("Display updated successfully.")
    except Exception as err:
        print(f"SPI hardware error: {err}")


def main():
    parser = argparse.ArgumentParser(
        description="Processes a JPG/PNG image from a direct URL or local file path for e-Paper displays."
    )
    # Target source can be a URL or local path
    parser.add_argument(
        "source", help="Direct URL (http/https) OR local path to a JPG/PNG image"
    )

    # Display Dimensions & Model
    parser.add_argument(
        "--width", type=int, default=800, help="Target e-Paper width (default: 800)"
    )
    parser.add_argument(
        "--height", type=int, default=480, help="Target e-Paper height (default: 480)"
    )
    parser.add_argument(
        "--model", type=str, default="epd7in5_V2", help="Waveshare model name (default: epd7in5_V2)"
    )

    # Image Tuning Arguments (with bilingual alias support)
    parser.add_argument(
        "--contrast",
        type=float,
        default=1.6,
        help="Contrast multiplier (default: 1.6)",
    )
    parser.add_argument(
        "--gamma",
        "--gama",
        type=float,
        default=1.4,
        help="Gamma correction factor to brighten midtones (default: 1.4)",
    )
    parser.add_argument(
        "--sharpness",
        type=float,
        default=2.5,
        help="Unsharp mask strength factor (default: 2.5)",
    )
    parser.add_argument(
        "--white-threshold",
        type=int,
        default=200,
        help="Luminance threshold (0-255) for white clipping (default: 200)",
    )
    parser.add_argument(
        "--no-dither",
        action="store_true",
        help="Disable Floyd-Steinberg dithering and use hard thresholding",
    )

    # Output & Hardware Flags
    parser.add_argument(
        "--display", action="store_true", help="Render directly to physical display over SPI"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Path to save processed 1-bit e-Paper PNG preview image locally",
    )
    parser.add_argument(
        "--save-original",
        type=str,
        default=None,
        help="Path to save the unmodified original image",
    )

    args = parser.parse_args()

    # 1. Load image bytes from URL or local path
    img_bytes = load_image_bytes(args.source)

    # 2. Save original image copy if requested
    if args.save_original:
        with open(args.save_original, "wb") as f:
            f.write(img_bytes)
        print(f"Original image saved to: {args.save_original}")

    # 3. Process image in memory
    bw_img = process_jpg_for_eink(
        image_bytes=img_bytes,
        target_width=args.width,
        target_height=args.height,
        contrast=args.contrast,
        gamma=args.gamma,
        sharpness=args.sharpness,
        white_threshold=args.white_threshold,
        no_dither=args.no_dither,
    )

    # 4. Save processed e-Paper preview PNG
    if args.output:
        bw_img.save(args.output)
        print(f"Processed 1-bit e-Paper PNG saved to: {args.output}")

    # 5. Render to physical hardware
    if args.display:
        render_to_waveshare(bw_img, args.model)


if __name__ == "__main__":
    main()
