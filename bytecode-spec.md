# UniLogic Bytecode Format Specification

**Version:** 1.0
**Status:** Draft
**Date:** 2026-03-18

---

## 1. Design Decision: Register-Based

The UL bytecode uses a **register-based** architecture. Each instruction names its source and destination registers explicitly rather than pushing to and popping from an implicit stack. UL is a new language with no legacy bytecode to maintain — this is the right call to make now rather than retrofitting later.

**Research basis:** Register-based VMs execute 2–3x fewer instructions than stack VMs for equivalent programs, with bytecode only 25–30% larger (Shi et al., "Virtual Machine Showdown," ACM VEE 2005). The instruction count reduction compounds when adding JIT compilation later — fewer bytecode instructions means fewer IR nodes to lower, faster compilation, and better native code. RegCPython — a register-based reimplementation of CPython — confirmed the register architecture is appreciably faster and that "compilation speed is never a reason for choosing stack architecture" (Brito & Valente, ACM SAC 2023).

**Why not stack-based:** CPython 3.11–3.14 invested heavily in the "Faster CPython" project, retrofitting quickening and specialization onto its stack-based interpreter. Even after that work, PyPy remains ~18x faster than CPython 3.14, and ~3x faster than Node.js (Grinberg, 2025). That gap demonstrates the ceiling of the stack-based model even with aggressive optimization. UL avoids this ceiling by starting register-based.

**Compiler cost:** Register allocation adds complexity to the compiler. UL uses a simple linear-scan allocator — each local variable and temporary maps to a register slot at compile time. Functions with more than 256 live values at any point (the register limit per frame) spill to a frame-local memory area. In practice, this limit is never reached in normal code.

---

## 2. File Format

A `.ulb` file (UniLogic Bytecode) has the following layout:

```
┌──────────────────────────────────┐
│  Header              (20 bytes)  │
├──────────────────────────────────┤
│  Constant Pool       (variable)  │
├──────────────────────────────────┤
│  Function Table      (variable)  │
├──────────────────────────────────┤
│  Block Metadata      (variable)  │
├──────────────────────────────────┤
│  Instruction Blocks  (variable)  │
└──────────────────────────────────┘
```

### 2.1 Header

| Offset | Size | Field | Value |
|--------|------|-------|-------|
| 0 | 4 | Magic bytes | `0x554C4243` (`ULBC` in ASCII) |
| 4 | 2 | Major version | `0x0100` (1.0) |
| 6 | 2 | Minor version | `0x0000` |
| 8 | 4 | Constant pool entry count | u32 LE |
| 12 | 4 | Function table entry count | u32 LE |
| 16 | 4 | Block metadata entry count | u32 LE |

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
| 4+N | 1 | Parameter count (u8) |
| 5+N | 1 | Register count (u8, total registers needed including params) |
| 6+N | 4 | Instruction offset (u32 LE, byte offset into instruction block) |
| 10+N | 4 | Instruction count (u32 LE, number of 32-bit instructions) |
| 14+N | 4 | First block metadata index (u32 LE) |
| 18+N | 2 | Block count (u16 LE) |

Functions are referenced by **zero-based index**. The entry point is resolved by name (default: `main`). Register slots 0..param_count-1 hold function parameters on entry.

### 2.4 Instruction Encoding

All instructions are **fixed-width 32 bits** (4 bytes). This simplifies PC arithmetic (`pc += 4` always), makes in-place patching a single aligned write, and improves I-cache utilization.

```
Standard 3-register form:
┌────────┬────────┬────────┬────────┐
│ opcode │  rA    │  rB    │  rC    │
│ 8 bits │ 8 bits │ 8 bits │ 8 bits │
└────────┴────────┴────────┴────────┘

2-register + immediate form:
┌────────┬────────┬─────────────────┐
│ opcode │  rA    │    imm16        │
│ 8 bits │ 8 bits │   16 bits LE    │
└────────┴────────┴─────────────────┘

1-register + wide immediate form:
┌────────┬────────────────────────────┐
│ opcode │         imm24              │
│ 8 bits │        24 bits LE          │
└────────┴────────────────────────────┘
```

The opcode determines which form applies. 256 registers per frame (r0–r255) covers any real function. The compiler assigns registers via linear-scan allocation.

### 2.5 Block Metadata Table

Contains `block_count` entries (one per basic block across all functions). Each entry:

