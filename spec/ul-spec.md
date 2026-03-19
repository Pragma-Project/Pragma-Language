# UniLogic Language Specification

**Version:** 1.1
**Date:** 2026-03-18

---

## 1. Lexical Structure

### 1.1 Character Set

UL source files are UTF-8 encoded. Keywords, operators, and identifiers use ASCII. String literals may contain any valid UTF-8 sequence.

### 1.2 Whitespace

Spaces, tabs, carriage returns, and newlines are insignificant except inside string literals. No indentation requirements.

### 1.3 Comments

Line comments: `//` to end of line. No block comments.

### 1.4 Keywords

**Implemented:**

- Control: `function`, `end`, `returns`, `return`, `if`, `else`, `while`, `do`, `for`, `each`, `in`, `match`, `default`, `escape`, `continue`
- Declarations: `type`, `object`, `inherits`, `new`, `fixed`, `const`, `import`, `from`, `export`
- I/O: `print`, `prompt`
- Concurrency: `parallel`, `spawn`, `wait`, `lock`, `unlock`
- Hints: `nocache`, `yield`, `yields`, `inline`, `pack`
- Literals: `true`, `false`, `empty`
- Logical: `and`, `or`, `not`
- Memory: `address`, `deref`, `memmove`, `memcopy`, `memset`, `memtake`, `memgive`, `left`, `right`
- Built-ins: `size`, `cast`, `absval`, `exit`, `typeof`
- Types: `int`, `integer`, `float`, `double`, `string`, `bool`, `none`, `complex`, `int8`, `int16`, `int32`, `int64`, `uint8`, `uint16`, `uint32`, `uint64`, `array`, `list`, `map`, `arena`, `file`
- Result: `ok`, `error`, `some`

**Reserved (in lexer, not implemented):** `iterate`, `goto`, `portal`, `killswitch`, `equals`, `both1`, `both0`, `either1`, `delta`, `bitflip`, `negate`, `change`, `constant`

### 1.5 Operators

Precedence (highest first):

| Prec | Operators | Assoc |
|------|-----------|-------|
| 1 | `()` `[]` `.` `++` `--` | left |
| 2 | `-` `not` `address` `deref` (unary) | right |
| 3 | `*` `/` `%` | left |
| 4 | `+` `-` | left |
| 5 | `\|>` (pipe) | left |
| 6 | `<` `>` `<=` `>=` | left |
| 7 | `==` `!=` | left |
| 8 | `and` | left |
| 9 | `or` | left |
| 10 | `=` `+=` `-=` `*=` `/=` `%=` `left=` `right=` | right |

Additional: `?` (result propagation), `|` (result type separator), `...` (variadic).

### 1.6 Literals

**Integer:** `42`, `0xFF`
**Float:** `3.14`, `1.0e-5`
**String:** `"hello"`, `"line\n"`. Interpolation: `"hello {name}"` — `{expr}` inside strings is evaluated and concatenated.
**Boolean:** `true`, `false`
**Empty:** `empty`
**Array:** `[1, 2, 3]`
**Array comprehension:** `[x * x for x in range(1, 10)]`

---

## 2. Types

### 2.1 Primitive Types

| Type | Size | Description |
|------|------|-------------|
| `int` | 4B | Signed 32-bit integer |
| `int8`..`int64` | 1-8B | Sized signed integers |
| `uint8`..`uint64` | 1-8B | Sized unsigned integers |
| `float` | 4B | IEEE 754 32-bit |
| `double` | 8B | IEEE 754 64-bit |
| `string` | ptr | Heap-allocated UTF-8 |
| `bool` | 1B | `true` / `false` |
| `none` | 0B | Void / absent |
| `complex` | 16B | Complex number |

### 2.2 Compound Types

- `array T` — fixed-size array of type T
- `<T>` — pointer to T
- `(T, T)` — tuple (multiple return values)
- `T|error` — result type

### 2.3 User-Defined Types (Value Semantics)

```
type Point
  float x
  float y
end type
```

Single inheritance: `type Point3D inherits Point`.

### 2.4 Objects (Reference Semantics)

```
object Shape
  string name
  int sides

  function area() returns float
    return 0.0
  end function
end object

object Circle inherits Shape
  float radius

  function area() returns float
    return 3.14159 * radius * radius
  end function
end object
```

Objects support methods (functions declared inside the object body), vtable dispatch for inherited methods, and `expr.method(args)` call syntax.

### 2.5 Result Types

```
function divide(int a, int b) returns int|error
  if b == 0
    return error "division by zero"
  end if
  return ok a / b
end function
```

---

## 3. Declarations

### 3.1 Function

```
function name(type param, type param = default, ...) [returns type]
  body
end function
```

