# UniLogic Bytecode Format Specification

**Version:** 0.1
**Status:** Draft
**Date:** 2026-03-18

---

## 1. Design Decision: Stack-Based

The UL bytecode uses a **stack-based** architecture for v0.1. Each instruction pushes to or pops from an operand stack rather than naming registers. This eliminates register allocation from the compiler, produces smaller bytecode (no register operands in most instructions), and simplifies the VM implementation to under 500 lines for a conforming interpreter. The JVM and CPython both validate this approach at scale.

**Acknowledged tradeoff:** Research is clear that register-based VMs eliminate an average of 46.5% of executed VM instructions compared to stack-based equivalents, with bytecode only ~26% larger (Shi et al., "Virtual Machine Showdown," ACM VEE 2005). The stack-based choice is correct for v0.1 because compiler simplicity is the priority at this stage — register allocation is a significant implementation cost. The superinstruction mechanism (§7.1) and quickening (§5.3) recover a substantial portion of the instruction-count disadvantage without requiring a register allocator. A future major version may move to a register-based encoding if profiling warrants it.

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

### 4.1 Constants and Variables

| Opcode | Hex | Operands | Stack effect | Description |
|--------|-----|----------|-------------|-------------|
| `LOAD_CONST` | `0x01` | u16 index | → value | Push constant pool entry `index` onto stack |
| `LOAD_LOCAL` | `0x02` | u16 slot | → value | Push local variable `slot` onto stack |
| `STORE_LOCAL` | `0x03` | u16 slot | value → | Pop stack top into local variable `slot` |
| `LOAD_GLOBAL` | `0x04` | u16 index | → value | Push global variable `index` onto stack |
| `STORE_GLOBAL` | `0x05` | u16 index | value → | Pop stack top into global variable `index` |

Local variable slots are numbered 0..N-1 where slots 0..param_count-1 hold function parameters (populated by the caller before `CALL`).

### 4.2 Arithmetic and Logic

| Opcode | Hex | Operands | Stack effect | Description |
|--------|-----|----------|-------------|-------------|
| `ADD` | `0x10` | — | b, a → result | `a + b`. Int+int→int, float+float→float, int+float→float, string+string→concat |
| `SUB` | `0x11` | — | b, a → result | `a - b`. Numeric only |
| `MUL` | `0x12` | — | b, a → result | `a * b`. Numeric only |
| `DIV` | `0x13` | — | b, a → result | `a / b`. Int/int→truncated int, float involved→float. Division by zero = runtime error |
| `MOD` | `0x14` | — | b, a → result | `a % b`. Numeric only. Zero divisor = runtime error |
| `NEG` | `0x15` | — | a → result | `-a`. Numeric only |
| `NOT` | `0x16` | — | a → result | Logical not. Truthy→false, falsy→true |
| `AND` | `0x17` | — | b, a → result | Logical and (not short-circuit in bytecode; compiler emits jumps for short-circuit) |
| `OR` | `0x18` | — | b, a → result | Logical or |

### 4.3 Comparison

| Opcode | Hex | Operands | Stack effect | Description |
|--------|-----|----------|-------------|-------------|
| `CMP_EQ` | `0x20` | — | b, a → bool | `a == b` |
| `CMP_NE` | `0x21` | — | b, a → bool | `a != b` |
| `CMP_LT` | `0x22` | — | b, a → bool | `a < b` |
| `CMP_GT` | `0x23` | — | b, a → bool | `a > b` |
| `CMP_LE` | `0x24` | — | b, a → bool | `a <= b` |
| `CMP_GE` | `0x25` | — | b, a → bool | `a >= b` |

### 4.4 Control Flow

| Opcode | Hex | Operands | Stack effect | Description |
|--------|-----|----------|-------------|-------------|
| `JUMP` | `0x30` | i16 offset | — | Unconditional jump. PC += offset (signed, relative to instruction after operand) |
| `JUMP_IF_FALSE` | `0x31` | i16 offset | cond → | Pop top; if falsy, PC += offset |
| `JUMP_IF_TRUE` | `0x32` | i16 offset | cond → | Pop top; if truthy, PC += offset |

Jump offsets are **signed 16-bit**, relative to the byte immediately after the operand. This gives a range of ±32KB per jump. For larger functions, the compiler must use jump chains.

### 4.5 Functions

| Opcode | Hex | Operands | Stack effect | Description |
|--------|-----|----------|-------------|-------------|
| `CALL` | `0x40` | u16 func_index, u8 arg_count | arg_count values → return_value | Pop `arg_count` arguments (top = last arg), invoke function `func_index`, push return value |
| `RETURN` | `0x41` | — | value → | Pop return value, return to caller. If function is void, push `empty` before executing |
| `RETURN_NONE` | `0x42` | — | — | Return `empty` (void return shorthand) |

The VM maintains a **call stack** of frames. Each frame stores: return address (function index + PC), local variable array, and operand stack base pointer. On `CALL`, a new frame is pushed. On `RETURN`, the frame is popped and the return value is pushed onto the caller's operand stack.

