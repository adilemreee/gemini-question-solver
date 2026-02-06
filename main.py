#!/usr/bin/env python3
"""
Gemini Parallel Question Solver
================================
Processes multiple question images in parallel using Gemini AI and generates a unified report.

Usage:
    python main.py --input ./questions --output ./output/rapor.md
    python main.py -i ./sorular -o ./cozumler/sonuc.md
    python main.py  # Uses default paths from config
"""
import argparse
import asyncio
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import QUESTIONS_DIR, OUTPUT_DIR, GEMINI_API_KEY
from src.image_loader import ImageLoader
from src.gemini_client import GeminiClient
from src.parallel_processor import ParallelProcessor
from src.report_generator import ReportGenerator

console = Console()


def print_banner():
    """Print application banner"""
    banner = Text()
    banner.append("🧠 ", style="bold")
    banner.append("Gemini Parallel Question Solver", style="bold cyan")
    banner.append("\n")
    banner.append("Paralel soru çözme ve rapor oluşturma sistemi", style="dim")
    
    console.print(Panel(banner, border_style="cyan"))


def validate_api_key():
    """Validate Gemini API key is set"""
    if not GEMINI_API_KEY:
        console.print(Panel(
            "[red]❌ GEMINI_API_KEY bulunamadı![/red]\n\n"
            "Lütfen aşağıdaki adımları takip edin:\n"
            "1. [link=https://aistudio.google.com/apikey]https://aistudio.google.com/apikey[/link] adresinden API key alın\n"
            "2. Proje klasöründe .env dosyası oluşturun\n"
            "3. GEMINI_API_KEY=your-api-key-here şeklinde ekleyin\n\n"
            "Veya: [cyan]export GEMINI_API_KEY=your-key[/cyan]",
            title="API Key Gerekli",
            border_style="red"
        ))
        return False
    return True


async def main(input_dir: Path, output_path: Path):
    """Main execution function"""
    print_banner()
    
    # Validate API key
    if not validate_api_key():
        return 1
    
    console.print(f"[dim]📁 Input: {input_dir}[/dim]")
    console.print(f"[dim]📄 Output: {output_path}[/dim]\n")
    
    # Step 1: Load images
    console.print("[bold]📷 Step 1: Loading Images[/bold]")
    loader = ImageLoader(input_dir)
    
    try:
        images = loader.load_all()
    except FileNotFoundError as e:
        console.print(f"[red]❌ {e}[/red]")
        return 1
    
    if not images:
        console.print("[yellow]⚠️ No valid images found. Exiting.[/yellow]")
        return 1
    
    # Step 2: Process questions in parallel
    console.print("\n[bold]🧠 Step 2: Processing Questions[/bold]")
    
    try:
        client = GeminiClient()
        processor = ParallelProcessor(client)
        results = await processor.process_all(images)
    except ValueError as e:
        console.print(f"[red]❌ {e}[/red]")
        return 1
    except Exception as e:
        console.print(f"[red]❌ Unexpected error: {e}[/red]")
        return 1
    
    # Step 3: Generate report
    console.print("\n[bold]📝 Step 3: Generating Report[/bold]")
    
    output_dir = output_path.parent
    output_filename = output_path.name
    
    generator = ReportGenerator(output_dir)
    report_path = generator.generate(results, input_dir, output_filename)
    
    if report_path:
        # Print final summary
        console.print(Panel(
            f"[green]✅ Rapor başarıyla oluşturuldu![/green]\n\n"
            f"📄 Dosya: [cyan]{report_path}[/cyan]\n"
            f"📊 Toplam: {len(results)} soru | "
            f"✅ Başarılı: {sum(1 for r in results if r['success'])} | "
            f"❌ Başarısız: {sum(1 for r in results if not r['success'])}",
            title="🎉 Tamamlandı!",
            border_style="green"
        ))
        return 0
    
    return 1


def run():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Gemini Parallel Question Solver - Paralel soru çözme sistemi",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  python main.py                           # Varsayılan klasörleri kullan
  python main.py -i ./sorular              # Özel input klasörü
  python main.py -i ./sorular -o ./rapor.md  # Özel input ve output

API Key:
  export GEMINI_API_KEY=your-key-here
  veya .env dosyasına ekleyin
        """
    )
    
    parser.add_argument(
        "-i", "--input",
        type=Path,
        default=QUESTIONS_DIR,
        help=f"Soru fotoğraflarının bulunduğu klasör (varsayılan: {QUESTIONS_DIR})"
    )
    
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=OUTPUT_DIR / "rapor.md",
        help=f"Çıktı rapor dosyası (varsayılan: {OUTPUT_DIR}/rapor.md)"
    )
    
    parser.add_argument(
        "-c", "--concurrent",
        type=int,
        default=10,
        help="Aynı anda işlenecek maksimum soru sayısı (varsayılan: 10)"
    )
    
    args = parser.parse_args()
    
    # Ensure directories exist
    args.input.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    
    # Run async main
    exit_code = asyncio.run(main(args.input, args.output))
    sys.exit(exit_code)


if __name__ == "__main__":
    run()
