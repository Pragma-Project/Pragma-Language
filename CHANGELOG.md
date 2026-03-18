# UniLogic — What Exists

Everything currently implemented in the UniLogic toolchain.

---

## Compiler (XPile)

### Lexer
- 56 reserved keywords covering control flow, declarations, types, operators, memory, concurrency hints, and result types
- Literal types: decimal integers, hex (`0x`), floats with optional exponent, strings with escape sequences (`\n`, `\t`, `\"`, `\\`)
- Operators: arithmetic (`+`, `-`, `*`, `/`, `%`), comparison (`==`, `!=`, `<`, `>`, `<=`, `>=`), compound assignment (`+=`, `-=`, `*=`, `/=`, `%=`, `left=`, `right=`), increment/decrement (`++`, `--`), cast arrow (`->`), result propagation (`?`)
- Delimiters: `( ) [ ] , . : @ #`
- Line comments: `//`

### Parser
- Recursive descent with precedence climbing
- Precedence levels (low to high): `or`, `and`, `not`, comparison, addition, multiplication, unary (`-`, `address`, `deref`), postfix (call, index, `->` cast, `.` field access, `++`, `--`)
- Statements: `if`/`else`/`end if`, `while`/`end while`, `for each`/`end for`, `match`/`default`/`end match`, `return`, `print`, `escape` (break), `continue`, variable declarations (`[fixed] type name [= expr]`), assignments with compound operators, expression statements
- Declarations: `function`/`end function` with params and return type, `type`/`end type` with fields and `inherits`, `import "lib" function name(...)` with variadic support
- DR directives: `@dr key = value` at file level
- Match case detection: literals, negative literals, `true`/`false`/`empty`, `default`

### AST
- 14 expression nodes: IntLiteral, FloatLiteral, StringLiteral, BoolLiteral, EmptyLiteral, Identifier, BinaryOp, UnaryOp, Cast, Call, Index, ArrayLiteral, FieldAccess, Yield
- 13 statement nodes: VarDecl, Assign, If, While, For, Return, Print, ExprStmt, Escape, Continue, PostIncrement, PostDecrement, Match/MatchCase
- 6 declaration nodes: Param, FunctionDecl, ForeignImport, TypeDecl, DrDirective, Program
- TypeName with pointer flag, array flag, and array size

### Semantic Checker
- Variable declaration tracking with scope chains (local, parent, global)
- No redeclaration in same scope
- Use-before-declare detection
- Function signature registration (first pass) for forward call resolution
- Function call argument validation
- Type inheritance chain validation (parent must exist)
- Field access resolution through inherited type hierarchy
- Built-in functions exempt from declaration: `absval`, `size`, `change`, `memmove`, `memcopy`, `memset`, `memtake`, `memgive`

### Normalization (optional)
- Level 0: none
- Level 1: compound assignment expansion (`x += y` to `x = x + y`), post-increment/decrement expansion
- Level 2: nested call flattening, chained cast expansion
- Level 3: boolean expression splitting, array initializer element-by-element expansion
- Per-file override via `// @norm N` comment in first 20 lines

### Code Generation — C (codegen_c.py)
- Targets C99 with `stdio.h`, `stdint.h`, `string.h` auto-included
- Struct definitions with inheritance via nested `_base` field
- Forward function declarations
- Format specifier auto-detection: `%s` for strings, `%f` for floats, `%d` for integers
- `fixed` keyword emits `const`
- Array declarations with initializer inference
- `for each` emits `sizeof`-based indexed loop
- `match` emits `if`/`else if` chain with `strcmp` for string cases
- Builtin mapping: `absval`→`abs`, `size`→`sizeof`, `memtake`→`malloc`, `memgive`→`free`, `memcopy`→`memcpy`
- Field access through inherited hierarchy inserts `._base.` chain

