#!/usr/bin/env python3
"""
Cross-platform build script for DG-LAB-VRCOSC
Handles version generation, dependency installation, and PyInstaller build
"""

import os
import sys
import subprocess
import argparse
import shutil
from pathlib import Path
from typing import Optional


def run_command(command: str, shell: bool = False, cwd: Optional[Path] = None) -> bool:
    """Run a command and return success status"""
    try:
        print(f"Running: {command}")
        result = subprocess.run(
            command if shell else command.split(),
            shell=shell,
            cwd=cwd or Path.cwd(),
            check=True
        )
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}")
        return False
    except Exception as e:
        print(f"Error running command: {e}")
        return False


def check_dependencies() -> bool:
    """Check if required tools are available"""
    required_tools = ['python', 'pip']
    
    for tool in required_tools:
        try:
            subprocess.run([tool, '--version'], capture_output=True, check=True)
            print(f"+ {tool} is available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"X {tool} is not available or not in PATH")
            return False
    
    return True


def install_dependencies(project_root: Path) -> bool:
    """Install Python dependencies"""
    requirements_file = project_root / 'requirements.txt'
    
    if not requirements_file.exists():
        print("- requirements.txt not found")
        return False
    
    print("Installing dependencies...")
    commands = [
        # Skip pip upgrade due to potential conflicts
        f"pip install -r {requirements_file}",
    ]
    
    for cmd in commands:
        if not run_command(cmd, shell=True, cwd=project_root):
            print(f"Warning: Command failed: {cmd}")
            # Continue with build even if some dependencies fail
    
    return True


def generate_version(project_root: Path) -> bool:
    """Generate version.py file"""
    version_script = project_root / 'scripts' / 'generate_version.py'
    
    if not version_script.exists():
        print("- Version generation script not found")
        return False
    
    print("Generating version file...")
    return run_command(f"python {version_script}", shell=True, cwd=project_root)


def run_type_check(project_root: Path) -> bool:
    """Run type checking with pyright"""
    print("Running type check...")
    return run_command("python -m pyright src/", shell=True, cwd=project_root)


def build_application(project_root: Path) -> bool:
    """Build the application with PyInstaller"""
    print("Building application...")
    print("Using upstream DG-LAB-VRCOSC.spec file")
    
    # Use upstream spec file
    spec_file = project_root / "DG-LAB-VRCOSC.spec"
    if not spec_file.exists():
        print(f"- Spec file not found: {spec_file}")
        return False
    
    command = ["pyinstaller", str(spec_file)]
    
    try:
        print(f"Running: pyinstaller {' '.join(command[1:])}")
        result = subprocess.run(command, cwd=project_root, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"PyInstaller failed with exit code {e.returncode}")
        return False
    except Exception as e:
        print(f"Error running PyInstaller: {e}")
        return False


def copy_additional_files(project_root: Path) -> bool:
    """Copy additional files to dist directory"""
    print("Copying additional files...")
    
    dist_dir = project_root / 'dist'
    if not dist_dir.exists():
        print("- dist directory not found")
        return False
    
    try:
        # Copy version info
        version_file = project_root / 'src' / 'version.py'
        if version_file.exists():
            shutil.copy2(version_file, dist_dir / 'version.txt')
        
        # Generate build info JSON
        build_info_script = f"""
import sys
sys.path.insert(0, 'src')
from version import get_build_info
import json
with open('dist/build-info.json', 'w') as f:
    json.dump(get_build_info(), f, indent=2)
"""
        with open(project_root / 'temp_build_info.py', 'w') as f:
            f.write(build_info_script)
        
        run_command("python temp_build_info.py", shell=True, cwd=project_root)
        (project_root / 'temp_build_info.py').unlink()
        
        print("+ Additional files copied")
        return True
        
    except Exception as e:
        print(f"- Error copying files: {e}")
        return False


def clean_build_artifacts(project_root: Path) -> None:
    """Clean up build artifacts"""
    print("Cleaning build artifacts...")
    
    # Only clean specific directories in project root
    cleanup_paths = [
        project_root / 'build',
        project_root / 'dist'
    ]
    
    for path in cleanup_paths:
        if path.exists():
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                    print(f"Removed directory: {path}")
                else:
                    path.unlink()
                    print(f"Removed file: {path}")
            except Exception as e:
                print(f"Warning: Could not remove {path}: {e}")


def main() -> int:
    """Main build function"""
    # Set UTF-8 encoding for Windows console
    if sys.platform == 'win32':
        os.environ['PYTHONIOENCODING'] = 'utf-8'
    
    parser = argparse.ArgumentParser(description="Build DG-LAB-VRCOSC application")
    parser.add_argument("--no-deps", action="store_true", help="Skip dependency installation")
    parser.add_argument("--no-typecheck", action="store_true", help="Skip type checking")
    parser.add_argument("--clean", action="store_true", help="Clean build artifacts before building")
    parser.add_argument("--version-only", action="store_true", help="Only generate version file")
    
    args = parser.parse_args()
    
    # Get project root
    project_root = Path(__file__).parent.parent
    print(f"Building DG-LAB-VRCOSC in: {project_root}")
    
    # Clean if requested
    if args.clean:
        clean_build_artifacts(project_root)
    
    # Check dependencies
    if not check_dependencies():
        print("- Required tools not available")
        return 1
    
    # Generate version
    if not generate_version(project_root):
        print("- Version generation failed")
        return 1
    
    if args.version_only:
        print("+ Version file generated successfully")
        return 0
    
    # Install dependencies
    if not args.no_deps:
        if not install_dependencies(project_root):
            print("- Dependency installation failed")
            return 1
    
    # Type check
    if not args.no_typecheck:
        if not run_type_check(project_root):
            print("! Type check failed, continuing anyway...")
    
    # Build application
    if not build_application(project_root):
        print("- Application build failed")
        return 1
    
    # Copy additional files
    if not copy_additional_files(project_root):
        print("! Failed to copy additional files")
    
    print("+ Build completed successfully!")
    
    # Show build results
    dist_dir = project_root / 'dist'
    if dist_dir.exists():
        print(f"\nBuild artifacts in: {dist_dir}")
        for item in dist_dir.iterdir():
            print(f"  - {item.name}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())