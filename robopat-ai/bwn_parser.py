#!/usr/bin/env python3
"""
Java Object Serialization Stream Protocol Parser for .bwn files

This parser fully reverse engineers the binary structure of Java serialized files,
handling all object types, references, class descriptors, and nested structures.
"""

import struct
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from enum import IntEnum
import io


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


# Java primitive type codes (for arrays)
PRIM_TYPES = {
    'B': 'byte',
    'C': 'char',
    'D': 'double',
    'F': 'float',
    'I': 'int',
    'J': 'long',
    'S': 'short',
    'Z': 'boolean',
    'L': 'object',
    '[': 'array'
}


@dataclass
class JavaField:
    """Represents a Java field descriptor"""
    type_code: str
    name: str
    class_name: Optional[str] = None

    def __repr__(self):
        if self.class_name:
            return f"JavaField({self.type_code} {self.name}: {self.class_name})"
        return f"JavaField({self.type_code} {self.name})"


@dataclass
class JavaClassDesc:
    """Represents a Java class descriptor"""
    name: str
    serial_version_uid: int
    flags: int
    fields: List[JavaField] = field(default_factory=list)
    super_class: Optional['JavaClassDesc'] = None
    annotations: List[Any] = field(default_factory=list)
    handle: Optional[int] = None

    def has_write_method(self):
        return (self.flags & SC.WRITE_METHOD) != 0

    def is_serializable(self):
        return (self.flags & SC.SERIALIZABLE) != 0

    def is_externalizable(self):
        return (self.flags & SC.EXTERNALIZABLE) != 0

    def is_enum(self):
        return (self.flags & SC.ENUM) != 0

    def __repr__(self):
        flags_str = []
        if self.has_write_method(): flags_str.append("SC_WRITE_METHOD")
        if self.is_serializable(): flags_str.append("SC_SERIALIZABLE")
        if self.is_externalizable(): flags_str.append("SC_EXTERNALIZABLE")
        if self.is_enum(): flags_str.append("SC_ENUM")
        return f"JavaClassDesc({self.name}, uid={self.serial_version_uid:#x}, flags=[{', '.join(flags_str)}], fields={len(self.fields)})"


@dataclass
class JavaObject:
    """Represents a deserialized Java object"""
    class_desc: JavaClassDesc
    field_values: Dict[str, Any] = field(default_factory=dict)
    annotations: List[Any] = field(default_factory=list)
    handle: Optional[int] = None

    def __repr__(self):
        return f"JavaObject({self.class_desc.name}, fields={list(self.field_values.keys())})"


@dataclass
class JavaArray:
    """Represents a Java array"""
    class_desc: JavaClassDesc
    elements: List[Any] = field(default_factory=list)
    handle: Optional[int] = None

    def __repr__(self):
        return f"JavaArray({self.class_desc.name}, length={len(self.elements)})"


@dataclass
class JavaEnum:
    """Represents a Java enum constant"""
    class_desc: JavaClassDesc
    constant_name: str
    handle: Optional[int] = None

    def __repr__(self):
        return f"JavaEnum({self.class_desc.name}.{self.constant_name})"


@dataclass
class JavaReference:
    """Reference to a previously defined handle"""
    handle: int
    resolved: Any = None

    def __repr__(self):
        if self.resolved:
            return f"Reference(handle={self.handle:#x}) -> {type(self.resolved).__name__}"
        return f"Reference(handle={self.handle:#x})"


