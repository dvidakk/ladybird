#!/usr/bin/env python3

import os
import sys
import subprocess
import shutil
import platform

def exit_if_running_as_root():
    if platform.system() != "Windows" and os.geteuid() == 0:
        print("Do not run BuildVcpkg.py as root, parts of your Toolchain directory will become root-owned")
        sys.exit(1)

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    source_dir = os.path.dirname(script_dir)

    # Check for CI mode
    ci = False
    if len(sys.argv) > 1 and sys.argv[1] == "--ci":
        print("Running in CI mode, will not check for root user")
        ci = True
    else:
        exit_if_running_as_root()

    GIT_REPO = "https://github.com/microsoft/vcpkg.git"
    #GIT_REV = "a39a74405f277773aba08018bb797cb4a6614d0c"  # 2024.09.19
    GIT_ERV = "c82f74667287d3dc386bce81e44964370c91a289"  # 2024.09.30

    PREFIX_DIR = os.path.join(script_dir, "Local", "vcpkg")

    os.makedirs(os.path.join(script_dir, "Tarballs"), exist_ok=True)
    os.chdir(os.path.join(script_dir, "Tarballs"))

    if not os.path.exists("vcpkg"):
        subprocess.run(["git", "clone", GIT_REPO], check=True)

    os.chdir("vcpkg")

    # Check if vcpkg is already at the correct version
    try:
        current_rev = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        if current_rev == GIT_REV:
            print("vcpkg is already at the correct version")
            return
    except subprocess.CalledProcessError:
        pass  # If git rev-parse fails, we'll proceed with the update

    print("Building vcpkg")

    subprocess.run(["git", "fetch", "origin"], check=True)
    subprocess.run(["git", "checkout", GIT_REV], check=True)

    # Run bootstrap script
    if platform.system() == "Windows":
        bootstrap_script = "bootstrap-vcpkg.bat"
    else:
        bootstrap_script = "./bootstrap-vcpkg.sh"
    
    subprocess.run([bootstrap_script, "-disableMetrics"], check=True)

    # Copy vcpkg executable
    os.makedirs(os.path.join(PREFIX_DIR, "bin"), exist_ok=True)
    vcpkg_exe = "vcpkg.exe" if platform.system() == "Windows" else "vcpkg"
    shutil.copy2(vcpkg_exe, os.path.join(PREFIX_DIR, "bin"))

    print("vcpkg built successfully")

if __name__ == "__main__":
    main()
