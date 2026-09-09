"""Storyboard PDF and Image Processor for Project Rosetta Board.

Extracts pages from storyboard PDFs and segments multi-panel sheets into individual
panel images for multimodal Gemini vision analysis.
"""

import io
from pathlib import Path
from typing import List, Tuple
from PIL import Image

from app.config import OUTPUTS_DIR


class StoryboardProcessor:
    """Handles PDF page extraction and storyboard panel slicing."""

    def __init__(self, output_dir: Path = OUTPUTS_DIR):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def process_file(self, file_path: str, scene_name: str = "Scene_42") -> List[Tuple[str, int, int]]:
        """Process any uploaded file (PDF, PNG, JPG) into individual panel images.
        
        Returns:
            List of tuples: (panel_image_path, page_number, panel_index)
        """
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext == ".pdf":
            return self._process_pdf(path, scene_name)
        elif ext in (".png", ".jpg", ".jpeg", ".webp"):
            return self._process_image(path, scene_name)
        else:
            raise ValueError(f"Unsupported storyboard file format: {ext}")

    def _process_pdf(self, pdf_path: Path, scene_name: str) -> List[Tuple[str, int, int]]:
        """Extract pages and images from a PDF file using pypdf and PIL."""
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        extracted_panels = []

        for page_idx, page in enumerate(reader.pages):
            page_num = page_idx + 1
            images = page.images

            if images:
                # Extract embedded images from the PDF page
                for img_idx, img_obj in enumerate(images):
                    panel_name = f"{scene_name}_p{page_num}_panel{img_idx + 1}.png"
                    save_path = self.output_dir / panel_name
                    with open(save_path, "wb") as f:
                        f.write(img_obj.data)
                    extracted_panels.append((str(save_path), page_num, img_idx + 1))
            else:
                # If no embedded raster images, save placeholder representation
                blank = Image.new("RGB", (800, 600), color=(250, 250, 250))
                panel_name = f"{scene_name}_p{page_num}_panel1.png"
                save_path = self.output_dir / panel_name
                blank.save(save_path)
                extracted_panels.append((str(save_path), page_num, 1))

        return extracted_panels

    def _process_image(self, img_path: Path, scene_name: str) -> List[Tuple[str, int, int]]:
        """Process an image file. If composite storyboard sheet (wide or tall), slices panels; else returns as single panel."""
        img = Image.open(img_path)
        width, height = img.size

        # If image aspect ratio indicates a composite multi-panel strip or grid (e.g. 3 panels horizontally)
        aspect = width / height
        if aspect >= 2.5:
            # 3 panels side by side
            num_panels = 3
            panel_w = width // num_panels
            panels = []
            for i in range(num_panels):
                box = (i * panel_w, 0, (i + 1) * panel_w, height)
                cropped = img.crop(box)
                panel_name = f"{scene_name}_panel_{i + 1}.png"
                save_path = self.output_dir / panel_name
                cropped.save(save_path)
                panels.append((str(save_path), 1, i + 1))
            return panels
        elif aspect <= 0.4:
            # 3 panels stacked vertically
            num_panels = 3
            panel_h = height // num_panels
            panels = []
            for i in range(num_panels):
                box = (0, i * panel_h, width, (i + 1) * panel_h)
                cropped = img.crop(box)
                panel_name = f"{scene_name}_panel_{i + 1}.png"
                save_path = self.output_dir / panel_name
                cropped.save(save_path)
                panels.append((str(save_path), 1, i + 1))
            return panels

        # Single panel image
        panel_name = f"{scene_name}_{img_path.name}"
        save_path = self.output_dir / panel_name
        img.save(save_path)
        return [(str(save_path), 1, 1)]


storyboard_processor = StoryboardProcessor()
