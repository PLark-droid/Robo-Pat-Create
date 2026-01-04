#!/usr/bin/env python3
"""
Java Object Serialization Stream Protocol Parser for .bwn files - Version 2

This parser fully reverse engineers the binary structure of Java serialized files,
with special handling for collection classes and detailed byte-level logging.
"""

import struct
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union, Tuple
from enum import IntEnum
import io
import json


# Java Serialization Protocol Constants
class TC(IntEnum):
    """Type codes for Java serialization"""
    NULL = 0x70
    OBJECT = 0x73
    CLASS = 0x76
    CLASSDESC = 0x72
    STRING = 0x74
    ARRAY = 0x75
    REFERENCE = 0x71
    BLOCKDATA = 0x77
    ENDBLOCKDATA = 0x78
    RESET = 0x79
    BLOCKDATALONG = 0x7A
    EXCEPTION = 0x7B
    LONGSTRING = 0x7C
    PROXYCLASSDESC = 0x7D
    ENUM = 0x7E


class SC(IntEnum):
    """Stream constants for serialization flags"""
    WRITE_METHOD = 0x01
    SERIALIZABLE = 0x02
    EXTERNALIZABLE = 0x04
    BLOCK_DATA = 0x08
    ENUM = 0x10


@dataclass
class JavaField:
    """Represents a Java field descriptor"""
    type_code: str
    name: str
    class_name: Optional[str] = None


@dataclass
class JavaClassDesc:
    """Represents a Java class descriptor"""
    name: str
    serial_version_uid: int
    flags: int
    fields: List[JavaField] = field(default_factory=list)
    super_class: Optional['JavaClassDesc'] = None
    handle: Optional[int] = None

    def has_write_method(self):
        return (self.flags & SC.WRITE_METHOD) != 0

    def is_serializable(self):
        return (self.flags & SC.SERIALIZABLE) != 0

    def is_enum(self):
        return (self.flags & SC.ENUM) != 0


@dataclass
class JavaObject:
    """Represents a deserialized Java object"""
    class_desc: JavaClassDesc
    field_data: Dict[str, Any] = field(default_factory=dict)
    annotations: List[Any] = field(default_factory=list)
    handle: Optional[int] = None


@dataclass
class JavaArray:
    """Represents a Java array"""
    class_desc: JavaClassDesc
    elements: List[Any] = field(default_factory=list)
    handle: Optional[int] = None


@dataclass
class JavaEnum:
    """Represents a Java enum constant"""
    class_desc: JavaClassDesc
    constant_name: str
    handle: Optional[int] = None


@dataclass
class BlockData:
    """Represents block data"""
    data: bytes


@dataclass
class ParseResult:
    """Container for parse results with position tracking"""
    value: Any
    start_offset: int
    end_offset: int