### Code Generation — LLVM IR (codegen_llvm.py)
- Alloca/load/store for all locals (mem2reg-friendly)
- Type mapping: `int`→`i32`, sized ints to matching LLVM types, `float`→`float`, `double`→`double`, `string`→`i8*`, `bool`→`i1`
- Struct type definitions: `%TypeName = type { ... }` with inheritance flattened
- Global string constants with LLVM hex escaping
- Branch-based control flow with labels (`if.then`, `if.else`, `while.cond`, `while.body`, `for.cond`, etc.)
- `match` emits LLVM `switch` instruction when all cases are integer literals; falls back to `br` chain otherwise
- Type promotion: int-to-float (`sitofp`), float-to-int (`fptosi`), width extension (`sext`), truncation (`trunc`), float extension/truncation (`fpext`/`fptrunc`)
- Printf integration with format string globals and variadic ABI promotion (`float`→`double`, `i1`→`i32`)
- Foreign import declarations with variadic (`...`) support
- Dead-code elimination via `block_terminated` flag after `ret`/`br`
- Escape/continue: branch to loop end/condition labels with dead-block insertion
- Post-increment/decrement in both statement and expression context

### Code Generation — Python (codegen_python.py)
- Emits Python 3 with `dataclasses` for user-defined types
- Type inheritance via class hierarchy
- Default values: `0` for ints, `0.0` for floats, `""` for strings, `False` for bools, `ClassName()` for custom types
- Mutable defaults use `field(default_factory=...)`
- `match` emits Python 3.10+ `match`/`case` syntax with `case _:` for default
- Auto-generates `if __name__ == "__main__": main()`

### Code Generation — JavaScript (codegen_js.py)
- Factory functions for types: `createTypeName()` returns object literal
- Inheritance via object spread: `{ ...createParent(), own_fields }`
- `fixed` keyword emits `const`, otherwise `let`
- Operators mapped: `and`→`&&`, `or`→`||`, `==`→`===`, `!=`→`!==`
- Casts: `Math.trunc()` for int targets, `Number()` for float, `String()`, `Boolean()`
- `match` emits `switch`/`case` with `break` injection
- `print` emits `console.log()`
- Auto-generates `main();` at module end

### Compiler Driver (Main.py)
- Targets: C (`-t c`), Python (`-t python`), JavaScript (`-t js`), LLVM IR (`-t llvm`)
- Target aliases: `py`, `javascript`, `ir`, `ll`
- Flags: `-t TARGET`, `-o OUTPUT`, `--normalize`, `--norm-level N`
- Interactive target selection menu when no `-t` flag provided
- Pipeline: tokenize → parse → normalize (optional) → semantic check → codegen → write file

---

## REPL

### Terminal REPL (repl.py)
- Launched via `ul` command
- Tree-walking interpreter: lexes, parses, and evaluates UL code line by line
- Persistent scope across inputs (variables and functions survive between entries)
- Multi-line input: detects open blocks (`function`, `if`, `while`, `for`, `match`) and reads continuation lines until `end` closes them
- Commands: `help`, `exit`/`quit`, `functions` (list with signatures), `vars` (list with values), `clear` (reset state)
- Built-in functions: `absval`, `size`, `change`
- Control flow signals: `ReturnValue`, `BreakSignal`, `ContinueSignal` as exceptions
- Integer division uses C-style truncation toward zero
- Print formatting: booleans as `0`/`1`, floats as `%f`, strings and ints as-is
- Bare expression statements print their result
- Colored output: navy prompt, red errors

### Browser REPL (repl.html)
- Runs 100% client-side — no server, no API calls, works offline
- Full JavaScript port of the Python lexer, parser, and tree-walking evaluator
- Same terminal-style UI as the site (dark background, navy prompt `ul>`)
- Startup banner: `∞ UniLogic / One Language for Everything / type help for commands`
- Tip line: "define functions first, then call them on a new line"
- Commands: `help`, `vars`, `functions`, `clear`
- Multi-line input with `...` continuation prompt
- Up/Down arrow key input history
- Syntax errors displayed in red
- Sidebar with clickable example expressions and a two-step function demo
- Infinite loop guard (100k iterations)
- Linked from index.html as "Try it in your browser →"

