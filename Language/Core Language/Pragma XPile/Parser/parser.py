"""
Pragma Parser
Recursive-descent parser for .run source files.

Method:  parse(source: str) -> Program
"""

from typing import List, Optional, Any
from lexer import Lexer, Token, TT
from ast_nodes import *


class ParseError(Exception):
    def __init__(self, msg: str, line: int):
        super().__init__(f"Line {line}: {msg}")


class Parser:
    """
    Inputs:  tokens: List[Token]  — output of Lexer.tokenize()
    Outputs: Program              — root AST node
    """

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    # ── Token helpers ──────────────────────────────────────────────────────────

    def peek(self, offset: int = 0) -> Token:
        i = self.pos + offset
        return self.tokens[i] if i < len(self.tokens) else self.tokens[-1]

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return tok

    def check(self, *types: TT) -> bool:
        return self.peek().type in types

    def match(self, *types: TT) -> Optional[Token]:
        if self.check(*types):
            return self.advance()
        return None

    def expect(self, tt: TT, msg: str = "") -> Token:
        if self.check(tt):
            return self.advance()
        tok = self.peek()
        raise ParseError(
            msg or f"Expected {tt.name}, got {tok.type.name} ({repr(tok.value)})",
            tok.line,
        )

    def skip_newlines(self):
        while self.check(TT.NEWLINE):
            self.advance()

    # Memory-op keywords (address/size/deref/mem) may appear as field or variable
    # names in user code — accept them wherever an IDENT name is expected.
    _NAME_TOKENS = {TT.IDENT, TT.SIZE, TT.DEREF, TT.MEM, TT.ADDRESS}

    def _expect_name(self, msg: str = "Expected name") -> Token:
        tok = self.peek()
        if tok.type in self._NAME_TOKENS:
            return self.advance()
        return self.expect(TT.IDENT, msg)

    # ── Top level ──────────────────────────────────────────────────────────────

    def parse(self) -> Program:
        prog = Program()
        self.skip_newlines()
        while not self.check(TT.EOF):
            if self.check(TT.NEWLINE):
                self.advance()
                continue
            prog.body.append(self._statement())
        return prog

    def _body(self, *end_tokens: TT) -> List[Any]:
        stmts = []
        while not self.check(*end_tokens) and not self.check(TT.EOF):
            if self.check(TT.NEWLINE):
                self.advance()
                continue
            stmts.append(self._statement())
        return stmts

    # ── Statement dispatch ────────────────────────────────────────────────────

    def _statement(self) -> Any:
        tok = self.peek()

        if tok.type == TT.IMPORT:      return self._import_decl()
        if tok.type == TT.CONSTANT:    return self._constant_decl()
        if tok.type == TT.TYPE:        return self._type_var_decl()
        if tok.type == TT.FUNCTION:    return self._func_decl()
        if tok.type == TT.TYPEBLOCK:   return self._obj_decl()
        if tok.type == TT.INTERFACE:   return self._interface_decl()
        if tok.type == TT.FIXED:       return self._fixed_decl()
        if tok.type == TT.VARIANT:     return self._variant_decl()
        if tok.type == TT.RAISE:       return self._raise_stmt()
        if tok.type == TT.RETURN:      return self._return_stmt()
        if tok.type == TT.PRINT:       return self._print_stmt()
        if tok.type == TT.IF:          return self._if_stmt()
        if tok.type == TT.FOR:         return self._for_stmt()
        if tok.type == TT.FOR_EACH:    return self._foreach_stmt()
        if tok.type == TT.WHILE:       return self._while_stmt()
        if tok.type == TT.TRY:         return self._try_stmt()
        if tok.type == TT.MATCH:       return self._match_stmt()
        if tok.type == TT.ITERATE:      return self._iterate_stmt()
        if tok.type == TT.ESCAPE:
            self.advance(); self.match(TT.NEWLINE); return EscapeStmt()
        if tok.type == TT.CONTINUE:
            self.advance(); self.match(TT.NEWLINE); return ContinueStmt()
        if tok.type == TT.NEW:
            s = self._new_expr(); self.match(TT.NEWLINE); return s

        if tok.type == TT.IDENT:
            # array int[5] name  or  array int[5][3] name
            if tok.value == 'array' and self.peek(1).type == TT.TYPE:
                self.advance(); return self._array_decl()
            # array[int] name  — legacy bracket syntax
            if tok.value == 'array' and self.peek(1).type == TT.LBRACKET:
                self.advance(); return self._array_decl_legacy()
            # list string[3] names
            if tok.value == 'list' and self.peek(1).type == TT.TYPE:
                self.advance(); return self._list_decl()
            # map [KeyType, ValType][capacity] name
            if tok.value == 'map' and self.peek(1).type == TT.LBRACKET:
                self.advance(); return self._map_decl()
            # User-defined type variable:  TypeName varName [= expr]
            # or pointer:                  TypeName <varName>
            if self.peek(1).type == TT.IDENT or self.peek(1).type == TT.LANGLE:
                type_name = self.advance().value
                if self.check(TT.LANGLE):
                    return self._ptr_decl(type_name)
                return self._var_decl(type_name)
            return self._expr_stmt()

        if tok.type in (TT.SUPER, TT.CHANGE, TT.ADDRESS, TT.DEREF,
                        TT.MEM, TT.SIZE):
            return self._expr_stmt()

        raise ParseError(
            f"Unexpected token: {tok.type.name} ({repr(tok.value)})",
            tok.line,
        )

    # ── Declaration parsers ───────────────────────────────────────────────────

    def _import_decl(self) -> ImportDecl:
        self.expect(TT.IMPORT)
        name = self.expect(TT.IDENT, "Expected module name after 'import'")
        self.match(TT.NEWLINE)
        return ImportDecl(module=name.value)

    def _constant_decl(self) -> ConstantDecl:
        self.expect(TT.CONSTANT)
        type_tok = self.expect(TT.TYPE, "Expected type after 'constant'")
        name = self.expect(TT.IDENT, "Expected constant name")
        self.expect(TT.ASSIGN, "Expected '=' in constant declaration")
        init = self._expr()
        self.match(TT.NEWLINE)
        return ConstantDecl(type_name=type_tok.value, name=name.value, init=init)

    def _type_var_decl(self) -> Any:
        type_tok = self.advance()
        if self.check(TT.LANGLE):
            return self._ptr_decl(type_tok.value)
        return self._var_decl(type_tok.value)

    def _var_decl(self, type_name: str) -> VarDecl:
        name = self._expect_name(f"Expected variable name after type '{type_name}'")
        init = None
        if self.match(TT.ASSIGN):
            init = self._expr()
        self.match(TT.NEWLINE)
        return VarDecl(type_name=type_name, name=name.value, init=init)

    def _ptr_decl(self, type_name: str) -> VarDecl:
        """int <p> = ...  or  int <<pp>> = ..."""
        levels = 0
        while self.check(TT.LANGLE):
            self.advance()
            levels += 1
        name = self._expect_name("Expected pointer name")
        for _ in range(levels):
            self.expect(TT.RANGLE, "Expected '>' to close pointer brackets")
        ptr_type = '<' * levels + type_name + '>' * levels
        init = None
        if self.match(TT.ASSIGN):
            init = self._expr()
        self.match(TT.NEWLINE)
        return VarDecl(type_name=ptr_type, name=name.value, init=init)

    def _array_decl_legacy(self) -> ArrayDecl:
        """array[Type] name = [...]  — legacy syntax"""
        self.expect(TT.LBRACKET)
        elem = self.advance()   # TYPE or IDENT
        self.expect(TT.RBRACKET)
        name = self.expect(TT.IDENT, "Expected array name")
        init: List[Any] = []
        if self.match(TT.ASSIGN):
            init = self._bracket_list()
        self.match(TT.NEWLINE)
        return ArrayDecl(elem_type=elem.value, name=name.value, dims=[], init=init)

    def _array_decl(self) -> ArrayDecl:
        """array int[5] name  or  array int[5][3] name = [...]"""
        elem_tok = self.expect(TT.TYPE, "Expected element type after 'array'")
        dims: List[int] = []
        while self.check(TT.LBRACKET):
            self.advance()
            if self.check(TT.INT_LIT):
                dims.append(int(self.advance().value))
            self.expect(TT.RBRACKET, "Expected ']' in array dimensions")
        name = self.expect(TT.IDENT, "Expected array name")
        init: List[Any] = []
        if self.match(TT.ASSIGN):
            init = self._bracket_list()
        self.match(TT.NEWLINE)
        return ArrayDecl(elem_type=elem_tok.value, name=name.value, dims=dims, init=init)

    def _list_decl(self) -> ListDecl:
        """list string[3] names = [...]"""
        elem_tok = self.expect(TT.TYPE, "Expected element type after 'list'")
        dims: List[int] = []
        while self.check(TT.LBRACKET):
            self.advance()
            if self.check(TT.INT_LIT):
                dims.append(int(self.advance().value))
            self.expect(TT.RBRACKET, "Expected ']' in list dimensions")
        name = self.expect(TT.IDENT, "Expected list name")
        init: List[Any] = []
        if self.match(TT.ASSIGN):
            init = self._bracket_list()
        self.match(TT.NEWLINE)
        return ListDecl(elem_type=elem_tok.value, name=name.value, dims=dims, init=init)

    def _map_decl(self) -> MapDecl:
        """map [string,int][50] wordCount"""
        self.expect(TT.LBRACKET, "Expected '[' for key-value types")
        key = self.advance().value   # key type (TYPE or IDENT)
        self.expect(TT.COMMA, "Expected ',' between key and value types")
        val = self.advance().value   # value type
        self.expect(TT.RBRACKET, "Expected ']' after types")
        capacity = None
        if self.check(TT.LBRACKET):
            self.advance()
            if self.check(TT.INT_LIT):
                capacity = int(self.advance().value)
            self.expect(TT.RBRACKET)
        name = self.expect(TT.IDENT, "Expected map name").value
        self.match(TT.NEWLINE)
        return MapDecl(key_type=key, val_type=val, capacity=capacity, name=name)

    def _func_decl(self) -> FunctionDecl:
        self.expect(TT.FUNCTION)
        name = self.expect(TT.IDENT, "Expected function name")
        params: List[Param] = []
        if self.match(TT.LPAREN):
            params = self._param_list()
            self.expect(TT.RPAREN, "Expected ')' after parameters")
        ret = 'void'
        if self.match(TT.RETURNS):
            if self.check(TT.TYPE) or self.check(TT.IDENT):
                ret_tok = self.advance()
            else:
                raise ParseError("Expected return type after 'returns'", self.peek().line)
            ret = ret_tok.value
            # Pointer return type: returns <Type>
            if ret_tok.type == TT.LANGLE:
                levels = 1
                while self.check(TT.LANGLE):
                    self.advance(); levels += 1
                inner = self.advance().value
                for _ in range(levels):
                    self.expect(TT.RANGLE)
                ret = '<' * levels + inner + '>' * levels
        self.skip_newlines()
        body = self._body(TT.END_FUNCTION)
        self.expect(TT.END_FUNCTION)
        self.match(TT.NEWLINE)
        return FunctionDecl(name=name.value, return_type=ret, params=params, body=body)

    def _param_list(self) -> List[Param]:
        params: List[Param] = []
        if self.check(TT.RPAREN):
            return params
        params.append(self._param())
        while self.match(TT.COMMA):
            params.append(self._param())
        return params

    def _param(self) -> Param:
        if self.check(TT.TYPE):
            type_tok = self.advance()
        elif self.check(TT.IDENT):
            type_tok = self.advance()
        else:
            tok = self.peek()
            raise ParseError(f"Expected parameter type, got {tok.type.name} ({repr(tok.value)})", tok.line)
        type_name = type_tok.value
        if self.check(TT.LANGLE):
            levels = 0
            while self.check(TT.LANGLE):
                self.advance(); levels += 1
            name_tok = self._expect_name("Expected parameter name")
            for _ in range(levels):
                self.expect(TT.RANGLE, "Expected '>' in pointer parameter")
            return Param(type_name='<' * levels + type_name + '>' * levels, name=name_tok.value)
        name_tok = self._expect_name("Expected parameter name")
        return Param(type_name=type_name, name=name_tok.value)

    def _obj_decl(self) -> ObjectDecl:
        """type Node ... end type"""
        self.expect(TT.TYPEBLOCK)
        name = self.expect(TT.IDENT, "Expected type name")
        parent = None
        ifaces: List[str] = []
        if self.match(TT.INHERITS):
            parent = self.expect(TT.IDENT, "Expected parent type name after 'inherits'").value
        if self.match(TT.INTERFACES):
            ifaces.append(self.expect(TT.IDENT, "Expected interface name").value)
            while self.match(TT.COMMA):
                ifaces.append(self.expect(TT.IDENT, "Expected interface name").value)
        self.skip_newlines()
        fields: List[ObjectField] = []
        methods: List[FunctionDecl] = []
        while not self.check(TT.END_TYPEBLOCK, TT.EOF):
            if self.check(TT.NEWLINE):
                self.advance(); continue
            if self.check(TT.FUNCTION):
                methods.append(self._func_decl())
            elif self.check(TT.TYPE) or self.check(TT.IDENT):
                fields.append(self._obj_field())
            else:
                tok = self.peek()
                raise ParseError(
                    f"Expected field or method in type, got {tok.type.name}",
                    tok.line,
                )
        self.expect(TT.END_TYPEBLOCK)
        self.match(TT.NEWLINE)
        return ObjectDecl(name=name.value, parent=parent, ifaces=ifaces,
                          fields=fields, methods=methods)

    def _obj_field(self) -> ObjectField:
        type_tok = self.advance()
        type_name = type_tok.value

        # Bit field:  uint.bits=7 count
        if self.check(TT.DOT):
            self.advance()
            kw = self._expect_name("Expected 'bits' after '.'")
            if kw.value == 'bits':
                self.expect(TT.ASSIGN, "Expected '=' after 'bits'")
                bits_tok = self.expect(TT.INT_LIT, "Expected bit count")
                bits = int(bits_tok.value)
                name_tok = self._expect_name("Expected field name")
                self.match(TT.NEWLINE)
                return ObjectField(type_name=type_name, name=name_tok.value, bits=bits)

        # Pointer field: Type <field>
        if self.check(TT.LANGLE):
            levels = 0
            while self.check(TT.LANGLE):
                self.advance(); levels += 1
            name_tok = self._expect_name("Expected field name")
            for _ in range(levels):
                self.expect(TT.RANGLE, "Expected '>' in pointer field")
            default = None
            if self.match(TT.ASSIGN):
                default = self._expr()
            self.match(TT.NEWLINE)
            ptr_type = '<' * levels + type_name + '>' * levels
            return ObjectField(type_name=ptr_type, name=name_tok.value, default=default)

        name_tok = self._expect_name("Expected field name")
        default = None
        if self.match(TT.ASSIGN):
            default = self._expr()
        self.match(TT.NEWLINE)
        return ObjectField(type_name=type_name, name=name_tok.value, default=default)

    def _interface_decl(self) -> InterfaceDecl:
        self.expect(TT.INTERFACE)
        name = self.expect(TT.IDENT, "Expected interface name")
        self.skip_newlines()
        methods: List[FunctionDecl] = []
        while not self.check(TT.END_INTERFACE, TT.EOF):
            if self.check(TT.NEWLINE):
                self.advance(); continue
            if self.check(TT.FUNCTION):
                methods.append(self._func_sig())
            else:
                tok = self.peek()
                raise ParseError(f"Expected method signature in interface, got {tok.type.name}", tok.line)
        self.expect(TT.END_INTERFACE)
        self.match(TT.NEWLINE)
        return InterfaceDecl(name=name.value, methods=methods)

    def _func_sig(self) -> FunctionDecl:
        self.expect(TT.FUNCTION)
        name = self.expect(TT.IDENT, "Expected function name")
        params: List[Param] = []
        if self.match(TT.LPAREN):
            params = self._param_list()
            self.expect(TT.RPAREN)
        ret = 'void'
        if self.match(TT.RETURNS):
            if self.check(TT.TYPE) or self.check(TT.IDENT):
                ret_tok = self.advance()
            else:
                raise ParseError("Expected return type", self.peek().line)
            ret = ret_tok.value
        self.match(TT.NEWLINE)
        return FunctionDecl(name=name.value, return_type=ret, params=params, body=[])

    def _variant_decl(self) -> VariantDecl:
        """variant Packet ... end variant  →  C union"""
        self.expect(TT.VARIANT)
        name = self.expect(TT.IDENT, "Expected variant name")
        self.skip_newlines()
        fields: List[VariantField] = []
        while not self.check(TT.END_VARIANT, TT.EOF):
            if self.check(TT.NEWLINE):
                self.advance(); continue
            type_tok = self.advance()
            type_name = type_tok.value
            if self.check(TT.LANGLE):
                levels = 0
                while self.check(TT.LANGLE):
                    self.advance(); levels += 1
                name_tok = self._expect_name("Expected field name")
                for _ in range(levels):
                    self.expect(TT.RANGLE, "Expected '>' in pointer field")
                ptr_type = '<' * levels + type_name + '>' * levels
                self.match(TT.NEWLINE)
                fields.append(VariantField(type_name=ptr_type, name=name_tok.value))
            else:
                name_tok = self._expect_name("Expected field name")
                self.match(TT.NEWLINE)
                fields.append(VariantField(type_name=type_name, name=name_tok.value))
        self.expect(TT.END_VARIANT)
        self.match(TT.NEWLINE)
        return VariantDecl(name=name.value, fields=fields)

    def _raise_stmt(self) -> RaiseStmt:
        """error ExceptionType  or  error ExceptionType "message" """
        self.expect(TT.RAISE)
        exc_type = self.expect(TT.IDENT, "Expected exception type name after 'error'").value
        message = None
        if not self.check(TT.NEWLINE, TT.EOF):
            message = self._expr()
        self.match(TT.NEWLINE)
        return RaiseStmt(exc_type=exc_type, message=message)

    def _fixed_decl(self) -> FixedDecl:
        """fixed Priority low=1, medium=2, high=3 end fixed"""
        self.expect(TT.FIXED)
        name = self.expect(TT.IDENT, "Expected fixed (enum) name")
        members: List[FixedMember] = []
        if self.check(TT.NEWLINE):
            self.skip_newlines()
            while not self.check(TT.END_FIXED, TT.EOF):
                if self.check(TT.NEWLINE):
                    self.advance(); continue
                members.append(self._fixed_member())
                self.match(TT.COMMA)
        else:
            members.append(self._fixed_member())
            while self.match(TT.COMMA):
                if self.check(TT.END_FIXED, TT.NEWLINE, TT.EOF):
                    break
                members.append(self._fixed_member())
        self.expect(TT.END_FIXED)
        self.match(TT.NEWLINE)
        return FixedDecl(name=name.value, members=members)

    def _fixed_member(self) -> FixedMember:
        name = self.expect(TT.IDENT, "Expected member name")
        value = None
        if self.match(TT.ASSIGN):
            val_tok = self.expect(TT.INT_LIT, "Expected integer value")
            value = int(val_tok.value, 0)
        return FixedMember(name=name.value, value=value)

    # ── Statement parsers ─────────────────────────────────────────────────────

    def _return_stmt(self) -> ReturnStmt:
        self.expect(TT.RETURN)
        value = None
        if not self.check(TT.NEWLINE, TT.EOF):
            value = self._expr()
        self.match(TT.NEWLINE)
        return ReturnStmt(value=value)

    def _print_stmt(self) -> PrintStmt:
        self.expect(TT.PRINT)
        value = self._expr()
        self.match(TT.NEWLINE)
        return PrintStmt(value=value)

    def _if_stmt(self) -> IfStmt:
        self.expect(TT.IF)
        cond = self._expr()
        self.skip_newlines()
        body = self._body(TT.ELSE_IF, TT.ELSE, TT.END_IF)
        elifs: List[ElifClause] = []
        else_body = None
        while self.check(TT.ELSE_IF):
            self.advance()
            elif_cond = self._expr()
            self.skip_newlines()
            elif_body = self._body(TT.ELSE_IF, TT.ELSE, TT.END_IF)
            elifs.append(ElifClause(condition=elif_cond, body=elif_body))
        if self.check(TT.ELSE):
            self.advance()
            self.skip_newlines()
            else_body = self._body(TT.END_ELSE, TT.END_IF)
            self.match(TT.END_ELSE)
            self.skip_newlines()
        self.expect(TT.END_IF)
        self.match(TT.NEWLINE)
        return IfStmt(condition=cond, body=body, elif_clauses=elifs, else_body=else_body)

    def _for_stmt(self) -> ForStmt:
        self.expect(TT.FOR)
        if self.check(TT.TYPE):
            # Expressive: for int i = 0 while i < 10 do i++
            return self._for_expressive()
        else:
            # C-style:    for i=0, i<10, i++
            return self._for_cstyle()

    def _for_expressive(self) -> ForStmt:
        type_tok = self.expect(TT.TYPE, "Expected type in for-loop init")
        name_tok = self.expect(TT.IDENT, "Expected variable name")
        self.expect(TT.ASSIGN, "Expected '='")
        start_val = self._expr()
        init = VarDecl(type_name=type_tok.value, name=name_tok.value, init=start_val)
        self.expect(TT.WHILE, "Expected 'while'")
        cond = self._expr()
        self.expect(TT.DO, "Expected 'do'")
        step = self._step_expr()
        self.skip_newlines()
        body = self._body(TT.END_FOR)
        self.expect(TT.END_FOR)
        self.match(TT.NEWLINE)
        return ForStmt(init=init, condition=cond, step=step, body=body, c_style=False)

    def _for_cstyle(self) -> ForStmt:
        # for i=0, i<10, i++
        name_tok = self.expect(TT.IDENT, "Expected variable name")
        self.expect(TT.ASSIGN, "Expected '='")
        start_val = self._expr()
        init = AssignStmt(target=Identifier(name=name_tok.value), op='=', value=start_val)
        self.expect(TT.COMMA, "Expected ',' after init")
        cond = self._expr()
        self.expect(TT.COMMA, "Expected ',' after condition")
        step = self._step_expr()
        self.skip_newlines()
        body = self._body(TT.END_FOR)
        self.expect(TT.END_FOR)
        self.match(TT.NEWLINE)
        return ForStmt(init=init, condition=cond, step=step, body=body, c_style=True)

    def _step_expr(self) -> Any:
        name_tok = self.expect(TT.IDENT, "Expected variable in step")
        ident = Identifier(name=name_tok.value)
        if self.match(TT.INCREMENT):
            return PostfixOp(op='++', operand=ident)
        if self.match(TT.DECREMENT):
            return PostfixOp(op='--', operand=ident)
        for tt, op in [(TT.PLUS_ASSIGN, '+='), (TT.MINUS_ASSIGN, '-='),
                       (TT.STAR_ASSIGN,  '*='), (TT.SLASH_ASSIGN, '/=')]:
            if self.match(tt):
                return AssignStmt(target=ident, op=op, value=self._expr())
        raise ParseError("Expected ++, --, or compound-assign in step", name_tok.line)

    def _foreach_stmt(self) -> ForEachStmt:
        self.expect(TT.FOR_EACH)
        var = self.expect(TT.IDENT, "Expected variable in 'for each'")
        self.expect(TT.IN, "Expected 'in'")
        iterable = self._expr()
        self.skip_newlines()
        body = self._body(TT.END_FOR)
        self.expect(TT.END_FOR)
        self.match(TT.NEWLINE)
        return ForEachStmt(var=var.value, iterable=iterable, body=body)

    def _while_stmt(self) -> WhileStmt:
        self.expect(TT.WHILE)
        cond = self._expr()
        self.expect(TT.DO, "Expected 'do' after while condition")
        self.skip_newlines()
        body = self._body(TT.END_DO)
        self.expect(TT.END_DO)
        self.match(TT.NEWLINE)
        return WhileStmt(condition=cond, body=body)

    def _try_stmt(self) -> TryStmt:
        self.expect(TT.TRY)
        self.skip_newlines()
        body = self._body(TT.CATCH, TT.END_TRY)
        catches: List[CatchClause] = []
        while self.check(TT.CATCH):
            catches.append(self._catch_clause())
        self.expect(TT.END_TRY)
        self.match(TT.NEWLINE)
        return TryStmt(body=body, catches=catches)

    def _catch_clause(self) -> CatchClause:
        self.expect(TT.CATCH)
        self.expect(TT.LPAREN)
        exceptions = [self.expect(TT.IDENT, "Expected exception type").value]
        while self.match(TT.OR):
            exceptions.append(self.expect(TT.IDENT, "Expected exception type").value)
        var = self.expect(TT.IDENT, "Expected exception variable")
        self.expect(TT.RPAREN)
        self.skip_newlines()
        body = self._body(TT.END_CATCH, TT.CATCH, TT.END_TRY)
        self.expect(TT.END_CATCH)
        self.match(TT.NEWLINE)
        return CatchClause(exceptions=exceptions, var=var.value, body=body)

    def _match_stmt(self) -> MatchStmt:
        """match x ... end match  — no fall-through"""
        self.expect(TT.MATCH)
        expr = self._expr()
        self.skip_newlines()
        cases: List[MatchCase] = []
        while not self.check(TT.END_MATCH, TT.EOF):
            if self.check(TT.NEWLINE):
                self.advance(); continue
            cases.append(self._case_clause(TT.END_MATCH))
        self.expect(TT.END_MATCH)
        self.match(TT.NEWLINE)
        return MatchStmt(expr=expr, cases=cases)

    def _iterate_stmt(self) -> SwitchStmt:
        """iterate x ... end iterate  — fall-through"""
        self.expect(TT.ITERATE)
        expr = self._expr()
        self.skip_newlines()
        cases: List[MatchCase] = []
        while not self.check(TT.END_ITERATE, TT.EOF):
            if self.check(TT.NEWLINE):
                self.advance(); continue
            cases.append(self._case_clause(TT.END_ITERATE))
        self.expect(TT.END_ITERATE)
        self.match(TT.NEWLINE)
        return SwitchStmt(expr=expr, cases=cases)

    def _is_case_start(self, end_tok: TT) -> bool:
        if self.check(TT.DEFAULT, TT.WHEN, end_tok, TT.EOF):
            return True
        if self.check(TT.INT_LIT, TT.STRING_LIT, TT.FLOAT_LIT, TT.BOOL_LIT):
            nxt = self.peek(1).type
            return nxt in (TT.COLON, TT.NEWLINE, TT.EOF)
        return False

    def _case_clause(self, end_tok: TT) -> MatchCase:
        is_default = False
        value = None
        # Accept optional 'when' keyword before case value
        self.match(TT.WHEN)
        if self.match(TT.DEFAULT):
            is_default = True
        else:
            value = self._primary_expr()
        if self.match(TT.COLON):
            # Inline form: when 12: stmt
            if not self.check(TT.NEWLINE, TT.EOF):
                body_stmt = self._statement()
                return MatchCase(value=value, is_default=is_default, body=[body_stmt])
        self.skip_newlines()
        body: List[Any] = []
        while not self._is_case_start(end_tok) and not self.check(TT.EOF):
            if self.check(TT.NEWLINE):
                self.advance(); continue
            body.append(self._statement())
        return MatchCase(value=value, is_default=is_default, body=body)

    def _new_expr(self) -> NewStmt:
        self.expect(TT.NEW)
        type_name = self.expect(TT.IDENT, "Expected type name after 'new'")
        args: List[Any] = []
        if self.match(TT.LBRACKET):
            args = self._arg_list()
            self.expect(TT.RBRACKET)
        return NewStmt(type_name=type_name.value, args=args)

    def _expr_stmt(self) -> Any:
        expr = self._postfix_expr()
        for tt, op in [
            (TT.ASSIGN,        '='),
            (TT.PLUS_ASSIGN,  '+='),
            (TT.MINUS_ASSIGN, '-='),
            (TT.STAR_ASSIGN,  '*='),
            (TT.SLASH_ASSIGN, '/='),
            (TT.LEFT_ASSIGN,  '<<='),
            (TT.RIGHT_ASSIGN, '>>='),
        ]:
            if self.match(tt):
                value = self._expr()
                self.match(TT.NEWLINE)
                return AssignStmt(target=expr, op=op, value=value)
        # left= and right= as two-token compound assigns
        if self.check(TT.LEFT) and self.peek(1).type == TT.ASSIGN:
            self.advance(); self.advance()
            value = self._expr()
            self.match(TT.NEWLINE)
            return AssignStmt(target=expr, op='<<=', value=value)
        if self.check(TT.RIGHT) and self.peek(1).type == TT.ASSIGN:
            self.advance(); self.advance()
            value = self._expr()
            self.match(TT.NEWLINE)
            return AssignStmt(target=expr, op='>>=', value=value)
        self.match(TT.NEWLINE)
        return expr

    # ── Expression hierarchy ──────────────────────────────────────────────────
    # Precedence (low → high):
    #   or | and | either1/both0 | delta | both1 | equality | comparison
    #   | shift | additive | multiplicative | unary | postfix | call | primary

    def _expr(self) -> Any:
        return self._or_expr()

    def _or_expr(self) -> Any:
        left = self._and_expr()
        while self.check(TT.OR):
            op = self.advance().value
            left = BinOp(op=op, left=left, right=self._and_expr())
        return left

    def _and_expr(self) -> Any:
        left = self._bitor_expr()
        while self.check(TT.AND):
            op = self.advance().value
            left = BinOp(op=op, left=left, right=self._bitor_expr())
        return left

    def _bitor_expr(self) -> Any:
        """either1 (bitwise OR) and both0 (bitwise NOR)"""
        left = self._delta_expr()
        while self.check(TT.BOR, TT.BNOR):
            op = self.advance().value
            left = BinOp(op=op, left=left, right=self._delta_expr())
        return left

    def _delta_expr(self) -> Any:
        """XOR: a delta b"""
        left = self._bitand_expr()
        while self.check(TT.DELTA):
            self.advance()
            left = BinOp(op='delta', left=left, right=self._bitand_expr())
        return left

    def _bitand_expr(self) -> Any:
        """both1 (bitwise AND)"""
        left = self._equality_expr()
        while self.check(TT.BAND):
            op = self.advance().value
            left = BinOp(op=op, left=left, right=self._equality_expr())
        return left

    def _equality_expr(self) -> Any:
        left = self._comparison_expr()
        while self.check(TT.EQ, TT.NEQ, TT.EQUALS, TT.NOT):
            tok = self.advance()
            if tok.type == TT.NOT:
                # x not y  →  x != y
                right = self._comparison_expr()
                left = BinOp(op='!=', left=left, right=right)
            elif tok.type == TT.EQUALS:
                right = self._comparison_expr()
                left = BinOp(op='==', left=left, right=right)
            else:
                left = BinOp(op=tok.value, left=left, right=self._comparison_expr())
        return left

    def _comparison_expr(self) -> Any:
        left = self._shift_expr()
        while self.check(TT.LANGLE, TT.RANGLE, TT.LTE, TT.GTE):
            op = self.advance().value
            left = BinOp(op=op, left=left, right=self._shift_expr())
        return left

    def _shift_expr(self) -> Any:
        left = self._additive_expr()
        while self.check(TT.LEFT, TT.RIGHT):
            op = self.advance().value
            left = BinOp(op=op, left=left, right=self._additive_expr())
        return left

    def _additive_expr(self) -> Any:
        left = self._multiplicative_expr()
        while self.check(TT.PLUS, TT.MINUS):
            op = self.advance().value
            left = BinOp(op=op, left=left, right=self._multiplicative_expr())
        return left

    def _multiplicative_expr(self) -> Any:
        left = self._unary_expr()
        while self.check(TT.STAR, TT.SLASH, TT.MODULO):
            op = self.advance().value
            left = BinOp(op=op, left=left, right=self._unary_expr())
        return left

    def _unary_expr(self) -> Any:
        if self.check(TT.NOT):
            self.advance()
            return UnaryOp(op='!', operand=self._unary_expr())
        if self.check(TT.MINUS):
            self.advance()
            return UnaryOp(op='-', operand=self._unary_expr())
        if self.check(TT.FLIP):
            self.advance()
            return UnaryOp(op='flip', operand=self._unary_expr())
        if self.check(TT.NEGATE):
            self.advance()
            return UnaryOp(op='-', operand=self._unary_expr())
        return self._postfix_expr()

    def _postfix_expr(self) -> Any:
        expr = self._call_expr()
        if self.match(TT.INCREMENT):
            return PostfixOp(op='++', operand=expr)
        if self.match(TT.DECREMENT):
            return PostfixOp(op='--', operand=expr)
        return expr

    def _call_expr(self) -> Any:
        expr = self._primary_expr()
        while True:
            if self.check(TT.DOT):
                self.advance()
                field = self._expect_name("Expected field name after '.'")
                expr = FieldAccess(obj=expr, field=field.value)
            elif self.check(TT.LPAREN):
                self.advance()
                args = self._arg_list()
                self.expect(TT.RPAREN)
                expr = CallExpr(func=expr, args=args)
            elif self.check(TT.LBRACKET):
                self.advance()
                index = self._expr()
                self.expect(TT.RBRACKET, "Expected ']' after index")
                expr = IndexExpr(array=expr, index=index)
            else:
                break
        return expr

    def _arg_list(self) -> List[Any]:
        args: List[Any] = []
        if self.check(TT.RPAREN, TT.RBRACKET):
            return args
        args.append(self._expr())
        while self.match(TT.COMMA):
            args.append(self._expr())
        return args

    def _bracket_list(self) -> List[Any]:
        self.expect(TT.LBRACKET)
        items: List[Any] = []
        if not self.check(TT.RBRACKET):
            items.append(self._expr())
            while self.match(TT.COMMA):
                items.append(self._expr())
        self.expect(TT.RBRACKET)
        return items

    def _primary_expr(self) -> Any:
        tok = self.peek()

        if tok.type == TT.INT_LIT:
            self.advance(); return IntLit(value=int(tok.value, 0))
        if tok.type == TT.FLOAT_LIT:
            self.advance(); return FloatLit(value=float(tok.value))
        if tok.type == TT.STRING_LIT:
            self.advance(); return StringLit(value=tok.value)
        if tok.type == TT.BOOL_LIT:
            self.advance(); return BoolLit(value=tok.value == 'true')
        if tok.type == TT.NULL:
            self.advance(); return NullLit()
        if tok.type == TT.EMPTY:
            self.advance(); return EmptyLit()
        if tok.type == TT.SUPER:
            self.advance(); return SuperRef()
        if tok.type == TT.IDENT:
            self.advance(); return Identifier(name=tok.value)
        if tok.type == TT.LPAREN:
            self.advance()
            expr = self._expr()
            self.expect(TT.RPAREN)
            return expr
        if tok.type == TT.NEW:
            return self._new_expr()

        # change(x)->type  — cast
        if tok.type == TT.CHANGE:
            self.advance()
            self.expect(TT.LPAREN)
            expr = self._expr()
            self.expect(TT.RPAREN)
            self.expect(TT.ARROW, "Expected '->' after change(...)")
            if self.check(TT.LANGLE):
                levels = 0
                while self.check(TT.LANGLE):
                    self.advance(); levels += 1
                if self.check(TT.TYPE):
                    type_tok = self.advance()
                else:
                    type_tok = self.expect(TT.IDENT, "Expected type name in cast")
                for _ in range(levels):
                    self.expect(TT.RANGLE, "Expected '>' in cast type")
                target = '<' * levels + type_tok.value + '>' * levels
            elif self.check(TT.TYPE):
                target = self.advance().value
            else:
                target = self.expect(TT.IDENT, "Expected type name after '->'").value
            return CastExpr(expr=expr, target_type=target)

        # <varname>  — pointer value (used in expressions and as arg to address/deref)
        if tok.type == TT.LANGLE:
            self.advance()
            if self.check(TT.IDENT):
                var = self.advance()
                self.expect(TT.RANGLE, "Expected '>' after pointer name")
                return Identifier(name=var.value)   # <p> is just p (the pointer value)
            elif self.check(TT.INT_LIT):
                addr = self._additive_expr()
                self.expect(TT.RANGLE, "Expected '>' after raw address")
                return MemAccess(address=addr)
            raise ParseError("Expected pointer variable or raw address inside < >", tok.line)

        # address(x) or address(<p>)  — take the address of x
        if tok.type == TT.ADDRESS:
            self.advance()
            self.expect(TT.LPAREN, "Expected '(' after 'address'")
            inner = self._expr()   # Identifier or <p> (already parsed as Identifier)
            self.expect(TT.RPAREN, "Expected ')' after address argument")
            return AddressOf(target=inner)

        # deref(<p>)  — read value at pointer
        if tok.type == TT.DEREF:
            self.advance()
            self.expect(TT.LPAREN, "Expected '(' after 'deref'")
            ptr = self._expr()
            self.expect(TT.RPAREN, "Expected ')' after deref argument")
            return DerefExpr(pointer=ptr)

        # size(Type)  — byte size of type
        if tok.type == TT.SIZE:
            self.advance()
            self.expect(TT.LPAREN, "Expected '(' after 'size'")
            if self.check(TT.TYPE):
                type_tok = self.advance()
            elif self.check(TT.IDENT):
                type_tok = self.advance()
            else:
                raise ParseError("Expected type name in size()", self.peek().line)
            self.expect(TT.RPAREN, "Expected ')' after size argument")
            return SizeOf(type_name=type_tok.value)

        # mem(addr)  — raw memory access
        if tok.type == TT.MEM:
            self.advance()
            self.expect(TT.LPAREN, "Expected '(' after 'mem'")
            addr = self._expr()
            self.expect(TT.RPAREN, "Expected ')' after mem argument")
            return MemAccess(address=addr)

        raise ParseError(
            f"Unexpected token in expression: {tok.type.name} ({repr(tok.value)})",
            tok.line,
        )


# ── Public API ─────────────────────────────────────────────────────────────────

def parse(source: str) -> Program:
    """Lex and parse a Pragma .run source string into the root Program AST."""
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()