### 4.6 Built-ins

| Opcode | Hex | Operands | Stack effect | Description |
|--------|-----|----------|-------------|-------------|
| `PRINT` | `0x50` | — | value → | Pop and print to stdout. Bool prints as `0`/`1`, float as `%f`, empty as `empty` |
| `POP` | `0x51` | — | value → | Discard stack top |
| `DUP` | `0x52` | — | a → a, a | Duplicate stack top |

### 4.7 Array Operations

| Opcode | Hex | Operands | Stack effect | Description |
|--------|-----|----------|-------------|-------------|
| `NEW_ARRAY` | `0x60` | u16 count | count values → array | Pop `count` values, create array (first popped = last element) |
| `INDEX_GET` | `0x61` | — | index, array → value | Pop index and array, push `array[index]`. Out of bounds = runtime error |
| `INDEX_SET` | `0x62` | — | value, index, array → | Set `array[index] = value` |
| `LENGTH` | `0x63` | — | array_or_string → int | Push length |

### 4.8 Type Operations

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

### 5.2 Dispatch Method

The fetch-decode-execute loop described above implies a switch statement over opcodes. This is the simplest implementation but not the fastest. The recommended implementation approach for production VMs is **computed goto** (a GCC/Clang extension via `&&label` and `goto *dispatch_table[opcode]`). This eliminates the branch prediction overhead of a central switch by jumping directly from the end of one handler to the start of the next. Benchmarks consistently show 15–25% speedup over switch dispatch for interpreter-heavy workloads.

A conforming VM may use any dispatch method (switch, computed goto, threaded code, JIT compilation). The bytecode format does not depend on the dispatch strategy.

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
01 00 00   ; LOAD_CONST 0
03 00 00   ; STORE_LOCAL 0
01 00 01   ; LOAD_CONST 1
03 00 01   ; STORE_LOCAL 1
02 00 00   ; LOAD_LOCAL 0
02 00 01   ; LOAD_LOCAL 1
10         ; ADD
50         ; PRINT
01 00 02   ; LOAD_CONST 2
41         ; RETURN
```

---

## 7. Reserved Opcodes and Superinstructions

### 7.1 Superinstructions (`0xE0–0xEF`)

A superinstruction combines a common multi-opcode sequence into a single opcode, eliminating intermediate stack pushes/pops and dispatch overhead. Research shows superinstructions can reduce executed VM instructions by over 46% for typical programs (Yunhe Shi et al., "Virtual Machine Showdown: Stack vs. Register Machine," ACM VEE 2005).

The compiler emits superinstructions as an optimization pass over the bytecode. The VM must support both the expanded and super forms — if a VM does not recognize a superinstruction, it is an error (not a fallback).

**Priority superinstructions for v0.1:**

| Opcode | Hex | Equivalent sequence | Description |
|--------|-----|-------------------|-------------|
| `ADD_LOCALS` | `0xE0` | `LOAD_LOCAL a` + `LOAD_LOCAL b` + `ADD` | Add two locals, push result. Operands: u16 slot_a, u16 slot_b |
| `STORE_CONST` | `0xE1` | `LOAD_CONST i` + `STORE_LOCAL s` | Load constant directly into local. Operands: u16 const_index, u16 slot |
| `LOAD_LOCAL_LOAD_CONST` | `0xE2` | `LOAD_LOCAL s` + `LOAD_CONST i` | Push local then constant (common before compare/add). Operands: u16 slot, u16 const_index |
| `CMP_JUMP` | `0xE3` | `CMP_LT` + `JUMP_IF_FALSE` | Compare and branch in one dispatch. Operands: i16 offset |
| `LOAD_PRINT` | `0xE4` | `LOAD_LOCAL s` + `PRINT` | Load and print. Operands: u16 slot |
| `INC_LOCAL` | `0xE5` | `LOAD_LOCAL s` + `LOAD_CONST 1` + `ADD` + `STORE_LOCAL s` | Increment local by 1. Operands: u16 slot |

The range `0xE6–0xEF` is reserved for additional superinstructions identified by profiling real programs.

### 7.2 Future Reserved (`0xF0–0xFF`)

The range `0xF0–0xFF` is reserved for future use: closures, coroutines, match dispatch, DR enforcement, and memory operations. Encountering a reserved opcode halts execution with an "unknown opcode" error.

### 7.3 Quickened Opcodes (`0xC0–0xDF`)

Reserved for VM-internal quickened variants (see §5.3). Never emitted by the compiler. Never present in `.ulb` files on disk.

---

## 8. Versioning

The major version increments on breaking changes to the instruction encoding or file format. The minor version increments on backward-compatible additions (new opcodes in unused ranges). A VM must reject files with a major version it does not support. A VM should accept files with a minor version greater than its own, ignoring unknown opcodes only if they appear in unreachable code paths.
