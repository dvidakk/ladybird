#!/usr/bin/env python3

import os
import sys
import subprocess
import argparse
import shutil
from pathlib import Path
import platform

BUILD_PRESET = os.environ.get('BUILD_PRESET', 'default')

def print_help():
    script_name = Path(sys.argv[0]).name
    print(f"""Usage: {script_name} COMMAND [ARGS...]
  Supported COMMANDs:
    build:      Compiles the target binaries, [ARGS...] are passed through to ninja
    install:    Installs the target binary
    run:        {script_name} run EXECUTABLE [ARGS...]
                    Runs the EXECUTABLE on the build host, e.g.
                    'shell' or 'js', [ARGS...] are passed through to the executable
    gdb:        Same as run, but also starts a gdb remote session.
                {script_name} gdb EXECUTABLE [-ex 'any gdb command']...
                    Passes through '-ex' commands to gdb
    vcpkg:      Ensure that dependencies are available
    test:       {script_name} test [TEST_NAME_PATTERN]
                    Runs the unit tests on the build host, or if TEST_NAME_PATTERN
                    is specified tests matching it.
    delete:     Removes the build environment
    rebuild:    Deletes and re-creates the build environment, and compiles the project
    addr2line:  {script_name} addr2line BINARY_FILE ADDRESS
                    Resolves the ADDRESS in BINARY_FILE to a file:line. It will
                    attempt to find the BINARY_FILE in the appropriate build directory

  Examples:
    {script_name} run ladybird
        Runs the Ladybird browser
    {script_name} run js -A
        Runs the js(1) REPL
    {script_name} test
        Runs the unit tests on the build host
    {script_name} addr2line RequestServer 0x12345678
        Resolves the address 0x12345678 in the RequestServer binary
""")

def get_top_dir():
    return subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True).strip()

def create_build_dir():
    subprocess.run(['cmake', '--preset', BUILD_PRESET] + CMAKE_ARGS + ['-S', LADYBIRD_SOURCE_DIR, '-B', BUILD_DIR], check=True)

def check_ninja():
    ninja_path = shutil.which('ninja')
    if not ninja_path:
        print("Error: Ninja build system not found. Please install Ninja and ensure it is in your PATH.")
        sys.exit(1)
    os.environ['CMAKE_MAKE_PROGRAM'] = ninja_path

def pick_host_compiler():
    global CMAKE_ARGS

    is_windows = platform.system() == "Windows"

    if is_windows:
        vswhere_path = os.path.join(os.environ.get('ProgramFiles(x86)', ''), 'Microsoft Visual Studio', 'Installer', 'vswhere.exe')
        if os.path.exists(vswhere_path):
            try:
                vs_path = subprocess.check_output([vswhere_path, '-latest', '-property', 'installationPath'], text=True).strip()
                vcvarsall = os.path.join(vs_path, 'VC', 'Auxiliary', 'Build', 'vcvarsall.bat')
                if os.path.exists(vcvarsall):
                    print(f"Found Visual Studio at: {vs_path}")
                    # Set up environment for Visual Studio
                    env_cmd = f'"{vcvarsall}" x64 && set'
                    env_output = subprocess.check_output(env_cmd, shell=True, text=True)
                    for line in env_output.splitlines():
                        if '=' in line:
                            key, value = line.split('=', 1)
                            os.environ[key] = value
                    cl_path = shutil.which('cl')
                    link_path = shutil.which('link')
                    if cl_path and link_path:
                        cc = cxx = cl_path
                        print("Visual Studio environment set up successfully.")
                        CMAKE_ARGS = [
                            f"-DCMAKE_C_COMPILER={cc}",
                            f"-DCMAKE_CXX_COMPILER={cxx}",
                            f"-DCMAKE_LINKER={link_path}",
                            "-DCMAKE_MT=C:/Program Files (x86)/Windows Kits/10/bin/10.0.22621.0/x64/mt.exe"
                            
                        ]
                        os.environ['CC'] = cc
                        os.environ['CXX'] = cxx
                        return
                    else:
                        print("Warning: 'cl' or 'link' not found in PATH after setting up Visual Studio environment.")
            except subprocess.CalledProcessError:
                print("Warning: Failed to set up Visual Studio environment.")

        print("Visual Studio not found or setup failed. Cannot proceed on Windows without Visual Studio.")
        sys.exit(1)
    else:
        # Unix-like system logic (unchanged)
        compiler_pairs = [
            ('gcc', 'g++'),
            ('clang', 'clang++'),
            ('cc', 'c++')
        ]
        for c_compiler, cpp_compiler in compiler_pairs:
            if shutil.which(c_compiler) and shutil.which(cpp_compiler):
                cc = shutil.which(c_compiler)
                cxx = shutil.which(cpp_compiler)
                break
        else:
            print("No suitable compiler found. Please set CC and CXX environment variables.")
            sys.exit(1)

        CMAKE_ARGS = [f"-DCMAKE_C_COMPILER={cc}", f"-DCMAKE_CXX_COMPILER={cxx}"]
        os.environ['CC'] = cc
        os.environ['CXX'] = cxx

    print(f"Using compiler: CC={os.environ['CC']}, CXX={os.environ['CXX']}")

    # Check compiler version
    try:
        if 'cl' in os.environ['CC'].lower():
            version_output = subprocess.check_output(f"{os.environ['CC']}", shell=True, text=True, stderr=subprocess.STDOUT)
        else:
            version_output = subprocess.check_output([os.environ['CC'], '--version'], text=True)
        print(f"Compiler version:\n{version_output.strip()}")
    except subprocess.CalledProcessError as e:
        print(f"Warning: Unable to determine compiler version. Error: {e}")
    except FileNotFoundError:
        print(f"Warning: Compiler {os.environ['CC']} not found in PATH. Make sure it's correctly installed and accessible.")

