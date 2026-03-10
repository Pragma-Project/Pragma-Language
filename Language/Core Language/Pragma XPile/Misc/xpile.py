"""
XPile — Transpile C source to Pragma.

Usage:
  python xpile.py input.c              # print Pragma to stdout
  python xpile.py input.c -o out.run   # write to file
  python xpile.py input.c --no-pp      # skip C preprocessor (for files with no #include)

Requirements:
  pip install pycparser

The transpiler handles:
  - Functions, return values, parameters
  - Basic types: int, double, char, bool, void
  - Structs -> type / end type
  - if / else if / else -> if / else if / else / end if
  - C for loops -> Pragma for ... while ... do ... end for
  - while loops -> while ... do / end do
  - break -> escape, continue -> continue
  - printf/puts -> print
  - Arrays, pointer declarations with angle-bracket syntax
  - Global variable declarations and constants (#define)
  - sizeof(T) -> size(T)
  - &x -> address(x), *p -> deref(<p>)
  - Logical not: !x (both !x and 'not x' are valid Pragma — emits !x)
  - Arithmetic negation: -x (both -x and 'negate x' are valid Pragma — emits -x)
"""

import sys
import os
import re
import subprocess
import tempfile
from pathlib import Path

import pycparser
from pycparser import c_ast


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


# ── Type mapping C → Pragma ────────────────────────────────────────────────────

_TYPE_MAP = {
    'int':           'int',
    'long':          'int',
    'short':         'int',
    'unsigned':      'int',
    'char':          'char',
    'float':         'double',
    'double':        'double',
    'void':          'void',
    '_Bool':         'bool',
    'bool':          'bool',
    'size_t':        'int',
    'int8_t':        'int',
    'int16_t':       'int',
    'int32_t':       'int',
    'int64_t':       'int',
    'uint8_t':       'int',
    'uint16_t':      'int',
    'uint32_t':      'int',
    'uint64_t':      'int',
    'unsigned int':  'int',
    'unsigned long': 'int',
    'unsigned char': 'char',
}

def _pragma_decl(t: str, name: str) -> str:
    """Return correct Pragma declaration string for a type + name.
    Pointer types: '<int>' + 'p'  →  'int <p>'
    Function ptr:  '__funcptr' + 'fn'  →  'none <fn>'
    Plain types:   'int'  + 'x'  →  'int x'
    """
    if t == '__funcptr':
        return f'none <{name}>'
    if t.startswith('<') and t.endswith('>'):
        levels = 0
        inner = t
        while inner.startswith('<') and inner.endswith('>'):
            levels += 1
            inner = inner[1:-1]
        brackets = '<' * levels + name + '>' * levels
        return f'{inner} {brackets}'
    return f'{t} {name}'


_OP_MAP = {
    '&&': 'and',
    '||': 'or',
    '<<': 'left',
    '>>': 'right',
}

# Pragma reserved words that cannot be used as variable/parameter names in C source.
# When a C name collides, append '_v' to disambiguate.
_PRAGMA_RESERVED = {
    'left', 'right', 'do', 'end', 'escape', 'continue', 'type', 'function',
    'returns', 'while', 'for', 'if', 'else', 'print', 'return', 'constant',
    'array', 'list', 'map', 'change', 'address', 'size', 'deref', 'flip', 'delta',
    'fixed', 'match', 'switch', 'interface', 'import', 'not', 'negate', 'equals',
    'and', 'or', 'both1', 'either1', 'both0', 'true', 'false',
    'null', 'empty', 'new', 'void', 'bool', 'string', 'none', 'variant',
}

def _safe_name(name: str) -> str:
    """Rename C identifiers that clash with Pragma keywords."""
    # Only rename exact-case matches — C is case-sensitive; Pragma keywords are lowercase.
    # NULL/TRUE/FALSE are uppercase macros, not keyword conflicts.
    if name in _PRAGMA_RESERVED:
        return name + '_v'
    return name


