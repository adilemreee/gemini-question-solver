"""
Image Loader Module
Handles loading and validating question images from a directory
"""
import base64
from pathlib import Path
from typing import List, Tuple
from PIL import Image
from rich.console import Console

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import SUPPORTED_FORMATS

console = Console()


class ImageLoader:
    """Loads and validates images from a directory"""
    
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.images: List[Tuple[str, bytes]] = []  # (filename, image_bytes)
    
    def scan_directory(self) -> List[Path]:
        """Scan directory for supported image files"""
        if not self.directory.exists():
            raise FileNotFoundError(f"Directory not found: {self.directory}")
        
        image_files = []
        for file_path in sorted(self.directory.iterdir()):
            if file_path.suffix.lower() in SUPPORTED_FORMATS:
                image_files.append(file_path)
        
        return image_files
    
    def validate_image(self, file_path: Path) -> bool:
        """Validate that file is a valid image"""
        try:
            with Image.open(file_path) as img:
                img.verify()
            return True
        except Exception as e:
            console.print(f"[yellow]⚠️ Invalid image: {file_path.name} - {e}[/yellow]")
            return False
    
    def load_image_bytes(self, file_path: Path) -> bytes:
        """Load image as bytes"""
        with open(file_path, "rb") as f:
            return f.read()
    
    def load_image_base64(self, file_path: Path) -> str:
        """Load image as base64 string"""
        image_bytes = self.load_image_bytes(file_path)
        return base64.b64encode(image_bytes).decode("utf-8")
    
    def get_mime_type(self, file_path: Path) -> str:
        """Get MIME type for image"""
        suffix = file_path.suffix.lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        return mime_types.get(suffix, "image/jpeg")
    
    def load_all(self) -> List[Tuple[str, bytes, str]]:
        """
        Load all valid images from directory
        Returns: List of (filename, image_bytes, mime_type)
        """
        image_files = self.scan_directory()
        
        if not image_files:
            console.print(f"[red]❌ No images found in {self.directory}[/red]")
            return []
        
        console.print(f"[cyan]📁 Found {len(image_files)} image(s) in {self.directory}[/cyan]")
        
        loaded_images = []
        for file_path in image_files:
            if self.validate_image(file_path):
                image_bytes = self.load_image_bytes(file_path)
                mime_type = self.get_mime_type(file_path)
                loaded_images.append((file_path.name, image_bytes, mime_type))
                console.print(f"  [green]✓[/green] {file_path.name}")
        
        console.print(f"[green]✅ Loaded {len(loaded_images)} valid image(s)[/green]")
        return loaded_images


if __name__ == "__main__":
    # Test the loader
    from config import QUESTIONS_DIR
    loader = ImageLoader(QUESTIONS_DIR)
    images = loader.load_all()
    print(f"Loaded {len(images)} images")