def cmd_with_target():
    global BUILD_DIR, LADYBIRD_SOURCE_DIR
    # TODO: Implement pick_host_compiler
    pick_host_compiler()
    CMAKE_ARGS.extend([f"-DCMAKE_C_COMPILER={os.environ.get('CC', 'cc')}", 
                       f"-DCMAKE_CXX_COMPILER={os.environ.get('CXX', 'c++')}"])

    if not os.path.isdir(LADYBIRD_SOURCE_DIR):
        LADYBIRD_SOURCE_DIR = get_top_dir()
        os.environ['LADYBIRD_SOURCE_DIR'] = LADYBIRD_SOURCE_DIR

    # Note: Keep in sync with buildDir defaults in CMakePresets.json
    if BUILD_PRESET == "default":
        BUILD_DIR = os.path.join(LADYBIRD_SOURCE_DIR, "Build", "ladybird")
    elif BUILD_PRESET == "Debug":
        BUILD_DIR = os.path.join(LADYBIRD_SOURCE_DIR, "Build", "ladybird-debug")
    elif BUILD_PRESET == "Sanitizer":
        BUILD_DIR = os.path.join(LADYBIRD_SOURCE_DIR, "Build", "ladybird-sanitizers")

    CMAKE_ARGS.append(f"-DCMAKE_INSTALL_PREFIX={os.path.join(LADYBIRD_SOURCE_DIR, 'Build', f'ladybird-install-{BUILD_PRESET}')}")

    path_separator = ';' if platform.system() == "Windows" else ':'
    os.environ['PATH'] = f"{os.path.join(LADYBIRD_SOURCE_DIR, 'Toolchain', 'Local', 'cmake', 'bin')}{path_separator}{os.path.join(LADYBIRD_SOURCE_DIR, 'Toolchain', 'Local', 'vcpkg', 'bin')}{path_separator}{os.environ['PATH']}"
    os.environ['VCPKG_ROOT'] = os.path.join(LADYBIRD_SOURCE_DIR, "Toolchain", "Tarballs", "vcpkg")

def ensure_target():
    if not os.path.isfile(os.path.join(BUILD_DIR, "build.ninja")):
        create_build_dir()

def run_tests(test_name=None):
    ctest_args = ["--preset", BUILD_PRESET, "--output-on-failure", "--test-dir", BUILD_DIR]
    if test_name:
        if test_name == "WPT":
            ctest_args.extend(["-C", "Integration"])
        ctest_args.extend(["-R", test_name])
    subprocess.run(["ctest"] + ctest_args, check=True)

def build_target(*args):
    makejobs = os.environ.get('MAKEJOBS', subprocess.check_output(['cmake', '-P', f"{LADYBIRD_SOURCE_DIR}/Meta/CMake/processor-count.cmake"], text=True).strip())

    if not args:
        os.environ['CMAKE_BUILD_PARALLEL_LEVEL'] = makejobs
        subprocess.run(['cmake', '--build', BUILD_DIR], check=True)
    else:
        subprocess.run(['ninja', '-j', makejobs, '-C', BUILD_DIR, '--'] + list(args), check=True)

def delete_target():
    if os.path.isdir(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)