- If `returns` is omitted, returns `none`. Compiler inserts `return 0` at OS level for `main`.
- **Default parameters:** `type name = literal` in parameter list.
- **Variadic:** `...` as last parameter.
- **Multiple return:** `returns (type, type)`.

### 3.2 Variable

```
type name = expr          // initialized
type name                 // zero-initialized
fixed type name = expr    // immutable (legacy)
const type name = expr    // immutable (preferred)
```

### 3.3 Type Declaration

```
type Name [inherits Parent]
  type field_name
end type
```

### 3.4 Object Declaration

```
object Name [inherits Parent]
  type field_name

  function method(type param) [returns type]
    body
  end function
end object
```

Methods are called via `instance.method(args)`. The compiler rewrites `obj.method(args)` to pass `obj` as an implicit first parameter.

### 3.5 Foreign Import

```
import "library" function name(type param, ...) [returns type]
```

### 3.6 Local Import

```
import "file.ul" function name(type param) [returns type]
```

### 3.7 Const Declaration

```
const int MAX = 100
const string VERSION = "1.0"
```

Compile-time constant. Must be initialized with a literal. Cannot be reassigned.

---

## 4. Expressions

### 4.1 Arithmetic

`+`, `-`, `*`, `/`, `%`. Integer division truncates toward zero. Division by zero is a runtime error.

### 4.2 Comparison

`==`, `!=`, `<`, `>`, `<=`, `>=`. Result is `bool`.

### 4.3 Logical

`and`, `or` (short-circuit), `not` (unary).

### 4.4 Cast

```
cast(expr, type)
```

Float-to-int truncates. Any-to-string converts to representation. Any-to-bool via truthiness.

### 4.5 String Interpolation

```
"hello {name}, you are {age} years old"
```

Expressions inside `{}` are evaluated and converted to string. Nesting not supported.

### 4.6 Array Literal and Comprehension

```
[1, 2, 3]
[x * x for x in range(1, 10)]
```

### 4.7 Pipe Operator

```
data |> transform |> filter |> print
```

`a |> f` rewrites to `f(a)`. Chains left to right.

### 4.8 Index

```
arr[i]
```

### 4.9 Field Access and Method Call

```
point.x
circle.area()
```

Method calls: `obj.method(args)` dispatches through vtable for objects.

### 4.10 Function Call

```
name(expr, expr, ...)
```

### 4.11 Result Propagation

```
expr?
```

If error, enclosing function returns that error. If ok, unwraps value.

### 4.12 Post-Increment / Post-Decrement

```
x++
x--
```

### 4.13 Multiple Return Values

```
(int a, int b) = swap(x, y)
```

---

## 5. Statements

### 5.1 Assignment

`=`, `+=`, `-=`, `*=`, `/=`, `%=`, `left=`, `right=`

### 5.2 If / Else

```
if condition
  body
else
  body
end if
```

### 5.3 While

```
while condition
  body
end while
```

### 5.4 For Each

```
for each var in iterable
  body
end for
```

### 5.5 Match

```
match subject
  value
    body
  default
    body
end match
```

### 5.6 Return

```
return expr
return ok expr
return error "msg"
return (expr, expr)       // multiple return
return                    // return none
```

### 5.7 Print

```
print expr
```

### 5.8 Escape / Continue

```
escape      // break
continue    // next iteration
```

### 5.9 Spawn / Wait

```
spawn process_data(chunk)
wait
```

`spawn` starts a concurrent task. `wait` blocks until all spawned tasks complete.

### 5.10 Lock / Unlock

```
lock mutex_name
  // critical section
unlock mutex_name
```

---

## 6. DR Directives

```
@dr memory = gc
@dr safety = checked
```

| Setting | Values | Default |
|---------|--------|---------|
| `memory` | `gc`, `manual`, `refcount`, `arena` | `gc` |
| `safety` | `checked`, `unchecked` | `checked` |
| `types` | `strict`, `dynamic` | `strict` |
| `int_width` | `32`, `64`, `platform` | `32` |
| `concurrency` | `threaded`, `parallel`, `async`, `cooperative` | `threaded` |

---

## 7. Annotations

| Annotation | Scope | Description |
|-----------|-------|-------------|
| `@dr key = value` | File | Runtime directive |
| `@norm N` | File or function | Normalization level (0-3) |
| `@deprecated("msg")` | Function | Mark as deprecated |
| `@fuse` | Block | Hint to fuse operations |
| `@prefetch(distance=N)` | Loop/data | Insert prefetch instructions |
| `@layout = value` | Type | Memory layout (SoA, AoS) |
| `@precision = value` | File/function | Float precision mode |
| `@sparsity = value` | Type | Tensor sparsity pattern |
| `@asm(arch)` | Block | Inline assembly |

### 7.1 Inline Assembly

```
@asm(x86)
  mov eax, [rdi]
  add eax, [rsi]
  ret
end asm
```

