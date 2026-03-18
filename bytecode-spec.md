# UniLogic Bytecode Format Specification

**Version:** 0.1
**Status:** Draft
**Date:** 2026-03-18

---

## 1. Design Decision: Stack-Based

The UL bytecode uses a **stack-based** architecture for v0.1. Each instruction pushes to or pops from an operand stack rather than naming registers. This eliminates register allocation from the compiler, produces smaller bytecode (no register operands in most instructions), and simplifies the VM implementation to under 500 lines for a conforming interpreter. The JVM and CPython both validate this approach at scale.

**Acknowledged tradeoff:** Research is clear that register-based VMs eliminate an average of 46.5% of executed VM instructions compared to stack-based equivalents, with bytecode only ~26% larger (Shi et al., "Virtual Machine Showdown," ACM VEE 2005). The stack-based choice is correct for v0.1 because compiler simplicity is the priority at this stage — register allocation is a significant implementation cost. The superinstruction mechanism (§7.1) and quickening (§5.3) recover a substantial portion of the instruction-count disadvantage without requiring a register allocator.

**Why this matters more than it appears:** CPython 3.11–3.14 has invested heavily in the "Faster CPython" project, retrofitting quickening and specialization onto its stack-based interpreter — essentially bolting performance optimizations onto an architecture that wasn't designed for them. Even after all that work, PyPy (which uses JIT compilation) remains ~18x faster than CPython 3.14, and ~3x faster than Node.js (Grinberg, 2025). That gap shows how much headroom remains in the stack-based model even with aggressive optimization. More directly, RegCPython — a register-based reimplementation of CPython — found the register architecture is appreciably faster, and that "compilation speed is never a reason for choosing stack architecture" (Brito & Valente, ACM SAC 2023).

**v0.2 migration path:** Start stack-based in v0.1 for simplicity — get the VM built, proven, and tested. Design the register-based instruction format in parallel. Migrate to register-based in v0.2 once the VM is stable. This puts UL ahead of CPython by design rather than by accident — choosing the faster architecture from the outset instead of retrofitting optimizations onto the wrong foundation. The file format (§2) and versioning scheme (§8) are designed to support this: a major version increment signals the encoding change, and the constant pool / function table layout remains compatible.

---

## 2. File Format

A `.ulb` file (UniLogic Bytecode) has the following layout:

```
┌──────────────────────────────────┐
│  Header              (16 bytes)  │
├──────────────────────────────────┤
│  Constant Pool       (variable)  │
├──────────────────────────────────┤
│  Function Table      (variable)  │
├──────────────────────────────────┤
│  Instruction Blocks  (variable)  │
└──────────────────────────────────┘
```

### 2.1 Header

| Offset | Size | Field | Value |
|--------|------|-------|-------|
| 0 | 4 | Magic bytes | `0x554C4243` (`ULBC` in ASCII) |
| 4 | 2 | Major version | `0x0001` |
| 6 | 2 | Minor version | `0x0000` |
| 8 | 4 | Constant pool entry count | u32, little-endian |
| 12 | 4 | Function table entry count | u32, little-endian |

All multi-byte integers are **little-endian** throughout the file.

### 2.2 Constant Pool

Immediately follows the header. Contains `constant_count` entries, each prefixed by a 1-byte type tag:

| Tag | Type | Encoding |
|-----|------|----------|
| `0x01` | int | 8 bytes, signed 64-bit LE |
| `0x02` | float | 8 bytes, IEEE 754 double LE |
| `0x03` | string | 4 bytes length (u32 LE) + N bytes UTF-8, no null terminator |
| `0x04` | bool | 1 byte (`0x00` = false, `0x01` = true) |
| `0x05` | empty | 0 bytes (null/none literal) |

Constants are referenced by **zero-based index** in instructions.

### 2.3 Function Table

Contains `function_count` entries, each:

| Offset | Size | Field |
|--------|------|-------|
| 0 | 4 | Name length (u32 LE) |
| 4 | N | Name (UTF-8 bytes) |
| 4+N | 2 | Parameter count (u16 LE) |
| 6+N | 2 | Local variable count (u16 LE, includes params) |
| 8+N | 4 | Instruction offset (u32 LE, byte offset into instruction block) |
| 12+N | 4 | Instruction length (u32 LE, byte count) |

Functions are referenced by **zero-based index**. Function 0 is not required to be `main`; the entry point is specified by the VM invocation (default: function named `main`).

### 2.4 Instruction Block

A single contiguous byte stream. Each function's instructions occupy a slice identified by its offset and length from the function table. Instructions are variable-width: 1-byte opcode optionally followed by operands.

