"""Imagen 3 Concept Sketch Generator for Project Rosetta Board.

Automatically generates standardized, clean cinematic concept sketches for crude napkin doodles
or low-fidelity storyboard sketches using Gemini / Imagen 3 capabilities.
"""

from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

from app.config import OUTPUTS_DIR, config
from app.models import NormalizedPanel


class ConceptRenderEngine:
    """Generates clean studio concept art from rough storyboard sketches."""

    def __init__(self):
        self.renders_dir = OUTPUTS_DIR / "concept_renders"
        self.renders_dir.mkdir(parents=True, exist_ok=True)
        self.api_key = config.GEMINI_API_KEY
        self.client = None

        if self.api_key and self.api_key != "your_gemini_api_key_here":
            try:
                from google import genai
                if config.USE_VERTEXAI:
                    self.client = genai.Client(
                        vertexai=True,
                        project=config.GCP_PROJECT,
                        location=config.GCP_LOCATION,
                    )
                else:
                    self.client = genai.Client(api_key=self.api_key)
            except Exception:
                self.client = None

    def render_concept_sketch(self, panel: NormalizedPanel) -> Optional[str]:
        """Generate a clean visual render for a panel."""
        prompt = (
            f"Cinematic production storyboard sketch, high contrast black and white with charcoal wash. "
            f"Scene: {panel.scene}, Shot: {panel.shot}. Framing: {panel.shot_size} from a {panel.camera_angle}. "
            f"Action: {panel.action_notes}. Characters: {', '.join(panel.characters)}. "
            f"Visible props: {', '.join(panel.props)}. Professional feature film concept art."
        )

        render_filename = f"{panel.panel_id}_concept_render.png"
        save_path = self.renders_dir / render_filename

        # If live Imagen 3 client is available
        if self.client:
            try:
                # Call Imagen 3 model via genai client
                result = self.client.models.generate_images(
                    model="imagen-3.0-generate-002",
                    prompt=prompt,
                    config=dict(number_of_images=1, aspect_ratio="16:9"),
                )
                if result.generated_images:
                    img_bytes = result.generated_images[0].image.image_bytes
                    with open(save_path, "wb") as f:
                        f.write(img_bytes)
                    return str(save_path)
            except Exception:
                pass

        # Stylized studio concept graphic fallback
        img = Image.new("RGB", (960, 540), color=(30, 32, 38))
        draw = ImageDraw.Draw(img)

        # Draw framing box and cinema grid
        draw.rectangle([(20, 20), (940, 520)], outline=(80, 85, 95), width=2)
        draw.line([(480, 20), (480, 520)], fill=(50, 55, 65), width=1)
        draw.line([(20, 270), (940, 270)], fill=(50, 55, 65), width=1)

        # Draw metadata header
        header_text = f"STUDIO CONCEPT RENDER | SCENE {panel.scene} - SHOT {panel.shot} ({panel.version.upper()})"
        framing_text = f"FRAMING: {panel.shot_size.upper()} | ANGLE: {panel.camera_angle.upper()}"
        props_text = f"PROPS: {', '.join(panel.props) if panel.props else 'NONE'}"
        action_text = f"ACTION: {panel.action_notes[:80]}" if panel.action_notes else ""

        draw.text((40, 40), header_text, fill=(240, 240, 245))
        draw.text((40, 70), framing_text, fill=(130, 210, 255))
        draw.text((40, 100), props_text, fill=(255, 195, 110))
        if action_text:
            draw.text((40, 130), action_text, fill=(180, 185, 195))

        # Central artistic composition
        draw.rounded_rectangle([(300, 180), (660, 440)], radius=8, outline=(140, 145, 160), fill=(45, 48, 56), width=2)
        draw.text((380, 300), "[ CONCEPT SKETCH ]", fill=(200, 205, 220))

        img.save(save_path)
        return str(save_path)


concept_renderer = ConceptRenderEngine()