| Offset | Size | Field |
|--------|------|-------|
| 0 | 4 | Start instruction index (u32 LE, within owning function) |
| 4 | 4 | End instruction index (u32 LE, exclusive) |
| 8 | 1 | Register pressure at entry (u8, highest live register) |
| 9 | 1 | Successor count (u8) |
| 10 | 2 | Reserved / padding (u16, zero) |
| 12 | 4 | Hotness counter slot (u32 LE, initialized to 0) |

The hotness counter is incremented by the VM each time the block is entered. This enables cheap profiling for JIT tiering — when a block's counter exceeds a threshold, the VM can trigger compilation of the owning function. The metadata table is writable at runtime (mapped read-write by the VM, not shared across processes).

Successor blocks are identified implicitly from the terminator instruction of each block (jump targets, fall-through). The VM does not need to recompute control flow on each execution — block boundaries are pre-identified by the compiler.

---

## 3. Type Encoding in Registers

Each register holds a tagged value. The tag is stored alongside the value in a discriminated union:

| Tag | Type | Register representation |
|-----|------|----------------------|
| `0x01` | int | signed 64-bit integer |
| `0x02` | float | IEEE 754 64-bit double |
| `0x03` | string | pointer to heap-allocated UTF-8 string |
| `0x04` | bool | 0 or 1 |
| `0x05` | empty | null/none sentinel |

Type tags are carried at runtime for Tier 0 instructions. Tier 1 instructions with type feedback slots may bypass the tag check after specialization (see §7).

---

## 4. Instruction Set

All opcodes are 8 bits. Instructions are 32 bits wide. Opcode numbering places the hottest instructions in the lowest range for I-cache locality and dense jump-table dispatch.

### 4.1 Hot Path — Tier 0 (0x01–0x0F)

| Opcode | Hex | Form | Semantics |
|--------|-----|------|-----------|
| `MOV` | `0x01` | `rA, rB, _` | `rA = rB` |
| `LOAD_CONST` | `0x02` | `rA, imm16` | `rA = constant_pool[imm16]` |
| `ADD` | `0x03` | `rA, rB, rC` | `rA = rB + rC` |
| `SUB` | `0x04` | `rA, rB, rC` | `rA = rB - rC` |
| `MUL` | `0x05` | `rA, rB, rC` | `rA = rB * rC` |
| `DIV` | `0x06` | `rA, rB, rC` | `rA = rB / rC` (int truncates, zero = error) |
| `CMP_LT` | `0x07` | `rA, rB, rC` | `rA = (rB < rC) ? true : false` |
| `JUMP_IF_FALSE` | `0x08` | `rA, imm16` | `if !rA: pc += sign_extend(imm16) * 4` |
| `CALL` | `0x09` | `rA, rB, rC` | Call function `rB` with `rC` args starting at `rA`. Result in `rA`. |
| `RETURN` | `0x0A` | `rA, _, _` | Return value in `rA` to caller |
| `PRINT` | `0x0B` | `rA, _, _` | Print `rA` to stdout |

### 4.2 Arithmetic and Logic — Tier 0 (0x10–0x1F)

| Opcode | Hex | Form | Semantics |
|--------|-----|------|-----------|
| `MOD` | `0x10` | `rA, rB, rC` | `rA = rB % rC` |
| `NEG` | `0x11` | `rA, rB, _` | `rA = -rB` |
| `NOT` | `0x12` | `rA, rB, _` | `rA = !rB` (logical) |
| `AND` | `0x13` | `rA, rB, rC` | `rA = rB && rC` |
| `OR` | `0x14` | `rA, rB, rC` | `rA = rB \|\| rC` |
| `ADD_IMM` | `0x15` | `rA, rB, imm8` | `rA = rB + imm8` (unsigned 8-bit immediate) |
| `SUB_IMM` | `0x16` | `rA, rB, imm8` | `rA = rB - imm8` |

### 4.3 Comparison — Tier 0 (0x20–0x2F)

| Opcode | Hex | Form | Semantics |
|--------|-----|------|-----------|
| `CMP_EQ` | `0x20` | `rA, rB, rC` | `rA = (rB == rC)` |
| `CMP_NE` | `0x21` | `rA, rB, rC` | `rA = (rB != rC)` |
| `CMP_GT` | `0x22` | `rA, rB, rC` | `rA = (rB > rC)` |
| `CMP_LE` | `0x23` | `rA, rB, rC` | `rA = (rB <= rC)` |
| `CMP_GE` | `0x24` | `rA, rB, rC` | `rA = (rB >= rC)` |

Note: `CMP_LT` is in the hot path at `0x07`.

### 4.4 Control Flow — Tier 0 (0x30–0x3F)