# ── Pragma emitter ─────────────────────────────────────────────────────────────

class PragmaEmitter(c_ast.NodeVisitor):
    def __init__(self):
        self._lines = []
        self._indent = 0
        self._in_switch = 0
        self._array_names: set = set()   # array vars whose _len is auto-generated
        self._var_types: dict = {}        # name → Pragma type (for __auto_type inference)
        self._enum_types: set = set()     # typedef names that are enums → map to int
        self._defines: dict = {}          # #define NAME → value (for array dim resolution)

    def _emit(self, s=''):
        self._lines.append('  ' * self._indent + s)

    def result(self) -> str:
        return '\n'.join(self._lines)

    def _resolve_dim(self, dim_node, default: str) -> str:
        """Resolve an array dimension node to a string value."""
        if dim_node is None:
            return default
        if isinstance(dim_node, c_ast.Constant):
            return dim_node.value
        if isinstance(dim_node, c_ast.ID):
            # Look up #define constant; fall back to identifier name
            return self._defines.get(dim_node.name, dim_node.name)
        return default

    # ── Type helpers ──────────────────────────────────────────────────────────

    def _map_type(self, node) -> str:
        if isinstance(node, c_ast.TypeDecl):
            return self._map_type(node.type)
        if isinstance(node, c_ast.IdentifierType):
            name = ' '.join(node.names)
            if name in self._enum_types:
                return 'int'
            return _TYPE_MAP.get(name, name)
        if isinstance(node, c_ast.PtrDecl):
            # Function pointer → mark as such
            if isinstance(node.type, (c_ast.FuncDecl,)):
                return '__funcptr'
            inner = self._map_type(node.type)
            # char* → string
            if inner == 'char':
                return 'string'
            # void* → none (void pointer)
            if inner == 'void':
                return 'none'
            # Nested pointer: <inner> wrapped in one more level
            if inner.startswith('<') and inner.endswith('>'):
                return f'<{inner}>'
            return f'<{inner}>'
        if isinstance(node, c_ast.ArrayDecl):
            inner = self._map_type(node.type)
            if inner == 'char':
                # Fixed-size char array — encode size so codegen can emit char name[N]
                # instead of a bare char* pointer (which would be a dangling pointer).
                dim = self._resolve_dim(node.dim, '256')
                return f'chararray_{dim}'
            dim = self._resolve_dim(node.dim, '')
            return f'array[{inner}][{dim}]' if dim else f'array[{inner}]'
        if isinstance(node, c_ast.Struct):
            return node.name or 'UnnamedType'
        if isinstance(node, c_ast.FuncDecl):
            return self._map_type(node.type)
        return 'int'

    # ── Expression helpers ────────────────────────────────────────────────────

    def _expr(self, node) -> str:
        if node is None:
            return ''
        if isinstance(node, c_ast.Constant):
            if node.type == 'char':
                # Convert C char literal to its integer value for Pragma
                raw = node.value  # e.g. "'a'" or "'\\n'"
                inner = raw[1:-1]  # strip surrounding single quotes
                esc_map = {'\\n': 10, '\\t': 9, '\\r': 13, '\\0': 0, '\\\\': 92,
                           "\\'": 39, '\\"': 34, '\\a': 7, '\\b': 8, '\\f': 12, '\\v': 11}
                if inner in esc_map:
                    return str(esc_map[inner])
                if len(inner) == 1:
                    return str(ord(inner))
                return str(ord(inner[0]))  # fallback
            if node.type == 'float':
                # Strip C float suffix: 1.5f → 1.5
                return node.value.rstrip('fF')
            return node.value
        if isinstance(node, c_ast.ID):
            return _safe_name(node.name)
        if isinstance(node, c_ast.BinaryOp):
            left  = self._expr(node.left)
            right = self._expr(node.right)
            op    = _OP_MAP.get(node.op, node.op)
            # Wrap sub-exprs in parens to preserve C operator precedence
            if isinstance(node.left, c_ast.BinaryOp):
                left = f'({left})'
            if isinstance(node.right, c_ast.BinaryOp):
                right = f'({right})'
            return f'{left} {op} {right}'
        if isinstance(node, c_ast.UnaryOp):
            return self._unary_expr(node)
        if isinstance(node, c_ast.Assignment):
            return f'{self._expr(node.lvalue)} {node.op} {self._expr(node.rvalue)}'
        if isinstance(node, c_ast.FuncCall):
            return self._func_call_expr(node)
        if isinstance(node, c_ast.ArrayRef):
            return f'{self._expr(node.name)}[{self._expr(node.subscript)}]'
        if isinstance(node, c_ast.StructRef):
            # both . and -> become . in Pragma
            return f'{self._expr(node.name)}.{node.field.name}'
        if isinstance(node, c_ast.Cast):
            t = self._map_type(node.to_type.type)
            return f'change({self._expr(node.expr)})->{t}'
        if isinstance(node, c_ast.ExprList):
            return ', '.join(self._expr(e) for e in node.exprs)
        if isinstance(node, c_ast.TernaryOp):
            # No ternary in Pragma — emit a comment placeholder
            return (f'/* {self._expr(node.cond)} ? '
                    f'{self._expr(node.iftrue)} : {self._expr(node.iffalse)} */')
        if isinstance(node, c_ast.Typename):
            return self._map_type(node.type)
        if isinstance(node, c_ast.UnaryOp) and node.op == 'sizeof':
            return f'size({self._expr(node.expr)})'
        return f'/* unsupported: {type(node).__name__} */'

    def _unary_expr(self, node) -> str:
        op   = node.op
        if op == 'sizeof':
            inner = self._expr(node.expr)
            return f'size({inner})'
        expr = self._expr(node.expr)
        if op == '!':     return f'!{expr}'
        if op == '-':     return f'-{expr}'
        if op == '+':     return expr
        if op == '&':     return f'address({expr})'
        if op == '*':
            # Wrap simple pointer identifiers in <> as visual hint
            if isinstance(node.expr, c_ast.ID):
                return f'deref(<{expr}>)'
            return f'deref({expr})'
        if op == 'p++':   return f'{expr}++'
        if op == 'p--':   return f'{expr}--'
        if op == '++':    return f'++{expr}'
        if op == '--':    return f'--{expr}'
        if op == '~':     return f'~{expr}'
        return f'{op}{expr}'

    def _func_call_expr(self, node) -> str:
        name = self._expr(node.name)
        if name in ('printf', 'puts', 'fprintf', 'fputs', '__pp'):
            return self._map_printf(node)
        args = [self._expr(a) for a in node.args.exprs] if node.args else []
        return f'{name}({", ".join(args)})'

    def _map_printf(self, node) -> str:
        """Best-effort printf/puts → print mapping."""
        exprs = node.args.exprs if node.args else []
        if not exprs:
            return 'print ""'
        # fprintf: skip first arg (FILE*)
        name = self._expr(node.name)
        if name in ('fprintf', 'fputs'):
            exprs = exprs[1:]
        if not exprs:
            return 'print ""'
        first = exprs[0]
        if isinstance(first, c_ast.Constant) and first.type == 'string':
            fmt = first.value[1:-1]          # strip surrounding quotes
            rest = [self._expr(a) for a in exprs[1:]]
            fmt_clean = fmt.replace('\\n', '').replace('\\t', ' ')
            if not rest:
                return f'print "{fmt_clean}"'
            if len(rest) == 1 and fmt.count('%') == 1:
                return f'print {rest[0]}'
            # Multiple args: emit each on its own line (newline-joined, split in visit_FuncCall)
            return '\n'.join(f'print {a}' for a in rest)
        # puts/simple: just print the expression
        return f'print {self._expr(exprs[0])}'

    # ── Top-level visitors ────────────────────────────────────────────────────

    def visit_FileAST(self, node):
        for item in node.ext:
            self.visit(item)

    def visit_Decl(self, node):
        if isinstance(node.type, (c_ast.FuncDecl,)):
            # Forward declaration — skip
            return
        if isinstance(node.type, c_ast.FuncDef):
            self.visit(node.type)
            return
        if isinstance(node.type, c_ast.Struct) and node.name is None:
            # Anonymous struct at top level — emit as object
            self._emit_struct(node.type)
            return
        if isinstance(node.type, c_ast.ArrayDecl):
            self._emit_array_decl(node)
            return
        # Regular variable / constant
        t    = self._map_type(node.type)
        name = _safe_name(node.name or '_')

        # Skip auto-generated Pragma _len companions for array variables
        if name.endswith('_len') and name[:-4] in self._array_names:
            return

        # Resolve __auto_type (for-each loop var): infer from array element type
        if t == '__auto_type' and node.init is not None:
            init_expr = self._expr(node.init)
            # Try to infer type from array subscript: names[__i] → element type of names
            if isinstance(node.init, c_ast.ArrayRef):
                arr_name = self._expr(node.init.name)
                t = self._var_types.get(arr_name, 'int')
            else:
                t = 'int'

        if node.init is not None:
            init_str = self._expr(node.init)
            # Function pointer variable: none <fp> = funcname()
            # Append () to trigger codegen's function pointer detection
            if t == '__funcptr' and isinstance(node.init, c_ast.ID):
                init_str = f'{init_str}()'
            self._emit(f'{_pragma_decl(t, name)} = {init_str}')
        else:
            self._emit(_pragma_decl(t, name))

    def _emit_array_decl(self, node):
        arr_decl = node.type   # c_ast.ArrayDecl
        t    = self._map_type(arr_decl)   # e.g. array[int][5], or chararray_N for char[]
        name = _safe_name(node.name)
        if t.startswith('chararray_'):
            # char buf[N] local variable — emit as stack array (no malloc needed)
            dim = t[len('chararray_'):]
            self._emit(f'chararray_{dim} {name}')
            return
        # Convert array[int][5] → 'array int[5] name' (new Pragma syntax)
        # or array[int] → 'array int name' (no size)
        pragma_arr = self._format_array_decl(t, name)
        # Track element type for __auto_type resolution
        if t.startswith('array['):
            elem = t[6:t.index(']')]
            self._var_types[name] = elem
        self._array_names.add(name)
        if node.init and isinstance(node.init, c_ast.InitList):
            vals = ', '.join(self._expr(e) for e in node.init.exprs)
            self._emit(f'{pragma_arr} = [{vals}]')
        else:
            self._emit(pragma_arr)

    def _format_array_decl(self, t: str, name: str) -> str:
        """Convert array[int][5] type string + name → 'array int[5] name'."""
        if not t.startswith('array['):
            return f'{t} {name}'
        # Strip leading 'array['
        rest = t[6:]   # e.g. 'int][5]' or 'int]'
        bracket = rest.index(']')
        elem = rest[:bracket]
        after = rest[bracket+1:]  # e.g. '[5]' or ''
        if after.startswith('[') and after.endswith(']'):
            dim = after[1:-1]
            return f'array {elem}[{dim}] {name}'
        return f'array {elem} {name}'

    def visit_FuncDef(self, node):
        decl      = node.decl
        fname     = decl.name
        func_decl = decl.type          # FuncDecl
        ret_type  = self._map_type(func_decl.type)

        # Skip auto-generated Pragma constructor stubs (new<TypeName>)
        # Pragma codegen re-generates these from the object declaration
        if fname.startswith('new') and fname[3:4].isupper() and self._is_constructor_stub(node):
            self._emit(f'// constructor {fname} — auto-generated by Pragma from object declaration')
            self._emit()
            return

        params = []
        if func_decl.args:
            for param in func_decl.args.params:
                if isinstance(param, c_ast.EllipsisParam):
                    params.append('// ...')
                    continue
                pt   = self._map_type(param.type)
                pn   = _safe_name(param.name or '_')
                params.append(_pragma_decl(pt, pn))

        pstr = ', '.join(p for p in params if not p.startswith('//'))

        if fname == 'main':
            self._emit('function main()')
        else:
            self._emit(f'function {fname}({pstr}) returns {ret_type}')

        self._indent += 1
        self.visit(node.body)
        self._indent -= 1
        self._emit('end function')
        self._emit()

    def visit_Typedef(self, node):
        inner = node.type.type if hasattr(node.type, 'type') else None
        if isinstance(inner, c_ast.Struct):
            struct = inner
            if not struct.name:
                struct = c_ast.Struct(node.name, struct.decls, struct.coord)
            self._emit_struct(struct)
        elif isinstance(inner, c_ast.Union):
            union = inner
            if not union.name:
                union = c_ast.Union(node.name, union.decls, union.coord)
            self._emit_union(union)
        elif isinstance(inner, c_ast.Enum):
            self._enum_types.add(node.name)  # track so we can map it to 'int' as a type
            self._emit_enum(inner)
        elif isinstance(inner, c_ast.PtrDecl) and isinstance(inner.type, c_ast.FuncDecl):
            # Function pointer typedef: typedef int (*BinOp)(int,int)
            # No direct Pragma equivalent — emit a comment
            self._emit(f'// typedef (function pointer): {node.name}')
            self._emit()
        # Otherwise skip (e.g. typedef int MyInt)

    def _emit_enum(self, node):
        """Emit enum values as integer constants."""
        if not node.values:
            return
        counter = 0
        for enumerator in node.values.enumerators:
            if enumerator.value is not None:
                val = self._expr(enumerator.value)
                try:
                    counter = int(val)
                except ValueError:
                    counter = val
            self._emit(f'constant int {enumerator.name} = {counter}')
            if isinstance(counter, int):
                counter += 1
        self._emit()

    def _emit_union(self, node):
        """Emit a C union as a Pragma variant."""
        if not node.decls:
            return
        name = node.name or 'UnnamedVariant'
        self._emit(f'variant {name}')
        self._indent += 1
        for field in node.decls:
            ft = self._map_type(field.type)
            if ft == '__funcptr':
                continue
            fn = field.name
            # Bit field support
            if (isinstance(field.type, c_ast.TypeDecl)
                    and hasattr(field, 'bitsize') and field.bitsize):
                bits = self._expr(field.bitsize)
                self._emit(f'{ft}.bits={bits} {fn}')
            else:
                self._emit(_pragma_decl(ft, fn))
        self._indent -= 1
        self._emit('end variant')
        self._emit()

    def _emit_struct(self, node):
        if not node.decls:
            return
        # Skip structs that are purely vtable (all function pointer fields)
        real_fields = [f for f in node.decls
                       if self._map_type(f.type) != '__funcptr']
        if not real_fields:
            self._emit(f'// interface {node.name or "unnamed"} (vtable — use interface keyword in Pragma)')
            self._emit()
            return
        name = node.name or 'UnnamedType'
        self._emit(f'type {name}')
        self._indent += 1
        for field in real_fields:
            ft = self._map_type(field.type)
            fn = field.name
            self._emit(_pragma_decl(ft, fn))
        self._indent -= 1
        self._emit('end type')
        self._emit()

    # ── Statement visitors ────────────────────────────────────────────────────

    def _is_constructor_stub(self, funcdef) -> bool:
        """Detect Pragma-generated constructor: declares __obj, sets fields, returns it."""
        body = funcdef.body
        if not body or not body.block_items:
            return False
        items = body.block_items
        # Must end with: return __obj
        last = items[-1]
        if not isinstance(last, c_ast.Return):
            return False
        if not isinstance(last.expr, c_ast.ID) or last.expr.name != '__obj':
            return False
        return True

    def visit_Compound(self, node):
        if node.block_items:
            for item in node.block_items:
                self.visit(item)

    def visit_If(self, node):
        self._emit(f'if {self._expr(node.cond)}')
        self._indent += 1
        self.visit(node.iftrue)
        self._indent -= 1
        if node.iffalse:
            self._emit_else_chain(node.iffalse)
        self._emit('end if')

    def _emit_else_chain(self, node):
        if isinstance(node, c_ast.If):
            self._emit(f'else if {self._expr(node.cond)}')
            self._indent += 1
            self.visit(node.iftrue)
            self._indent -= 1
            if node.iffalse:
                self._emit_else_chain(node.iffalse)
        else:
            self._emit('else')
            self._indent += 1
            self.visit(node)
            self._indent -= 1

    def visit_For(self, node):
        cond  = self._expr(node.cond) if node.cond else 'true'
        step  = self._expr(node.next) if node.next else ''
        init  = node.init

        if isinstance(init, c_ast.DeclList) and init.decls:
            d   = init.decls[0]
            t   = self._map_type(d.type)
            vn  = d.name
            val = self._expr(d.init) if d.init else '0'
            self._emit(f'for {t} {vn} = {val} while {cond} do {step}')
        elif isinstance(init, c_ast.Assignment):
            vn  = self._expr(init.lvalue)
            val = self._expr(init.rvalue)
            self._emit(f'for {vn} = {val} while {cond} do {step}')
        else:
            self._emit(f'for while {cond} do {step}')

        self._indent += 1
        self.visit(node.stmt)
        self._indent -= 1
        self._emit('end for')

    def visit_While(self, node):
        self._emit(f'while {self._expr(node.cond)} do')
        self._indent += 1
        self.visit(node.stmt)
        self._indent -= 1
        self._emit('end do')

    def visit_DoWhile(self, node):
        # Pragma has no do-while; convert to while with a leading true-guard
        self._emit(f'// do-while converted — runs body at least once')
        self._emit(f'while true do')
        self._indent += 1
        self.visit(node.stmt)
        self._emit(f'if !({self._expr(node.cond)})')
        self._indent += 1
        self._emit('escape')
        self._indent -= 1
        self._emit('end if')
        self._indent -= 1
        self._emit('end do')

    def visit_Return(self, node):
        if node.expr:
            self._emit(f'return {self._expr(node.expr)}')
        else:
            self._emit('return')

    def visit_Break(self, node):
        if self._in_switch:
            pass  # breaks handled per-case in visit_Case/visit_Default
        else:
            self._emit('escape')

    def visit_Continue(self, node):
        self._emit('continue')

    def visit_Label(self, node):
        self._emit(f'// label: {node.name}')
        self.visit(node.stmt)

    def visit_Goto(self, node):
        self._emit(f'// goto {node.name}  (unsupported — review manually)')

    def visit_Switch(self, node):
        self._emit(f'switch {self._expr(node.cond)}')
        self._in_switch += 1
        self._indent += 1
        if isinstance(node.stmt, c_ast.Compound) and node.stmt.block_items:
            for item in node.stmt.block_items:
                self.visit(item)
        self._indent -= 1
        self._in_switch -= 1
        self._emit('end switch')

    def visit_Case(self, node):
        self._indent -= 1
        self._emit(f'when {self._expr(node.expr)}')
        self._indent += 1
        if node.stmts:
            for s in node.stmts:
                if not isinstance(s, c_ast.Break):
                    self.visit(s)

    def visit_Default(self, node):
        self._indent -= 1
        self._emit('default')
        self._indent += 1
        if node.stmts:
            for s in node.stmts:
                if not isinstance(s, c_ast.Break):
                    self.visit(s)

    # ── Expression-as-statement ───────────────────────────────────────────────

    def visit_Assignment(self, node):
        self._emit(self._expr(node))

    def visit_FuncCall(self, node):
        result = self._func_call_expr(node)
        # Multi-print: _func_call_expr may return newline-joined prints for printf with multiple args
        for line in result.split('\n'):
            if line.strip():
                self._emit(line.strip())

    def visit_UnaryOp(self, node):
        # i++, i--, ++i, --i as statements
        if node.op in ('p++', 'p--', '++', '--'):
            self._emit(self._unary_expr(node))
        else:
            self._emit(self._expr(node))

    # ── Fallback ──────────────────────────────────────────────────────────────

    def generic_visit(self, node):
        for _, child in node.children():
            self.visit(child)