Architecture-specific. The block is emitted verbatim into the target output. Only valid for C and LLVM IR targets.

---

## 8. Built-in Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `print` | `print expr` | Print to stdout with newline |
| `prompt` | `prompt(string msg) returns string` | Read line from stdin |
| `absval` | `absval(numeric x) returns numeric` | Absolute value |
| `size` | `size(T) returns int` | Size of type in bytes |
| `cast` | `cast(expr, type) returns type` | Type conversion |
| `exit` | `exit(int code)` | Terminate with exit code |
| `typeof` | `typeof(expr) returns string` | Runtime type name |
| `memtake` | `memtake(int bytes) returns <none>` | Allocate heap memory |
| `memgive` | `memgive(<none> ptr)` | Free heap memory |
| `memcopy` | `memcopy(<none> dst, <none> src, int n)` | Copy bytes (no overlap) |
| `memmove` | `memmove(<none> dst, <none> src, int n)` | Copy bytes (overlap safe) |
| `memset` | `memset(<none> ptr, int val, int n)` | Fill bytes |
| `time` | `time() returns int` | Unix timestamp in seconds |
| `clock` | `clock() returns int` | Nanoseconds, for benchmarking |
| `sleep` | `sleep(int ms)` | Sleep for ms milliseconds |
| `random` | `random() returns float` | Random float 0.0 to 1.0 |
| `random_int` | `random_int(int lo, int hi) returns int` | Random int between lo and hi inclusive |
| `random_seed` | `random_seed(int n)` | Set seed for reproducible results |
| `userinput` | `userinput() returns array string` | Command line arguments |
| `vault` | `vault(string name) returns string\|error` | Read environment variable |
| `abort` | `abort()` | Terminate immediately, non-zero exit |
| `killswitch` | `killswitch condition` | Runtime assertion (compiled out when safety=unchecked) |

---

## 9. Standard Library

Function names use module prefix. Method syntax `obj.method()` rewrites to `module_method(obj)`.

### 9.1 String

`str_len(s)`, `str_upper(s)`, `str_lower(s)`, `str_contains(s, sub)`, `str_starts_with(s, prefix)`, `str_ends_with(s, suffix)`, `str_trim(s)`, `str_split(s, delim)`, `str_replace(s, old, new)`, `str_concat(a, b)`, `str_substring(s, start, len)`, `str_index_of(s, sub)`

Method syntax: `s.len()` → `str_len(s)`, `s.upper()` → `str_upper(s)`, etc.

### 9.2 Array

`array_len(arr)`, `array_sort(arr)`, `array_reverse(arr)`, `array_contains(arr, val)`, `array_sum(arr)`, `array_min(arr)`, `array_max(arr)`, `array_get(arr, idx)`, `array_set(arr, idx, val)`, `array_push(arr, val)`, `array_pop(arr)`, `array_slice(arr, start, end)`

Method syntax: `arr.sort()` → `array_sort(arr)`, `arr.len()` → `array_len(arr)`, etc.

### 9.3 Math

`math_sqrt(x)`, `math_pow(x, y)`, `math_abs(x)`, `math_floor(x)`, `math_ceil(x)`, `math_round(x)`, `math_min(a, b)`, `math_max(a, b)`, `math_log(x)`, `math_log2(x)`, `math_exp(x)`, `math_pi`, `math_e`

### 9.4 Map

`map_keys(m)`, `map_values(m)`, `map_has(m, key)`, `map_get(m, key)`, `map_set(m, key, val)`, `map_delete(m, key)`, `map_size(m)`

### 9.5 File

`file_open(path [, mode])`, `file_read(f)`, `file_write(f, data)`, `file_close(f)`, `file_exists(path)`, `file_readlines(f)`

### 9.6 JSON

`json_parse(s)`, `json_stringify(val)`

---

## 10. Grammar (EBNF)

