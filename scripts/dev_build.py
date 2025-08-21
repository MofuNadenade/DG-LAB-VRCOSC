#!/usr/bin/env python3
"""
Development build script for DG-LAB-VRCOSC
Quick rebuild for development with hot-reload capabilities
"""

import sys
import time
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class BuildHandler(FileSystemEventHandler):
    """Handle file system events for auto-rebuild"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.last_build = 0.0
        self.build_delay = 2.0  # seconds
        
    def on_modified(self, event):
        if event.is_directory:
            return
        
        # Only rebuild for Python files
        if not event.src_path.endswith('.py'):
            return
        
        # Avoid rebuilding too frequently
        current_time = time.time()
        if current_time - self.last_build < self.build_delay:
            return
        
        print(f"File modified: {event.src_path}")
        self.rebuild()
        self.last_build = current_time
    
    def rebuild(self):
        """Quick rebuild - version generation only"""
        print("Quick rebuild...")
        try:
            result = subprocess.run([
                sys.executable, 
                'scripts/generate_version.py'
            ], cwd=self.project_root, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("+ Version updated")
            else:
                print(f"- Version update failed: {result.stderr}")
                
        except Exception as e:
            print(f"- Rebuild error: {e}")


def run_development_server(project_root: Path):
    """Run the application in development mode"""
    print("Starting development mode...")
    
    # Generate initial version
    print("Generating initial version...")
    subprocess.run([sys.executable, 'scripts/generate_version.py'], cwd=project_root)
    
    # Start file watcher
    event_handler = BuildHandler(project_root)
    observer = Observer()
    observer.schedule(event_handler, str(project_root / 'src'), recursive=True)
    observer.start()
    
    print("Watching for file changes...")
    print("Watching directory: src/")
    print("Auto-rebuild on .py file changes")
    print("Press Ctrl+C to stop")
    
    try:
        # Run the application
        app_process = subprocess.Popen([
            sys.executable, 'src/app.py'
        ], cwd=project_root)
        
        # Wait for application to finish
        app_process.wait()
        
    except KeyboardInterrupt:
        print("\nStopping development server...")
        if 'app_process' in locals():
            app_process.terminate()
    finally:
        if observer:
            observer.stop()
            observer.join()


def main():
    """Main function"""
    project_root = Path(__file__).parent.parent
    
    if len(sys.argv) > 1 and sys.argv[1] == '--watch':
        run_development_server(project_root)
    else:
        # Quick build only
        print("Quick development build...")
        
        # Generate version
        result = subprocess.run([
            sys.executable, 'scripts/generate_version.py'
        ], cwd=project_root)
        
        if result.returncode == 0:
            print("+ Development build ready")
            print("Run with --watch for auto-rebuild")
        else:
            print("- Build failed")
            return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())