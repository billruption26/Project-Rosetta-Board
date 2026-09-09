"""Sample Storyboard Generator for Project Rosetta Board.

Generates synthetic storyboard panels and multi-page PDFs representing
Scene 42 Version 1 and Scene 42 Version 2 to benchmark visual extraction,
implied prop detection, taxonomy normalization, and revision delta checking.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from app.config import SAMPLES_DIR


def create_panel_image(
    scene: str,
    shot: str,
    panel_num: int,
    version: str,
    framing: str,
    dialogue: str,
    action: str,
    drawn_element: str,
    save_path: Path,
):
    """Draw a synthetic storyboard panel sketch."""
    img = Image.new("RGB", (960, 540), color=(245, 244, 240))
    draw = ImageDraw.Draw(img)

    # Outer border and framing box
    draw.rectangle([(20, 20), (940, 520)], outline=(40, 40, 40), width=3)

    # Header bar
    draw.rectangle([(20, 20), (940, 65)], fill=(220, 220, 220), outline=(40, 40, 40), width=2)
    header_text = f"SCENE: {scene} | SHOT: {shot} | PANEL: {panel_num} | VER: {version.upper()} | ANGLE/SIZE: {framing}"
    draw.text((35, 35), header_text, fill=(20, 20, 20))

    # Center drawing area simulating sketched artwork
    draw.rounded_rectangle([(140, 90), (820, 400)], radius=6, outline=(60, 60, 60), fill=(255, 255, 255), width=2)

    # Sketch lines / artistic mockup
    draw.line([(180, 360), (780, 360)], fill=(120, 120, 120), width=2)  # Horizon / counter line
    draw.text((200, 150), f"[ SKETCH COMPOSITION: {framing} ]", fill=(100, 100, 100))
    draw.text((200, 210), f"VISUALLY DRAWN: {drawn_element.upper()}", fill=(180, 40, 40))

    # Sketch figure outline
    draw.ellipse([(420, 180), (540, 300)], outline=(50, 50, 50), width=3)  # Head / torso
    draw.line([(480, 300), (480, 360)], fill=(50, 50, 50), width=3)

    # Footer Action & Dialogue notes
    draw.rectangle([(20, 420), (940, 520)], fill=(235, 235, 235), outline=(40, 40, 40), width=1)
    if dialogue:
        draw.text((35, 430), f"DIALOGUE: \"{dialogue}\"", fill=(10, 10, 10))
    if action:
        draw.text((35, 465), f"ACTION NOTE: {action}", fill=(50, 50, 50))

    img.save(save_path)
    return img


def generate_all_samples():
    """Create sample storyboards for Scene 42 V1 and V2."""
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    v1_images = []
    v2_images = []

    # ====================
    # SCENE 42 VERSION 1
    # ====================
    # Shot 1: John at counter. Text says "John talks", visually drawn holding a coffee cup!
    s1_v1 = SAMPLES_DIR / "scene_42_v1_shot_1.png"
    img1 = create_panel_image(
        scene="42",
        shot="1",
        panel_num=1,
        version="v1",
        framing="HA / MCU",
        dialogue="Where is the package?",
        action="John leans against counter, talking calmly.",
        drawn_element="Character holding a ceramic coffee cup in left hand",
        save_path=s1_v1,
    )
    v1_images.append(img1)

    # Shot 2: Teller close up. Framing: XCU
    s2_v1 = SAMPLES_DIR / "scene_42_v1_shot_2.png"
    img2 = create_panel_image(
        scene="42",
        shot="2",
        panel_num=1,
        version="v1",
        framing="Eye Level / XCU",
        dialogue="I told you, it hasn't arrived.",
        action="Close on Teller's nervous eyes glancing towards vault door.",
        drawn_element="Eyes wide with sweat drops, wearing wire-frame glasses",
        save_path=s2_v1,
    )
    v1_images.append(img2)

    # Shot 3: Exterior getaway car. Framing: DUTCH / WS. VFX: Pyro Explosion
    s3_v1 = SAMPLES_DIR / "scene_42_v1_shot_3.png"
    img3 = create_panel_image(
        scene="42",
        shot="3",
        panel_num=1,
        version="v1",
        framing="DUTCH / WS",
        dialogue="",
        action="Exterior getaway car idles by curb. Suddenly vault door explodes.",
        drawn_element="1967 Mustang muscle car, giant fiery explosion in background",
        save_path=s3_v1,
    )
    v1_images.append(img3)

    # Compile Scene 42 V1 PDF
    pdf_v1_path = SAMPLES_DIR / "Scene_42_V1.pdf"
    v1_images[0].save(pdf_v1_path, "PDF", resolution=100.0, save_all=True, append_images=v1_images[1:])

    # ====================
    # SCENE 42 VERSION 2 (REVISION)
    # ====================
    # Shot 1 Revised: Now John draws a PROP GUN!
    s1_v2 = SAMPLES_DIR / "scene_42_v2_shot_1.png"
    img1_v2 = create_panel_image(
        scene="42",
        shot="1",
        panel_num=1,
        version="v2",
        framing="HA / MCU",
        dialogue="Don't make me ask twice.",
        action="John draws a suppressed pistol from his coat.",
        drawn_element="Character brandishing a prop gun / suppressed pistol",
        save_path=s1_v2,
    )
    v2_images.append(img1_v2)

    # Shot 2 Revised: Framing changed from XCU to CU
    s2_v2 = SAMPLES_DIR / "scene_42_v2_shot_2.png"
    img2_v2 = create_panel_image(
        scene="42",
        shot="2",
        panel_num=1,
        version="v2",
        framing="Eye Level / CU",  # Changed from XCU to CU
        dialogue="Okay! The code is 9-4-1-2!",
        action="Teller raises hands in panic.",
        drawn_element="Teller terrified with hands raised in frame",
        save_path=s2_v2,
    )
    v2_images.append(img2_v2)

    # Shot 4 Added: Helicopter arrival (Shot 3 deleted)
    s4_v2 = SAMPLES_DIR / "scene_42_v2_shot_4.png"
    img4_v2 = create_panel_image(
        scene="42",
        shot="4",
        panel_num=1,
        version="v2",
        framing="BIRD / EWS",
        dialogue="",
        action="Police tactical helicopter swoops overhead on bank rooftop.",
        drawn_element="Helicopter searchlight on roof, green screen backdrop",
        save_path=s4_v2,
    )
    v2_images.append(img4_v2)

    # Compile Scene 42 V2 PDF
    pdf_v2_path = SAMPLES_DIR / "Scene_42_V2.pdf"
    v2_images[0].save(pdf_v2_path, "PDF", resolution=100.0, save_all=True, append_images=v2_images[1:])

    print(f"Sample storyboards generated in {SAMPLES_DIR}:")
    print(f"  - {pdf_v1_path.name}")
    print(f"  - {pdf_v2_path.name}")


if __name__ == "__main__":
    generate_all_samples()
