# Pragma Language

**Syntax reference, safety documentation, and compiler source.**

## Live Site

| Page | URL |
|------|-----|
| Syntax Reference | https://pragma-project.github.io/Pragma-Language/syntax-reference.html |
| Safety & MemProof | https://pragma-project.github.io/Pragma-Language/safety.html |

## What is Pragma?

Pragma is a statically-typed systems language that transpiles to C. Designed to be readable to anyone who has written code in any modern language, while providing access to the full hardware stack when needed.

Standard Pragma reads like natural language. Base Pragma adds memory management, pointers, and bitwise operations in the same file — no mode switch, no separate language.

**Example — `container_of`.** Recovering a struct from a pointer to one of its members. A pattern used throughout the Linux kernel.

<table>
<tr>
<th>C — linux/container_of.h</th>
<th>Pragma</th>
</tr>
<tr>
<td>

```c
#define container_of(ptr, type, member) ({              \
    void *__mptr = (void *)(ptr);                       \
    static_assert(__same_type(*(ptr), ((type *)0)->member) || \
              __same_type(*(ptr), void),                \
              "pointer type mismatch in container_of"); \
    ((type *)(__mptr - offsetof(type, member))); })
```

</td>
<td>

```
none <raw>   = change(<list_ptr>)->none      // cast to byte pointer
raw          = raw - offset(Device, list)    // walk back to struct start
Device <dev> = change(raw)-><Device>         // typed pointer to struct
```

</td>
</tr>
</table>

## Compiler

Requires Python 3 and clang or gcc.



## Safety

Pragma targets mathematically proven memory safety and functional correctness via Frama-C with the WP plugin. See the [Safety page](https://pragma-project.github.io/Pragma-Language/safety.html) for the full methodology.

## Org

Part of the [Pragma Project](https://github.com/Pragma-Project) — Language, Metal (hardware optimization), and OS.