| Opcode | Hex | Form | Semantics |
|--------|-----|------|-----------|
| `JUMP` | `0x30` | `imm24` | `pc += sign_extend(imm24) * 4` |
| `JUMP_IF_TRUE` | `0x31` | `rA, imm16` | `if rA: pc += sign_extend(imm16) * 4` |
| `RETURN_NONE` | `0x32` | `_, _, _` | Return `empty` |

Note: `JUMP_IF_FALSE` is in the hot path at `0x08`. Jump offsets are in **instruction units** (multiply by 4 for byte offset), signed. Range: ±8M instructions for `JUMP` (imm24), ±32K instructions for conditional jumps (imm16).

### 4.5 Globals — Tier 0 (0x40–0x4F)

| Opcode | Hex | Form | Semantics |
|--------|-----|------|-----------|
| `LOAD_GLOBAL` | `0x40` | `rA, imm16` | `rA = globals[imm16]` |
| `STORE_GLOBAL` | `0x41` | `rA, imm16` | `globals[imm16] = rA` |

### 4.6 Arrays — Tier 0 (0x60–0x6F)

| Opcode | Hex | Form | Semantics |
|--------|-----|------|-----------|
| `NEW_ARRAY` | `0x60` | `rA, rB, rC` | Create array of `rC` elements starting at register `rB`, store in `rA` |
| `INDEX_GET` | `0x61` | `rA, rB, rC` | `rA = rB[rC]` (bounds checked) |
| `INDEX_SET` | `0x62` | `rA, rB, rC` | `rA[rB] = rC` |
| `LENGTH` | `0x63` | `rA, rB, _` | `rA = len(rB)` |

### 4.7 Type Operations — Tier 0 (0x70–0x7F)

| Opcode | Hex | Form | Semantics |
|--------|-----|------|-----------|
| `CAST_INT` | `0x70` | `rA, rB, _` | `rA = int(rB)` |
| `CAST_FLOAT` | `0x71` | `rA, rB, _` | `rA = float(rB)` |
| `CAST_STRING` | `0x72` | `rA, rB, _` | `rA = string(rB)` |
| `CAST_BOOL` | `0x73` | `rA, rB, _` | `rA = bool(rB)` |

---

## 5. Execution Model

1. The VM loads the `.ulb` file, validates magic bytes and version, parses the constant pool, function table, and block metadata into memory.
2. The VM locates the entry-point function (default: `main`) by name.
3. A root call frame is created with a register file of `register_count` slots, all initialized to `empty`.
4. The PC is set to the function's instruction offset.
5. The VM enters the fetch-decode-execute loop:
   - Read 32-bit instruction word at PC.
   - Decode opcode (byte 0), operands (bytes 1–3).
   - Execute. PC += 4 (always, unless a jump modifies PC).
   - Repeat until `RETURN` with no caller frame.
6. Exit code = integer value of the return register from `main`, or 0 if `empty`.

### 5.1 Register File

Each call frame has its own register file of `register_count` slots (specified in the function table). Registers r0..r(param_count-1) are loaded with arguments by the caller. The compiler assigns all locals and temporaries to registers at compile time via linear-scan allocation. No operand stack exists.

### 5.2 Recommended Dispatch Implementation

The main enemy of interpreter performance is **indirect branch misprediction**. Each opcode dispatch is a branch the CPU must predict, and a central `switch` gives the branch predictor a single site shared by all opcodes.

**Primary: direct threaded dispatch** via computed goto (GCC/Clang `&&label` extension). Each handler ends with `goto *dispatch_table[*(uint8_t*)pc]`, jumping directly to the next handler. This gives the branch predictor a separate site per handler. Benchmarks show 15–25% speedup over switch dispatch.

**Fallback: dense jump table.** Use a `switch` with contiguous opcode values. Hot opcodes are numbered `0x01–0x0B` with no gaps so the jump table stays dense and small.

**Never use:** `if/else if` chains. O(n) per dispatch, destroys branch prediction.

### 5.3 Quickening

After the first execution, the VM may **rewrite an instruction's opcode byte in-place** to a specialized variant. The 32-bit fixed-width format makes this a single aligned byte write with no instruction-stream resizing.

| Original | Quickened | What changes |
|----------|-----------|-------------|
| `ADD` | `ADD_INT` | Both operands confirmed int — skip type dispatch |
| `ADD` | `ADD_FLOAT` | Both operands confirmed float |
| `CMP_LT` | `CMP_LT_INT` | Both operands confirmed int |
| `CALL` | `CALL_RESOLVED` | Function pointer cached after first name resolution |
| `LOAD_CONST` | `LOAD_CONST_INT` | Constant type cached — skip pool tag check |