def build_vcpkg():
    build_vcpkg_script = os.path.join(LADYBIRD_SOURCE_DIR, 'Toolchain', 'Build_vcpkg.py')
    if not os.path.exists(build_vcpkg_script):
        print(f"Error: {build_vcpkg_script} not found.")
        sys.exit(1)
    try:
        subprocess.run([sys.executable, build_vcpkg_script], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running BuildVcpkg.py: {e}")
        sys.exit(1)

def ensure_toolchain():
    build_vcpkg()

def run_gdb(args):
    gdb_args = []
    pass_arg_to_gdb = ""
    lagom_executable = ""
    gdb = "gdb" if shutil.which("gdb") else "lldb"

    if not shutil.which(gdb):
        sys.exit("Please install gdb or lldb!")

    for arg in args:
        if pass_arg_to_gdb:
            gdb_args.extend([pass_arg_to_gdb, arg])
            pass_arg_to_gdb = ""
        elif arg == "-ex":
            pass_arg_to_gdb = arg
        elif arg.startswith('-'):
            sys.exit(f"Don't know how to handle argument: {arg}")
        else:
            if lagom_executable:
                sys.exit("Lagom executable can't be specified more than once")
            lagom_executable = arg

    if pass_arg_to_gdb:
        gdb_args.append(pass_arg_to_gdb)

    if lagom_executable == "ladybird":
        lagom_executable = "Ladybird.app" if sys.platform == "darwin" else "Ladybird"

    subprocess.run([gdb, os.path.join(BUILD_DIR, "bin", lagom_executable)] + gdb_args, check=True)

def build_and_run_lagom_target(args):
    lagom_target = args[0] if args else "Ladybird"
    lagom_args = args[1:]

    if lagom_target == "ladybird":
        lagom_target = "Ladybird"

    if BUILD_PRESET == "Sanitizer":
        os.environ['ASAN_OPTIONS'] = os.environ.get('ASAN_OPTIONS', "strict_string_checks=1:check_initialization_order=1:strict_init_order=1:detect_stack_use_after_return=1:allocator_may_return_null=1")
        os.environ['UBSAN_OPTIONS'] = os.environ.get('UBSAN_OPTIONS', "print_stacktrace=1:print_summary=1:halt_on_error=1")

    build_target(lagom_target)

    if lagom_target in ["headless-browser", "ImageDecoder", "Ladybird", "RequestServer", "WebContent", "WebDriver", "WebWorker"] and sys.platform == "darwin":
        subprocess.run([os.path.join(BUILD_DIR, "bin", "Ladybird.app", "Contents", "MacOS", lagom_target)] + lagom_args, check=True)
    else:
        executable = f"{lagom_target}.exe" if platform.system() == "Windows" else lagom_target
        subprocess.run([os.path.join(BUILD_DIR, "bin", executable)] + lagom_args, check=True)

def main():
    global CMAKE_ARGS, LADYBIRD_SOURCE_DIR
    CMAKE_ARGS = []
    LADYBIRD_SOURCE_DIR = os.environ.get('LADYBIRD_SOURCE_DIR', '')

    parser = argparse.ArgumentParser(description="Ladybird build script", add_help=False)
    parser.add_argument('command', help='Command to execute')
    parser.add_argument('args', nargs=argparse.REMAINDER, help='Additional arguments')

    args = parser.parse_args()

    if not args.command or args.command == "help":
        print_help()
        sys.exit(0)

    if args.command in ["build", "install", "run", "gdb", "test", "rebuild", "recreate", "addr2line"]:
        cmd_with_target()
        pick_host_compiler()
        check_ninja()
        if args.command in ["recreate", "rebuild"]:
            delete_target()
        ensure_toolchain()
        ensure_target()

        if args.command == "build":
            build_target(*args.args)
        elif args.command == "install":
            build_target()
            build_target("install")
        elif args.command == "run":
            build_and_run_lagom_target(args.args)
        elif args.command == "gdb":
            if not args.args:
                parser.error("gdb command requires at least one argument")
            build_target(*args.args)
            run_gdb(args.args)
        elif args.command == "test":
            build_target()
            run_tests(args.args[0] if args.args else None)
        elif args.command == "rebuild":
            build_target(*args.args)
        elif args.command == "recreate":
            pass
        elif args.command == "addr2line":
            build_target()
            if len(args.args) < 2:
                parser.error("addr2line command requires at least two arguments")
            binary_file, *addresses = args.args
            binary_file_path = os.path.join(BUILD_DIR, binary_file)
            if platform.system() == "Windows":
                print("addr2line is not available on Windows. Consider using debugging tools specific to Windows.")
            else:
                if not shutil.which("addr2line"):
                    sys.exit("Please install addr2line!")
                if os.path.isfile(binary_file_path) and os.access(binary_file_path, os.X_OK):
                    subprocess.run(["addr2line", "-e", binary_file_path] + addresses, check=True)
                else:
                    for file in Path(BUILD_DIR).rglob(binary_file):
                        if file.is_file() and os.access(file, os.X.OK):
                            subprocess.run(["addr2line", "-e", str(file)] + addresses, check=True)
        else:
            build_target(args.command, *args.args)
    elif args.command == "delete":
        cmd_with_target()
        delete_target()
    elif args.command == "vcpkg":
        cmd_with_target()
        ensure_toolchain()
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