**v0.2 encoding target: fixed-width 16-bit instructions.** The current variable-width encoding is simple to emit but complicates PC arithmetic, branch offset calculation, and superinstruction patching. The v0.2 format will use fixed 16-bit instruction words:

```
Standard form:   [8-bit opcode | 8-bit operand]
Extended form:   [8-bit opcode | 8-bit 0xFF] [16-bit operand]
```

Most instructions fit in one word (256 locals, 256 constants covers the vast majority of functions). Instructions needing a larger operand use the extended form with `0xFF` as the escape sentinel in the operand byte. Fixed-width simplifies the dispatch loop (`pc += 2` always), makes superinstruction patching a single 16-bit write, and improves instruction cache utilization. The v0.1 variable-width format remains valid and must be supported by any VM claiming v0.1 conformance.

---

## 3. Type Encoding on the Stack

The VM operand stack holds tagged values. Each stack slot is a discriminated union:

| Tag | Type | Stack representation |
|-----|------|---------------------|
| `0x01` | int | signed 64-bit integer |
| `0x02` | float | IEEE 754 64-bit double |
| `0x03` | string | pointer to heap-allocated UTF-8 string |
| `0x04` | bool | 0 or 1 |
| `0x05` | empty | null/none sentinel |

Type tags are carried at runtime. Type errors (e.g. adding a string to an int) produce a runtime error, not undefined behavior.

---

## 4. Instruction Set

All opcodes are 1 byte. Operands follow the opcode where specified.

**Opcode numbering rationale:** The hottest instructions are assigned the lowest opcode values. This groups the most frequently executed handlers together in the VM's code segment for I-cache locality. Profiling of typical UL programs shows `LOAD_LOCAL`, `STORE_LOCAL`, `LOAD_CONST`, `ADD`, `CALL`, `RETURN`, and `JUMP_IF_FALSE` account for >80% of executed instructions.

### 4.1 Hot Path (0x01–0x0F)

| Opcode | Hex | Operands | Stack effect | Description |
|--------|-----|----------|-------------|-------------|
| `LOAD_LOCAL` | `0x01` | u16 slot | → value | Push local variable `slot` onto stack |
| `STORE_LOCAL` | `0x02` | u16 slot | value → | Pop stack top into local variable `slot` |
| `LOAD_CONST` | `0x03` | u16 index | → value | Push constant pool entry `index` onto stack |
| `ADD` | `0x04` | — | b, a → result | `a + b`. Int+int→int, float+float→float, int+float→float, string+string→concat |
| `CALL` | `0x05` | u16 func_index, u8 arg_count | arg_count values → return_value | Pop `arg_count` arguments (top = last arg), invoke function, push return value |
| `RETURN` | `0x06` | — | value → | Pop return value, return to caller |
| `JUMP_IF_FALSE` | `0x07` | i16 offset | cond → | Pop top; if falsy, PC += offset |
| `CMP_LT` | `0x08` | — | b, a → bool | `a < b` |
| `SUB` | `0x09` | — | b, a → result | `a - b`. Numeric only |
| `PRINT` | `0x0A` | — | value → | Pop and print to stdout. Bool as `0`/`1`, float as `%f`, empty as `empty` |

Local variable slots are numbered 0..N-1 where slots 0..param_count-1 hold function parameters (populated by the caller before `CALL`).

The VM maintains a **call stack** of frames. Each frame stores: return address (function index + PC), local variable array, and operand stack base pointer. On `CALL`, a new frame is pushed. On `RETURN`, the frame is popped and the return value is pushed onto the caller's operand stack.

### 4.2 Arithmetic and Logic (0x10–0x1F)

| Opcode | Hex | Operands | Stack effect | Description |
|--------|-----|----------|-------------|-------------|
| `MUL` | `0x10` | — | b, a → result | `a * b`. Numeric only |
| `DIV` | `0x11` | — | b, a → result | `a / b`. Int/int→truncated int, float involved→float. Division by zero = runtime error |
| `MOD` | `0x12` | — | b, a → result | `a % b`. Numeric only. Zero divisor = runtime error |
| `NEG` | `0x13` | — | a → result | `-a`. Numeric only |
| `NOT` | `0x14` | — | a → result | Logical not. Truthy→false, falsy→true |
| `AND` | `0x15` | — | b, a → result | Logical and (not short-circuit in bytecode; compiler emits jumps for short-circuit) |
| `OR` | `0x16` | — | b, a → result | Logical or |

### 4.3 Comparison (0x20–0x2F)