# ── Preprocessor / parsing ─────────────────────────────────────────────────────

def _find_fake_includes() -> str | None:
    try:
        pkg_dir = os.path.dirname(pycparser.__file__)
        fake    = os.path.join(pkg_dir, 'utils', 'fake_libc_include')
        if os.path.isdir(fake):
            return fake
    except Exception:
        pass
    return None


def _find_clang() -> str | None:
    import shutil
    clang_env = os.environ.get('CLANG_PATH', r'C:\Program Files\LLVM\bin\clang.exe')
    for cc in [clang_env, 'clang', 'gcc']:
        if os.path.isfile(cc): return cc
        if shutil.which(cc):   return cc
    return None


# Injected preamble so pycparser knows about common types without real stdlib headers
_PYCPARSER_PREAMBLE = """\
typedef _Bool bool;
typedef unsigned long size_t;
typedef int int8_t;
typedef int int16_t;
typedef int int32_t;
typedef long int64_t;
typedef unsigned int uint8_t;
typedef unsigned int uint16_t;
typedef unsigned int uint32_t;
typedef unsigned long uint64_t;
typedef unsigned long uintptr_t;
typedef int __auto_type;
typedef void* __pp_t;
"""


def _preprocess(path: str, src_dir: str = None) -> str | None:
    """Run C preprocessor; return preprocessed text or None on failure."""
    clang = _find_clang()
    if not clang:
        return None
    fake = _find_fake_includes()
    # -nostdinc: ignore system headers; pycparser's fake_libc_include covers them
    cmd  = [clang, '-E', '-nostdinc',
            '-D__attribute__(x)=', '-D__extension__=', '-D__inline=',
            '-D__inline__=', '-D__restrict=', '-D__restrict__=',
            '-D__volatile__=', '-D__const=',
            '-Dbool=int', '-D_Bool=int', '-Dtrue=1', '-Dfalse=0']
    if fake:
        cmd += [f'-I{fake}']
    if src_dir:
        cmd += [f'-I{src_dir}']   # resolve local #include "..." from source dir
    cmd.append(path)
    r = subprocess.run(cmd, capture_output=True, text=True, errors='replace')
    out = r.stdout.strip()
    if not out:
        return None
    # Strip clang line-marker lines: "# <num> "<file>" <flags>"
    cleaned = '\n'.join(
        line for line in out.splitlines()
        if not re.match(r'^\s*#\s*\d+', line)
    )
    return _PYCPARSER_PREAMBLE + cleaned