class JavaSerializationParser:
    """Parser for Java Object Serialization Stream Protocol"""

    STREAM_MAGIC = 0xACED
    STREAM_VERSION = 0x0005
    BASE_WIRE_HANDLE = 0x7E0000

    def __init__(self, data: bytes):
        self.stream = io.BytesIO(data)
        self.handles: Dict[int, Any] = {}
        self.next_handle = self.BASE_WIRE_HANDLE
        self.parse_log: List[Dict] = []

    def log(self, offset: int, type_name: str, value: Any, raw_bytes: bytes = b''):
        """Log parsing information for debugging"""
        self.parse_log.append({
            'offset': offset,
            'type': type_name,
            'value': value,
            'raw_bytes': raw_bytes.hex() if raw_bytes else ''
        })

    def new_handle(self) -> int:
        """Allocate a new handle"""
        handle = self.next_handle
        self.next_handle += 1
        return handle

    def register_handle(self, handle: int, obj: Any):
        """Register an object with a handle"""
        self.handles[handle] = obj

    def read_bytes(self, n: int) -> bytes:
        """Read n bytes from the stream"""
        data = self.stream.read(n)
        if len(data) != n:
            raise ValueError(f"Expected {n} bytes, got {len(data)}")
        return data

    def read_byte(self) -> int:
        """Read a single byte"""
        return struct.unpack('>B', self.read_bytes(1))[0]

    def read_short(self) -> int:
        """Read a 2-byte signed short"""
        return struct.unpack('>h', self.read_bytes(2))[0]

    def read_ushort(self) -> int:
        """Read a 2-byte unsigned short"""
        return struct.unpack('>H', self.read_bytes(2))[0]

    def read_int(self) -> int:
        """Read a 4-byte signed int"""
        return struct.unpack('>i', self.read_bytes(4))[0]

    def read_uint(self) -> int:
        """Read a 4-byte unsigned int"""
        return struct.unpack('>I', self.read_bytes(4))[0]

    def read_long(self) -> int:
        """Read an 8-byte signed long"""
        return struct.unpack('>q', self.read_bytes(8))[0]

    def read_float(self) -> float:
        """Read a 4-byte float"""
        return struct.unpack('>f', self.read_bytes(4))[0]

    def read_double(self) -> float:
        """Read an 8-byte double"""
        return struct.unpack('>d', self.read_bytes(8))[0]

    def read_boolean(self) -> bool:
        """Read a boolean (1 byte)"""
        return self.read_byte() != 0

    def read_utf(self) -> str:
        """Read a modified UTF-8 string"""
        length = self.read_ushort()
        data = self.read_bytes(length)
        # Modified UTF-8 - for now, try standard UTF-8 decoding
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError:
            return data.decode('latin-1')

    def read_long_utf(self) -> str:
        """Read a long modified UTF-8 string"""
        length = self.read_long()
        data = self.read_bytes(length)
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError:
            return data.decode('latin-1')

    def parse(self) -> Any:
        """Parse the complete serialization stream"""
        offset = self.stream.tell()

        # Read and verify magic number
        magic = self.read_ushort()
        if magic != self.STREAM_MAGIC:
            raise ValueError(f"Invalid stream magic: {magic:#x}, expected {self.STREAM_MAGIC:#x}")
        self.log(offset, 'STREAM_MAGIC', f'{magic:#x}')

        # Read and verify version
        version = self.read_ushort()
        if version != self.STREAM_VERSION:
            raise ValueError(f"Invalid stream version: {version:#x}, expected {self.STREAM_VERSION:#x}")
        self.log(offset + 2, 'STREAM_VERSION', f'{version:#x}')

        # Parse stream contents
        return self.read_content()

    def read_content(self) -> Any:
        """Read a content element from the stream"""
        offset = self.stream.tell()
        tc = self.read_byte()
        tc_name = TC(tc).name if tc in TC._value2member_map_ else f'{tc:#x}'
        self.log(offset, 'TC', tc_name)

        if tc == TC.NULL:
            return None
        elif tc == TC.OBJECT:
            return self.read_new_object()
        elif tc == TC.CLASS:
            return self.read_new_class()
        elif tc == TC.ARRAY:
            return self.read_new_array()
        elif tc == TC.STRING:
            return self.read_new_string()
        elif tc == TC.LONGSTRING:
            return self.read_new_long_string()
        elif tc == TC.ENUM:
            return self.read_new_enum()
        elif tc == TC.CLASSDESC:
            return self.read_new_class_desc()
        elif tc == TC.PROXYCLASSDESC:
            return self.read_new_proxy_class_desc()
        elif tc == TC.REFERENCE:
            return self.read_prev_object()
        elif tc == TC.BLOCKDATA:
            return self.read_block_data()
        elif tc == TC.BLOCKDATALONG:
            return self.read_block_data_long()
        elif tc == TC.ENDBLOCKDATA:
            return None  # Signal end of block data
        elif tc == TC.EXCEPTION:
            raise ValueError("Exception in stream")
        elif tc == TC.RESET:
            self.handles.clear()
            self.next_handle = self.BASE_WIRE_HANDLE
            return self.read_content()
        else:
            raise ValueError(f"Unknown type code: {tc:#x} at offset {offset}")

    def read_class_desc(self) -> Optional[JavaClassDesc]:
        """Read a class descriptor (with type code)"""
        offset = self.stream.tell()
        tc = self.read_byte()

        if tc == TC.NULL:
            return None
        elif tc == TC.CLASSDESC:
            return self.read_new_class_desc()
        elif tc == TC.PROXYCLASSDESC:
            return self.read_new_proxy_class_desc()
        elif tc == TC.REFERENCE:
            ref = self.read_prev_object()
            if isinstance(ref, JavaReference):
                return ref.resolved
            return ref
        else:
            raise ValueError(f"Expected class descriptor, got TC {tc:#x} at offset {offset}")

    def read_new_class_desc(self) -> JavaClassDesc:
        """Read a new class descriptor"""
        offset = self.stream.tell()

        # Read class name
        class_name = self.read_utf()
        self.log(offset, 'CLASS_NAME', class_name)

        # Read serial version UID
        serial_version_uid = self.read_long()

        # Assign handle
        handle = self.new_handle()

        # Read flags
        flags = self.read_byte()

        # Read field count
        field_count = self.read_ushort()

        # Create class descriptor
        class_desc = JavaClassDesc(
            name=class_name,
            serial_version_uid=serial_version_uid,
            flags=flags,
            handle=handle
        )
        self.register_handle(handle, class_desc)

        # Read field descriptors
        for _ in range(field_count):
            field = self.read_field_desc()
            class_desc.fields.append(field)

        # Read class annotations
        class_desc.annotations = self.read_class_annotations()

        # Read super class descriptor
        class_desc.super_class = self.read_class_desc()

        self.log(offset, 'CLASSDESC', str(class_desc))
        return class_desc

    def read_new_proxy_class_desc(self) -> JavaClassDesc:
        """Read a new proxy class descriptor"""
        # Read number of interfaces
        interface_count = self.read_int()
        interfaces = []
        for _ in range(interface_count):
            interfaces.append(self.read_utf())

        # Assign handle
        handle = self.new_handle()

        class_desc = JavaClassDesc(
            name=f"$Proxy[{','.join(interfaces)}]",
            serial_version_uid=0,
            flags=SC.SERIALIZABLE,
            handle=handle
        )
        self.register_handle(handle, class_desc)

        # Read class annotations
        class_desc.annotations = self.read_class_annotations()

        # Read super class descriptor
        class_desc.super_class = self.read_class_desc()

        return class_desc

    def read_field_desc(self) -> JavaField:
        """Read a field descriptor"""
        type_code = chr(self.read_byte())
        field_name = self.read_utf()

        class_name = None
        if type_code in ('L', '['):
            # Read class name for objects and arrays
            class_name = self.read_type_string()

        return JavaField(type_code=type_code, name=field_name, class_name=class_name)

    def read_type_string(self) -> str:
        """Read a type string (for field class names)"""
        tc = self.read_byte()
        if tc == TC.STRING:
            s = self.read_new_string()
            return s
        elif tc == TC.REFERENCE:
            ref = self.read_prev_object()
            if isinstance(ref, JavaReference):
                return ref.resolved
            return ref
        else:
            raise ValueError(f"Expected string or reference, got TC {tc:#x}")

    def read_class_annotations(self) -> List[Any]:
        """Read class annotations until TC_ENDBLOCKDATA"""
        annotations = []
        while True:
            offset = self.stream.tell()
            tc = self.read_byte()
            if tc == TC.ENDBLOCKDATA:
                break
            # Put the byte back and read content
            self.stream.seek(offset)
            content = self.read_content()
            if content is not None:
                annotations.append(content)
        return annotations

    def read_new_string(self) -> str:
        """Read a new string and assign handle"""
        handle = self.new_handle()
        s = self.read_utf()
        self.register_handle(handle, s)
        return s

    def read_new_long_string(self) -> str:
        """Read a new long string and assign handle"""
        handle = self.new_handle()
        s = self.read_long_utf()
        self.register_handle(handle, s)
        return s

    def read_prev_object(self) -> Any:
        """Read a reference to a previously defined object"""
        offset = self.stream.tell()
        handle = self.read_int()
        self.log(offset, 'REFERENCE', f'handle={handle:#x}')
        if handle not in self.handles:
            # Try to continue anyway for debugging
            print(f"Warning: Invalid handle reference: {handle:#x} at offset {offset:#x}")
            return JavaReference(handle=handle, resolved=None)
        ref = JavaReference(handle=handle, resolved=self.handles[handle])
        return ref

    def read_new_object(self) -> JavaObject:
        """Read a new object"""
        # Read class descriptor
        class_desc = self.read_class_desc()

        if class_desc is None:
            return None

        # Assign handle
        handle = self.new_handle()

        # Create object
        obj = JavaObject(class_desc=class_desc, handle=handle)
        self.register_handle(handle, obj)

        # Read object data based on class hierarchy
        self.read_object_data(obj, class_desc)

        return obj

    def read_object_data(self, obj: JavaObject, class_desc: JavaClassDesc):
        """Read object data for a class and its superclasses"""
        # Build class hierarchy (from superclass to subclass)
        hierarchy = []
        current = class_desc
        while current is not None:
            hierarchy.append(current)
            current = current.super_class
        hierarchy.reverse()

        # Read data for each class in hierarchy
        for cls in hierarchy:
            # Read field values
            for field in cls.fields:
                value = self.read_field_value(field)
                field_key = f"{cls.name}.{field.name}" if field.name in obj.field_values else field.name
                obj.field_values[field.name] = value

            # If class has writeObject method, read annotations
            if cls.has_write_method():
                annotations = self.read_object_annotations()
                obj.annotations.extend(annotations)

    def read_field_value(self, field: JavaField) -> Any:
        """Read a field value based on its type"""
        tc = field.type_code

        if tc == 'B':
            return self.read_byte()
        elif tc == 'C':
            return chr(self.read_ushort())
        elif tc == 'D':
            return self.read_double()
        elif tc == 'F':
            return self.read_float()
        elif tc == 'I':
            return self.read_int()
        elif tc == 'J':
            return self.read_long()
        elif tc == 'S':
            return self.read_short()
        elif tc == 'Z':
            return self.read_boolean()
        elif tc in ('L', '['):
            return self.read_content()
        else:
            raise ValueError(f"Unknown field type code: {tc}")

    def read_object_annotations(self) -> List[Any]:
        """Read object annotations (block data from writeObject)"""
        annotations = []
        while True:
            offset = self.stream.tell()
            tc = self.read_byte()
            if tc == TC.ENDBLOCKDATA:
                break
            # Put the byte back and read content
            self.stream.seek(offset)
            content = self.read_content()
            if content is not None:
                annotations.append(content)
        return annotations

    def read_new_array(self) -> JavaArray:
        """Read a new array"""
        # Read class descriptor
        class_desc = self.read_class_desc()

        # Assign handle
        handle = self.new_handle()

        # Read array size
        size = self.read_int()

        # Create array
        arr = JavaArray(class_desc=class_desc, handle=handle)
        self.register_handle(handle, arr)

        # Determine element type from class name
        class_name = class_desc.name
        if class_name.startswith('['):
            element_type = class_name[1:]
        else:
            element_type = 'L'

        # Read array elements
        for _ in range(size):
            if element_type == 'B':
                arr.elements.append(self.read_byte())
            elif element_type == 'C':
                arr.elements.append(chr(self.read_ushort()))
            elif element_type == 'D':
                arr.elements.append(self.read_double())
            elif element_type == 'F':
                arr.elements.append(self.read_float())
            elif element_type == 'I':
                arr.elements.append(self.read_int())
            elif element_type == 'J':
                arr.elements.append(self.read_long())
            elif element_type == 'S':
                arr.elements.append(self.read_short())
            elif element_type == 'Z':
                arr.elements.append(self.read_boolean())
            else:
                # Object type
                arr.elements.append(self.read_content())

        return arr

    def read_new_enum(self) -> JavaEnum:
        """Read a new enum constant"""
        # Read class descriptor
        class_desc = self.read_class_desc()

        # Assign handle
        handle = self.new_handle()

        # Read enum constant name
        constant_name_obj = self.read_content()
        if isinstance(constant_name_obj, JavaReference):
            constant_name = constant_name_obj.resolved
        else:
            constant_name = constant_name_obj

        enum_val = JavaEnum(
            class_desc=class_desc,
            constant_name=constant_name,
            handle=handle
        )
        self.register_handle(handle, enum_val)

        return enum_val

    def read_new_class(self) -> JavaClassDesc:
        """Read a new class object"""
        class_desc = self.read_class_desc()
        handle = self.new_handle()
        self.register_handle(handle, class_desc)
        return class_desc

    def read_block_data(self) -> bytes:
        """Read block data (short)"""
        size = self.read_byte()
        return self.read_bytes(size)

    def read_block_data_long(self) -> bytes:
        """Read block data (long)"""
        size = self.read_int()
        return self.read_bytes(size)