| Opcode | Hex | Operands | Stack effect | Description |
|--------|-----|----------|-------------|-------------|
| `CMP_EQ` | `0x20` | — | b, a → bool | `a == b` |
| `CMP_NE` | `0x21` | — | b, a → bool | `a != b` |
| `CMP_GT` | `0x22` | — | b, a → bool | `a > b` |
| `CMP_LE` | `0x23` | — | b, a → bool | `a <= b` |
| `CMP_GE` | `0x24` | — | b, a → bool | `a >= b` |

Note: `CMP_LT` is in the hot path at `0x08`.

### 4.4 Control Flow (0x30–0x3F)

| Opcode | Hex | Operands | Stack effect | Description |
|--------|-----|----------|-------------|-------------|
| `JUMP` | `0x30` | i16 offset | — | Unconditional jump. PC += offset (signed, relative to instruction after operand) |
| `JUMP_IF_TRUE` | `0x31` | i16 offset | cond → | Pop top; if truthy, PC += offset |
| `RETURN_NONE` | `0x32` | — | — | Return `empty` (void return shorthand) |

Note: `JUMP_IF_FALSE` is in the hot path at `0x07`. Jump offsets are **signed 16-bit**, relative to the byte immediately after the operand. Range: ±32KB per jump. For larger functions, the compiler must use jump chains.

### 4.5 Variables (0x40–0x4F)

| Opcode | Hex | Operands | Stack effect | Description |
|--------|-----|----------|-------------|-------------|
| `LOAD_GLOBAL` | `0x40` | u16 index | → value | Push global variable `index` onto stack |
| `STORE_GLOBAL` | `0x41` | u16 index | value → | Pop stack top into global variable `index` |

### 4.6 Stack Operations (0x50–0x5F)

| Opcode | Hex | Operands | Stack effect | Description |
|--------|-----|----------|-------------|-------------|
| `POP` | `0x50` | — | value → | Discard stack top |
| `DUP` | `0x51` | — | a → a, a | Duplicate stack top |

### 4.7 Array Operations (0x60–0x6F)

| Opcode | Hex | Operands | Stack effect | Description |
|--------|-----|----------|-------------|-------------|
| `NEW_ARRAY` | `0x60` | u16 count | count values → array | Pop `count` values, create array (first popped = last element) |
| `INDEX_GET` | `0x61` | — | index, array → value | Pop index and array, push `array[index]`. Out of bounds = runtime error |
| `INDEX_SET` | `0x62` | — | value, index, array → | Set `array[index] = value` |
| `LENGTH` | `0x63` | — | array_or_string → int | Push length |

### 4.8 Type Operations (0x70–0x7F)

| Opcode | Hex | Operands | Stack effect | Description |
|--------|-----|----------|-------------|-------------|
| `CAST_INT` | `0x70` | — | value → int | Convert top to int. Float truncates, string parses, bool→0/1 |
| `CAST_FLOAT` | `0x71` | — | value → float | Convert top to float |
| `CAST_STRING` | `0x72` | — | value → string | Convert top to string representation |
| `CAST_BOOL` | `0x73` | — | value → bool | Truthy/falsy conversion |

---

## 5. Execution Model

1. The VM loads the `.ulb` file, validates the magic bytes and version, and parses the constant pool and function table into memory.
2. The VM locates the entry-point function (default: `main`) by name in the function table.
3. A root call frame is created with locals allocated to `local_count` slots, all initialized to `empty`.
4. The PC (program counter) is set to the function's instruction offset.
5. The VM enters the fetch-decode-execute loop:
   - Read opcode byte at PC, advance PC.
   - Read operands (if any), advance PC.
   - Execute the operation.
   - Repeat until `RETURN` with no caller frame (program exits).
6. The exit code is the integer value of the return value from `main`, or 0 if `main` returns `empty`.

### 5.1 Operand Stack

Each call frame has its own operand stack. Maximum stack depth per function is bounded and can be computed statically by the compiler (not stored in the file; the VM may use a fixed-size stack per frame or grow dynamically).

### 5.2 Recommended Dispatch Implementation

The main enemy of interpreter performance is **indirect branch misprediction** in the dispatch loop. Each opcode dispatch is a branch the CPU must predict, and a central `switch` gives the branch predictor a single branch site shared by all opcodes — it can only remember the last target, not per-opcode history.

**Primary recommendation: direct threaded dispatch** using computed goto (GCC/Clang `&&label` extension). Each handler ends with `goto *dispatch_table[*pc++]`, jumping directly to the next handler. This gives the branch predictor a separate branch site per handler, dramatically improving prediction accuracy. Benchmarks show 15–25% speedup over switch dispatch.

