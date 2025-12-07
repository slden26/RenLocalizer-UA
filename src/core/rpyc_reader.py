"""
RPYC File Reader for RenLocalizer.

This module reads compiled Ren'Py script files (.rpyc) and extracts
translatable text directly from the AST (Abstract Syntax Tree).

This provides more reliable extraction than regex-based parsing of .rpy files,
especially for:
- Text inside init python blocks
- Dynamically generated dialogue
- Complex screen definitions
- Menu items with conditions

Implementation based on Ren'Py's internal pickle format (MIT licensed).
"""

from __future__ import annotations

import logging
import pickle
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


# ============================================================================
# FAKE REN'PY MODULE SYSTEM
# ============================================================================
# We need to create fake classes that match Ren'Py's AST structure
# so pickle can deserialize the .rpyc files without the actual Ren'Py SDK


class FakeModuleRegistry:
    """Registry for fake modules needed to unpickle Ren'Py AST."""
    
    _modules: Dict[str, Any] = {}
    _classes: Dict[str, type] = {}
    
    @classmethod
    def register_module(cls, name: str, module: Any) -> None:
        cls._modules[name] = module
    
    @classmethod
    def register_class(cls, full_name: str, klass: type) -> None:
        cls._classes[full_name] = klass
    
    @classmethod
    def get_class(cls, module: str, name: str) -> Optional[type]:
        full_name = f"{module}.{name}"
        return cls._classes.get(full_name)


class FakeASTBase:
    """Base class for fake Ren'Py AST nodes."""
    
    def __init__(self):
        self.linenumber: int = 0
        self.filename: str = ""
    
    def __setstate__(self, state: dict) -> None:
        """Handle pickle deserialization."""
        if isinstance(state, dict):
            self.__dict__.update(state)
        elif isinstance(state, tuple) and len(state) == 2:
            # Some nodes use (dict, slotstate) format
            if state[0]:
                self.__dict__.update(state[0])
            if state[1]:
                self.__dict__.update(state[1])


# ============================================================================
# FAKE REN'PY AST CLASSES
# ============================================================================
# These mirror the essential Ren'Py AST node types we need for text extraction


class FakeSay(FakeASTBase):
    """Represents dialogue: character "text" """
    def __init__(self):
        super().__init__()
        self.who: Optional[str] = None  # Character speaking
        self.who_fast: bool = False  # Fast lookup for simple names
        self.what: str = ""  # The dialogue text
        self.with_: Optional[str] = None
        self.interact: bool = True
        self.attributes: Optional[tuple] = None
        self.arguments: Optional[Any] = None
        self.temporary_attributes: Optional[tuple] = None
        self.identifier: Optional[str] = None
        self.explicit_identifier: bool = False


class FakeTranslateSay(FakeSay):
    """
    A node that combines a translate and a say statement.
    This is used in newer Ren'Py versions for translatable dialogue.
    """
    def __init__(self):
        super().__init__()
        self.identifier: Optional[str] = None
        self.alternate: Optional[str] = None
        self.language: Optional[str] = None
        self.translatable: bool = True
        self.translation_relevant: bool = True
    
    @property
    def after(self):
        return getattr(self, 'next', None)
    
    @property
    def block(self) -> list:
        return []


class FakeMenu(FakeASTBase):
    """Represents menu statement with choices."""
    def __init__(self):
        super().__init__()
        self.items: List[Tuple[str, Any, Any]] = []  # (label, condition, block)
        self.set: Optional[str] = None
        self.with_: Optional[str] = None
        self.has_caption: bool = False
        self.arguments: Optional[Any] = None
        self.item_arguments: Optional[List[Any]] = None
        self.statement_start: Optional[Any] = None


class FakeLabel(FakeASTBase):
    """Represents label statement."""
    def __init__(self):
        super().__init__()
        self.name: str = ""
        self.block: List[Any] = []
        self.parameters: Optional[Any] = None
        self.hide: bool = False


class FakeInit(FakeASTBase):
    """Represents init block."""
    def __init__(self):
        super().__init__()
        self.block: List[Any] = []
        self.priority: int = 0


class FakePython(FakeASTBase):
    """Represents python/$ code block."""
    def __init__(self):
        super().__init__()
        self.code: Optional[Any] = None
        self.hide: bool = False
        self.store: str = "store"


class FakePyCode:
    """Represents Python code object inside AST."""
    def __init__(self):
        self.source: str = ""
        self.location: tuple = ()
        self.mode: str = "exec"
        self.py: Optional[int] = None
        self.bytecode: Optional[bytes] = None
    
    def __setstate__(self, state: tuple) -> None:
        if len(state) >= 4:
            _, self.source, self.location, self.mode = state[:4]
            if len(state) >= 5:
                self.py = state[4]
        self.bytecode = None


class FakePyExpr(str):
    """
    Represents Python expression in AST (subclass of str).
    In newer Ren'Py versions, includes additional fields like hashcode and col_offset.
    """
    
    def __new__(cls, s: str = "", filename: str = "", linenumber: int = 0, 
                py: int = None, hashcode: int = None, col_offset: int = 0,
                *args):  # Accept any extra arguments
        instance = str.__new__(cls, s)
        instance.filename = filename
        instance.linenumber = linenumber
        instance.py = py
        instance.hashcode = hashcode
        instance.col_offset = col_offset
        return instance
    
    def __getnewargs__(self) -> tuple:
        return (str(self),)
    
    def __reduce__(self):
        # Handle pickle properly
        return (FakePyExpr, (str(self), getattr(self, 'filename', ''), 
                            getattr(self, 'linenumber', 0)))
    
    def __setstate__(self, state):
        # Handle any extra state
        if isinstance(state, dict):
            for k, v in state.items():
                setattr(self, k, v)


