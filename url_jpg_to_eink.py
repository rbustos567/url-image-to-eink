import argparse
import importlib
from io import BytesIO
import logging
import os
import sys
import urllib.parse
import urllib.request
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def setup_logging(log_file=None, log_level="INFO"):
    """Configures structured logging to console and optionally to a log file."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    log_formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    logger = logging.getLogger()
    logger.setLevel(numeric_level)
    logger.handlers.clear()

    # Stream Handler for Console Output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    logger.addHandler(console_handler)

    # File Handler if a path is specified
    if log_file:
        expanded_log_path = os.path.expanduser(log_file)
        log_dir = os.path.dirname(expanded_log_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        file_handler = logging.FileHandler(expanded_log_path, mode="a", encoding="utf-8")
        file_handler.setFormatter(log_formatter)
        logger.addHandler(file_handler)
        logging.info(f"Logging initialized. Output file: {expanded_log_path}")


def load_image_bytes(source):
    """Loads raw image bytes from either a remote HTTP/HTTPS URL or a local file path."""
    parsed = urllib.parse.urlparse(source)

    if parsed.scheme in ("http", "https"):
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        req = urllib.request.Request(source, headers=headers)
        logging.info(f"Downloading image from URL: {source}...")
        try:
            with urllib.request.urlopen(req) as response:
                img_data = response.read()
                logging.info(f"Downloaded {len(img_data)} bytes successfully.")
                return img_data
        except Exception as err:
            logging.error(f"Failed to download image from URL: {err}")
            raise
    else:
        expanded_path = os.path.expanduser(source)
        if not os.path.exists(expanded_path):
            error_msg = f"Local image file not found: {expanded_path}"
            logging.error(error_msg)
            raise FileNotFoundError(error_msg)

        logging.info(f"Reading local image file: {expanded_path}...")
        with open(expanded_path, "rb") as f:
            img_data = f.read()
            logging.info(f"Read {len(img_data)} bytes from disk.")
            return img_data


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
    logging.info("Starting image processing pipeline...")
    with Image.open(BytesIO(image_bytes)) as img:
        logging.debug(f"Original image format: {img.format}, size: {img.size}, mode: {img.mode}")

        # 1. Resize and crop
        img_fit = ImageOps.fit(
            img, (target_width, target_height), method=Image.Resampling.LANCZOS
        )
        logging.info(f"Resized and cropped image to: {target_width}x{target_height}")

        # 2. Convert to 8-bit Grayscale
        img_gray = img_fit.convert("L")

        # 3. White clipping + Gamma adjustment
        logging.info(f"Applying lookup table (white_threshold={white_threshold}, gamma={gamma})...")
        lookup_table = []
        for i in range(256):
            if i >= white_threshold:
                lookup_table.append(255)
            else:
                val = int(((i / float(white_threshold)) ** (1.0 / gamma)) * 255)
                lookup_table.append(min(255, max(0, val)))

        img_gamma = img_gray.point(lookup_table)

        # 4. Unsharp Masking
        if sharpness > 0:
            logging.info(f"Applying UnsharpMask (sharpness={sharpness})...")
            img_sharp = img_gamma.filter(
                ImageFilter.UnsharpMask(
                    radius=2.0, percent=int(sharpness * 100), threshold=2
                )
            )
        else:
            img_sharp = img_gamma

        # 5. Contrast Enhancement
        logging.info(f"Enhancing contrast (factor={contrast})...")
        img_contrast = ImageEnhance.Contrast(img_sharp).enhance(contrast)

        # 6. Convert to 1-bit monochrome
        if no_dither:
            logging.info("Converting to 1-bit monochrome using hard thresholding (no dither)...")
            img_bw = img_contrast.convert("1", dither=Image.Dither.NONE)
        else:
            logging.info("Converting to 1-bit monochrome using Floyd-Steinberg dithering...")
            img_bw = img_contrast.convert("1", dither=Image.FLOYDSTEINBERG)

        logging.info("Image processing complete.")
        return img_bw


def render_to_waveshare(bw_image, display_model):
    """Sends the processed image buffer to the Waveshare display via SPI."""
    try:
        logging.info(f"Importing Waveshare driver module: waveshare_epd.{display_model}...")
        epd_module = importlib.import_module(f"waveshare_epd.{display_model}")
        epd = epd_module.EPD()

        logging.info(f"Initializing Waveshare SPI display hardware ({display_model})...")
        epd.init()

        logging.info("Writing frame buffer to e-Paper display...")
        epd.display(epd.getbuffer(bw_image))

        logging.info("Putting e-Paper display to deep sleep...")
        epd.sleep()
        logging.info("Hardware update finished successfully.")
    except Exception as err:
        logging.error(f"SPI hardware / driver error: {err}", exc_info=True)


def main():
    parser = argparse.ArgumentParser(
        description="Processes a JPG/PNG image from a direct URL or local file path for e-Paper displays."
    )
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

    # Image Tuning Arguments
    parser.add_argument(
        "--contrast", type=float, default=1.6, help="Contrast multiplier (default: 1.6)"
    )
    parser.add_argument(
        "--gamma", "--gama", type=float, default=1.4, help="Gamma correction factor (default: 1.4)"
    )
    parser.add_argument(
        "--sharpness", type=float, default=2.5, help="Unsharp mask strength factor (default: 2.5)"
    )
    parser.add_argument(
        "--white-threshold", type=int, default=200, help="Luminance threshold (0-255) for white clipping (default: 200)"
    )
    parser.add_argument(
        "--no-dither", action="store_true", help="Disable Floyd-Steinberg dithering"
    )

    # Output & Hardware Flags
    parser.add_argument(
        "--display", action="store_true", help="Render directly to physical display over SPI"
    )
    parser.add_argument(
        "-o", "--output", type=str, default=None, help="Path to save processed 1-bit PNG preview image"
    )
    parser.add_argument(
        "--save-original", type=str, default=None, help="Path to save the unmodified original image"
    )

    # Logging Flags
    parser.add_argument(
        "--log-file", type=str, default=None, help="Path to write execution logs (e.g. /var/log/eink.log)"
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Logging level (default: INFO)"
    )

    args = parser.parse_args()

    # 0. Initialize logging configuration
    setup_logging(log_file=args.log_file, log_level=args.log_level)

    try:
        # 1. Load image bytes
        img_bytes = load_image_bytes(args.source)

        # 2. Save original image copy if requested
        if args.save_original:
            expanded_save_orig = os.path.expanduser(args.save_original)
            with open(expanded_save_orig, "wb") as f:
                f.write(img_bytes)
            logging.info(f"Original image saved to: {expanded_save_orig}")

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
            expanded_output = os.path.expanduser(args.output)
            bw_img.save(expanded_output)
            logging.info(f"Processed 1-bit e-Paper PNG saved to: {expanded_output}")

        # 5. Render to physical hardware
        if args.display:
            render_to_waveshare(bw_img, args.model)

    except Exception as e:
        logging.critical(f"Execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