Quickened opcodes use the range `0xC0–0xDF`. Never emitted by the compiler. Never present in `.ulb` files on disk. See §7 for the full type specialization plan.

### 5.4 Error Handling

Runtime errors (division by zero, out-of-bounds index, type mismatch, register out of range) halt execution with an error message including the function name and instruction offset. No exceptions or try/catch in v1.0.

---

## 6. Tiered ISA

The instruction set is organized into three tiers. Tier 0 ships in v1.0. Tiers 1 and 2 are designed now and implemented incrementally.

### Tier 0 — Primitive Operations

All instructions in §4. Integer/float arithmetic, register moves, branches, calls, returns. Each maps to one or two machine instructions under JIT. No metadata, no side tables. The baseline that every VM must implement.

### Tier 1 — Semantic Operations (0x80–0x9F)

Instructions that carry **inline cache (IC) metadata indices** for runtime specialization. Each Tier 1 instruction has a `rC` field that indexes into a per-function IC table (not part of the `.ulb` file — allocated by the VM at load time).

| Opcode | Hex | Form | Semantics |
|--------|-----|------|-----------|
| `CALL_IC` | `0x80` | `rA, rB, ic_slot` | Call function in `rB` with IC slot for monomorphic/polymorphic dispatch |
| `FIELD_GET` | `0x81` | `rA, rB, ic_slot` | `rA = rB.field` with type feedback in IC slot |
| `FIELD_SET` | `0x82` | `rA, rB, ic_slot` | `rA.field = rB` with type feedback |
| `ITER_INIT` | `0x83` | `rA, rB, _` | Initialize iterator over array/string in `rB`, store state in `rA` |
| `ITER_NEXT` | `0x84` | `rA, rB, imm8` | Advance iterator `rB`, store value in `rA`, jump +imm8 instructions if exhausted |

The IC table stores observed types, cached method pointers, and field offsets. On first execution, the IC slot is empty and the instruction takes the slow generic path. On subsequent executions, the cached information provides a fast path. If the observed type changes (deoptimization), the IC slot is cleared and reverts to generic.

### Tier 2 — Superinstructions and Domain Operations (0xA0–0xBF)

Fused instruction sequences and domain-specific operations added by the **load-time rewriting pass** (§8). Never emitted by the compiler directly. The VM rewrites Tier 0 sequences into Tier 2 equivalents when profitable.

| Opcode | Hex | Form | Semantics |
|--------|-----|------|-----------|
| `ADD_REGS` | `0xA0` | `rA, rB, rC` | `rA = rB + rC` (int-only, no type check — post-specialization) |
| `LOOP_TEST` | `0xA1` | `rA, rB, imm8` | `if !(rA < rB): pc += imm8 * 4`. Fused compare-and-branch for loop headers. |
| `RETURN_REG` | `0xA2` | `rA, _, _` | Equivalent to `RETURN rA` but skips frame teardown checks for leaf functions |
| `CALL_STORE` | `0xA3` | `rA, rB, rC` | Call `rB` with `rC` args, store result directly in `rA`. Fused call+move. |
| `STRUCT_COPY` | `0xA4` | `rA, rB, imm8` | Copy `imm8` consecutive registers from `rB..rB+imm8` to `rA..rA+imm8` |
| `BULK_ZERO` | `0xA5` | `rA, imm16` | Zero `imm16` consecutive registers starting at `rA` |
| `SLICE` | `0xA6` | `rA, rB, rC` | `rA = rB[rC.start..rC.end]` (array/string slice) |
| `INC_REG` | `0xA7` | `rA, _, _` | `rA = rA + 1` (integer only, no type check) |
| `DEC_REG` | `0xA8` | `rA, _, _` | `rA = rA - 1` |
| `CMP_JUMP_EQ` | `0xA9` | `rA, rB, imm8` | `if rA == rB: pc += imm8 * 4`. Fused compare-and-branch for match cases. |

---

## 7. Type Specialization

Generic arithmetic instructions (`ADD`, `SUB`, `MUL`, `DIV`, `CMP_LT`) perform runtime type dispatch on every execution. Type specialization eliminates this overhead after the first execution reveals operand types.

**Quickened typed variants** (range `0xC0–0xDF`):