```ebnf
program        = { dr_directive | annotation | declaration } ;

declaration    = function_decl
               | type_decl
               | object_decl
               | foreign_import
               | local_import
               | const_decl ;

dr_directive   = "@dr" IDENT "=" IDENT ;
annotation     = "@" IDENT [ "(" annotation_args ")" ] ;

const_decl     = "const" type IDENT "=" expr ;

function_decl  = "function" IDENT "(" [ param_list ] ")"
                 [ "returns" return_type ] body "end" "function" ;

return_type    = type | "(" type { "," type } ")" ;

type_decl      = "type" IDENT [ "inherits" IDENT ]
                 { field } "end" "type" ;

object_decl    = "object" IDENT [ "inherits" IDENT ]
                 { field | method_decl } "end" "object" ;

method_decl    = "function" IDENT "(" [ param_list ] ")"
                 [ "returns" return_type ] body "end" "function" ;

foreign_import = "import" STRING "function" IDENT
                 "(" [ param_list ] ")" [ "returns" type ] ;

local_import   = "import" STRING "function" IDENT
                 "(" [ param_list ] ")" [ "returns" type ] ;

param_list     = param { "," param } [ "," "..." ] ;
param          = type IDENT [ "=" literal ] ;

field          = type IDENT ;

type           = [ "<" ] type_name [ ">" ]
               | "array" type_name ;

type_name      = "int" | "int8" | "int16" | "int32" | "int64"
               | "uint8" | "uint16" | "uint32" | "uint64"
               | "float" | "double" | "string" | "bool" | "none"
               | "complex" | "list" | "map" | "arena" | "file"
               | IDENT ;

body           = { statement } ;

statement      = var_decl | const_decl | assignment | if_stmt | while_stmt
               | for_stmt | match_stmt | return_stmt | print_stmt
               | spawn_stmt | wait_stmt | lock_stmt
               | asm_block | "escape" | "continue" | expr_stmt ;

var_decl       = [ "fixed" | "const" ] type IDENT [ "=" expr ] ;

assignment     = expr assign_op expr ;
assign_op      = "=" | "+=" | "-=" | "*=" | "/=" | "%=" | "left=" | "right=" ;

if_stmt        = "if" expr body [ "else" body ] "end" "if" ;
while_stmt     = "while" expr body "end" "while" ;
for_stmt       = "for" "each" IDENT "in" expr body "end" "for" ;

match_stmt     = "match" expr { match_case } [ default_case ] "end" "match" ;
match_case     = expr body ;
default_case   = "default" body ;

return_stmt    = "return" [ expr | "ok" expr | "error" expr
               | "(" expr { "," expr } ")" ] ;

print_stmt     = "print" expr ;
spawn_stmt     = "spawn" expr ;
wait_stmt      = "wait" ;
lock_stmt      = "lock" IDENT body "unlock" IDENT ;
asm_block      = "@asm" "(" IDENT ")" { ASM_LINE } "end" "asm" ;

expr_stmt      = expr ;

expr           = pipe_expr ;
pipe_expr      = or_expr { "|>" or_expr } ;
or_expr        = and_expr { "or" and_expr } ;
and_expr       = not_expr { "and" not_expr } ;
not_expr       = "not" not_expr | comparison ;
comparison     = addition { ( "==" | "!=" | "<" | ">" | "<=" | ">=" ) addition } ;
addition       = multiplication { ( "+" | "-" ) multiplication } ;
multiplication = unary { ( "*" | "/" | "%" ) unary } ;
unary          = ( "-" | "address" | "deref" ) unary | postfix ;

postfix        = primary { call | index | field_access | method_call
               | "++" | "--" | "?" } ;
call           = "(" [ arg_list ] ")" ;
index          = "[" expr "]" ;
field_access   = "." IDENT ;
method_call    = "." IDENT "(" [ arg_list ] ")" ;

arg_list       = expr { "," expr } ;

primary        = INT_LITERAL | HEX_LITERAL | FLOAT_LITERAL
               | string_literal | "true" | "false" | "empty"
               | IDENT
               | "cast" "(" expr "," type ")"
               | "typeof" "(" expr ")"
               | "[" [ array_body ] "]"
               | "(" expr { "," expr } ")" ;

array_body     = expr { "," expr }
               | expr "for" IDENT "in" expr ;

string_literal = '"' { char | escape | interpolation } '"' ;
interpolation  = "{" expr "}" ;

INT_LITERAL    = digit { digit } ;
HEX_LITERAL    = "0" ( "x" | "X" ) hex_digit { hex_digit } ;
FLOAT_LITERAL  = digit { digit } "." digit { digit }
                 [ ( "e" | "E" ) [ "+" | "-" ] digit { digit } ] ;
IDENT          = ( letter | "_" ) { letter | digit | "_" } ;
```

---

## 11. Compilation Targets

| Target | Flag | Output |
|--------|------|--------|
| C | `-t c` | `.c` (C99) |
| Python | `-t python` | `.py` (Python 3.10+) |
| JavaScript | `-t js` | `.js` (ES6) |
| LLVM IR | `-t llvm` | `.ll` |
| WebAssembly | `-t wasm` | `.wasm` |

---

## 12. Semantics

- Integer division truncates toward zero (C99).
- `and`/`or` short-circuit.
- Inner scopes shadow outer.
- Parameters passed by value. Pointers for pass-by-reference.
- `?` in non-result functions prints error to stderr and exits with code 1.
- `fixed` and `const` variables are immutable.
- Falsy: `empty`, `0`, `0.0`, `""`, `false`. All else truthy.
- Method syntax `obj.method(args)` rewrites to `Type_method(obj, args)`.
- Pipe `a |> f` rewrites to `f(a)`.
- String interpolation `"x = {expr}"` rewrites to `"x = " + cast(expr, string)`.
