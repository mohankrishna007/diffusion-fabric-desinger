#!/usr/bin/env python3
"""
Weaver AI - Cross-Platform Launcher
Launch UI, API, or run tests with a simple menu interface.
"""

import sys
import os
import subprocess
import platform
from pathlib import Path


def print_header():
    """Print application header."""
    print("\n" + "=" * 60)
    print("🧵  Weaver AI - Fabric Design Studio")
    print("=" * 60 + "\n")


def print_menu():
    """Print main menu options."""
    print("What would you like to run?\n")
    print("  1. 🎨  Design Studio (UI)")
    print("  2. 🔌  API Server")
    print("  3. 🧪  Run Tests")
    print("  4. 📦  Setup/Install Dependencies")
    print("  5. ❌  Exit")
    print()


def get_python_command():
    """Get the appropriate Python command for the platform."""
    if platform.system() == "Windows":
        return "python"
    return "python3"


def check_uv():
    """Check if uv is installed."""
    try:
        result = subprocess.run(
            ["uv", "--version"],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            print(f"✅ Found UV: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    return False


def check_dependencies():
    """Check if dependencies are installed."""
    venv_path = Path(".venv")
    if not venv_path.exists():
        print("⚠️  Virtual environment not found.")
        return False
    
    # Check for key packages
    try:
        import streamlit
        import fastapi
        print("✅ Dependencies installed")
        return True
    except ImportError:
        print("⚠️  Some dependencies are missing.")
        return False


def run_setup():
    """Run setup/installation."""
    print("\n" + "=" * 60)
    print("📦  Setting up Weaver AI...")
    print("=" * 60 + "\n")
    
    has_uv = check_uv()
    
    if not has_uv:
        print("UV not found. Installing UV...\n")
        
        if platform.system() == "Windows":
            # Install UV on Windows
            subprocess.run(
                ["powershell", "-c", "irm https://astral.sh/uv/install.ps1 | iex"],
                check=False
            )
        else:
            # Install UV on Unix
            subprocess.run(
                ["curl", "-LsSf", "https://astral.sh/uv/install.sh", "|", "sh"],
                shell=True,
                check=False
            )
        
        print("\n✅ UV installed!")
        has_uv = check_uv()
    
    if has_uv:
        print("\nInstalling project dependencies...\n")
        subprocess.run(["uv", "sync"], check=True)
        print("\n✅ Setup complete!")
    else:
        print("\n❌ Setup failed. Please install UV manually:")
        print("   Windows: powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\"")
        print("   Linux/Mac: curl -LsSf https://astral.sh/uv/install.sh | sh")
    
    input("\nPress Enter to continue...")


def run_ui():
    """Launch the Streamlit UI."""
    print("\n" + "=" * 60)
    print("🎨  Launching Design Studio...")
    print("=" * 60 + "\n")
    
    app_path = Path("src/ui/streamlit_app.py")
    
    if not app_path.exists():
        print(f"❌ UI app not found at: {app_path}")
        input("\nPress Enter to continue...")
        return
    
    print(f"✅ App found at: {app_path}")
    print("\n🚀 Starting Streamlit...")
    print("   URL: http://localhost:8501")
    print("   Press Ctrl+C to stop\n")
    
    has_uv = check_uv()
    
    try:
        if has_uv:
            subprocess.run(
                [
                    "uv", "run", "streamlit", "run", str(app_path),
                    "--server.port=8501",
                    "--server.headless=true",
                    "--browser.gatherUsageStats=false"
                ],
                check=True
            )
        else:
            subprocess.run(
                [
                    "streamlit", "run", str(app_path),
                    "--server.port=8501",
                    "--server.headless=true",
                    "--browser.gatherUsageStats=false"
                ],
                check=True
            )
    except KeyboardInterrupt:
        print("\n\n✅ UI stopped")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error launching UI: {e}")
    except FileNotFoundError:
        print("\n❌ Streamlit not found. Please run setup first (option 4)")
    
    input("\nPress Enter to continue...")


def run_api():
    """Launch the FastAPI server."""
    print("\n" + "=" * 60)
    print("🔌  Launching API Server...")
    print("=" * 60 + "\n")
    
    print("🚀 Starting FastAPI server...")
    print("   URL: http://localhost:8000")
    print("   Docs: http://localhost:8000/docs")
    print("   Press Ctrl+C to stop\n")
    
    has_uv = check_uv()
    
    try:
        if has_uv:
            subprocess.run(
                ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
                check=True
            )
        else:
            subprocess.run(
                ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
                check=True
            )
    except KeyboardInterrupt:
        print("\n\n✅ API server stopped")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error launching API: {e}")
    except FileNotFoundError:
        print("\n❌ Uvicorn not found. Please run setup first (option 4)")
    
    input("\nPress Enter to continue...")


def run_tests():
    """Run the test suite."""
    print("\n" + "=" * 60)
    print("🧪  Running Tests...")
    print("=" * 60 + "\n")
    
    has_uv = check_uv()
    
    try:
        if has_uv:
            result = subprocess.run(
                ["uv", "run", "pytest", "-v", "--tb=short"],
                check=False
            )
        else:
            result = subprocess.run(
                ["pytest", "-v", "--tb=short"],
                check=False
            )
        
        if result.returncode == 0:
            print("\n✅ All tests passed!")
        else:
            print("\n⚠️  Some tests failed. See output above.")
    
    except FileNotFoundError:
        print("\n❌ Pytest not found. Please run setup first (option 4)")
    
    input("\nPress Enter to continue...")


def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if platform.system() == 'Windows' else 'clear')


def main():
    """Main application loop."""
    while True:
        clear_screen()
        print_header()
        
        # Check dependencies status
        if not check_dependencies():
            print("⚠️  Dependencies not installed. Please run setup (option 4)\n")
        
        print_menu()
        
        choice = input("Enter your choice (1-5): ").strip()
        
        if choice == "1":
            run_ui()
        elif choice == "2":
            run_api()
        elif choice == "3":
            run_tests()
        elif choice == "4":
            run_setup()
        elif choice == "5":
            print("\n👋 Goodbye!\n")
            sys.exit(0)
        else:
            print("\n❌ Invalid choice. Please enter 1-5.")
            input("\nPress Enter to continue...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!\n")
        sys.exit(0)