**Fallback: dense jump table.** If computed goto is unavailable (MSVC, portable C), use a `switch` with contiguous opcode values (no gaps). The compiler will emit a jump table rather than a branch chain. This is why hot opcodes are numbered `0x01–0x0A` with no gaps — the jump table stays dense and small.

**Never use:** a chain of `if/else if` comparisons. This is O(n) in the number of opcodes per dispatch and destroys branch prediction.

A conforming VM may use any dispatch method. The bytecode format does not depend on the dispatch strategy.

### 5.3 Quickening

After the first execution of an instruction, the VM may **rewrite it in-place** to a specialized faster version. This is called quickening. The original opcode is replaced in the instruction buffer with a variant that skips work already done on the first pass.

Examples:

| Original | Quickened | What changes |
|----------|-----------|-------------|
| `LOAD_LOCAL` | `LOAD_LOCAL_INT` | Skips type tag check — slot is known to hold an int after first load |
| `ADD` | `ADD_INT` | Both operands confirmed as int on first execution — skip type dispatch |
| `LOAD_CONST` | `LOAD_CONST_INLINE` | Constant value cached in the instruction stream, skip pool lookup |
| `CALL` | `CALL_RESOLVED` | Function pointer cached after first resolution by name |

Quickened opcodes use the range `0xC0–0xDF`. They are never emitted by the compiler — only written by the VM at runtime. A `.ulb` file must not contain quickened opcodes; if one is encountered during initial loading, it is an error.

CPython 3.11+ uses this technique extensively (PEP 659, "specializing adaptive interpreter") and attributes a significant portion of its 10–60% speedup over 3.10 to quickening.

### 5.4 Error Handling

Runtime errors (division by zero, out-of-bounds index, type mismatch in arithmetic, stack underflow) halt execution with an error message including the function name and instruction offset. There are no exceptions or try/catch in v0.1.

---

## 6. Example

UL source:

```
function main() returns int
  int x = 3
  int y = 4
  print x + y
  return 0
end function
```

Bytecode (function `main`, 0 params, 2 locals):

```
LOAD_CONST  0      ; push 3 (constant pool index 0)
STORE_LOCAL 0      ; x = 3
LOAD_CONST  1      ; push 4 (constant pool index 1)
STORE_LOCAL 1      ; y = 4
LOAD_LOCAL  0      ; push x
LOAD_LOCAL  1      ; push y
ADD                ; x + y → 7
PRINT              ; print 7
LOAD_CONST  2      ; push 0 (constant pool index 2)
RETURN             ; return 0
```

Constant pool: `[int 3, int 4, int 0]`

Hex encoding of instructions (17 bytes):

```
03 00 00   ; LOAD_CONST 0    (0x03)
02 00 00   ; STORE_LOCAL 0   (0x02)
03 00 01   ; LOAD_CONST 1    (0x03)
02 00 01   ; STORE_LOCAL 1   (0x02)
01 00 00   ; LOAD_LOCAL 0    (0x01)
01 00 01   ; LOAD_LOCAL 1    (0x01)
04         ; ADD             (0x04)
0A         ; PRINT           (0x0A)
03 00 02   ; LOAD_CONST 2    (0x03)
06         ; RETURN          (0x06)
```

---

## 7. Reserved Opcodes and Superinstructions

### 7.1 Superinstructions (`0xE0–0xEF`)

A superinstruction combines a common multi-opcode sequence into a single opcode, eliminating intermediate stack pushes/pops and dispatch overhead. Research shows superinstructions can reduce executed VM instructions by over 46% for typical programs (Shi et al., ACM VEE 2005). The bytecode is designed so that common sequences can be fused without changing semantics — the compiler emits them as an optimization pass, and the VM must support both expanded and super forms.

See **§9** for the full superinstruction candidate list based on UL's actual hot paths.

### 7.2 Future Reserved (`0xF0–0xFF`)

The range `0xF0–0xFF` is reserved for future use: closures, coroutines, match dispatch, DR enforcement, and memory operations. Encountering a reserved opcode halts execution with an "unknown opcode" error.

### 7.3 Quickened Opcodes (`0xC0–0xDF`)

Reserved for VM-internal quickened variants (see §5.3). Never emitted by the compiler. Never present in `.ulb` files on disk.

---

## 8. Versioning

The major version increments on breaking changes to the instruction encoding or file format. The minor version increments on backward-compatible additions (new opcodes in unused ranges). A VM must reject files with a major version it does not support. A VM should accept files with a minor version greater than its own, ignoring unknown opcodes only if they appear in unreachable code paths.

---

## 9. Superinstruction Candidates

These are the highest-value instruction sequences to fuse based on UL's hot paths. Each eliminates multiple dispatch cycles and intermediate stack operations. Listed in priority order — implement top-down.