class FakeScreen(FakeASTBase):
    """Represents screen definition."""
    def __init__(self):
        super().__init__()
        self.name: str = ""
        self.screen: Optional[Any] = None  # SL2 screen object
        self.parameters: Optional[Any] = None


class FakeTranslate(FakeASTBase):
    """Represents translate block."""
    def __init__(self):
        super().__init__()
        self.identifier: str = ""
        self.language: Optional[str] = None
        self.block: List[Any] = []


class FakeTranslateString(FakeASTBase):
    """Represents string translation."""
    def __init__(self):
        super().__init__()
        self.language: Optional[str] = None
        self.old: str = ""
        self.new: str = ""


class FakeTranslateBlock(FakeASTBase):
    """Represents translate block (style/python)."""
    def __init__(self):
        super().__init__()
        self.language: Optional[str] = None
        self.block: List[Any] = []


class FakeUserStatement(FakeASTBase):
    """Represents user-defined statement (like nvl, music, etc.)."""
    def __init__(self):
        super().__init__()
        self.line: str = ""
        self.parsed: Optional[Any] = None
        self.block: Optional[List[Any]] = None
        self.translatable: bool = False
        self.code_block: Optional[List[Any]] = None
        self.translation_relevant: bool = False
        self.subparses: List[Any] = []
        self.atl: Optional[Any] = None
        self.init_priority: Optional[int] = None
        self.init_offset: Optional[int] = None


class FakePostUserStatement(FakeASTBase):
    """Post-execution node for user statements."""
    def __init__(self):
        super().__init__()
        self.parent: Optional[Any] = None


class FakeIf(FakeASTBase):
    """Represents if/elif/else statement."""
    def __init__(self):
        super().__init__()
        self.entries: List[Tuple[Any, List[Any]]] = []  # (condition, block)


class FakeWhile(FakeASTBase):
    """Represents while loop."""
    def __init__(self):
        super().__init__()
        self.condition: Any = None
        self.block: List[Any] = []


class FakeDefine(FakeASTBase):
    """Represents define statement."""
    def __init__(self):
        super().__init__()
        self.varname: str = ""
        self.code: Optional[Any] = None
        self.store: str = "store"
        self.operator: str = "="
        self.index: Optional[Any] = None


class FakeDefault(FakeASTBase):
    """Represents default statement."""
    def __init__(self):
        super().__init__()
        self.varname: str = ""
        self.code: Optional[Any] = None
        self.store: str = "store"


class FakeImage(FakeASTBase):
    """Represents image statement."""
    def __init__(self):
        super().__init__()
        self.imgname: tuple = ()
        self.code: Optional[Any] = None
        self.atl: Optional[Any] = None


class FakeShow(FakeASTBase):
    """Represents show statement."""
    def __init__(self):
        super().__init__()
        self.imspec: tuple = ()
        self.atl: Optional[Any] = None


class FakeScene(FakeASTBase):
    """Represents scene statement."""
    def __init__(self):
        super().__init__()
        self.imspec: Optional[tuple] = None
        self.layer: str = "master"
        self.atl: Optional[Any] = None


class FakeHide(FakeASTBase):
    """Represents hide statement."""
    def __init__(self):
        super().__init__()
        self.imspec: tuple = ()


class FakeWith(FakeASTBase):
    """Represents with statement."""
    def __init__(self):
        super().__init__()
        self.expr: str = ""
        self.paired: Optional[str] = None


class FakeCall(FakeASTBase):
    """Represents call statement."""
    def __init__(self):
        super().__init__()
        self.label: str = ""
        self.expression: bool = False
        self.arguments: Optional[Any] = None


class FakeJump(FakeASTBase):
    """Represents jump statement."""
    def __init__(self):
        super().__init__()
        self.target: str = ""
        self.expression: bool = False


class FakeReturn(FakeASTBase):
    """Represents return statement."""
    def __init__(self):
        super().__init__()
        self.expression: Optional[str] = None


class FakePass(FakeASTBase):
    """Represents pass statement."""
    pass


class FakeGeneric(FakeASTBase):
    """Generic fallback for unknown AST nodes."""
    def __init__(self):
        super().__init__()
        self._unknown_type: str = ""


class FakeArgumentInfo:
    """Represents argument information for calls."""
    def __init__(self):
        self.arguments: List[tuple] = []
        self.extrapos: Optional[str] = None
        self.extrakw: Optional[str] = None
    
    def __setstate__(self, state):
        if isinstance(state, dict):
            self.__dict__.update(state)
        elif isinstance(state, tuple):
            if state[0]:
                self.__dict__.update(state[0])


class FakeParameterInfo:
    """Represents parameter information for definitions."""
    def __init__(self):
        self.parameters: List[tuple] = []
        self.extrapos: Optional[str] = None
        self.extrakw: Optional[str] = None
    
    def __setstate__(self, state):
        if isinstance(state, dict):
            self.__dict__.update(state)
        elif isinstance(state, tuple):
            if state[0]:
                self.__dict__.update(state[0])


