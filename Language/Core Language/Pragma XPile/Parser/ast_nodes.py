"""
Pragma AST Nodes
Each node represents one construct in a .run file.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any


# ─── Top level ────────────────────────────────────────────────────────────────

@dataclass
class Program:
    body: List[Any] = field(default_factory=list)


# ─── Declarations ─────────────────────────────────────────────────────────────

@dataclass
class ImportDecl:
    module: str


@dataclass
class VarDecl:
    """int x = 3  or  int x  (no initializer)"""
    type_name: str
    name: str
    init: Optional[Any] = None


@dataclass
class ConstantDecl:
    """constant int x = 3"""
    type_name: str
    name: str
    init: Any


@dataclass
class ArrayDecl:
    """array int[5] a = [...]  or  array int[5][3] grid"""
    elem_type: str
    name: str
    dims: List[int] = field(default_factory=list)   # [] = no size declared
    init: List[Any] = field(default_factory=list)


@dataclass
class ListDecl:
    """list string[3] names = [...]"""
    elem_type: str
    name: str
    dims: List[int] = field(default_factory=list)
    init: List[Any] = field(default_factory=list)


@dataclass
class MapDecl:
    """map [string,int][50] wordCount"""
    key_type: str
    val_type: str
    capacity: Optional[int]    # None = unbounded
    name: str


@dataclass
class FunctionDecl:
    name: str
    return_type: str
    params: List[Any] = field(default_factory=list)
    body: List[Any] = field(default_factory=list)


@dataclass
class Param:
    type_name: str
    name: str


@dataclass
class ObjectDecl:
    """type Node ... end type  (compiles to C struct)"""
    name: str
    parent: Optional[str] = None
    ifaces: List[str] = field(default_factory=list)
    fields: List[Any] = field(default_factory=list)
    methods: List[Any] = field(default_factory=list)


@dataclass
class ObjectField:
    type_name: str
    name: str
    default: Optional[Any] = None
    bits: Optional[int] = None    # set for bit fields: uint.bits=7 count


@dataclass
class InterfaceDecl:
    name: str
    methods: List[Any] = field(default_factory=list)


@dataclass
class FixedMember:
    name: str
    value: Optional[int] = None


@dataclass
class FixedDecl:
    """fixed Priority low=1, medium=2, high=3 end fixed"""
    name: str
    members: List[FixedMember] = field(default_factory=list)


@dataclass
class VariantField:
    """A single field in a variant (union) type"""
    type_name: str
    name: str


@dataclass
class VariantDecl:
    """variant Packet ... end variant  (compiles to C union)"""
    name: str
    fields: List[Any] = field(default_factory=list)


# ─── Statements ───────────────────────────────────────────────────────────────

@dataclass
class AssignStmt:
    target: Any
    op: str
    value: Any


@dataclass
class ReturnStmt:
    value: Optional[Any] = None


@dataclass
class PrintStmt:
    value: Any


@dataclass
class IfStmt:
    condition: Any
    body: List[Any] = field(default_factory=list)
    elif_clauses: List[Any] = field(default_factory=list)
    else_body: Optional[List[Any]] = None


@dataclass
class ElifClause:
    condition: Any
    body: List[Any] = field(default_factory=list)


@dataclass
class ForEachStmt:
    var: str
    iterable: Any
    body: List[Any] = field(default_factory=list)


@dataclass
class ForStmt:
    """for int i = 0 while i < 10 do i++  or  for i=0, i<10, i++"""
    init: Any          # VarDecl (expressive) or AssignStmt (C-style)
    condition: Any
    step: Any
    body: List[Any] = field(default_factory=list)
    c_style: bool = False


@dataclass
class WhileStmt:
    condition: Any
    body: List[Any] = field(default_factory=list)


@dataclass
class TryStmt:
    body: List[Any] = field(default_factory=list)
    catches: List[Any] = field(default_factory=list)


@dataclass
class CatchClause:
    exceptions: List[str]
    var: str
    body: List[Any] = field(default_factory=list)


@dataclass
class NewStmt:
    type_name: str
    args: List[Any] = field(default_factory=list)


@dataclass
class EscapeStmt:
    """escape — break out of loop"""
    pass


@dataclass
class ContinueStmt:
    """continue — next loop iteration"""
    pass


@dataclass
class RaiseStmt:
    """raise ExceptionType "message"  — throw an exception"""
    exc_type: str
    message: Optional[Any] = None


@dataclass
class MatchCase:
    value: Optional[Any]
    is_default: bool
    body: List[Any] = field(default_factory=list)


@dataclass
class MatchStmt:
    """match x ... end match  — no fall-through"""
    expr: Any
    cases: List[MatchCase] = field(default_factory=list)


@dataclass
class SwitchStmt:
    """iterate x ... end iterate  — fall-through (C behaviour)"""
    expr: Any
    cases: List[MatchCase] = field(default_factory=list)


# ─── Expressions ──────────────────────────────────────────────────────────────

@dataclass
class Identifier:
    name: str


@dataclass
class SuperRef:
    pass


@dataclass
class FieldAccess:
    obj: Any
    field: str


@dataclass
class CallExpr:
    func: Any
    args: List[Any] = field(default_factory=list)


@dataclass
class BinOp:
    op: str
    left: Any
    right: Any


@dataclass
class UnaryOp:
    op: str
    operand: Any


@dataclass
class PostfixOp:
    op: str
    operand: Any


@dataclass
class IndexExpr:
    array: Any
    index: Any


@dataclass
class CastExpr:
    """change(x)->int"""
    expr: Any
    target_type: str


@dataclass
class IntLit:
    value: int


@dataclass
class FloatLit:
    value: float


@dataclass
class StringLit:
    value: str


@dataclass
class BoolLit:
    value: bool


@dataclass
class NullLit:
    pass


@dataclass
class EmptyLit:
    pass


# ─── Memory ───────────────────────────────────────────────────────────────────

@dataclass
class AddressOf:
    """address(x) or address(<p>) — take the address of an expression"""
    target: Any    # expression (Identifier or other)


@dataclass
class MemAccess:
    """mem(0xDEAD0000) — read/write at a raw address"""
    address: Any


@dataclass
class DerefExpr:
    """deref(<p>) — read value at the address p holds"""
    pointer: Any


@dataclass
class SizeOf:
    """size(Type) — byte size of a type"""
    type_name: str
