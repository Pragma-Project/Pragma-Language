"""
Pragma Lexer
Tokenizes .run source files into a stream of tokens.
"""

from enum import Enum, auto
from dataclasses import dataclass
from typing import List, Optional


class TT(Enum):
    """Token types."""
    # Literals
    INT_LIT      = auto()
    FLOAT_LIT    = auto()
    STRING_LIT   = auto()
    BOOL_LIT     = auto()
    NULL         = auto()
    EMPTY        = auto()

    # Identifiers and types
    IDENT        = auto()
    TYPE         = auto()

    # Keywords - structure
    GLOBAL       = auto()
    END_GLOBAL   = auto()
    MAIN         = auto()
    END_MAIN     = auto()

    # Keywords - blocks
    FUNCTION     = auto()
    END_FUNCTION = auto()
    TYPEBLOCK    = auto()    # 'type' ... 'end type'  (struct declaration)
    END_TYPEBLOCK= auto()
    INTERFACE    = auto()
    END_INTERFACE= auto()
    IF           = auto()
    ELSE_IF      = auto()
    ELSE         = auto()
    END_ELSE     = auto()
    END_IF       = auto()
    FOR          = auto()
    END_FOR      = auto()
    FOR_EACH     = auto()
    WHILE        = auto()
    END_DO       = auto()
    TRY          = auto()
    END_TRY      = auto()
    CATCH        = auto()
    END_CATCH    = auto()
    FIXED        = auto()    # enum declaration  (was MANDATE)
    END_FIXED    = auto()
    MATCH        = auto()    # no-fall-through switch  (was CONDITIONS)
    END_MATCH    = auto()
    ITERATE      = auto()    # fall-through iterate
    END_ITERATE  = auto()
    VARIANT      = auto()    # union type: variant Foo ... end variant
    END_VARIANT  = auto()

    # Keywords - control
    RETURNS      = auto()
    INPUTS       = auto()
    RETURN       = auto()
    NEW          = auto()
    IMPORT       = auto()
    IN           = auto()
    DO           = auto()
    PRINT        = auto()
    ESCAPE       = auto()    # break
    CONTINUE     = auto()    # continue  (was SKIP)
    DEFAULT      = auto()    # match/iterate default case
    WHEN         = auto()    # match/iterate case label: when VALUE
    RAISE        = auto()    # error ExceptionType "msg"

    # Keywords - declarations
    CONSTANT     = auto()
    INHERITS     = auto()
    INTERFACES   = auto()
    SUPER        = auto()
    CHANGE       = auto()    # cast: change(x)->type

    # Keywords - word operators
    DELTA        = auto()    # XOR:          a delta b
    FLIP         = auto()    # bitwise NOT:  bitflip a
    LEFT         = auto()    # left shift:   a left n
    RIGHT        = auto()    # right shift:  a right n
    BAND         = auto()    # bitwise AND:  a both1 b
    BOR          = auto()    # bitwise OR:   a either1 b
    BNOR         = auto()    # bitwise NOR:  a both0 b
    NEGATE       = auto()    # arithmetic negation: negate x
    EQUALS       = auto()    # == alternative: x equals y

    # Memory
    ADDRESS      = auto()
    MEM          = auto()
    DEREF        = auto()
    SIZE         = auto()

    # Arithmetic operators
    PLUS         = auto()
    MINUS        = auto()
    STAR         = auto()
    SLASH        = auto()
    MODULO       = auto()

    # Comparison / assignment
    ASSIGN       = auto()
    EQ           = auto()
    NEQ          = auto()
    LT           = auto()
    GT           = auto()
    LTE          = auto()
    GTE          = auto()

    # Logical operators
    AND          = auto()    # 'and'  logical AND
    OR           = auto()    # 'or'   logical OR
    NOT          = auto()    # '!' or 'not'

    # Increment / compound assign
    INCREMENT    = auto()
    DECREMENT    = auto()
    PLUS_ASSIGN  = auto()
    MINUS_ASSIGN = auto()
    STAR_ASSIGN  = auto()
    SLASH_ASSIGN = auto()
    LEFT_ASSIGN  = auto()    # <<=  (left=)
    RIGHT_ASSIGN = auto()    # >>=  (right=)

    # Special
    ARROW        = auto()    # ->

    # Delimiters
    LPAREN       = auto()
    RPAREN       = auto()
    LBRACKET     = auto()
    RBRACKET     = auto()
    LANGLE       = auto()    # <  (pointer brackets)
    RANGLE       = auto()    # >
    DOT          = auto()
    COMMA        = auto()
    COLON        = auto()

    NEWLINE      = auto()
    EOF          = auto()