class FakeATLTransformBase:
    """Base for ATL transform objects."""
    def __init__(self):
        self.atl: Optional[Any] = None
        self.parameters: Optional[Any] = None
        self.statements: List[Any] = []
    
    def __setstate__(self, state):
        if isinstance(state, dict):
            self.__dict__.update(state)


class FakeRawBlock:
    """ATL raw block."""
    def __init__(self):
        self.statements: List[Any] = []
        self.animation: bool = False
        self.loc: tuple = ()
    
    def __setstate__(self, state):
        if isinstance(state, dict):
            self.__dict__.update(state)


class FakeNode:
    """Generic node from renpy.ast.Node."""
    def __init__(self):
        self.filename: str = ""
        self.linenumber: int = 0
        self._name: Optional[Any] = None
        self.name_version: int = 0
        self.name_serial: int = 0
        self.next: Optional[Any] = None
    
    def __setstate__(self, state):
        if isinstance(state, dict):
            self.__dict__.update(state)
        elif isinstance(state, tuple) and len(state) == 2:
            # (dict, slotstate) format
            if state[0]:
                self.__dict__.update(state[0])
            if state[1]:
                # Handle slot state (cslots)
                self.__dict__.update(state[1])


# SL2 (Screen Language 2) fake classes
class FakeSLScreen:
    """Screen Language 2 screen object."""
    def __init__(self):
        self.name: str = ""
        self.children: List[Any] = []
        self.keyword: List[tuple] = []
        self.parameters: Optional[Any] = None
        self.location: tuple = ()
    
    def __setstate__(self, state: dict) -> None:
        if isinstance(state, dict):
            self.__dict__.update(state)


class FakeSLDisplayable:
    """Screen Language displayable (text, textbutton, etc.)."""
    def __init__(self):
        self.displayable: Any = None
        self.style: Optional[str] = None
        self.positional: List[str] = []
        self.keyword: List[tuple] = []
        self.children: List[Any] = []
        self.location: tuple = ()
    
    def __setstate__(self, state: dict) -> None:
        if isinstance(state, dict):
            self.__dict__.update(state)


class FakeSLIf:
    """Screen Language if statement."""
    def __init__(self):
        self.entries: List[tuple] = []
        self.location: tuple = ()
    
    def __setstate__(self, state: dict) -> None:
        if isinstance(state, dict):
            self.__dict__.update(state)


class FakeSLFor:
    """Screen Language for loop."""
    def __init__(self):
        self.variable: str = ""
        self.expression: str = ""
        self.children: List[Any] = []
        self.location: tuple = ()
    
    def __setstate__(self, state: dict) -> None:
        if isinstance(state, dict):
            self.__dict__.update(state)


class FakeSLBlock:
    """Screen Language block."""
    def __init__(self):
        self.children: List[Any] = []
        self.keyword: List[tuple] = []
        self.location: tuple = ()
    
    def __setstate__(self, state: dict) -> None:
        if isinstance(state, dict):
            self.__dict__.update(state)


class FakeSLUse:
    """Screen Language use statement."""
    def __init__(self):
        self.target: str = ""
        self.args: Optional[Any] = None
        self.block: Optional[Any] = None
        self.location: tuple = ()
    
    def __setstate__(self, state: dict) -> None:
        if isinstance(state, dict):
            self.__dict__.update(state)


class FakeSLPython:
    """Screen Language python block."""
    def __init__(self):
        self.code: Optional[Any] = None
        self.location: tuple = ()
    
    def __setstate__(self, state: dict) -> None:
        if isinstance(state, dict):
            self.__dict__.update(state)


class FakeSLDefault:
    """Screen Language default statement."""
    def __init__(self):
        self.variable: str = ""
        self.expression: str = ""
        self.location: tuple = ()
    
    def __setstate__(self, state: dict) -> None:
        if isinstance(state, dict):
            self.__dict__.update(state)


# Revertable containers from renpy.revertable / renpy.python
class FakeRevertableList(list):
    """Ren'Py revertable list."""
    pass


class FakeRevertableDict(dict):
    """Ren'Py revertable dict."""
    pass


class FakeRevertableSet(set):
    """Ren'Py revertable set."""
    def __setstate__(self, state):
        if isinstance(state, tuple):
            self.update(state[0].keys() if isinstance(state[0], dict) else state[0])
        else:
            self.update(state)


class FakeSentinel:
    """Ren'Py sentinel object."""
    def __init__(self, name: str = ""):
        self.name = name


# ============================================================================
# CUSTOM UNPICKLER
# ============================================================================