class JavaSerializationParser:
    """Parser for Java Object Serialization Stream Protocol"""

    STREAM_MAGIC = 0xACED
    STREAM_VERSION = 0x0005
    BASE_WIRE_HANDLE = 0x7E0000

    def __init__(self, data: bytes, verbose: bool = False):
        self.stream = io.BytesIO(data)
        self.handles: Dict[int, Any] = {}
        self.next_handle = self.BASE_WIRE_HANDLE
        self.verbose = verbose
        self.indent = 0

    def log(self, msg: str):
        if self.verbose:
            indent_str = "  " * self.indent
            print(f"{indent_str}{msg}")

    def pos(self) -> int:
        return self.stream.tell()

    def new_handle(self) -> int:
        handle = self.next_handle
        self.next_handle += 1
        return handle

    def read_bytes(self, n: int) -> bytes:
        data = self.stream.read(n)
        if len(data) != n:
            raise ValueError(f"Expected {n} bytes, got {len(data)} at offset {self.pos():#x}")
        return data

    def read_byte(self) -> int:
        return struct.unpack('>B', self.read_bytes(1))[0]

    def read_short(self) -> int:
        return struct.unpack('>h', self.read_bytes(2))[0]

    def read_ushort(self) -> int:
        return struct.unpack('>H', self.read_bytes(2))[0]

    def read_int(self) -> int:
        return struct.unpack('>i', self.read_bytes(4))[0]

    def read_long(self) -> int:
        return struct.unpack('>q', self.read_bytes(8))[0]

    def read_float(self) -> float:
        return struct.unpack('>f', self.read_bytes(4))[0]

    def read_double(self) -> float:
        return struct.unpack('>d', self.read_bytes(8))[0]

    def read_boolean(self) -> bool:
        return self.read_byte() != 0

    def read_utf(self) -> str:
        length = self.read_ushort()
        data = self.read_bytes(length)
        try:
            return data.decode('utf-8')
        except:
            return data.decode('latin-1')

    def peek_byte(self) -> int:
        """Peek at the next byte without consuming it"""
        b = self.read_byte()
        self.stream.seek(self.pos() - 1)
        return b

    def parse(self) -> Any:
        """Parse the complete serialization stream"""
        magic = self.read_ushort()
        if magic != self.STREAM_MAGIC:
            raise ValueError(f"Invalid magic: {magic:#x}")

        version = self.read_ushort()
        if version != self.STREAM_VERSION:
            raise ValueError(f"Invalid version: {version:#x}")

        self.log(f"Stream magic: {magic:#x}, version: {version:#x}")
        return self.read_content()

    def read_content(self) -> Any:
        """Read any content from the stream"""
        start = self.pos()
        tc = self.read_byte()

        tc_name = TC(tc).name if tc in TC._value2member_map_ else f'{tc:#x}'
        # Always log near the problem area
        if start >= 0x6700:
            print(f"DEBUG [{start:#x}] TC_{tc_name} (next byte would be at {self.pos():#x})")
        self.log(f"[{start:#x}] TC_{tc_name}")
        self.indent += 1

        try:
            if tc == TC.NULL:
                result = None
            elif tc == TC.OBJECT:
                result = self.read_new_object()
            elif tc == TC.CLASS:
                result = self.read_new_class()
            elif tc == TC.ARRAY:
                result = self.read_new_array()
            elif tc == TC.STRING:
                result = self.read_new_string()
            elif tc == TC.LONGSTRING:
                result = self.read_new_long_string()
            elif tc == TC.ENUM:
                result = self.read_new_enum()
            elif tc == TC.CLASSDESC:
                result = self.read_new_class_desc()
            elif tc == TC.PROXYCLASSDESC:
                result = self.read_new_proxy_class_desc()
            elif tc == TC.REFERENCE:
                result = self.read_prev_object()
            elif tc == TC.BLOCKDATA:
                result = self.read_block_data()
            elif tc == TC.BLOCKDATALONG:
                result = self.read_block_data_long()
            elif tc == TC.ENDBLOCKDATA:
                result = None  # Signal end
            else:
                raise ValueError(f"Unknown TC: {tc:#x} at offset {start:#x}")
        finally:
            self.indent -= 1

        return result

    def read_class_desc(self) -> Optional[JavaClassDesc]:
        """Read a class descriptor"""
        start = self.pos()
        tc = self.read_byte()

        if tc == TC.NULL:
            return None
        elif tc == TC.CLASSDESC:
            return self.read_new_class_desc()
        elif tc == TC.PROXYCLASSDESC:
            return self.read_new_proxy_class_desc()
        elif tc == TC.REFERENCE:
            handle = self.read_int()
            result = self.handles.get(handle)
            if start >= 0x6200:
                if isinstance(result, JavaClassDesc):
                    print(f"DEBUG CLASSREF at {start:#x}: handle={handle:#x} -> {result.name}")
                else:
                    print(f"DEBUG CLASSREF at {start:#x}: handle={handle:#x} -> {type(result)}")
            return result
        else:
            raise ValueError(f"Expected classdesc, got TC {tc:#x} at {start:#x}")

    def read_new_class_desc(self) -> JavaClassDesc:
        """Read a new class descriptor"""
        start = self.pos()

        class_name = self.read_utf()
        serial_uid = self.read_long()

        handle = self.new_handle()

        flags = self.read_byte()
        field_count = self.read_ushort()

        self.log(f"ClassDesc: {class_name} (handle={handle:#x}, flags={flags:#x}, fields={field_count})")
        if "FindElement" in class_name or "WebCommand" in class_name:
            print(f"DEBUG CLASSDESC at {start:#x}: {class_name}, handle={handle:#x}, {field_count} fields")

        class_desc = JavaClassDesc(
            name=class_name,
            serial_version_uid=serial_uid,
            flags=flags,
            handle=handle
        )
        self.handles[handle] = class_desc

        # Read field descriptors
        for _ in range(field_count):
            type_code = chr(self.read_byte())
            field_name = self.read_utf()
            class_name_ref = None
            if type_code in ('L', '['):
                class_name_ref = self.read_type_string()
            class_desc.fields.append(JavaField(type_code, field_name, class_name_ref))
            self.log(f"  Field: {type_code} {field_name} {class_name_ref or ''}")

        # Read class annotation
        self.read_class_annotation()

        # Read super class
        class_desc.super_class = self.read_class_desc()

        return class_desc

    def read_new_proxy_class_desc(self) -> JavaClassDesc:
        """Read a proxy class descriptor"""
        interface_count = self.read_int()
        interfaces = [self.read_utf() for _ in range(interface_count)]

        handle = self.new_handle()
        class_desc = JavaClassDesc(
            name=f"$Proxy[{','.join(interfaces)}]",
            serial_version_uid=0,
            flags=SC.SERIALIZABLE,
            handle=handle
        )
        self.handles[handle] = class_desc

        self.read_class_annotation()
        class_desc.super_class = self.read_class_desc()

        return class_desc

    def read_type_string(self) -> str:
        """Read a type string for field class names"""
        tc = self.read_byte()
        if tc == TC.STRING:
            return self.read_new_string()
        elif tc == TC.REFERENCE:
            handle = self.read_int()
            return self.handles.get(handle, f"<ref:{handle:#x}>")
        else:
            raise ValueError(f"Expected string in type, got TC {tc:#x}")

    def read_class_annotation(self):
        """Read class annotations until ENDBLOCKDATA"""
        while True:
            tc = self.peek_byte()
            if tc == TC.ENDBLOCKDATA:
                self.read_byte()  # consume
                return
            self.read_content()

    def read_new_string(self) -> str:
        """Read a new string"""
        handle = self.new_handle()
        s = self.read_utf()
        self.handles[handle] = s
        self.log(f"String (handle={handle:#x}): {s[:50]}{'...' if len(s) > 50 else ''}")
        return s

    def read_new_long_string(self) -> str:
        """Read a long string"""
        handle = self.new_handle()
        length = self.read_long()
        data = self.read_bytes(length)
        try:
            s = data.decode('utf-8')
        except:
            s = data.decode('latin-1')
        self.handles[handle] = s
        return s

    def read_prev_object(self) -> Any:
        """Read a reference"""
        start = self.pos()
        handle = self.read_int()
        end = self.pos()
        obj = self.handles.get(handle)
        if start >= 0x6700:
            print(f"DEBUG REF: handle={handle:#x}, read {start:#x}-{end:#x}, pos now {self.pos():#x}")
        self.log(f"Reference: {handle:#x} (read from {start:#x} to {end:#x})")
        return obj

    def read_new_object(self) -> JavaObject:
        """Read a new object"""
        class_desc = self.read_class_desc()
        if class_desc is None:
            return None

        handle = self.new_handle()
        obj = JavaObject(class_desc=class_desc, handle=handle)
        self.handles[handle] = obj

        self.log(f"Object: {class_desc.name} (handle={handle:#x})")

        # Read object data following class hierarchy
        self.read_object_data(obj, class_desc)

        return obj

    def read_object_data(self, obj: JavaObject, class_desc: JavaClassDesc):
        """Read object instance data following class hierarchy"""
        # Build hierarchy from super to sub
        hierarchy = []
        current = class_desc
        while current:
            hierarchy.append(current)
            current = current.super_class
        hierarchy.reverse()

        if self.pos() >= 0x5e00 and self.pos() <= 0x6900:
            print(f"DEBUG HIERARCHY for {class_desc.name}:")
            for i, cls in enumerate(hierarchy):
                print(f"  [{i}] {cls.name} - {len(cls.fields)} fields, flags={cls.flags:#x}")

        self.indent += 1
        for cls in hierarchy:
            # Read primitive and object field values
            for fld in cls.fields:
                value = self.read_field_value(fld)
                obj.field_data[fld.name] = value
                if self.verbose:
                    val_str = str(value)[:50] if value is not None else "null"
                    self.log(f".{fld.name} = {val_str}")

            # If has writeObject, read annotations
            if cls.has_write_method():
                if self.pos() >= 0x6700:
                    print(f"DEBUG: Reading annotations for {cls.name} at pos {self.pos():#x}, flags={cls.flags:#x}")
                self.log(f"Reading annotations for {cls.name}")
                anns = self.read_object_annotation()
                obj.annotations.extend(anns)
        self.indent -= 1

    def read_field_value(self, fld: JavaField) -> Any:
        """Read a field value based on type"""
        tc = fld.type_code
        pos_before = self.pos()
        if tc == 'B': result = self.read_byte()
        elif tc == 'C': result = chr(self.read_ushort())
        elif tc == 'D': result = self.read_double()
        elif tc == 'F': result = self.read_float()
        elif tc == 'I': result = self.read_int()
        elif tc == 'J': result = self.read_long()
        elif tc == 'S': result = self.read_short()
        elif tc == 'Z': result = self.read_boolean()
        elif tc in ('L', '['): result = self.read_content()
        else: raise ValueError(f"Unknown field type: {tc}")

        pos_after = self.pos()
        if pos_before >= 0x6700 or pos_after >= 0x6700:
            print(f"DEBUG FIELD: {fld.name} ({tc}) read {pos_before:#x}-{pos_after:#x}")
        return result

    def read_object_annotation(self) -> List[Any]:
        """Read object annotations until ENDBLOCKDATA"""
        annotations = []
        while True:
            pos_before = self.pos()
            tc = self.peek_byte()
            if pos_before >= 0x6700:
                print(f"DEBUG ANNOT: peek at {pos_before:#x} = {tc:#x}")
            if tc == TC.ENDBLOCKDATA:
                self.read_byte()
                return annotations
            content = self.read_content()
            if content is not None:
                annotations.append(content)
        return annotations

    def read_new_array(self) -> JavaArray:
        """Read an array"""
        class_desc = self.read_class_desc()
        handle = self.new_handle()
        size = self.read_int()

        arr = JavaArray(class_desc=class_desc, handle=handle)
        self.handles[handle] = arr

        self.log(f"Array: {class_desc.name} size={size} (handle={handle:#x})")

        # Determine element type
        name = class_desc.name
        if name.startswith('['):
            elem_type = name[1]
        else:
            elem_type = 'L'

        for _ in range(size):
            if elem_type == 'B': arr.elements.append(self.read_byte())
            elif elem_type == 'C': arr.elements.append(chr(self.read_ushort()))
            elif elem_type == 'D': arr.elements.append(self.read_double())
            elif elem_type == 'F': arr.elements.append(self.read_float())
            elif elem_type == 'I': arr.elements.append(self.read_int())
            elif elem_type == 'J': arr.elements.append(self.read_long())
            elif elem_type == 'S': arr.elements.append(self.read_short())
            elif elem_type == 'Z': arr.elements.append(self.read_boolean())
            else: arr.elements.append(self.read_content())

        return arr

    def read_new_enum(self) -> JavaEnum:
        """Read an enum constant"""
        class_desc = self.read_class_desc()
        handle = self.new_handle()

        constant = self.read_content()
        if isinstance(constant, str):
            constant_name = constant
        else:
            constant_name = str(constant)

        enum_val = JavaEnum(class_desc=class_desc, constant_name=constant_name, handle=handle)
        self.handles[handle] = enum_val

        self.log(f"Enum: {class_desc.name}.{constant_name}")
        return enum_val

    def read_new_class(self) -> JavaClassDesc:
        """Read a Class object"""
        class_desc = self.read_class_desc()
        handle = self.new_handle()
        self.handles[handle] = class_desc
        return class_desc

    def read_block_data(self) -> BlockData:
        """Read short block data"""
        size = self.read_byte()
        data = self.read_bytes(size)
        self.log(f"BlockData: {size} bytes")
        return BlockData(data)

    def read_block_data_long(self) -> BlockData:
        """Read long block data"""
        size = self.read_int()
        data = self.read_bytes(size)
        self.log(f"BlockDataLong: {size} bytes")
        return BlockData(data)