| Generic | Int variant | Float variant | Hex |
|---------|-----------|--------------|-----|
| `ADD` (0x03) | `ADD_INT` | `ADD_FLOAT` | `0xC0`, `0xC1` |
| `SUB` (0x04) | `SUB_INT` | `SUB_FLOAT` | `0xC2`, `0xC3` |
| `MUL` (0x05) | `MUL_INT` | `MUL_FLOAT` | `0xC4`, `0xC5` |
| `DIV` (0x06) | `DIV_INT` | `DIV_FLOAT` | `0xC6`, `0xC7` |
| `CMP_LT` (0x07) | `CMP_LT_INT` | `CMP_LT_FLOAT` | `0xC8`, `0xC9` |
| `CMP_EQ` (0x20) | `CMP_EQ_INT` | `CMP_EQ_FLOAT` | `0xCA`, `0xCB` |
| `LOAD_CONST` (0x02) | `LOAD_CONST_INT` | `LOAD_CONST_FLOAT` | `0xCC`, `0xCD` |

The VM rewrites the opcode byte in-place after the first execution. If types change at that instruction site (deoptimization), the opcode reverts to generic and retries. This is CPython 3.11's PEP 659 approach, designed into UL's instruction set from the start.

---

## 8. Load-Time Rewriting

On first load of a `.ulb` file, the VM runs a **bytecode rewriting pass** before execution begins. This pass:

1. **Sequence fusion.** Scans for Tier 0 instruction sequences that match Tier 2 superinstruction patterns and rewrites them in-place. Because instructions are fixed 32-bit width, replacing a multi-instruction sequence with a superinstruction + NOPs is a simple aligned write. Example: `CMP_LT r3 r0 r1` + `JUMP_IF_FALSE r3 +4` becomes `LOOP_TEST r0 r1 +5` + `NOP`.

2. **Handler reindexing.** The VM may remap opcode values in the loaded bytecode to reorder dispatch table entries for this specific program's hot paths. If profiling (via block metadata hotness counters) shows that `ADD` and `CALL` dominate, the VM can swap their dispatch table positions so they occupy adjacent I-cache lines. This is transparent to semantics — the remapping is applied to both the bytecode and the dispatch table atomically.

3. **IC table allocation.** For each Tier 1 instruction, the VM allocates an inline cache slot in a per-function side table. The `ic_slot` operand in Tier 1 instructions indexes into this table. The table is not part of the `.ulb` file — it is allocated at load time and populated during execution.

The rewriting pass runs once per function on first load. Subsequent invocations of the same function use the rewritten bytecode. The original `.ulb` file on disk is never modified.

---

## 9. Example

UL source:

```
function main() returns int
  int x = 3
  int y = 4
  print x + y
  return 0
end function
```

Bytecode (function `main`, 0 params, 3 registers: r0=x, r1=y, r2=temp):

```
LOAD_CONST  r0, #0       ; r0 = 3  (constant pool index 0)
LOAD_CONST  r1, #1       ; r1 = 4  (constant pool index 1)
ADD         r2, r0, r1   ; r2 = r0 + r1 = 7
PRINT       r2           ; print 7
LOAD_CONST  r0, #2       ; r0 = 0  (constant pool index 2)
RETURN      r0           ; return 0
```

Constant pool: `[int 3, int 4, int 0]`

Hex encoding (6 instructions × 4 bytes = 24 bytes):

```
02 00 00 00   ; LOAD_CONST r0, const[0]
02 01 01 00   ; LOAD_CONST r1, const[1]
03 02 00 01   ; ADD r2, r0, r1
0B 02 00 00   ; PRINT r2
02 00 02 00   ; LOAD_CONST r0, const[2]
0A 00 00 00   ; RETURN r0
```

After load-time rewriting, the VM may fuse instructions 0–1 into `BULK_ZERO` + two `LOAD_CONST_INT` (if quickening determines all constants are int).

---

## 10. Reserved Ranges

| Range | Purpose |
|-------|---------|
| `0x01–0x7F` | Tier 0 primitive operations |
| `0x80–0x9F` | Tier 1 semantic operations with IC slots |
| `0xA0–0xBF` | Tier 2 superinstructions and domain operations |
| `0xC0–0xDF` | Quickened type-specialized variants (VM-internal, never on disk) |
| `0xE0–0xEF` | Reserved for future tiers |
| `0xF0–0xFE` | Reserved for future use (closures, coroutines, DR enforcement) |
| `0xFF` | `NOP` — no operation (used as padding after superinstruction fusion) |

---

## 11. Versioning

The major version increments on breaking changes to the instruction encoding or file format. The minor version increments on backward-compatible additions (new opcodes in unused ranges). A VM must reject files with a major version it does not support. A VM should accept files with a minor version greater than its own, executing unknown Tier 1/2 opcodes via their Tier 0 expansions stored in the block metadata.