class RenpyUnpickler(pickle.Unpickler):
    """
    Custom unpickler that redirects Ren'Py classes to our fake implementations.
    """
    
    # Mapping of Ren'Py class paths to our fake classes
    CLASS_MAP = {
        # Core AST nodes (renpy.ast)
        ("renpy.ast", "Say"): FakeSay,
        ("renpy.ast", "TranslateSay"): FakeTranslateSay,  # New: combined translate+say
        ("renpy.ast", "Menu"): FakeMenu,
        ("renpy.ast", "Label"): FakeLabel,
        ("renpy.ast", "Init"): FakeInit,
        ("renpy.ast", "Python"): FakePython,
        ("renpy.ast", "EarlyPython"): FakePython,
        ("renpy.ast", "PyCode"): FakePyCode,
        ("renpy.ast", "Screen"): FakeScreen,
        ("renpy.ast", "Translate"): FakeTranslate,
        ("renpy.ast", "TranslateString"): FakeTranslateString,
        ("renpy.ast", "TranslateBlock"): FakeTranslateBlock,
        ("renpy.ast", "TranslateEarlyBlock"): FakeTranslateBlock,
        ("renpy.ast", "TranslatePython"): FakeTranslateBlock,
        ("renpy.ast", "EndTranslate"): FakePass,
        ("renpy.ast", "UserStatement"): FakeUserStatement,
        ("renpy.ast", "PostUserStatement"): FakePostUserStatement,  # New
        ("renpy.ast", "If"): FakeIf,
        ("renpy.ast", "While"): FakeWhile,
        ("renpy.ast", "Define"): FakeDefine,
        ("renpy.ast", "Default"): FakeDefault,
        ("renpy.ast", "Image"): FakeImage,
        ("renpy.ast", "Show"): FakeShow,
        ("renpy.ast", "Scene"): FakeScene,
        ("renpy.ast", "Hide"): FakeHide,
        ("renpy.ast", "With"): FakeWith,
        ("renpy.ast", "Call"): FakeCall,
        ("renpy.ast", "Jump"): FakeJump,
        ("renpy.ast", "Return"): FakeReturn,
        ("renpy.ast", "Pass"): FakePass,
        ("renpy.ast", "Transform"): FakeGeneric,
        ("renpy.ast", "Style"): FakeGeneric,
        ("renpy.ast", "Testcase"): FakeGeneric,
        ("renpy.ast", "Camera"): FakeGeneric,
        ("renpy.ast", "ShowLayer"): FakeGeneric,
        ("renpy.ast", "RPY"): FakeGeneric,
        ("renpy.ast", "Node"): FakeNode,  # Base node
        
        # PyExpr locations
        ("renpy.ast", "PyExpr"): FakePyExpr,
        ("renpy.astsupport", "PyExpr"): FakePyExpr,
        
        # Parameter and Argument info
        ("renpy.ast", "ArgumentInfo"): FakeArgumentInfo,
        ("renpy.parameter", "ArgumentInfo"): FakeArgumentInfo,
        ("renpy.parameter", "ParameterInfo"): FakeParameterInfo,
        ("renpy.ast", "ParameterInfo"): FakeParameterInfo,
        ("renpy.parameter", "Parameter"): FakeGeneric,
        ("renpy.parameter", "Signature"): FakeGeneric,
        
        # ATL (Animation and Transformation Language)
        ("renpy.atl", "RawBlock"): FakeRawBlock,
        ("renpy.atl", "RawMultipurpose"): FakeGeneric,
        ("renpy.atl", "RawChild"): FakeGeneric,
        ("renpy.atl", "RawChoice"): FakeGeneric,
        ("renpy.atl", "RawParallel"): FakeGeneric,
        ("renpy.atl", "RawRepeat"): FakeGeneric,
        ("renpy.atl", "RawTime"): FakeGeneric,
        ("renpy.atl", "RawOn"): FakeGeneric,
        ("renpy.atl", "RawEvent"): FakeGeneric,
        ("renpy.atl", "RawFunction"): FakeGeneric,
        ("renpy.atl", "RawContainsExpr"): FakeGeneric,
        
        # Screen Language 2 (renpy.sl2.slast)
        ("renpy.sl2.slast", "SLScreen"): FakeSLScreen,
        ("renpy.sl2.slast", "SLDisplayable"): FakeSLDisplayable,
        ("renpy.sl2.slast", "SLIf"): FakeSLIf,
        ("renpy.sl2.slast", "SLShowIf"): FakeSLIf,
        ("renpy.sl2.slast", "SLFor"): FakeSLFor,
        ("renpy.sl2.slast", "SLBlock"): FakeSLBlock,
        ("renpy.sl2.slast", "SLUse"): FakeSLUse,
        ("renpy.sl2.slast", "SLPython"): FakeSLPython,
        ("renpy.sl2.slast", "SLDefault"): FakeSLDefault,
        ("renpy.sl2.slast", "SLPass"): FakeGeneric,
        ("renpy.sl2.slast", "SLBreak"): FakeGeneric,
        ("renpy.sl2.slast", "SLContinue"): FakeGeneric,
        ("renpy.sl2.slast", "SLTransclude"): FakeGeneric,
        ("renpy.sl2.slast", "SLNull"): FakeGeneric,
        ("renpy.sl2.slast", "SLUseTransform"): FakeGeneric,
        
        # Revertable containers
        ("renpy.revertable", "RevertableList"): FakeRevertableList,
        ("renpy.revertable", "RevertableDict"): FakeRevertableDict,
        ("renpy.revertable", "RevertableSet"): FakeRevertableSet,
        ("renpy.revertable", "RevertableObject"): FakeGeneric,
        ("renpy.python", "RevertableList"): FakeRevertableList,
        ("renpy.python", "RevertableDict"): FakeRevertableDict,
        ("renpy.python", "RevertableSet"): FakeRevertableSet,
        ("renpy.python", "RevertableObject"): FakeGeneric,
        
        # CSlots support (Ren'Py 8.x+)
        ("renpy.cslots", "Object"): FakeGeneric,
        
        # Character and other display
        ("renpy.character", "ADVCharacter"): FakeGeneric,
        ("renpy.character", "Character"): FakeGeneric,
        
        # Lexer/Parser support
        ("renpy.lexer", "SubParse"): FakeGeneric,
        
        # Audio
        ("renpy.audio.audio", "AudioData"): FakeGeneric,
        ("renpy.audio.music", "MusicContext"): FakeGeneric,
        
        # Display
        ("renpy.display.transform", "ATLTransform"): FakeATLTransformBase,
        ("renpy.display.motion", "ATLTransform"): FakeATLTransformBase,
        
        # Object/Other
        ("renpy.object", "Sentinel"): FakeSentinel,
        ("renpy.object", "Object"): FakeGeneric,
        
        # Store
        ("renpy.store", "object"): FakeGeneric,
        ("store", "object"): FakeGeneric,
        
        # Python 2 compatibility (fix_imports issue)
        ("__builtin__", "set"): set,
        ("__builtin__", "frozenset"): frozenset,
        
        # Collections
        ("collections", "OrderedDict"): dict,
    }
    
    def find_class(self, module: str, name: str) -> type:
        """Override to redirect Ren'Py classes to our fakes."""
        key = (module, name)
        
        if key in self.CLASS_MAP:
            return self.CLASS_MAP[key]
        
        # For unknown renpy classes, return generic handler
        if module.startswith("renpy."):
            logger.debug(f"Unknown Ren'Py class: {module}.{name}")
            return FakeGeneric
        
        # For store classes (game-defined)
        if module.startswith("store.") or module == "store":
            logger.debug(f"Store class: {module}.{name}")
            return FakeGeneric
        
        # For standard library, use default behavior
        try:
            return super().find_class(module, name)
        except (ModuleNotFoundError, AttributeError):
            logger.debug(f"Could not find class: {module}.{name}")
            return FakeGeneric