---

## VS Code Extension

### Syntax Highlighting (TextMate grammar)
- Full tokenization of UniLogic keywords, types, operators, literals, comments, identifiers
- Scope groups: control keywords, type keywords, literal keywords, operator keywords, builtin keywords, modifier keywords
- At-modifiers (`@name`), hash-macros (`#`)
- Function declaration and call capture rules
- String literals with escape sequences

### Language Configuration
- Line comment: `//`
- Bracket pairs: `()`, `[]`
- Auto-closing pairs: `()`, `[]`, `""`
- Folding on `function`/`if`/`while`/`for` ... `end`
- Indentation increase on block-opening keywords, decrease on `end`/`else`

### LSP Server (lsp.py)
- **Diagnostics**: runs lexer → parser → semantic checker on every open/change/save; reports errors with line/column positions
- **Semantic tokens**: full semantic highlighting with 10 token types (keyword, function, variable, number, string, operator, comment, type, parameter, macro) and 3 modifiers (declaration, readonly, defaultLibrary)
- **Hover**: keyword glossary (56 entries with one-line definitions), function signatures, foreign import signatures, type definitions with field list, variable types with user-type expansion
- **Go-to-definition**: jumps to FunctionDecl, TypeDecl, VarDecl/Param declaration sites; cross-file workspace search for symbols not found locally
- **Autocomplete**: all keywords (with glossary as detail), all function names (with signatures), all type names (with field lists), scope-aware variables at cursor position, foreign import function names
- **Signature help**: triggers on `(` and `,`; scans backwards from cursor to find function name and active parameter; handles nested calls via paren-depth tracking; highlights active parameter with offset-based labels
- Stdio transport (default) or TCP on 127.0.0.1:2087 (`--tcp`)

### AI Features (extension.js)
- **Explain Structure**: calls AI provider with file content, returns step-by-step structural walkthrough (types, functions, signatures)
- **Explain Execution Flow**: calls AI with file content, returns execution order walkthrough (what calls what, data flow)
- **Webview rendering**: step navigation (prev/next/goto), line highlighting in editor, section list
- **AI providers**: Anthropic (Claude via SDK), OpenAI-compatible (Ollama, OpenAI, LM Studio via fetch)
- **Model selection**: fetches available models from provider API, QuickPick UI, hardcoded Anthropic fallback list
- **Connection test**: validates settings, makes test call, reports errors

### Dependency Graph (extension.js)
- Scans all `.ul` files in workspace
- Extracts function declarations, cross-file function calls, import statements
- Only creates edges for uniquely-declared functions (functions like `main` that exist in multiple files are excluded)
- Skips keywords and locally-declared functions when detecting calls
- DR memory setting detection from file content (`memory: gc|manual|refcount`)
- DR conflict highlighting: red dashed edges between connected files with different memory settings
- D3.js force-directed graph in a WebviewPanel
- Node colors by DR setting: blue=gc, green=manual, orange=refcount, grey=none
- Clicking a node opens the file in the editor
- Draggable nodes, arrow markers, legend panel

### Status Bar
- Rotating tips every 20 seconds with keyboard shortcuts
- Only visible when a `.ul` file is active

### Other
- Python auto-detection across common install paths
- Automatic `pygls` installation if missing
- Workspace trust check
- Welcome message on first install
- `.ul` language ID fix for session-restored files

---

## Project Manager GUI

- PySide6 desktop application
- New project creation with directory selection
- DR Configurator: interactive setting of 6 runtime directives (memory, safety, types, int_width, concurrency)
- Build tab: compile project with target selection
- DR Conflict Checker: validates consistency of DR settings across all project files
- Project structure tree view showing files, functions, and types
- Dark navy theme