def to_python_structure(obj: Any, seen: set = None, depth: int = 0) -> Any:
    """Convert Java objects to Python data structure"""
    if seen is None:
        seen = set()

    if obj is None:
        return None

    if isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, bytes):
        return f"<bytes:{len(obj)}>"

    if isinstance(obj, BlockData):
        # Try to interpret block data
        return {'__blockdata__': obj.data.hex(), '__len__': len(obj.data)}

    if id(obj) in seen:
        if isinstance(obj, JavaObject):
            return f"<circular:{obj.class_desc.name}>"
        elif isinstance(obj, JavaArray):
            return f"<circular:array>"
        return f"<circular:{type(obj).__name__}>"

    if isinstance(obj, (JavaObject, JavaArray)):
        seen = seen.copy()
        seen.add(id(obj))

    if isinstance(obj, JavaObject):
        result = {
            '__class__': obj.class_desc.name,
            '__handle__': f"{obj.handle:#x}"
        }
        for name, value in obj.field_data.items():
            result[name] = to_python_structure(value, seen, depth+1)
        if obj.annotations:
            ann_list = []
            for ann in obj.annotations:
                ann_list.append(to_python_structure(ann, seen, depth+1))
            if ann_list:
                result['__annotations__'] = ann_list
        return result

    if isinstance(obj, JavaArray):
        elements = []
        for elem in obj.elements:
            elements.append(to_python_structure(elem, seen, depth+1))
        return {
            '__array__': obj.class_desc.name,
            '__len__': len(obj.elements),
            '__elements__': elements
        }

    if isinstance(obj, JavaEnum):
        return {
            '__enum__': obj.class_desc.name,
            '__value__': obj.constant_name
        }

    if isinstance(obj, JavaClassDesc):
        return {
            '__classdesc__': obj.name
        }

    if isinstance(obj, list):
        return [to_python_structure(x, seen, depth+1) for x in obj]

    return str(obj)


