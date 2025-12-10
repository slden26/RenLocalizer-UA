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

# Import the whitelist and parser utilities from parser.py
from .parser import DATA_KEY_WHITELIST, RenPyParser
import ast
import re
import io
import traceback
import binascii
import sys


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
        elif isinstance(state, tuple):
            # Some nodes use (dict, slotstate) or longer tuples.
            # Merge any dict parts into the object's __dict__.
            for part in state:
                if isinstance(part, dict):
                    self.__dict__.update(part)


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
        try:
            if isinstance(state, dict):
                # Older pickles may supply a dict
                self.__dict__.update(state)
            elif isinstance(state, tuple) or isinstance(state, list):
                # Some pickles provide (something, source, location, mode, py, ...)
                if len(state) >= 4:
                    # Safely assign known positions
                    # skip first element if it's not the source
                    possible = state[:5]
                    # Find the first element that looks like source (string)
                    for elem in possible:
                        if isinstance(elem, str) and elem and elem != possible[0]:
                            # prefer the second position for source when structure matches
                            break
                    # Best-effort assignment based on common layouts
                    try:
                        _, self.source, self.location, self.mode = state[:4]
                    except Exception:
                        # Fallback: try to find string and assign
                        for part in state:
                            if isinstance(part, str):
                                self.source = part
                                break
                        # location/mode may remain defaults
                    if len(state) >= 5:
                        try:
                            self.py = state[4]
                        except Exception:
                            pass
        except Exception:
            # Be conservative on unknown formats
            pass
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
        elif isinstance(state, tuple) or isinstance(state, list):
            # Some pickles provide a tuple/list whose first element contains the dict state
            # Be lenient: if the first element is a dict, merge it; otherwise merge any dict parts
            if state:
                if isinstance(state[0], dict):
                    self.__dict__.update(state[0])
                else:
                    for part in state:
                        if isinstance(part, dict):
                            self.__dict__.update(part)


class FakeParameterInfo:
    """Represents parameter information for definitions."""
    def __init__(self):
        self.parameters: List[tuple] = []
        self.extrapos: Optional[str] = None
        self.extrakw: Optional[str] = None
    
    def __setstate__(self, state):
        if isinstance(state, dict):
            self.__dict__.update(state)
        elif isinstance(state, tuple) or isinstance(state, list):
            # Be lenient: merge any dict parts from tuple/list state
            for part in state:
                if isinstance(part, dict):
                    self.__dict__.update(part)


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
        elif isinstance(state, tuple) or isinstance(state, list):
            # (dict, slotstate, ...) format - merge any dict parts
            for part in state:
                if isinstance(part, dict):
                    self.__dict__.update(part)


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