@dataclass
class Token:
    type: TT
    value: str
    line: int


# ── Type set ───────────────────────────────────────────────────────────────────

TYPES = {
    'int', 'integer',
    'int8',  'integer8',
    'int16', 'integer16',
    'int32', 'integer32',
    'int64', 'integer64',
    'uint',
    'uint8', 'uint16', 'uint32', 'uint64',
    'double', 'float',
    'string', 'String',
    'bool',
    'char',
    'none',      # no-value / void pointer: none <p> → void*
}

# ── Keyword map ────────────────────────────────────────────────────────────────

KEYWORDS = {
    # Structure
    'GLOBAL':     TT.GLOBAL,
    'MAIN':       TT.MAIN,
    # Blocks
    'function':   TT.FUNCTION,
    'type':       TT.TYPEBLOCK,
    'interface':  TT.INTERFACE,
    'if':         TT.IF,
    'else':       TT.ELSE,
    'for':        TT.FOR,
    'while':      TT.WHILE,
    'try':        TT.TRY,
    'catch':      TT.CATCH,
    'fixed':      TT.FIXED,
    'match':      TT.MATCH,
    'iterate':    TT.ITERATE,
    'variant':    TT.VARIANT,
    # Control
    'returns':    TT.RETURNS,
    'inputs':     TT.INPUTS,
    'return':     TT.RETURN,
    'new':        TT.NEW,
    'import':     TT.IMPORT,
    'in':         TT.IN,
    'do':         TT.DO,
    'print':      TT.PRINT,
    'escape':     TT.ESCAPE,
    'continue':   TT.CONTINUE,
    'default':    TT.DEFAULT,
    'when':       TT.WHEN,    # optional alias for match/iterate case syntax
    'error':      TT.RAISE,
    # Declarations
    'constant':   TT.CONSTANT,
    'inherits':   TT.INHERITS,
    'change':     TT.CHANGE,
    # Word operators
    'and':        TT.AND,
    'or':         TT.OR,
    'not':        TT.NOT,
    'equals':     TT.EQUALS,
    'delta':      TT.DELTA,
    'bitflip':    TT.FLIP,
    'left':       TT.LEFT,
    'right':      TT.RIGHT,
    'both1':      TT.BAND,
    'either1':    TT.BOR,
    'both0':      TT.BNOR,
    'negate':     TT.NEGATE,
    # Literals
    'null':       TT.NULL,
    'empty':      TT.EMPTY,
    'true':       TT.BOOL_LIT,
    'false':      TT.BOOL_LIT,
    # Memory ops
    'address':    TT.ADDRESS,
    'mem':        TT.MEM,
    'deref':      TT.DEREF,
    'size':       TT.SIZE,
}

# ── End-keyword map ────────────────────────────────────────────────────────────

END_KEYWORDS = {
    'function':  TT.END_FUNCTION,
    'type':      TT.END_TYPEBLOCK,
    'interface': TT.END_INTERFACE,
    'if':        TT.END_IF,
    'else':      TT.END_ELSE,
    'for':       TT.END_FOR,
    'do':        TT.END_DO,
    'try':       TT.END_TRY,
    'catch':     TT.END_CATCH,
    'GLOBAL':    TT.END_GLOBAL,
    'MAIN':      TT.END_MAIN,
    'fixed':     TT.END_FIXED,
    'match':     TT.END_MATCH,
    'iterate':   TT.END_ITERATE,
    'variant':   TT.END_VARIANT,
}


# ── Error ──────────────────────────────────────────────────────────────────────

