import os
import sys
import platform
import subprocess
import shutil

def run_command(command):
    try:
        print(f"\n[Command]: {' '.join(command)}\n")
        result = subprocess.run(command, check=True)
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e}")
        sys.exit(1)

def main():
    system_os = platform.system()
    
    common_args = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--enable-plugin=pyside6",
        "--assume-yes-for-downloads",
        "--include-data-dir=fonts=fonts",
        "--include-data-dir=models=models",
        "--include-data-dir=assets=assets",
        "--include-data-file=version.json=version.json",
        "main.py"
    ]

    print(f"Detected OS: {system_os}")

    if system_os == "Windows":
        # === Windows 설정 (Onefile) ===
        print("Starting build for Windows (Onefile)...")
        
        windows_args = [
            "--onefile",
            "--windows-console-mode=disable",
            "--windows-icon-from-ico=assets/icon.ico",
            "--output-filename=ScoreCapturePro.exe"
        ]
        
        final_cmd = common_args[:-1] + windows_args + [common_args[-1]]
        
        run_command(final_cmd)
        print("\nBuild Complete! Check 'ScoreCapturePro.exe'")

    elif system_os == "Darwin":
        # === macOS 설정 (App Bundle) ===
        print("Starting build for macOS (App Bundle)...")
        
        app_name = "ScoreCapturePro.app"
        zip_name = "ScoreCapturePro_Mac.zip"
        
        macos_args = [
            "--macos-create-app-bundle",
            "--macos-disable-console",
            "--macos-app-icon=assets/icon.png",
            "--output-filename=ScoreCapturePro"
        ]
        
        final_cmd = common_args[:-1] + macos_args + [common_args[-1]]
        
        run_command(final_cmd)
        
        if os.path.exists("main.app") and not os.path.exists(app_name):
            print(f"Renaming main.app to {app_name}...")
            shutil.move("main.app", app_name)
        elif os.path.exists(f"ScoreCapturePro.app"):
            pass
            
        if not os.path.exists(app_name):
            print(f"Error: {app_name} not found after build.")
            sys.exit(1)

        print("Updating Info.plist (Bundle ID & Permissions)...")
        plist_path = os.path.join(app_name, "Contents", "Info.plist")
        
        if os.path.exists(plist_path):
            run_command([
                "plutil", "-replace", "CFBundleIdentifier", 
                "-string", "com.scorecapturepro.app", 
                plist_path
            ])

            run_command([
                "plutil", "-replace", "NSScreenCaptureUsageDescription", 
                "-string", "악보 캡처를 위해 화면 녹화 권한이 필요합니다.", 
                plist_path
            ])
            
            print("Re-signing the application to fix 'damaged' error...")
            run_command([
                "codesign", "--force", "--deep", "--sign", "-", app_name
            ])
            
        else:
            print(f"Warning: {plist_path} not found. Settings skipped.")

        # 압축 (Zip)
        print(f"Zipping {app_name} to {zip_name}...")
        if os.path.exists(zip_name):
            os.remove(zip_name)
            
        subprocess.run(["zip", "-r", zip_name, app_name], check=True)
        print(f"\nBuild Complete! Check '{zip_name}'")

    else:
        print(f"Unsupported OS: {system_os}")
        sys.exit(1)

if __name__ == "__main__":
    print("Installing build dependencies...")
    build_deps = ["nuitka", "zstandard"]
    if sys.platform == "darwin":
        build_deps.append("pyobjc-framework-Quartz")
        
    subprocess.run([sys.executable, "-m", "pip", "install"] + build_deps, check=False)
    
    main()