def object_to_dict(obj: Any, seen: set = None) -> Any:
    """Convert parsed Java objects to Python dict representation"""
    if seen is None:
        seen = set()

    if obj is None:
        return None

    if isinstance(obj, (str, int, float, bool, bytes)):
        return obj

    if isinstance(obj, JavaReference):
        obj = obj.resolved

    if id(obj) in seen:
        if isinstance(obj, JavaObject):
            return f"<circular ref: {obj.class_desc.name}>"
        elif isinstance(obj, JavaArray):
            return f"<circular ref: {obj.class_desc.name}>"
        elif isinstance(obj, JavaClassDesc):
            return f"<class: {obj.name}>"
        return f"<circular ref: {type(obj).__name__}>"

    if isinstance(obj, (JavaObject, JavaArray, JavaClassDesc)):
        seen = seen.copy()
        seen.add(id(obj))

    if isinstance(obj, JavaObject):
        result = {
            '__class__': obj.class_desc.name,
            '__handle__': obj.handle
        }
        for name, value in obj.field_values.items():
            result[name] = object_to_dict(value, seen)
        if obj.annotations:
            result['__annotations__'] = [object_to_dict(a, seen) for a in obj.annotations]
        return result

    if isinstance(obj, JavaArray):
        return {
            '__array__': obj.class_desc.name,
            '__handle__': obj.handle,
            '__elements__': [object_to_dict(e, seen) for e in obj.elements]
        }

    if isinstance(obj, JavaEnum):
        return {
            '__enum__': obj.class_desc.name,
            '__value__': obj.constant_name
        }

    if isinstance(obj, JavaClassDesc):
        return {
            '__classdesc__': obj.name,
            '__uid__': obj.serial_version_uid,
            '__fields__': [str(f) for f in obj.fields]
        }

    if isinstance(obj, list):
        return [object_to_dict(item, seen) for item in obj]

    if isinstance(obj, dict):
        return {k: object_to_dict(v, seen) for k, v in obj.items()}

    return str(obj)