class FakeOrderedDict(dict):
    """Tolerant OrderedDict replacement for unpickling.

    Some pickles encode ordered mappings as a sequence of pairs or slightly
    different structures. The standard `dict.update()` can raise
    "too many values to unpack (expected 2)" when an item tuple contains
    more than two elements. This class accepts several state shapes and
    only consumes the first two elements of each pair when present.
    """
    def __setstate__(self, state):
        # If state is a mapping, update normally
        if isinstance(state, dict):
            self.update(state)
            return

        # If state is tuple/list, it may be: (items_list,) or list(items)
        if isinstance(state, (tuple, list)):
            # If it's a one-element tuple whose element is a dict, handle it
            if len(state) == 1 and isinstance(state[0], dict):
                self.update(state[0])
                return

            # Walk through sequence and accept pairs (or longer tuples where
            # the first two elements are key/value)
            for part in state:
                if isinstance(part, dict):
                    self.update(part)
                elif isinstance(part, (list, tuple)):
                    # If it's a sequence of (k,v,...) or ((k,v), (k2,v2))
                    # try to handle both
                    # If it's a flat list of 2-tuples, update will work below
                    if all(isinstance(el, (list, tuple)) and len(el) >= 2 for el in part):
                        for el in part:
                            k, v = el[0], el[1]
                            self[k] = v
                    elif len(part) >= 2 and not any(isinstance(el, (list, tuple, dict)) for el in part):
                        # single pair-like tuple possibly with extras
                        self[part[0]] = part[1]
                else:
                    # Unknown element, ignore
                    continue

            return

        # Fallback: try to update directly (may raise) but catch exceptions
        try:
            self.update(state)
        except Exception:
            # Last resort - ignore problematic state
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
        ("collections", "OrderedDict"): FakeOrderedDict,
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
    # Eğer RPC2 değilse hemen pes etme, belki de RPC3'tür ama yapısı benzerdir.
    if data.startswith(b"RENPY RPC"):
        # RPC2 veya RPC3 fark etmeksizin işlemeyi dene
        pass
    elif not data.startswith(b"RENPY RPC2"):
        # V1 (Sıkıştırılmış pickle) varsayımı
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
        unpickler = RenpyUnpickler(io.BytesIO(decompressed))
        result = unpickler.load()

        # Result is typically (data, stmts) tuple
        if isinstance(result, tuple) and len(result) >= 2:
            return result[1]  # Return statements

        return result if isinstance(result, list) else [result]

    except Exception as e:
        # Log detailed diagnostics to help identify problematic pickle state
        tb = traceback.format_exc()
        # Show header/slot summary when available
        try:
            slot_info = getattr(header, 'slots', None)
        except Exception:
            slot_info = None

        # Provide a hex snippet of the decompressed pickle to aid debugging
        try:
            snippet = decompressed[:512]
            snippet_hex = binascii.hexlify(snippet).decode('ascii')
        except Exception:
            snippet_hex = repr(decompressed[:200])

        msg = (
            f"Unpickle failed for {file_path}: {e}\n"
            f"Header slots: {slot_info}\n"
            f"Traceback:\n{tb}\n"
            f"Decompressed (first 512 bytes, hex): {snippet_hex}"
        )

        # Log via logger and also write to stderr as a fallback so Tee-Object captures it
        try:
            logger.error(msg)
        except Exception:
            pass

        try:
            # Use errors='replace' to avoid UnicodeEncodeError when console encoding is limited
            sys.stderr.write(msg + "\n")
        except Exception:
            try:
                sys.stderr.write(msg.encode('utf-8', errors='replace').decode('utf-8', errors='replace') + "\n")
            except Exception:
                pass

        raise RpycReadError(
            f"Unpickle failed: {e}. See application logs for details (traceback and decompressed snippet)."
        )


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
    placeholder_map: Dict[str, str] = None