# ============================================================================
# RPYC FILE READER
# ============================================================================


@dataclass
class RpycHeader:
    """Header information from .rpyc file."""
    version: int  # 1 or 2
    slot_count: int
    slots: Dict[int, Tuple[int, int]]  # slot_id -> (start, length)


class RpycReadError(Exception):
    """Error reading .rpyc file."""
    pass


def read_rpyc_header(data: bytes) -> RpycHeader:
    """
    Parse .rpyc file header.
    
    RPYC v2 format:
    - 10 bytes: "RENPY RPC2"
    - Repeated: 12 bytes (slot_id, start, length) as little-endian uint32
    - End when slot_id == 0
    
    RPYC v1 format:
    - Just zlib-compressed pickle data (no header)
    """
    if not data.startswith(b"RENPY RPC2"):
        # RPYC v1 - no header, just compressed data
        return RpycHeader(version=1, slot_count=0, slots={})
    
    # RPYC v2
    position = 10
    slots = {}
    
    while position + 12 <= len(data):
        slot_id, start, length = struct.unpack("<III", data[position:position + 12])
        
        if slot_id == 0:
            break
        
        slots[slot_id] = (start, length)
        position += 12
    
    return RpycHeader(version=2, slot_count=len(slots), slots=slots)


def read_rpyc_file(file_path: Union[str, Path]) -> List[Any]:
    """
    Read .rpyc file and return AST nodes.
    
    Args:
        file_path: Path to .rpyc file
        
    Returns:
        List of AST nodes
        
    Raises:
        RpycReadError: If file cannot be read/parsed
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise RpycReadError(f"File not found: {file_path}")
    
    if file_path.suffix.lower() not in ('.rpyc', '.rpymc'):
        raise RpycReadError(f"Not an RPYC file: {file_path}")
    
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
    except IOError as e:
        raise RpycReadError(f"Cannot read file: {e}")
    
    header = read_rpyc_header(data)
    
    # Get the compressed data
    if header.version == 1:
        compressed = data
    else:
        if 1 not in header.slots:
            raise RpycReadError("No data slot found in RPYC v2 file")
        
        start, length = header.slots[1]
        compressed = data[start:start + length]
    
    # Decompress
    try:
        decompressed = zlib.decompress(compressed)
    except zlib.error as e:
        raise RpycReadError(f"Decompression failed: {e}")
    
    # Unpickle using our custom unpickler
    try:
        import io
        unpickler = RenpyUnpickler(io.BytesIO(decompressed))
        result = unpickler.load()
        
        # Result is typically (data, stmts) tuple
        if isinstance(result, tuple) and len(result) >= 2:
            return result[1]  # Return statements
        
        return result if isinstance(result, list) else [result]
        
    except Exception as e:
        raise RpycReadError(f"Unpickle failed: {e}")


# ============================================================================
# AST TEXT EXTRACTOR
# ============================================================================


@dataclass
class ExtractedText:
    """Represents text extracted from AST."""
    text: str
    line_number: int
    source_file: str
    text_type: str  # 'dialogue', 'menu', 'ui', 'string', etc.
    character: str = ""
    context: str = ""


class ASTTextExtractor:
    """
    Extracts translatable text from Ren'Py AST nodes.
    """
    
    def __init__(self):
        self.extracted: List[ExtractedText] = []
        self.seen_texts: Set[str] = set()
        self.current_file: str = ""
    
    def extract_from_file(self, file_path: Union[str, Path]) -> List[ExtractedText]:
        """
        Extract all translatable text from an .rpyc file.
        
        Args:
            file_path: Path to .rpyc file
            
        Returns:
            List of ExtractedText objects
        """
        self.extracted = []
        self.seen_texts = set()
        self.current_file = str(file_path)
        
        try:
            ast_nodes = read_rpyc_file(file_path)
            self._walk_nodes(ast_nodes)
        except RpycReadError as e:
            logger.error(f"Failed to read {file_path}: {e}")
        
        return self.extracted
    
    def _add_text(
        self,
        text: str,
        line_number: int,
        text_type: str,
        character: str = "",
        context: str = ""
    ) -> None:
        """Add extracted text if it's meaningful."""
        if not text or not text.strip():
            return
        
        # Skip duplicates
        if text in self.seen_texts:
            return
        
        # Skip technical strings
        if self._is_technical_string(text):
            return
        
        self.seen_texts.add(text)
        self.extracted.append(ExtractedText(
            text=text,
            line_number=line_number,
            source_file=self.current_file,
            text_type=text_type,
            character=character,
            context=context
        ))
    
    def _is_technical_string(self, text: str) -> bool:
        """Check if string is technical (not translatable)."""
        import re
        
        text_strip = text.strip()
        text_lower = text_strip.lower()
        
        # Skip if too short
        if len(text_strip) < 2:
            return True
        
        # Skip file paths
        extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.mp3', '.ogg', 
                      '.wav', '.ttf', '.otf', '.rpy', '.rpyc', '.json')
        if any(text_lower.endswith(ext) for ext in extensions):
            return True
        
        # Skip paths
        if text_strip.startswith(('images/', 'audio/', 'gui/', 'fonts/')):
            return True
        
        # Skip color codes
        if re.match(r'^#[0-9a-fA-F]{3,8}$', text_strip):
            return True
        
        # Skip pure numbers
        if re.match(r'^-?\d+\.?\d*$', text_strip):
            return True
        
        # Skip snake_case identifiers
        if re.match(r'^[a-z][a-z0-9]*(_[a-z0-9]+)+$', text_strip):
            return True
        
        # Must contain at least one letter
        if not re.search(r'[a-zA-Z\u00C0-\u024F\u0400-\u04FF]', text):
            return True
        
        return False
    
    def _walk_nodes(self, nodes: List[Any], context: str = "") -> None:
        """Recursively walk AST nodes and extract text."""
        if not isinstance(nodes, (list, tuple)):
            nodes = [nodes]
        
        for node in nodes:
            self._process_node(node, context)
    
    def _process_node(self, node: Any, context: str = "") -> None:
        """Process a single AST node."""
        if node is None:
            return
        
        node_type = type(node).__name__
        
        # TranslateSay (combined translate+say in newer Ren'Py)
        if isinstance(node, FakeTranslateSay):
            character = getattr(node, 'who', '') or ""
            what = getattr(node, 'what', '')
            if what:
                self._add_text(
                    what,
                    getattr(node, 'linenumber', 0),
                    'dialogue',
                    character=character,
                    context=f"translate:{getattr(node, 'identifier', '')}"
                )
        
        # Dialogue (Say statement)
        elif isinstance(node, FakeSay):
            character = getattr(node, 'who', '') or ""
            what = getattr(node, 'what', '')
            if what:
                self._add_text(
                    what,
                    getattr(node, 'linenumber', 0),
                    'dialogue',
                    character=character,
                    context=context
                )
        
        # Menu choices
        elif isinstance(node, FakeMenu):
            for item in getattr(node, 'items', []):
                if isinstance(item, (list, tuple)) and len(item) >= 1:
                    label = item[0]
                    if label and isinstance(label, str):
                        self._add_text(
                            label,
                            getattr(node, 'linenumber', 0),
                            'menu',
                            context=context
                        )
                    # Process menu item block
                    if len(item) >= 3 and item[2]:
                        self._walk_nodes(item[2], f"{context}/menu_item")
        
        # Label block
        elif isinstance(node, FakeLabel):
            label_name = getattr(node, 'name', '')
            new_context = f"label:{label_name}"
            if getattr(node, 'block', None):
                self._walk_nodes(node.block, new_context)
        
        # Init block
        elif isinstance(node, FakeInit):
            if getattr(node, 'block', None):
                self._walk_nodes(node.block, f"{context}/init")
        
        # If statement
        elif isinstance(node, FakeIf):
            for entry in getattr(node, 'entries', []):
                if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                    if entry[1]:
                        self._walk_nodes(entry[1], context)
        
        # While loop
        elif isinstance(node, FakeWhile):
            if getattr(node, 'block', None):
                self._walk_nodes(node.block, context)
        
        # Translate block - extract both old and new
        elif isinstance(node, FakeTranslateString):
            if getattr(node, 'old', ''):
                self._add_text(
                    node.old,
                    getattr(node, 'linenumber', 0),
                    'string',
                    context='translate'
                )
        
        # Translate (dialogue) block
        elif isinstance(node, FakeTranslate):
            block = getattr(node, 'block', None)
            if block:
                lang = getattr(node, 'language', None)
                self._walk_nodes(block, f"translate:{lang or 'None'}")
        
        # Screen
        elif isinstance(node, FakeScreen):
            screen_obj = getattr(node, 'screen', None)
            screen_name = getattr(node, 'name', getattr(screen_obj, 'name', 'unknown') if screen_obj else 'unknown')
            if screen_obj:
                self._process_screen_node(screen_obj, f"screen:{screen_name}")
        
        # Define statement - check for translatable strings
        elif isinstance(node, FakeDefine):
            code = getattr(node, 'code', None)
            if code and hasattr(code, 'source'):
                self._extract_strings_from_code(code.source, getattr(node, 'linenumber', 0))
        
        # Python block - look for strings
        elif isinstance(node, FakePython):
            code = getattr(node, 'code', None)
            if code and hasattr(code, 'source'):
                self._extract_strings_from_code(code.source, getattr(node, 'linenumber', 0))
        
        # User statement - may contain text
        elif isinstance(node, FakeUserStatement):
            line = getattr(node, 'line', '')
            if line:
                self._extract_strings_from_line(line, getattr(node, 'linenumber', 0))
        
        # Generic block handling
        elif hasattr(node, 'block') and node.block:
            self._walk_nodes(node.block, context)
    
    def _process_screen_node(self, node: Any, context: str = "") -> None:
        """Process Screen Language nodes."""
        if node is None:
            return
        
        # SL2 Screen
        if isinstance(node, FakeSLScreen):
            # Process children
            for child in getattr(node, 'children', []):
                self._process_screen_node(child, context)
        
        # SL2 Displayable (text, textbutton, etc.)
        elif isinstance(node, FakeSLDisplayable):
            # Check positional arguments for text
            for pos in getattr(node, 'positional', []):
                if isinstance(pos, str) and pos.strip():
                    # Remove quotes if present
                    text = pos.strip()
                    if (text.startswith('"') and text.endswith('"')) or \
                       (text.startswith("'") and text.endswith("'")):
                        text = text[1:-1]
                    
                    if text and not self._is_technical_string(text):
                        self._add_text(
                            text,
                            getattr(node, 'location', (0, 0))[1] if hasattr(node, 'location') else 0,
                            'ui',
                            context=context
                        )
            
            # Check keyword arguments for text-related properties
            for kw in getattr(node, 'keyword', []):
                if isinstance(kw, (list, tuple)) and len(kw) >= 2:
                    key, value = kw[0], kw[1]
                    if key in ('text', 'alt', 'tooltip', 'caption', 'title') and value:
                        if isinstance(value, str):
                            self._extract_strings_from_line(value, 0)
                        elif isinstance(value, FakePyExpr):
                            self._extract_strings_from_code(str(value), 0)
            
            # Process children
            for child in getattr(node, 'children', []):
                self._process_screen_node(child, context)
        
        # SL2 If/ShowIf
        elif isinstance(node, FakeSLIf):
            for entry in getattr(node, 'entries', []):
                if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                    self._process_screen_node(entry[1], context)
        
        # SL2 For
        elif isinstance(node, FakeSLFor):
            for child in getattr(node, 'children', []):
                self._process_screen_node(child, context)
        
        # SL2 Block
        elif isinstance(node, FakeSLBlock):
            for child in getattr(node, 'children', []):
                self._process_screen_node(child, context)
        
        # SL2 Use
        elif isinstance(node, FakeSLUse):
            block = getattr(node, 'block', None)
            if block:
                self._process_screen_node(block, context)
    
    def _extract_strings_from_code(self, code: str, line_number: int) -> None:
        """Extract string literals from Python code with enhanced pattern matching."""
        import re
        
        # Match _("text") pattern - standard translation function
        translatable_pattern = r'_\s*\(\s*["\'](.+?)["\']\s*\)'
        for match in re.finditer(translatable_pattern, code):
            text = match.group(1)
            self._add_text(text, line_number, 'string', context='python/_')
        
        # Match __("text") pattern - double underscore translation
        double_under_pattern = r'__\s*\(\s*["\'](.+?)["\']\s*\)'
        for match in re.finditer(double_under_pattern, code):
            text = match.group(1)
            self._add_text(text, line_number, 'string', context='python/__')
        
        # Match renpy.notify("text") pattern
        notify_pattern = r'renpy\.notify\s*\(\s*["\'](.+?)["\']\s*\)'
        for match in re.finditer(notify_pattern, code):
            text = match.group(1)
            self._add_text(text, line_number, 'ui', context='notify')
        
        # Match Character("Name", ...) pattern
        char_pattern = r'Character\s*\(\s*["\'](.+?)["\']\s*[\),]'
        for match in re.finditer(char_pattern, code):
            text = match.group(1)
            self._add_text(text, line_number, 'string', context='character_define')
        
        # Match DynamicCharacter("Name", ...) pattern
        dyn_char_pattern = r'DynamicCharacter\s*\(\s*["\'](.+?)["\']\s*[\),]'
        for match in re.finditer(dyn_char_pattern, code):
            text = match.group(1)
            self._add_text(text, line_number, 'string', context='character_define')
        
        # Match renpy.say(who, "text") pattern
        say_pattern = r'renpy\.say\s*\([^,]*,\s*["\'](.+?)["\']\s*[\),]'
        for match in re.finditer(say_pattern, code):
            text = match.group(1)
            self._add_text(text, line_number, 'dialogue', context='python/say')
        
        # Match Text("content") pattern (displayable)
        text_display_pattern = r'Text\s*\(\s*["\'](.+?)["\']\s*[\),]'
        for match in re.finditer(text_display_pattern, code):
            text = match.group(1)
            self._add_text(text, line_number, 'ui', context='displayable')
        
        # Match config.name = "Game Name" pattern
        config_name_pattern = r'config\.(name|version)\s*=\s*["\'](.+?)["\']'
        for match in re.finditer(config_name_pattern, code):
            text = match.group(2)
            self._add_text(text, line_number, 'string', context='config')
        
        # Match gui.text_* = "..." patterns
        gui_text_pattern = r'gui\.\w*text\w*\s*=\s*["\'](.+?)["\']'
        for match in re.finditer(gui_text_pattern, code):
            text = match.group(1)
            self._add_text(text, line_number, 'ui', context='gui')
    
    def _extract_strings_from_line(self, line: str, line_number: int) -> None:
        """Extract string literals from a line of code."""
        import re
        
        # First check for common translatable patterns
        self._extract_strings_from_code(line, line_number)
        
        # Match quoted strings for user statements like "nvl clear"
        # Only for lines that might contain displayable text
        if any(kw in line.lower() for kw in ['text', 'label', 'button', 'tooltip', 'caption', 'title']):
            string_pattern = r'"([^"\\]|\\.)*"|\'([^\'\\]|\\.)*\''
            for match in re.finditer(string_pattern, line):
                text = match.group(0)[1:-1]  # Remove quotes
                if text and len(text) >= 3 and not self._is_technical_string(text):
                    self._add_text(text, line_number, 'string')