def extract_commands(obj: Any, commands: list = None, seen: set = None) -> list:
    """Extract all command objects"""
    if commands is None:
        commands = []
    if seen is None:
        seen = set()

    if id(obj) in seen:
        return commands

    if isinstance(obj, JavaObject):
        seen.add(id(obj))
        class_name = obj.class_desc.name

        # Collect command info
        if 'Command' in class_name or 'command' in class_name:
            cmd = {
                'class': class_name,
                'handle': f"{obj.handle:#x}",
                'fields': {}
            }
            for name, value in obj.field_data.items():
                if isinstance(value, (str, int, float, bool)) or value is None:
                    cmd['fields'][name] = value
                elif isinstance(value, JavaEnum):
                    cmd['fields'][name] = f"{value.class_desc.name}.{value.constant_name}"
            commands.append(cmd)

        # Recurse
        for value in obj.field_data.values():
            extract_commands(value, commands, seen)
        for ann in obj.annotations:
            extract_commands(ann, commands, seen)

    elif isinstance(obj, JavaArray):
        seen.add(id(obj))
        for elem in obj.elements:
            extract_commands(elem, commands, seen)

    elif isinstance(obj, list):
        for item in obj:
            extract_commands(item, commands, seen)

    return commands


def print_structure_summary(obj: Any, indent: int = 0, seen: set = None):
    """Print a summary of the structure"""
    if seen is None:
        seen = set()

    prefix = "  " * indent

    if obj is None:
        print(f"{prefix}null")
        return

    if isinstance(obj, str):
        s = obj[:60] + "..." if len(obj) > 60 else obj
        print(f'{prefix}"{s}"')
        return

    if isinstance(obj, (int, float, bool)):
        print(f"{prefix}{obj}")
        return

    if isinstance(obj, BlockData):
        print(f"{prefix}<BlockData: {len(obj.data)} bytes>")
        return

    if id(obj) in seen:
        if isinstance(obj, JavaObject):
            print(f"{prefix}<ref: {obj.class_desc.name}>")
        else:
            print(f"{prefix}<ref>")
        return

    if isinstance(obj, JavaObject):
        seen = seen.copy()
        seen.add(id(obj))
        print(f"{prefix}Object: {obj.class_desc.name}")
        for name, value in obj.field_data.items():
            print(f"{prefix}  .{name}:")
            print_structure_summary(value, indent + 2, seen)
        if obj.annotations:
            print(f"{prefix}  [annotations]:")
            for ann in obj.annotations:
                print_structure_summary(ann, indent + 2, seen)
        return

    if isinstance(obj, JavaArray):
        seen = seen.copy()
        seen.add(id(obj))
        print(f"{prefix}Array[{len(obj.elements)}]: {obj.class_desc.name}")
        for i, elem in enumerate(obj.elements[:5]):
            print(f"{prefix}  [{i}]:")
            print_structure_summary(elem, indent + 2, seen)
        if len(obj.elements) > 5:
            print(f"{prefix}  ... ({len(obj.elements) - 5} more)")
        return

    if isinstance(obj, JavaEnum):
        print(f"{prefix}Enum: {obj.class_desc.name}.{obj.constant_name}")
        return

    if isinstance(obj, list):
        print(f"{prefix}List[{len(obj)}]")
        for item in obj[:5]:
            print_structure_summary(item, indent + 1, seen)
        if len(obj) > 5:
            print(f"{prefix}  ... ({len(obj) - 5} more)")
        return

    print(f"{prefix}{type(obj).__name__}: {str(obj)[:50]}")