class ASTTextExtractor:
    """
    Extracts translatable text from Ren'Py AST nodes.
    """
    
    def __init__(self):
        self.extracted: List[ExtractedText] = []
        # Map text -> (context, ExtractedText) to handle deduplication and prefer more specific
        self.seen_map: Dict[str, ExtractedText] = {}
        self.current_file: str = ""
        # Copy whitelist from parser for context-aware extraction
        self.DATA_KEY_WHITELIST = DATA_KEY_WHITELIST
        # Instantiate parser once for performance (placeholder preservation, etc.)
        self.parser = RenPyParser()
    
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
            logger.exception(f"Failed to read {file_path}: {e}")
        
        return self.extracted
    
    def _add_text(
        self,
        text: str,
        line_number: int,
        text_type: str,
        character: str = "",
        context: str = "",
        placeholder_map: Dict[str, str] = None,
    ) -> None:
        """Add extracted text if it's meaningful."""
        if not text or not text.strip():
            return
        # Duplicate handling: if we already have this text, prefer the one with variable context or data_string
        existing = self.seen_map.get(text)
        # If existing has same (text, context) skip
        if existing:
            # If existing has no context but new context exists, replace existing
            if context and not existing.context:
                # Remove existing from list
                try:
                    self.extracted.remove(existing)
                except ValueError:
                    pass
                # continue to add new
            else:
                return
        
        # Skip technical strings
        if self._is_technical_string(text, context):
            return
        
        # store in seen_map
        self.seen_map[text] = ExtractedText(
            text=text,
            line_number=line_number,
            source_file=self.current_file,
            text_type=text_type,
            character=character,
            context=context,
            placeholder_map=placeholder_map or {}
        )
        self.extracted.append(self.seen_map[text])
    
    def _is_technical_string(self, text: str, context: str = "") -> bool:
        """Check if string is technical (not translatable)."""
        import re
        p = self.parser

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

        # Check against the whitelist
        if context and not any(key in context for key in DATA_KEY_WHITELIST):
            return True

        return False

    def _extract_string_content(self, quoted_string: str) -> str:
        """Helper to clean quotes and unescape characters.
        Supports optional Python string prefixes like f, r, b, u, fr, rf, etc.
        """
        if not quoted_string:
            return ''
        import re
        m = re.match(r"^(?P<prefix>[rRuUbBfF]{,2})?(?P<quoted>\"\"\"[\s\S]*?\"\"\"|\'\'\'[\s\S]*?\'\'\'|\"(?:[^\"\\]|\\.)*\"|\'(?:[^'\\]|\\.)*\')$", quoted_string, flags=re.S)
        if m:
            content_raw = m.group('quoted')
            if content_raw.startswith('"""') and content_raw.endswith('"""'):
                content = content_raw[3:-3]
            elif content_raw.startswith("'''") and content_raw.endswith("'''"):
                content = content_raw[3:-3]
            elif content_raw.startswith('"') and content_raw.endswith('"'):
                content = content_raw[1:-1]
            elif content_raw.startswith("'") and content_raw.endswith("'"):
                content = content_raw[1:-1]
            else:
                content = content_raw
        else:
            content = quoted_string

        # Unescape standard sequences
        content = content.replace('\"', '"').replace("\\'", "'")
        content = content.replace('\\n', '\n').replace('\\t', '\t')
        return content
    
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
        p = self.parser
        # Try AST-based parsing first — this is more robust for Python code
        try:
            if self._extract_strings_from_code_ast(code, line_number):
                return
        except Exception:
            pass
        
        # Match _("text") pattern - standard translation function
        translatable_pattern = r'_\s*\(\s*["\'](.+?)["\']\s*\)'
        for match in re.finditer(translatable_pattern, code):
            text = match.group(1)
            processed_text, placeholder_map = p.preserve_placeholders(text)
            self._add_text(processed_text, line_number, 'string', context='python/_', placeholder_map=placeholder_map)
        
        # Match __("text") pattern - double underscore translation
        double_under_pattern = r'__\s*\(\s*["\'](.+?)["\']\s*\)'
        for match in re.finditer(double_under_pattern, code):
            text = match.group(1)
            processed_text, placeholder_map = p.preserve_placeholders(text)
            self._add_text(processed_text, line_number, 'string', context='python/__', placeholder_map=placeholder_map)
        
        # Match renpy.notify("text") pattern
        notify_pattern = r'renpy\.notify\s*\(\s*["\'](.+?)["\']\s*\)'
        for match in re.finditer(notify_pattern, code):
            text = match.group(1)
            processed_text, placeholder_map = p.preserve_placeholders(text)
            self._add_text(processed_text, line_number, 'ui', context='notify', placeholder_map=placeholder_map)
        
        # Match Character("Name", ...) pattern
        char_pattern = r'Character\s*\(\s*["\'](.+?)["\']\s*[\),]'
        for match in re.finditer(char_pattern, code):
            text = match.group(1)
            processed_text, placeholder_map = p.preserve_placeholders(text)
            self._add_text(processed_text, line_number, 'string', context='character_define', placeholder_map=placeholder_map)
        
        # Match DynamicCharacter("Name", ...) pattern
        dyn_char_pattern = r'DynamicCharacter\s*\(\s*["\'](.+?)["\']\s*[\),]'
        for match in re.finditer(dyn_char_pattern, code):
            text = match.group(1)
            processed_text, placeholder_map = p.preserve_placeholders(text)
            self._add_text(processed_text, line_number, 'string', context='character_define', placeholder_map=placeholder_map)
        
        # Match renpy.say(who, "text") pattern
        say_pattern = r'renpy\.say\s*\([^,]*,\s*["\'](.+?)["\']\s*[\),]'
        for match in re.finditer(say_pattern, code):
            text = match.group(1)
            processed_text, placeholder_map = p.preserve_placeholders(text)
            self._add_text(processed_text, line_number, 'dialogue', context='python/say', placeholder_map=placeholder_map)
        
        # Match Text("content") pattern (displayable)
        text_display_pattern = r'Text\s*\(\s*["\'](.+?)["\']\s*[\),]'
        for match in re.finditer(text_display_pattern, code):
            text = match.group(1)
            processed_text, placeholder_map = p.preserve_placeholders(text)
            self._add_text(processed_text, line_number, 'ui', context='displayable', placeholder_map=placeholder_map)
        
        # Match config.name = "Game Name" pattern
        config_name_pattern = r'config\.(name|version)\s*=\s*["\'](.+?)["\']'
        for match in re.finditer(config_name_pattern, code):
            text = match.group(2)
            processed_text, placeholder_map = p.preserve_placeholders(text)
            self._add_text(processed_text, line_number, 'string', context='config', placeholder_map=placeholder_map)
        
        # Match gui.text_* = "..." patterns
        gui_text_pattern = r'gui\.\w*text\w*\s*=\s*["\'](.+?)["\']'
        for match in re.finditer(gui_text_pattern, code):
            text = match.group(1)
            processed_text, placeholder_map = p.preserve_placeholders(text)
            self._add_text(processed_text, line_number, 'ui', context='gui', placeholder_map=placeholder_map)
        
        # Match gui.* patterns for text extraction
        gui_variable_pattern = r'gui\.\w*\s*=\s*["\'](.+?)["\']'
        for match in re.finditer(gui_variable_pattern, code):
            text = match.group(1)
            processed_text, placeholder_map = p.preserve_placeholders(text)
            self._add_text(processed_text, line_number, 'ui', context='gui', placeholder_map=placeholder_map)
        
        # Match renpy.show("image") pattern
        show_pattern = r'renpy\.show\s*\(\s*["\'](.+?)["\']\s*\)'
        for match in re.finditer(show_pattern, code):
            text = match.group(1)
            processed_text, placeholder_map = p.preserve_placeholders(text)
            self._add_text(processed_text, line_number, 'ui', context='show', placeholder_map=placeholder_map)
        
        # --- UPDATED: Generic "Smart Key" Scanner ---
        # Use robust regex that handles escaped quotes
        # Support optional prefixes like f, r, b, u, fr, rf etc.
        generic_string_re = re.compile(r'''(?P<quote>(?:[rRuUbBfF]{,2})?(?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'))''')

        # Regex for context: var = [  OR  var = {  OR  "key":  OR var = "string" (assignment)
        list_context_re = re.compile(r'(?P<var>[a-zA-Z_]\w*)\s*(?:=\s*[\[\(\{]|\+=\s*[\[\(]|\.(?:append|extend|insert)\s*\()|["\'](?P<key>\w+)["\']\s*[:=]')
        assignment_context_re = re.compile(r'(?P<var>[a-zA-Z_]\w*)\s*=\s*')

        for match in generic_string_re.finditer(code):
            raw_text = match.group('quote')
            text = self._extract_string_content(raw_text)

            if not text or len(text) < 2:
                continue
            if self._is_technical_string(text):
                continue

            # Look backwards for context (multiple lines/1000 chars)
            start_pos = match.start()
            lookback_len = 1000
            lookback = code[max(0, start_pos-lookback_len):start_pos]

            found_key = None
            key_match = list(list_context_re.finditer(lookback))
            if key_match:
                last = key_match[-1]
                found_key = last.groupdict().get('var') or last.groupdict().get('key')

            is_whitelisted = found_key and found_key.lower() in self.DATA_KEY_WHITELIST

            if found_key:
                if is_whitelisted:
                    processed_text, placeholder_map = p.preserve_placeholders(text)
                    self._add_text(processed_text, line_number, 'data_string', context=f"rpyc_val:{found_key}", placeholder_map=placeholder_map)
                else:
                    # Not whitelisted, but was assigned to a var - add cautiously as generic string
                    # Use empty context to avoid whitelist-based rejection; context holds var name in metadata
                    processed_text, placeholder_map = p.preserve_placeholders(text)
                    self._add_text(processed_text, line_number, 'string', context='', placeholder_map=placeholder_map)
            else:
                # No variable found - treat as a generic string in code (non-whitelisted context)
                # Use empty context so technical string heuristics only filter out technical values
                processed_text, placeholder_map = p.preserve_placeholders(text)
                self._add_text(processed_text, line_number, 'string', context='', placeholder_map=placeholder_map)
    
    def _extract_strings_from_code_ast(self, code: str, line_number: int) -> None:
        """AST-based extraction for Python code blocks, focusing on string constants, f-strings, lists and dicts."""
        import textwrap
        clean_code = code
        # Strip leading Ren'Py python block header: init python: or python:
        header_re = re.compile(r'^(?:\s*init\s+python\s*:|\s*python\s*:)', flags=re.I)
        if header_re.match(code.strip().splitlines()[0]) if code.strip() else False:
            # Remove the first header line and dedent the rest
            lines = code.splitlines()
            # find first non-empty line that is the header
            idx = 0
            for i, l in enumerate(lines):
                if header_re.match(l):
                    idx = i
                    break
            block_lines = lines[idx+1:]
            clean_code = textwrap.dedent('\n'.join(block_lines))
        try:
            tree = ast.parse(clean_code)
        except Exception:
            return False

        p = self.parser

        def add_text_val(raw_text: str, ctx: str = '', text_type: str = 'python_string'):
            if not raw_text or len(raw_text.strip()) < 2:
                return
            processed_text, placeholder_map = p.preserve_placeholders(raw_text)
            if self._is_technical_string(raw_text, context=ctx):
                return
            self._add_text(processed_text, line_number, text_type, context=ctx or '', character='', placeholder_map=placeholder_map)

        class Visitor(ast.NodeVisitor):
            def __init__(self):
                super().__init__()
                self.current_assign_ctx = ''
            def visit_Constant(self, node):
                if isinstance(node.value, str):
                    add_text_val(node.value)
                self.generic_visit(node)

            def visit_JoinedStr(self, node):
                parts = []
                for v in node.values:
                    if isinstance(v, ast.Constant) and isinstance(v.value, str):
                        parts.append(v.value)
                    elif isinstance(v, ast.FormattedValue):
                        # Try to extract the source segment text for the expression when possible
                        try:
                            expr_src = ast.get_source_segment(code, v) or 'expr'
                        except Exception:
                            expr_src = 'expr'
                        parts.append('{' + expr_src + '}')
                add_text_val(''.join(parts))
                self.generic_visit(node)

            def visit_Call(self, node):
                # Detect join calls like ", ".join(['a','b']) where value is a constant string
                try:
                    func = node.func
                    # joined string: Attribute(value=Constant(', '), attr='join')
                    if isinstance(func, ast.Attribute) and func.attr == 'join':
                        val = func.value
                        if isinstance(val, ast.Constant) and isinstance(val.value, str):
                            add_text_val(val.value)
                    # format call: "{}".format(...)
                    if isinstance(func, ast.Attribute) and func.attr == 'format':
                        val = func.value
                        if isinstance(val, ast.Constant) and isinstance(val.value, str):
                            add_text_val(val.value)
                    # _p() call or renpy.notify call (not exhaustive)
                    if isinstance(func, ast.Name) and func.id in {'_p', 'renpy', 'notify'}:
                        # get constants in args
                        for a in node.args:
                            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                                add_text_val(a.value)
                            elif isinstance(a, ast.List):
                                for el in a.elts:
                                    if isinstance(el, ast.Constant) and isinstance(el.value, str):
                                        add_text_val(el.value)
                except Exception:
                    pass
                self.generic_visit(node)

            def visit_List(self, node):
                for elt in node.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        add_text_val(elt.value, ctx=self.current_assign_ctx, text_type='data_string' if self.current_assign_ctx else 'python_string')
                    elif isinstance(elt, ast.JoinedStr):
                        # If part of an assignment context, we should consider it data_string
                        parts = []
                        for v in elt.values:
                            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                                parts.append(v.value)
                            elif isinstance(v, ast.FormattedValue):
                                try:
                                    expr_src = ast.get_source_segment(code, v) or 'expr'
                                except Exception:
                                    expr_src = 'expr'
                                parts.append('{' + expr_src + '}')
                        add_text_val(''.join(parts), ctx=self.current_assign_ctx, text_type='data_string' if self.current_assign_ctx else 'python_string')
                self.generic_visit(node)

            def visit_Dict(self, node):
                for v in node.values:
                    if isinstance(v, ast.Constant) and isinstance(v.value, str):
                        add_text_val(v.value, ctx=self.current_assign_ctx, text_type='data_string' if self.current_assign_ctx else 'python_string')
                    elif isinstance(v, ast.JoinedStr):
                        self.visit_JoinedStr(v)
                self.generic_visit(node)

            def visit_Assign(self, node):
                # capture variable context by name if possible
                try:
                    if isinstance(node.targets[0], ast.Name):
                        varname = node.targets[0].id
                except Exception:
                    varname = None
                val = node.value
                ctx = ''
                if varname and varname.lower() in DATA_KEY_WHITELIST:
                    ctx = f'rpyc_val:{varname}'
                if isinstance(val, ast.Constant) and isinstance(val.value, str):
                    add_text_val(val.value, ctx=ctx, text_type='data_string' if ctx else 'python_string')
                elif isinstance(val, ast.JoinedStr):
                    # pass context for formats
                    parts = []
                    for v in val.values:
                        if isinstance(v, ast.Constant) and isinstance(v.value, str):
                            parts.append(v.value)
                        elif isinstance(v, ast.FormattedValue):
                            try:
                                expr_src = ast.get_source_segment(code, v) or 'expr'
                            except Exception:
                                expr_src = 'expr'
                            parts.append('{' + expr_src + '}')
                    add_text_val(''.join(parts), ctx=ctx, text_type='data_string' if ctx else 'python_string')
                else:
                    # Set a context to allow nested lists/dicts to be processed with variable context
                    prev_ctx = self.current_assign_ctx
                    self.current_assign_ctx = ctx
                    self.generic_visit(node)
                    self.current_assign_ctx = prev_ctx

            def visit_BinOp(self, node):
                # Extract strings from concatenations and % formatting
                try:
                    if isinstance(node.op, ast.Add):
                        left = node.left
                        right = node.right
                        if isinstance(left, ast.Constant) and isinstance(left.value, str):
                            add_text_val(left.value)
                        if isinstance(right, ast.Constant) and isinstance(right.value, str):
                            add_text_val(right.value)
                    if isinstance(node.op, ast.Mod):
                        # % formatting: left is constant string
                        left = node.left
                        if isinstance(left, ast.Constant) and isinstance(left.value, str):
                            add_text_val(left.value)
                except Exception:
                    pass
                self.generic_visit(node)

        Visitor().visit(tree)
        return True

    def _extract_strings_from_line(self, line: str, line_number: int) -> None:
        """Extract string literals from a line of code."""
        import re

        # First check for common translatable patterns
        self._extract_strings_from_code(line, line_number)

        # Robust regex for manual line scanning
        string_literal_re = re.compile(r'''(?P<quote>(?:[rRuUbBfF]{,2})?(?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'))''')

        # Context regex
        list_context_re = re.compile(r'([a-zA-Z_]\w*)\s*(?:=\s*[\[\(\{]|\+=\s*[\[\(]|\.(?:append|extend|insert)\s*\()')

        for match in string_literal_re.finditer(line):
            raw_text = match.group('quote')
            text = self._extract_string_content(raw_text)

            if text:
                # Check for variable context
                found_key = None
                list_match = list_context_re.search(line[:match.start()])
                if list_match:
                    found_key = list_match.group(1)

                is_whitelisted_key = found_key and found_key.lower() in self.DATA_KEY_WHITELIST

                # Check UI keywords if not whitelisted
                ui_keywords = ['text', 'label', 'button', 'tooltip', 'caption', 'title']
                is_ui_text = any(kw in line.lower() for kw in ui_keywords) and not self._is_technical_string(text)

                if is_whitelisted_key:
                    self._add_text(text, line_number, 'list_item', context=f"variable:{found_key}")
                elif is_ui_text:
                    self._add_text(text, line_number, 'string', context="ui_keyword")


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

    # Find .rpyc and .rpymc files
    pattern_rpyc = "**/*.rpyc" if recursive else "*.rpyc"
    pattern_rpymc = "**/*.rpymc" if recursive else "*.rpymc"
    rpyc_files = list(search_root.glob(pattern_rpyc)) + list(search_root.glob(pattern_rpymc))

    # Exclude tl/ folder and renpy engine files, except renpy/common
    filtered_files = []
    for f in rpyc_files:
        try:
            rel_path = f.relative_to(search_root)
            rel_str = str(rel_path).lower()
            # Skip if in tl/ subdirectory
            if rel_str.startswith('tl\\') or rel_str.startswith('tl/'):
                continue
            # Allow renpy/common and project-copied renpy under subfolders
            # Exclude only if renpy/ sits at the root of the search (engine files)
            if rel_str.startswith('renpy/') and 'common' not in rel_str:
                continue
            filtered_files.append(f)
        except ValueError:
            # If relative_to fails, include the file
            filtered_files.append(f)

    rpyc_files = filtered_files

    logger.info(f"Found {len(rpyc_files)} .rpyc/.rpymc files")

    for rpyc_file in rpyc_files:
        try:
            texts = extract_texts_from_rpyc(rpyc_file)
            results[rpyc_file] = texts
            logger.debug(f"Extracted {len(texts)} texts from {rpyc_file}")
        except Exception as e:
            logger.exception(f"Error extracting from {rpyc_file}: {e}")
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