def _sanitize_for_pycparser(src: str) -> str:
    """
    Rewrite C source so pycparser (C99 only) can handle it.
      - Remove multi-line #define blocks that use _Generic or other C11 features
      - Replace pragma_print(x) → __pp(x)
      - Strip #include / #pragma lines
      - Strip remaining #define lines
      - Strip __asm__ / __asm__/__volatile__ inline assembly statements
    """
    # Remove the entire pragma_print _Generic macro definition (multi-line)
    src = re.sub(
        r'#define\s+pragma_print\s*\(x\).*?(?=\n\s*\n|\n\s*#|\Z)',
        '',
        src,
        flags=re.DOTALL,
    )
    # Replace pragma_print calls with __pp (we map __pp → print in emitter)
    src = re.sub(r'\bpragma_print\s*\(', '__pp(', src)
    # Strip remaining _Generic expressions (replace with 0)
    src = re.sub(r'_Generic\s*\(.*?\)', '0', src, flags=re.DOTALL)
    # Strip inline asm statements: __asm__ [__volatile__] (...) ; → ;
    # The [^;]* is safe here because asm string literals in our kernel have no ;
    src = re.sub(r'\b__asm__\b[^;]*;', ';', src)
    out = []
    for line in src.splitlines():
        s = line.strip()
        if s.startswith('#include') or s.startswith('#pragma'):
            continue
        if s.startswith('#define'):
            continue
        out.append(line)
    return '\n'.join(out)