def extract_structure(obj: Any, depth: int = 0) -> str:
    """Extract and format the complete structure"""
    indent = "  " * depth
    lines = []

    if obj is None:
        return f"{indent}null"

    if isinstance(obj, str):
        # Escape and truncate long strings
        if len(obj) > 100:
            return f'{indent}"{obj[:100]}..."'
        return f'{indent}"{obj}"'

    if isinstance(obj, (int, float, bool)):
        return f"{indent}{obj}"

    if isinstance(obj, bytes):
        return f"{indent}<bytes: {len(obj)} bytes>"

    if isinstance(obj, JavaReference):
        resolved = obj.resolved
        if isinstance(resolved, str):
            return f'{indent}REF({obj.handle:#x}) -> "{resolved}"'
        elif isinstance(resolved, JavaClassDesc):
            return f"{indent}REF({obj.handle:#x}) -> ClassDesc({resolved.name})"
        else:
            return f"{indent}REF({obj.handle:#x})"

    if isinstance(obj, JavaObject):
        lines.append(f"{indent}Object: {obj.class_desc.name} (handle={obj.handle:#x})")
        for name, value in obj.field_values.items():
            lines.append(f"{indent}  .{name} =")
            lines.append(extract_structure(value, depth + 2))
        if obj.annotations:
            lines.append(f"{indent}  [annotations]:")
            for ann in obj.annotations:
                lines.append(extract_structure(ann, depth + 2))
        return "\n".join(lines)

    if isinstance(obj, JavaArray):
        lines.append(f"{indent}Array: {obj.class_desc.name} (handle={obj.handle:#x}, length={len(obj.elements)})")
        for i, elem in enumerate(obj.elements[:20]):  # Limit to first 20
            lines.append(f"{indent}  [{i}] =")
            lines.append(extract_structure(elem, depth + 2))
        if len(obj.elements) > 20:
            lines.append(f"{indent}  ... ({len(obj.elements) - 20} more elements)")
        return "\n".join(lines)

    if isinstance(obj, JavaEnum):
        return f"{indent}Enum: {obj.class_desc.name}.{obj.constant_name}"

    if isinstance(obj, JavaClassDesc):
        return f"{indent}ClassDesc: {obj.name} (uid={obj.serial_version_uid:#x})"

    return f"{indent}{type(obj).__name__}: {obj}"


