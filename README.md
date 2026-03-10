-------------------------------------------------------------------------------------
# PRAGMA LANGUAGE
[Full syntax reference →](https://pragma-project.github.io/Pragma-Language/syntax-reference.html)
-------------------------------------------------------------------------------------

Pragma is a systems language that transpiles to C. It has clean, readable syntax — English keywords, no braces, no semicolons — and gives you the same memory safety guarantees as Rust without fighting the compiler over every pointer.

### Why not Rust?

Rust is well-funded and has a strong safety model, but it's notorious for:
- A steep learning curve — the borrow checker fights you constantly
- Syntax that's dense and hard to read at a glance
- Being overkill when you don't need lifetime annotations on everything

Pragma gives you three levels to choose from:
- **Unsigned** — plain compiled C, no safety checks
- **MemResistant** — static analysis (ASan, TSan, UBSan, CBMC, custom bounds checker) run at build time; signed if they pass
- **MemProof** — everything in MemResistant + formal mathematical proof via Frama-C WP (same method Rust uses under the hood)

---

## What it looks like

**Hello World**
```pragma
function main()
  print "Hello, World!"
end function
```

**Variables, constants, control flow**
```pragma
constant int LIMIT = 5

function power(int base, int exp) returns int
  int result = 1
  for int i = 0 while i < exp do i++
    result *= base
  end for
  return result
end function

function main()
  for int i = 0 while i < LIMIT do i++
    print power(2, i)
  end for
end function
```

**Objects and methods**
```pragma
object Vec2
  double x
  double y

  function dot(Vec2 other) returns double
    return self.x * other.x + self.y * other.y
  end function
end object

function main()
  Vec2 v1 = new Vec2[3.0, 4.0]
  Vec2 v2 = new Vec2[1.0, 2.0]
  print v1.dot(v2)
end function
```

**Pointers**
```pragma
function main()
  int x = 42
  int <p> = address(x)     // p points to x
  deref(<p>) = 99          // write through pointer
  print x                  // prints 99
end function
```

Pointer depth is explicit and enforced: `int <p>` is one level, `int <<pp>>` is two, and mismatching levels is a compiler error.

**Lists and for-each**
```pragma
function main()
  list int[5] nums = [1, 2, 3, 4, 5]
  int total = 0
  for each n in nums
    total += n * n
  end for
  print total    // 55
end function
```

**Exceptions**
```pragma
function divide(int a, int b) returns int
  if b == 0
    error DivisionByZero "Cannot divide by zero"
  end if
  return a / b
end function

function main()
  try
    print divide(10, 2)
  catch(DivisionByZero e)
    print "caught: divide by zero"
  end catch
  end try
end function
```

Exception types are defined by use — no separate declaration needed. Implemented via `setjmp`/`longjmp`, no heap allocation, no C++ runtime.

**Operators**
```pragma
bool ok = (a > 0) and (b not 0)   // and / or / not / not (!=)
int bits = x delta y               // XOR
int flipped = bitflip x            // bitwise NOT
int shifted = x left 3             // left shift
```

---

## Memory safety verification

Pragma hashes your source with SHA-256. The verification pipeline runs every configured tool, hashes each tool's output, and bundles everything into a JSON attestation:

```json
{
  "tool_results": [
    { "tool": "cbmc",      "version": "5.95.1",     "passed": true, "output_hash": "a3f..." },
    { "tool": "asan+ubsan","version": "gcc 13.2.0", "passed": true, "output_hash": "b7c..." },
    { "tool": "tsan",      "version": "gcc 13.2.0", "passed": true, "output_hash": "d1e..." }
  ]
}
```

The attestation is pinned to IPFS via Pinata and registered on-chain via a Solidity smart contract on Ethereum. To verify any piece of code independently:

1. `sha256sum file.c` — hash the file yourself
2. Look up that hash in the on-chain registry
3. Fetch the attestation from IPFS using the stored CID
4. Optionally re-run CBMC and the sanitizers yourself — you'll get byte-for-byte identical results

No trust required.

---

## Running Pragma

```
python pragma.py file.run              # compile to binary
python pragma.py file.run --run        # compile and run immediately
python pragma.py file.run --emit-c     # also save the generated C
python pragma.py file.run --ast        # print AST (debug)
python xpile.py input.c                # transpile C → Pragma
python xpile.py input.c -o out.run     # transpile and write to file
```

---

## Included tools (as build flags)

- AOT sanitization — ASan, TSan, UBSan
- CBMC model checking
- Custom array out-of-bounds checker
- PGO + LTO optimization
- Frama-C WP formal verification (MemProof tier)
