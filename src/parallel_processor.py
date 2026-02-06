"""
Parallel Processor Module
Handles concurrent processing of multiple questions
"""
import asyncio
import time
from typing import List, Tuple, Optional
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import MAX_CONCURRENT_REQUESTS
from src.gemini_client import GeminiClient

console = Console()


class ParallelProcessor:
    """Processes multiple questions in parallel using asyncio"""
    
    def __init__(
        self,
        client: Optional[GeminiClient] = None,
        max_concurrent: int = MAX_CONCURRENT_REQUESTS,
    ):
        self.client = client or GeminiClient()
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.results: List[dict] = []
    
    async def _process_single(
        self,
        image_data: Tuple[str, bytes, str],
        progress: Progress,
        task_id: int,
    ) -> dict:
        """Process a single question with semaphore control"""
        filename, image_bytes, mime_type = image_data
        
        async with self.semaphore:
            progress.update(task_id, description=f"[cyan]🧠 Processing: {filename}[/cyan]")
            result = await self.client.solve_question(image_bytes, mime_type, filename)
            progress.advance(task_id)
            
            if result["success"]:
                console.print(f"  [green]✅ Solved: {filename} ({result['time_taken']:.1f}s)[/green]")
            else:
                console.print(f"  [red]❌ Failed: {filename} - {result['error']}[/red]")
            
            return result
    
    async def process_all(
        self,
        images: List[Tuple[str, bytes, str]],
    ) -> List[dict]:
        """
        Process all images in parallel
        
        Args:
            images: List of (filename, image_bytes, mime_type) tuples
            
        Returns:
            List of result dictionaries
        """
        if not images:
            console.print("[yellow]⚠️ No images to process[/yellow]")
            return []
        
        console.print(f"\n[bold cyan]🚀 Starting parallel processing of {len(images)} question(s)[/bold cyan]")
        console.print(f"[dim]Max concurrent requests: {self.max_concurrent}[/dim]\n")
        
        start_time = time.time()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task_id = progress.add_task(
                "[cyan]Processing questions...[/cyan]",
                total=len(images)
            )
            
            # Create tasks for all images
            tasks = [
                self._process_single(image_data, progress, task_id)
                for image_data in images
            ]
            
            # Run all tasks concurrently
            self.results = await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
        
        # Print summary
        successful = sum(1 for r in self.results if r["success"])
        failed = len(self.results) - successful
        
        console.print(f"\n[bold green]✨ Processing Complete![/bold green]")
        console.print(f"  📊 Total: {len(self.results)} | ✅ Success: {successful} | ❌ Failed: {failed}")
        console.print(f"  ⏱️ Total time: {total_time:.1f}s | Avg per question: {total_time/len(self.results):.1f}s")
        
        return self.results
    
    def get_results(self) -> List[dict]:
        """Get the processing results"""
        return self.results


if __name__ == "__main__":
    # Test the processor
    async def test():
        processor = ParallelProcessor()
        print(f"Processor initialized with max concurrent: {processor.max_concurrent}")
    
    asyncio.run(test())
