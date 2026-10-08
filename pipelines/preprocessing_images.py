import argparse
import os
import sys
from pathlib import Path

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.image_preprocessing import Filter, ImageAnalyzer

def parse_args():
    parser = argparse.ArgumentParser(description="Preprocess meter images.")
    parser.add_argument("--input", required=True, help="Input image directory")
    parser.add_argument("--output", required=True, help="Output image directory")
    return parser.parse_args()

def main():
    args = parse_args()
    os.makedirs(args.output, exist_ok=True)

    processed = 0
    errors = 0
    for filename in sorted(os.listdir(args.input)):
        if not filename.lower().endswith((".jpg", ".jpeg")):
            continue

        input_path = os.path.join(args.input, filename)

        try:
            with open(input_path, "rb") as image_file:
                analyzer = ImageAnalyzer(image_file)
                brightness = analyzer.brightness_status()
                noise = analyzer.noise_status()

                image_file.seek(0)
                filter_ = Filter(image_file)

            if brightness == "escura":
                filter_.increase_brightness()
            elif brightness == "clara":
                filter_.decrease_brightness()

            if noise == "borrada":
                filter_.sharpen()
            elif noise == "ruidosa":
                filter_.suavization()

            output_path = os.path.join(args.output, filename)
            if not cv2.imwrite(output_path, filter_.image):
                raise RuntimeError(f"could not write {output_path}")
            processed += 1
        except Exception as error:
            errors += 1
            print(f"Erro em {filename}: {error}")

    print(f"Preprocessamento concluído: {processed} imagens processadas, {errors} erros.")

if __name__ == "__main__":
    main()