def analyze_commands(obj: Any, commands: list = None) -> list:
    """Extract all command objects from the structure"""
    if commands is None:
        commands = []

    if isinstance(obj, JavaObject):
        class_name = obj.class_desc.name
        if 'command' in class_name.lower() or class_name.endswith('Command'):
            cmd_info = {
                'class': class_name,
                'handle': obj.handle,
                'fields': {}
            }
            for name, value in obj.field_values.items():
                if isinstance(value, (str, int, float, bool)) or value is None:
                    cmd_info['fields'][name] = value
                elif isinstance(value, JavaReference) and isinstance(value.resolved, str):
                    cmd_info['fields'][name] = value.resolved
                elif isinstance(value, JavaEnum):
                    cmd_info['fields'][name] = f"{value.class_desc.name}.{value.constant_name}"
            commands.append(cmd_info)

        # Recurse into field values
        for value in obj.field_values.values():
            analyze_commands(value, commands)
        for ann in obj.annotations:
            analyze_commands(ann, commands)

    elif isinstance(obj, JavaArray):
        for elem in obj.elements:
            analyze_commands(elem, commands)

    elif isinstance(obj, JavaReference):
        analyze_commands(obj.resolved, commands)

    return commands


def main():
    """Main function to parse and analyze the .bwn file"""
    import json

    file_path = "/Users/hiroki-matsui/Robo-Pat/Robo-Pat-Create/script/extracted/main.bwn"

    print(f"Parsing: {file_path}")
    print("=" * 80)

    with open(file_path, 'rb') as f:
        data = f.read()

    print(f"File size: {len(data)} bytes")
    print()

    # Parse the file
    parser = JavaSerializationParser(data)

    try:
        result = parser.parse()

        print("PARSING SUCCESSFUL!")
        print("=" * 80)

        # Print handle statistics
        print(f"\nTotal handles allocated: {parser.next_handle - parser.BASE_WIRE_HANDLE}")

        # Count object types
        type_counts = {}
        for handle, obj in parser.handles.items():
            type_name = type(obj).__name__
            if isinstance(obj, JavaObject):
                type_name = f"JavaObject({obj.class_desc.name})"
            elif isinstance(obj, JavaClassDesc):
                type_name = f"JavaClassDesc({obj.name})"
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

        print("\nObject types in handle table:")
        for type_name, count in sorted(type_counts.items(), key=lambda x: -x[1])[:30]:
            print(f"  {type_name}: {count}")

        # Print structure
        print("\n" + "=" * 80)
        print("FILE STRUCTURE:")
        print("=" * 80)
        print(extract_structure(result))

        # Extract commands
        print("\n" + "=" * 80)
        print("COMMANDS FOUND:")
        print("=" * 80)
        commands = analyze_commands(result)
        for i, cmd in enumerate(commands[:50]):  # Limit output
            print(f"\n[{i+1}] {cmd['class']}")
            for field, value in cmd['fields'].items():
                if value is not None and value != '':
                    val_str = str(value)
                    if len(val_str) > 80:
                        val_str = val_str[:80] + "..."
                    print(f"     .{field} = {val_str}")

        if len(commands) > 50:
            print(f"\n... and {len(commands) - 50} more commands")

        # Convert to dict and save as JSON
        print("\n" + "=" * 80)
        print("Converting to Python data structure...")

        data_structure = object_to_dict(result)

        # Save to JSON file
        output_file = "/Users/hiroki-matsui/Robo-Pat/Robo-Pat-Create/robopat-ai/bwn_structure.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data_structure, f, indent=2, ensure_ascii=False, default=str)

        print(f"Structure saved to: {output_file}")

        return data_structure

    except Exception as e:
        import traceback
        print(f"Parse error: {e}")
        traceback.print_exc()

        # Print last few log entries for debugging
        print("\nLast parse log entries:")
        for entry in parser.parse_log[-20:]:
            print(f"  offset={entry['offset']:#x}: {entry['type']} = {entry['value']}")

        return None


if __name__ == "__main__":
    result = main()