# ============================================================================
# PUBLIC API
# ============================================================================


def extract_texts_from_rpyc(
    file_path: Union[str, Path]
) -> List[Dict[str, Any]]:
    """
    Extract translatable texts from a .rpyc file.
    
    Args:
        file_path: Path to .rpyc file
        
    Returns:
        List of dicts with text, line_number, text_type, etc.
    """
    extractor = ASTTextExtractor()
    results = extractor.extract_from_file(file_path)
    
    return [
        {
            'text': r.text,
            'line_number': r.line_number,
            'text_type': r.text_type,
            'character': r.character,
            'context_path': [r.context] if r.context else [],
            'source_file': r.source_file,
            'is_rpyc': True,
        }
        for r in results
    ]


def extract_texts_from_rpyc_directory(
    directory: Union[str, Path],
    recursive: bool = True
) -> Dict[Path, List[Dict[str, Any]]]:
    """
    Extract translatable texts from all .rpyc files in a directory.
    
    Args:
        directory: Directory path (should be the game folder directly)
        recursive: Search subdirectories
        
    Returns:
        Dict mapping file paths to extracted texts
    """
    directory = Path(directory)
    results = {}
    
    # Use directory directly - caller should pass game folder
    search_root = directory
    
    # Find .rpyc files
    pattern = "**/*.rpyc" if recursive else "*.rpyc"
    rpyc_files = list(search_root.glob(pattern))
    
    # Exclude tl/ folder and renpy engine files
    # We check relative path to avoid filtering by parent directory names
    filtered_files = []
    for f in rpyc_files:
        try:
            rel_path = f.relative_to(search_root)
            rel_str = str(rel_path).lower()
            # Skip if in tl/ or renpy/ subdirectory
            if rel_str.startswith('tl\\') or rel_str.startswith('tl/'):
                continue
            if rel_str.startswith('renpy\\') or rel_str.startswith('renpy/'):
                continue
            if '\\tl\\' in rel_str or '/tl/' in rel_str:
                continue
            if '\\renpy\\' in rel_str or '/renpy/' in rel_str:
                continue
            filtered_files.append(f)
        except ValueError:
            # If relative_to fails, include the file
            filtered_files.append(f)
    
    rpyc_files = filtered_files
    
    logger.info(f"Found {len(rpyc_files)} .rpyc files")
    
    for rpyc_file in rpyc_files:
        try:
            texts = extract_texts_from_rpyc(rpyc_file)
            results[rpyc_file] = texts
            logger.debug(f"Extracted {len(texts)} texts from {rpyc_file}")
        except Exception as e:
            logger.error(f"Error extracting from {rpyc_file}: {e}")
            results[rpyc_file] = []
    
    total = sum(len(texts) for texts in results.values())
    logger.info(f"Total extracted from RPYC: {total} texts from {len(results)} files")
    
    return results


# Quick test
if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.DEBUG)
    
    if len(sys.argv) > 1:
        path = sys.argv[1]
        if Path(path).is_file():
            texts = extract_texts_from_rpyc(path)
            for t in texts:
                print(f"[{t['text_type']}] {t['text'][:50]}...")
        else:
            results = extract_texts_from_rpyc_directory(path)
            for file, texts in results.items():
                print(f"\n{file.name}: {len(texts)} texts")
                for t in texts[:5]:
                    print(f"  [{t['text_type']}] {t['text'][:40]}...")
