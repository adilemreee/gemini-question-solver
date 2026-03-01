"""
Report Generator Module
Creates unified markdown reports from question solutions
"""
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from rich.console import Console

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import OUTPUT_DIR

console = Console()


class ReportGenerator:
    """Generates markdown reports from question solutions"""
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = Path(output_dir) if output_dir else OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate(
        self,
        results: List[dict],
        questions_dir: Path,
        output_filename: Optional[str] = None,
    ) -> Path:
        """
        Generate a unified markdown report
        
        Args:
            results: List of result dicts from ParallelProcessor
            questions_dir: Path to the original questions directory
            output_filename: Custom output filename (optional)
            
        Returns:
            Path to the generated report
        """
        if not results:
            console.print("[yellow]⚠️ No results to generate report from[/yellow]")
            return None
        
        # Calculate statistics
        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]
        total_time = sum(r["time_taken"] for r in results)
        avg_time = total_time / len(results) if results else 0
        
        # Generate filename
        if not output_filename:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
            output_filename = f"rapor_{timestamp}.md"
        
        output_path = self.output_dir / output_filename
        
        # Build report content
        source_label = Path(questions_dir).name if questions_dir else "source"
        report_lines = [
            "# 📝 Soru Çözüm Raporu",
            "",
            f"**Oluşturulma Tarihi**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Kaynak Klasör**: `{source_label}`",
            "",
            "---",
            "",
            "## 📊 Özet İstatistikler",
            "",
            "| Metrik | Değer |",
            "|--------|-------|",
            f"| **Toplam Soru** | {len(results)} |",
            f"| **Başarılı** | {len(successful)} ✅ |",
            f"| **Başarısız** | {len(failed)} ❌ |",
            f"| **Başarı Oranı** | {len(successful)/len(results)*100:.1f}% |",
            f"| **Toplam Süre** | {total_time:.1f} saniye |",
            f"| **Ortalama Süre** | {avg_time:.1f} saniye/soru |",
            "",
            "---",
            "",
            "## 📋 Çözümler",
            "",
        ]
        
        # Add each question and solution
        for i, result in enumerate(results, 1):
            filename = result["filename"]
            
            report_lines.extend([
                f"### Soru {i}: `{filename}`",
                "",
            ])
            
            image_url = result.get("image_url")
            if not image_url:
                # CLI fallback: embed a relative filesystem path (not absolute)
                image_path = Path(questions_dir) / filename
                if image_path.exists():
                    rel_path = os.path.relpath(image_path, self.output_dir)
                    image_url = Path(rel_path).as_posix()
                else:
                    topic = result.get("topic")
                    image_url = f"/api/image/{quote(filename)}"
                    if topic and topic != "Genel":
                        image_url += f"?topic={quote(str(topic))}"

            if image_url:
                report_lines.extend([
                    f"![{filename}]({image_url})",
                    "",
                ])
            
            if result["success"]:
                report_lines.extend([
                    f"**⏱️ Çözüm Süresi**: {result['time_taken']:.1f}s",
                    "",
                    "#### 💡 Çözüm:",
                    "",
                    result["solution"],
                    "",
                ])
            else:
                report_lines.extend([
                    f"**❌ Hata**: {result['error']}",
                    "",
                ])
            
            report_lines.extend([
                "---",
                "",
            ])
        
        # Add failed questions summary if any
        if failed:
            report_lines.extend([
                "## ⚠️ Başarısız Sorular",
                "",
            ])
            for result in failed:
                report_lines.append(f"- `{result['filename']}`: {result['error']}")
            report_lines.extend(["", "---", ""])
        
        # Footer
        report_lines.extend([
            "",
            f"*Bu rapor Gemini Parallel Question Solver tarafından otomatik oluşturulmuştur.*",
        ])
        
        # Write report
        report_content = "\n".join(report_lines)
        output_path.write_text(report_content, encoding="utf-8")
        
        console.print(f"\n[bold green]📄 Report generated: {output_path}[/bold green]")
        return output_path


if __name__ == "__main__":
    # Test the generator
    generator = ReportGenerator()
    print(f"Output directory: {generator.output_dir}")