class LexError(Exception):
    def __init__(self, msg, line):
        super().__init__(f"Line {line}: {msg}")


# ── Lexer ──────────────────────────────────────────────────────────────────────

class Lexer:
    """
    Tokenizes Pragma source text.
    Inputs:  source: str  — full source text of a .run file
    Outputs: List[Token]  — flat list of tokens
    """

    def __init__(self, source: str):
        self.src = source
        self.pos = 0
        self.line = 1
        self.tokens: List[Token] = []

    def peek(self, offset: int = 0) -> Optional[str]:
        i = self.pos + offset
        return self.src[i] if i < len(self.src) else None

    def advance(self) -> str:
        ch = self.src[self.pos]
        self.pos += 1
        if ch == '\n':
            self.line += 1
        return ch

    def match_str(self, expected: str) -> bool:
        if self.src[self.pos:self.pos + len(expected)] == expected:
            for _ in expected:
                self.advance()
            return True
        return False

    def add(self, tt: TT, value: str):
        self.tokens.append(Token(tt, value, self.line))

    def tokenize(self) -> List[Token]:
        while self.pos < len(self.src):
            self._next()
        self.add(TT.EOF, '')
        return self.tokens

    def _next(self):
        ch = self.peek()

        # Whitespace (not newlines)
        if ch in (' ', '\t', '\r'):
            self.advance()
            return

        # Newline
        if ch == '\n':
            self.advance()
            self.add(TT.NEWLINE, '\\n')
            return

        # Comment  (//)
        if ch == '/' and self.peek(1) == '/':
            while self.peek() and self.peek() != '\n':
                self.advance()
            return

        # String literal
        if ch == '"':
            self._string()
            return

        # Number (hex / binary / decimal)
        if ch == '0' and self.peek(1) == 'x':
            self._hex(); return
        if ch == '0' and self.peek(1) == 'b':
            self._binary(); return
        if ch and ch.isdigit():
            self._number(); return

        # ── Operators ─────────────────────────────────────────────────────────

        if ch == '+':
            self.advance()
            if self.peek() == '+':
                self.advance(); self.add(TT.INCREMENT, '++')
            elif self.peek() == '=':
                self.advance(); self.add(TT.PLUS_ASSIGN, '+=')
            else:
                self.add(TT.PLUS, '+')
            return

        if ch == '-':
            self.advance()
            if self.peek() == '-':
                self.advance(); self.add(TT.DECREMENT, '--')
            elif self.peek() == '=':
                self.advance(); self.add(TT.MINUS_ASSIGN, '-=')
            elif self.peek() == '>':
                self.advance(); self.add(TT.ARROW, '->')
            else:
                self.add(TT.MINUS, '-')
            return

        if ch == '*':
            self.advance()
            if self.peek() == '=':
                self.advance(); self.add(TT.STAR_ASSIGN, '*=')
            else:
                self.add(TT.STAR, '*')
            return

        if ch == '/':
            self.advance()
            if self.peek() == '=':
                self.advance(); self.add(TT.SLASH_ASSIGN, '/=')
            else:
                self.add(TT.SLASH, '/')
            return

        if ch == '%':
            self.advance(); self.add(TT.MODULO, '%')
            return

        if ch == '=':
            self.advance()
            if self.peek() == '=':
                self.advance(); self.add(TT.EQ, '==')
            else:
                self.add(TT.ASSIGN, '=')
            return

        if ch == '!':
            self.advance()
            if self.peek() == '=':
                self.advance(); self.add(TT.NEQ, '!=')
            else:
                self.add(TT.NOT, '!')
            return

        if ch == '<':
            self.advance()
            # <<= (left-shift assign)
            if self.peek() == '<' and self.peek(1) == '=':
                self.advance(); self.advance()
                self.add(TT.LEFT_ASSIGN, '<<=')
            elif self.peek() == '=':
                self.advance(); self.add(TT.LTE, '<=')
            else:
                self.add(TT.LANGLE, '<')
            return

        if ch == '>':
            self.advance()
            # >>= (right-shift assign)
            if self.peek() == '>' and self.peek(1) == '=':
                self.advance(); self.advance()
                self.add(TT.RIGHT_ASSIGN, '>>=')
            elif self.peek() == '=':
                self.advance(); self.add(TT.GTE, '>=')
            else:
                self.add(TT.RANGLE, '>')
            return

        if ch == '^':
            self.advance(); self.add(TT.DELTA, '^')
            return

        if ch == '~':
            self.advance(); self.add(TT.FLIP, '~')
            return

        # ── Delimiters ────────────────────────────────────────────────────────

        if ch == '(': self.advance(); self.add(TT.LPAREN,   '('); return
        if ch == ')': self.advance(); self.add(TT.RPAREN,   ')'); return
        if ch == '[': self.advance(); self.add(TT.LBRACKET, '['); return
        if ch == ']': self.advance(); self.add(TT.RBRACKET, ']'); return
        if ch == '.': self.advance(); self.add(TT.DOT,      '.'); return
        if ch == ',': self.advance(); self.add(TT.COMMA,    ','); return
        if ch == ':': self.advance(); self.add(TT.COLON,    ':'); return

        # ── Identifier or keyword ─────────────────────────────────────────────

        if ch and (ch.isalpha() or ch == '_'):
            self._ident()
            return

        raise LexError(f"Unexpected character: {repr(ch)}", self.line)

    def _string(self):
        self.advance()          # opening "
        start = self.pos
        while self.peek() and self.peek() != '"':
            if self.peek() == '\\':
                self.advance()  # skip escape char
            self.advance()
        value = self.src[start:self.pos]
        self.advance()          # closing "
        self.add(TT.STRING_LIT, value)

    def _number(self):
        start = self.pos
        while self.peek() and self.peek().isdigit():
            self.advance()
        if self.peek() == '.' and self.peek(1) and self.peek(1).isdigit():
            self.advance()
            while self.peek() and self.peek().isdigit():
                self.advance()
            self.add(TT.FLOAT_LIT, self.src[start:self.pos])
        else:
            self.add(TT.INT_LIT, self.src[start:self.pos])

    def _hex(self):
        start = self.pos
        self.advance(); self.advance()      # 0x
        while self.peek() and self.peek() in '0123456789abcdefABCDEF':
            self.advance()
        self.add(TT.INT_LIT, self.src[start:self.pos])

    def _binary(self):
        start = self.pos
        self.advance(); self.advance()      # 0b
        while self.peek() and self.peek() in '01':
            self.advance()
        self.add(TT.INT_LIT, self.src[start:self.pos])

    def _ident(self):
        start = self.pos
        while self.peek() and (self.peek().isalnum() or self.peek() == '_'):
            self.advance()
        word = self.src[start:self.pos]

        # ── Multi-word keywords ───────────────────────────────────────────────

        if word in ('end', 'END'):
            sp = self.pos
            while sp < len(self.src) and self.src[sp] in (' ', '\t'):
                sp += 1
            we = sp
            while we < len(self.src) and (self.src[we].isalnum() or self.src[we] == '_'):
                we += 1
            next_word = self.src[sp:we]
            if next_word in END_KEYWORDS:
                self.pos = we
                self.add(END_KEYWORDS[next_word], f'end {next_word}')
                return

        if word == 'else':
            sp = self.pos
            while sp < len(self.src) and self.src[sp] in (' ', '\t'):
                sp += 1
            if self.src[sp:sp+2] == 'if':
                self.pos = sp + 2
                self.add(TT.ELSE_IF, 'else if')
                return
            self.add(TT.ELSE, 'else')
            return

        if word == 'for':
            sp = self.pos
            while sp < len(self.src) and self.src[sp] in (' ', '\t'):
                sp += 1
            if self.src[sp:sp+4] == 'each':
                self.pos = sp + 4
                self.add(TT.FOR_EACH, 'for each')
                return
            self.add(TT.FOR, 'for')
            return

        # ── Types, keywords, identifiers ──────────────────────────────────────

        if word in TYPES:
            self.add(TT.TYPE, word)
            return

        if word in KEYWORDS:
            self.add(KEYWORDS[word], word)
            return

        self.add(TT.IDENT, word)