def _strip_directives(src: str) -> str:
    """Fallback: strip preprocessor directives."""
    return _sanitize_for_pycparser(src)


def _extract_defines(src: str) -> list[tuple[str, str]]:
    """Pull out simple #define NAME value pairs."""
    defines = []
    for line in src.splitlines():
        m = re.match(r'^\s*#define\s+(\w+)\s+(.+)', line)
        if m:
            name, val = m.group(1).strip(), m.group(2).strip()
            if re.match(r'^[\d.]+$', val):
                defines.append((name, val))
    return defines


def transpile_c(c_source: str, use_pp: bool = True, src_dir: str = None) -> str:
    # Extract #define constants before preprocessing strips them
    defines = _extract_defines(c_source)

    if use_pp:
        # Write the ORIGINAL source (with #include intact) to a temp file placed
        # in the same directory as the source so relative includes resolve.
        tmp_dir = src_dir or tempfile.gettempdir()
        fd, path = tempfile.mkstemp(suffix='.c', prefix='xpile_', dir=tmp_dir)
        os.close(fd)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(c_source)
            pp_src = _preprocess(path, src_dir=src_dir)
        finally:
            os.unlink(path)

        if pp_src is None:
            # Preprocessor failed — fall back to sanitizing the raw source
            pp_src = _sanitize_for_pycparser(c_source)
        else:
            # Sanitize the already-expanded output (strips asm, line markers gone)
            pp_src = _sanitize_for_pycparser(pp_src)
    else:
        pp_src = _sanitize_for_pycparser(c_source)

    try:
        ast = pycparser.CParser().parse(pp_src, filename='<input>')
    except pycparser.plyparser.ParseError as e:
        raise ValueError(f'C parse error: {e}')

    emitter = PragmaEmitter()
    emitter._defines = {name: val for name, val in defines}
    emitter.visit(ast)
    pragma = emitter.result()

    # Prepend any #define constants as Pragma constants at top
    if defines:
        const_lines = []
        for name, val in defines:
            if '.' in val:
                const_lines.append(f'constant double {name} = {val}')
            else:
                const_lines.append(f'constant int {name} = {val}')
        pragma = '\n'.join(const_lines) + '\n\n' + pragma

    return pragma


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    src_path = args[0]
    if not os.path.exists(src_path):
        print(f'Error: file not found: {src_path!r}')
        sys.exit(1)

    out_path = None
    if '-o' in args:
        idx = args.index('-o')
        if idx + 1 < len(args):
            out_path = args[idx + 1]

    use_pp = '--no-pp' not in args

    with open(src_path, 'r', encoding='utf-8') as f:
        c_src = f.read()

    src_dir = os.path.dirname(os.path.abspath(src_path))
    try:
        pragma_src = transpile_c(c_src, use_pp=use_pp, src_dir=src_dir)
    except ValueError as e:
        print(e)
        sys.exit(1)

    if out_path:
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(pragma_src)
        print(f'Written: {out_path}')
    else:
        print(pragma_src)


if __name__ == '__main__':
    main()