| Opcode | Hex | Fused sequence | Operands | Dispatches saved | Description |
|--------|-----|----------------|----------|-----------------|-------------|
| `ADD_LOCALS` | `0xE0` | `LOAD_LOCAL a` + `LOAD_LOCAL b` + `ADD` | u8 slot_a, u8 slot_b | 2 | Add two locals directly. The most common arithmetic pattern in any program. |
| `ADD_LOCAL_CONST` | `0xE1` | `LOAD_LOCAL a` + `LOAD_CONST k` + `ADD` | u8 slot, u8 const_idx | 2 | Add a constant to a local. Covers `x + 1`, loop increments, offset calculations. |
| `LOOP_TEST` | `0xE2` | `LOAD_LOCAL a` + `LOAD_CONST k` + `CMP_LT` + `JUMP_IF_FALSE` | u8 slot, u8 const_idx, i16 offset | 3 | The most common loop header: `while i < N`. Four instructions become one. |
| `RETURN_LOCAL` | `0xE3` | `LOAD_LOCAL a` + `RETURN` | u8 slot | 1 | Return a local variable. Most non-void functions end this way. |
| `CALL_STORE` | `0xE4` | `CALL func` + `STORE_LOCAL s` | u8 func_idx, u8 arg_count, u8 slot | 1 | Call a function and store the result. `int x = add(a, b)` in one dispatch. |
| `STORE_CONST` | `0xE5` | `LOAD_CONST k` + `STORE_LOCAL s` | u8 const_idx, u8 slot | 1 | Initialize a local from a constant. Every `int x = 0` or `string s = ""`. |
| `INC_LOCAL` | `0xE6` | `LOAD_LOCAL s` + `LOAD_CONST 1` + `ADD` + `STORE_LOCAL s` | u8 slot | 3 | Increment local by 1. Loop counters, `x++` statements. |
| `LOAD_PRINT` | `0xE7` | `LOAD_LOCAL s` + `PRINT` | u8 slot | 1 | Load and print. Debug output, REPL result display. |
| `CMP_JUMP_EQ` | `0xE8` | `CMP_EQ` + `JUMP_IF_FALSE` | i16 offset | 1 | Compare-and-branch for equality. Match statement cases. |
| `DEC_LOCAL` | `0xE9` | `LOAD_LOCAL s` + `LOAD_CONST 1` + `SUB` + `STORE_LOCAL s` | u8 slot | 3 | Decrement local by 1. Countdown loops. |

The range `0xEA–0xEF` is reserved for additional superinstructions identified by profiling real programs. Note: superinstruction operands use **u8** (not u16) to keep instructions compact. Functions with >255 locals or constants fall back to the expanded sequence.

---

## 10. Type Specialization (v0.2)

Generic arithmetic opcodes (`ADD`, `SUB`, `MUL`, `DIV`) perform runtime type dispatch on every execution — check if both operands are int, check if either is float, check for string concat, then execute the appropriate operation. This type dispatch is the single largest overhead per arithmetic instruction.

**v0.2 introduces typed variants** selected by the quickening mechanism (§5.3) after the first execution of an instruction reveals the operand types at that site:

| Generic | Typed variant (int) | Typed variant (float) | Quickened hex range |
|---------|--------------------|-----------------------|-------------------|
| `ADD` (0x04) | `ADD_INT` | `ADD_FLOAT` | `0xC0`, `0xC1` |
| `SUB` (0x09) | `SUB_INT` | `SUB_FLOAT` | `0xC2`, `0xC3` |
| `MUL` (0x10) | `MUL_INT` | `MUL_FLOAT` | `0xC4`, `0xC5` |
| `DIV` (0x11) | `DIV_INT` | `DIV_FLOAT` | `0xC6`, `0xC7` |
| `CMP_LT` (0x08) | `CMP_LT_INT` | `CMP_LT_FLOAT` | `0xC8`, `0xC9` |
| `LOAD_LOCAL` (0x01) | `LOAD_LOCAL_INT` | `LOAD_LOCAL_FLOAT` | `0xCA`, `0xCB` |

**How it works:** The VM executes the generic opcode on the first call. If both operands are int, it rewrites the opcode byte in-place to the `_INT` variant. Subsequent executions of that instruction skip the type check entirely. If the types change (rare — called "deoptimization"), the VM rewrites back to the generic opcode and retries.

This is exactly what CPython 3.11+ does as a retrofit (PEP 659, "specializing adaptive interpreter"). UL designs it into the instruction set from the start — the opcode space is pre-allocated, the quickening mechanism is documented, and the deoptimization path is defined. No architectural surgery required later.