def main():
    file_path = "/Users/hiroki-matsui/Robo-Pat/Robo-Pat-Create/script/extracted/main.bwn"

    print(f"Parsing: {file_path}")
    print("=" * 80)

    with open(file_path, 'rb') as f:
        data = f.read()

    print(f"File size: {len(data)} bytes")
    print()

    # Parse with verbose mode off for first pass
    parser = JavaSerializationParser(data, verbose=False)

    try:
        result = parser.parse()

        print("PARSING SUCCESSFUL!")
        print(f"Total handles: {parser.next_handle - parser.BASE_WIRE_HANDLE}")
        print()

        # Print structure summary
        print("=" * 80)
        print("STRUCTURE SUMMARY:")
        print("=" * 80)
        print_structure_summary(result)

        # Extract commands
        print()
        print("=" * 80)
        print("COMMANDS:")
        print("=" * 80)
        commands = extract_commands(result)
        for i, cmd in enumerate(commands[:30]):
            print(f"\n[{i+1}] {cmd['class']}")
            for name, value in cmd['fields'].items():
                if value is not None and value != '' and value != '""':
                    v = str(value)[:60]
                    print(f"     .{name} = {v}")
        if len(commands) > 30:
            print(f"\n... and {len(commands) - 30} more commands")

        # Convert to Python structure
        print()
        print("=" * 80)
        print("Converting to Python structure...")

        py_struct = to_python_structure(result)

        output_file = "/Users/hiroki-matsui/Robo-Pat/Robo-Pat-Create/robopat-ai/bwn_structure.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(py_struct, f, indent=2, ensure_ascii=False, default=str)

        print(f"Saved to: {output_file}")

        return py_struct

    except Exception as e:
        import traceback
        print(f"\nParse error at offset {parser.pos():#x}: {e}")
        traceback.print_exc()

        # Show context
        print(f"\nBytes around error (offset {parser.pos():#x}):")
        pos = parser.pos()
        parser.stream.seek(max(0, pos - 16))
        context = parser.stream.read(48)
        print(f"  {context.hex()}")

        return None


if __name__ == "__main__":
    main()
