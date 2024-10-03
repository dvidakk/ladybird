#!/usr/bin/env python3

import os
import sys
import subprocess
import platform
import shutil

# This script builds the GN meta-build system
def main():
    script_dir = os.path.dirname(os.path.realpath(__file__))
    
    # Check if running as root (on Unix-like systems)
    if os.name == 'posix' and os.geteuid() == 0:
        print("Do not run BuildGN.py as root, parts of your Toolchain directory will become root-owned")
        sys.exit(1)

    # Determine number of processing units
    try:
        nproc = len(os.sched_getaffinity(0))
    except AttributeError:
        nproc = os.cpu_count()

    makejobs = os.environ.get('MAKEJOBS', str(nproc))

    git_repo = "https://gn.googlesource.com/gn"
    git_rev = "fae280eabe5d31accc53100137459ece19a7a295"
    build_dir = os.path.join(script_dir, "Build", "gn")
    prefix_dir = os.path.join(script_dir, "Local", "gn")

    tarballs_dir = os.path.join(script_dir, "Tarballs")
    os.makedirs(tarballs_dir, exist_ok=True)
    os.chdir(tarballs_dir)

    if not os.path.exists("gn"):
        subprocess.run(["git", "clone", git_repo], check=True)

    os.chdir("gn")
    subprocess.run(["git", "fetch", "origin"], check=True)
    subprocess.run(["git", "checkout", git_rev], check=True)

    # On Windows, we need to use a different command to run the gen script
    if platform.system() == "Windows":
        gen_command = ["python", "build/gen.py"]
    else:
        gen_command = ["./build/gen.py"]

    gen_command.extend(["--out-path", build_dir, "--allow-warnings"])
    subprocess.run(gen_command, check=True)

    # Use 'ninja' on Unix-like systems, 'ninja.exe' on Windows
    ninja_command = "ninja.exe" if platform.system() == "Windows" else "ninja"
    subprocess.run([ninja_command, "-C", build_dir], check=True)

    os.makedirs(os.path.join(prefix_dir, "bin"), exist_ok=True)
    
    # Copy the built 'gn' executable, adding '.exe' extension on Windows
    gn_executable = "gn.exe" if platform.system() == "Windows" else "gn"
    shutil.copy2(os.path.join(build_dir, gn_executable), os.path.join(prefix_dir, "bin"))

if __name__ == "__main__":
    main()
