"""
Pragma Compiler — build once, straight to binary.

Usage:
  python pragma.py <source.run>              Compile to binary (same name as source)
  python pragma.py <source.run> --run        Compile and immediately run
  python pragma.py <source.run> --emit-c     Also save the generated C file alongside binary
  python pragma.py <source.run> --ast        Print the AST (debug)
  python pragma.py <source.run> --tokens     Print the token stream (debug)

Optimisation flags:
  --lto          Link-time optimisation (-flto)
  --pgo-record   Instrument binary to record branch profiles (-fprofile-generate)
  --pgo-use      Compile using a recorded profile (-fprofile-use)

PGO workflow:
  1. python pragma.py prog.run --pgo-record    # build instrumented binary
  2. ./prog                                    # run with real workload -> *.gcda files
  3. python pragma.py prog.run --pgo-use       # build optimised binary

Safety / analysis flags:
  --fullsafety   Runtime bounds checks + ASan + UBSan (dev/test only)
  --tsan         ThreadSanitizer (threaded code, mutually exclusive with --fullsafety)

The C intermediate is written to a temp file and deleted after compilation
unless --emit-c is given, in which case it is saved as <source>.c.
"""

import sys
import os
import subprocess
import tempfile
from pathlib import Path

from lexer import Lexer
from parser import parse, ParseError
from codegen import generate


def _load_env():
    """Walk up from this file to find and load the nearest .env file."""
    here = Path(__file__).resolve().parent
    for directory in [here, *here.parents]:
        env_file = directory / '.env'
        if env_file.is_file():
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, _, val = line.partition('=')
                        os.environ.setdefault(key.strip(), val.strip())
            break

_load_env()

# Compiler search order: .env CLANG_PATH → standard LLVM Windows path → PATH
_CLANG_WIN = os.environ.get('CLANG_PATH', r'C:\Program Files\LLVM\bin\clang.exe')
_CC_CANDIDATES = [_CLANG_WIN, 'clang', 'gcc', 'cc']


def _find_compiler():
    import shutil
    for cc in _CC_CANDIDATES:
        if os.path.isfile(cc):
            return cc
        if shutil.which(cc):
            return cc
    return None


def transpile(source: str, safe: bool = False) -> str:
    program = parse(source)
    return generate(program, safe=safe)


def main():
    args = sys.argv[1:]

    if not args:
        print(__doc__)
        sys.exit(1)

    src_path = args[0]
    if not os.path.exists(src_path):
        print(f"Error: file not found: {src_path!r}")
        sys.exit(1)

    with open(src_path, 'r', encoding='utf-8') as f:
        source = f.read()

    flags = {a for a in args[1:] if a.startswith('--')}

    # ── Debug modes ──────────────────────────────────────────────────────────

    if '--tokens' in flags:
        tokens = Lexer(source).tokenize()
        for tok in tokens:
            print(f"  {tok.line:3}  {tok.type.name:<18} {tok.value!r}")
        return

    if '--ast' in flags:
        import pprint
        program = parse(source)
        pprint.pprint(program)
        return

    # ── Validate flag combinations ────────────────────────────────────────────

    if '--fullsafety' in flags and '--tsan' in flags:
        print("Error: --fullsafety (includes ASan) and --tsan cannot be combined.")
        sys.exit(1)
    if ('--fullsafety' in flags or '--tsan' in flags) and '--pgo-use' in flags:
        print("Error: sanitizers and --pgo-use cannot be combined.")
        sys.exit(1)
    if '--pgo-record' in flags and '--pgo-use' in flags:
        print("Error: --pgo-record and --pgo-use are mutually exclusive.")
        sys.exit(1)

    # ── Transpile to C ───────────────────────────────────────────────────────

    safe_mode = '--fullsafety' in flags
    try:
        c_src = transpile(source, safe=safe_mode)
    except ParseError as e:
        print(f"Parse error: {e}")
        sys.exit(1)

    # ── Write C (temp or named) ───────────────────────────────────────────────

    stem = os.path.splitext(src_path)[0]
    exe  = stem + ('.exe' if sys.platform == 'win32' else '')

    if '--emit-c' in flags:
        c_path = stem + '.c'
        with open(c_path, 'w', encoding='utf-8') as f:
            f.write(c_src)
        print(f"C source:    {c_path}")
        tmp_c = None
    else:
        fd, c_path = tempfile.mkstemp(suffix='.c', prefix='pragma_')
        os.close(fd)
        with open(c_path, 'w', encoding='utf-8') as f:
            f.write(c_src)
        tmp_c = c_path

    # ── Find compiler ─────────────────────────────────────────────────────────

    cc = _find_compiler()
    if not cc:
        print("Error: no C compiler found.")
        print("  Windows: winget install LLVM.LLVM")
        print("  Linux:   sudo apt install clang")
        if tmp_c:
            os.unlink(tmp_c)
        sys.exit(1)

    # ── Build flags ───────────────────────────────────────────────────────────

    cc_flags = ['-O2', '-Wall', '-Wno-unused-variable', '-Wno-format', '-Wno-parentheses',
                '-Wno-incompatible-function-pointer-types', '-Wno-cast-function-type-strict',
                '-Wno-deprecated-non-prototype']

    if '--lto'        in flags: cc_flags.append('-flto')
    if '--pgo-record' in flags: cc_flags.append('-fprofile-generate')
    if '--pgo-use'    in flags: cc_flags += ['-fprofile-use', '-fprofile-correction']
    if '--fullsafety' in flags: cc_flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
    if '--tsan'       in flags: cc_flags.append('-fsanitize=thread')

    # ── Compile ───────────────────────────────────────────────────────────────

    print(f"Compiling:   {src_path}  ->  {exe}")
    r = subprocess.run(
        [cc, *cc_flags, '-o', exe, c_path],
        capture_output=True, text=True, errors='replace'
    )

    if tmp_c:
        os.unlink(tmp_c)

    if r.stdout: print(r.stdout, end='')
    if r.stderr: print(r.stderr, end='')

    if r.returncode != 0:
        print(f"Compile failed (exit {r.returncode})")
        sys.exit(r.returncode)

    print(f"Built:       {exe}")

    # ── Run ───────────────────────────────────────────────────────────────────

    if '--run' in flags:
        print("Running...\n" + "-"*40)
        subprocess.run([os.path.abspath(exe)])


if __name__ == '__main__':
    main()
