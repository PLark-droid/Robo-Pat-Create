#!/usr/bin/env python3
"""
Simple byte-level dumper for Java serialization format.
This produces a detailed structural analysis without trying to fully deserialize.
"""

import struct
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import io


# Type codes
TC_NAMES = {
    0x70: "TC_NULL",
    0x71: "TC_REFERENCE",
    0x72: "TC_CLASSDESC",
    0x73: "TC_OBJECT",
    0x74: "TC_STRING",
    0x75: "TC_ARRAY",
    0x76: "TC_CLASS",
    0x77: "TC_BLOCKDATA",
    0x78: "TC_ENDBLOCKDATA",
    0x79: "TC_RESET",
    0x7A: "TC_BLOCKDATALONG",
    0x7B: "TC_EXCEPTION",
    0x7C: "TC_LONGSTRING",
    0x7D: "TC_PROXYCLASSDESC",
    0x7E: "TC_ENUM",
}

PRIM_NAMES = {
    'B': 'byte',
    'C': 'char',
    'D': 'double',
    'F': 'float',
    'I': 'int',
    'J': 'long',
    'S': 'short',
    'Z': 'boolean',
    'L': 'object',
    '[': 'array',
}


@dataclass
class ClassInfo:
    name: str
    uid: int
    flags: int
    fields: List[tuple]  # (type_code, name, class_name)
    super_handle: Optional[int] = None
    super_class: Optional['ClassInfo'] = None
    handle: int = 0


class JavaStreamDumper:
    def __init__(self, data: bytes):
        self.data = data
        self.stream = io.BytesIO(data)
        self.handles: Dict[int, Any] = {}
        self.next_handle = 0x7e0000
        self.output_lines = []
        self.indent = 0

    def pos(self):
        return self.stream.tell()

    def read_byte(self):
        return struct.unpack('>B', self.stream.read(1))[0]

    def read_short(self):
        return struct.unpack('>h', self.stream.read(2))[0]

    def read_ushort(self):
        return struct.unpack('>H', self.stream.read(2))[0]

    def read_int(self):
        return struct.unpack('>i', self.stream.read(4))[0]

    def read_long(self):
        return struct.unpack('>q', self.stream.read(8))[0]

    def read_float(self):
        return struct.unpack('>f', self.stream.read(4))[0]

    def read_double(self):
        return struct.unpack('>d', self.stream.read(8))[0]

    def read_utf(self):
        length = self.read_ushort()
        data = self.stream.read(length)
        try:
            return data.decode('utf-8')
        except:
            return data.decode('latin-1')

    def log(self, msg):
        indent = "  " * self.indent
        self.output_lines.append(f"{indent}{msg}")

    def new_handle(self):
        h = self.next_handle
        self.next_handle += 1
        return h

    def dump(self):
        magic = self.read_ushort()
        version = self.read_ushort()
        self.log(f"[0x0000] STREAM_MAGIC: {magic:#06x}")
        self.log(f"[0x0002] STREAM_VERSION: {version:#04x}")

        self.dump_content()

        return "\n".join(self.output_lines)

    def dump_content(self):
        start = self.pos()
        tc = self.read_byte()
        tc_name = TC_NAMES.get(tc, f"0x{tc:02x}")
        self.log(f"[{start:#06x}] {tc_name}")

        if tc == 0x70:  # TC_NULL
            pass
        elif tc == 0x71:  # TC_REFERENCE
            handle = self.read_int()
            self.indent += 1
            ref_obj = self.handles.get(handle)
            if isinstance(ref_obj, ClassInfo):
                self.log(f"-> handle {handle:#x} ({ref_obj.name})")
            elif isinstance(ref_obj, str):
                s = ref_obj[:40] + "..." if len(ref_obj) > 40 else ref_obj
                self.log(f'-> handle {handle:#x} ("{s}")')
            else:
                self.log(f"-> handle {handle:#x}")
            self.indent -= 1
        elif tc == 0x72:  # TC_CLASSDESC
            self.dump_new_classdesc()
        elif tc == 0x73:  # TC_OBJECT
            self.dump_new_object()
        elif tc == 0x74:  # TC_STRING
            self.dump_new_string()
        elif tc == 0x75:  # TC_ARRAY
            self.dump_new_array()
        elif tc == 0x77:  # TC_BLOCKDATA
            size = self.read_byte()
            data = self.stream.read(size)
            self.indent += 1
            self.log(f"BlockData: {size} bytes - {data.hex()[:60]}{'...' if len(data) > 30 else ''}")
            self.indent -= 1
        elif tc == 0x78:  # TC_ENDBLOCKDATA
            pass
        elif tc == 0x7E:  # TC_ENUM
            self.dump_new_enum()
        else:
            self.log(f"UNKNOWN TC: {tc:#x}")

    def dump_classdesc(self) -> Optional[ClassInfo]:
        """Read class descriptor (with type code)"""
        start = self.pos()
        tc = self.read_byte()

        if tc == 0x70:  # TC_NULL
            self.log(f"[{start:#06x}] TC_NULL (no super)")
            return None
        elif tc == 0x71:  # TC_REFERENCE
            handle = self.read_int()
            ref = self.handles.get(handle)
            if isinstance(ref, ClassInfo):
                self.log(f"[{start:#06x}] TC_REFERENCE -> {handle:#x} ({ref.name})")
            else:
                self.log(f"[{start:#06x}] TC_REFERENCE -> {handle:#x}")
            return ref
        elif tc == 0x72:  # TC_CLASSDESC
            self.log(f"[{start:#06x}] TC_CLASSDESC")
            return self.dump_new_classdesc()
        else:
            self.log(f"[{start:#06x}] Unexpected TC in classdesc: {tc:#x}")
            return None

    def dump_new_classdesc(self) -> ClassInfo:
        start = self.pos()
        class_name = self.read_utf()
        uid = self.read_long()
        handle = self.new_handle()
        flags = self.read_byte()
        field_count = self.read_ushort()

        flags_str = []
        if flags & 0x01: flags_str.append("SC_WRITE_METHOD")
        if flags & 0x02: flags_str.append("SC_SERIALIZABLE")
        if flags & 0x04: flags_str.append("SC_EXTERNALIZABLE")
        if flags & 0x10: flags_str.append("SC_ENUM")

        self.indent += 1
        self.log(f"Class: {class_name}")
        self.log(f"Handle: {handle:#x}")
        self.log(f"SerialVersionUID: {uid:#x}")
        self.log(f"Flags: {flags:#x} [{', '.join(flags_str)}]")
        self.log(f"Fields: {field_count}")

        fields = []
        for i in range(field_count):
            type_code = chr(self.read_byte())
            field_name = self.read_utf()
            class_name_ref = None
            if type_code in ('L', '['):
                # Read type string
                tc = self.read_byte()
                if tc == 0x74:  # TC_STRING
                    h = self.new_handle()
                    class_name_ref = self.read_utf()
                    self.handles[h] = class_name_ref
                elif tc == 0x71:  # TC_REFERENCE
                    ref_h = self.read_int()
                    class_name_ref = self.handles.get(ref_h, f"<ref:{ref_h:#x}>")
            fields.append((type_code, field_name, class_name_ref))
            type_str = PRIM_NAMES.get(type_code, type_code)
            if class_name_ref:
                self.log(f"  [{i}] {type_str} {field_name}: {class_name_ref}")
            else:
                self.log(f"  [{i}] {type_str} {field_name}")

        class_info = ClassInfo(
            name=class_name,
            uid=uid,
            flags=flags,
            fields=fields,
            handle=handle
        )
        self.handles[handle] = class_info

        # Read class annotation
        self.log("ClassAnnotation:")
        self.indent += 1
        while True:
            p = self.pos()
            tc = self.read_byte()
            if tc == 0x78:  # TC_ENDBLOCKDATA
                self.log(f"[{p:#06x}] TC_ENDBLOCKDATA")
                break
            self.stream.seek(p)
            self.dump_content()
        self.indent -= 1

        # Read super class
        self.log("SuperClass:")
        self.indent += 1
        class_info.super_class = self.dump_classdesc()
        self.indent -= 1

        self.indent -= 1
        return class_info

    def dump_new_object(self):
        self.indent += 1
        self.log("ClassDesc:")
        self.indent += 1
        class_info = self.dump_classdesc()
        self.indent -= 1

        if class_info is None:
            self.indent -= 1
            return

        handle = self.new_handle()
        if isinstance(class_info, ClassInfo):
            self.handles[handle] = ("Object", class_info.name)
        else:
            self.handles[handle] = ("Object", str(class_info))
        self.log(f"Object handle: {handle:#x}")

        # Build hierarchy
        hierarchy = []
        current = class_info
        while current and isinstance(current, ClassInfo):
            hierarchy.append(current)
            current = current.super_class
        hierarchy.reverse()

        if not hierarchy:
            self.log(f"No class hierarchy (class_info type: {type(class_info).__name__})")
            self.indent -= 1
            return

        self.log("Instance data (super to sub):")
        self.indent += 1
        for cls in hierarchy:
            self.log(f"[{cls.name}]")
            self.indent += 1
            for type_code, field_name, _ in cls.fields:
                self.dump_field_value(type_code, field_name)

            # Check for writeObject annotations
            if cls.flags & 0x01:  # SC_WRITE_METHOD
                self.log("ObjectAnnotation:")
                self.indent += 1
                while True:
                    p = self.pos()
                    tc = self.read_byte()
                    if tc == 0x78:  # TC_ENDBLOCKDATA
                        self.log(f"[{p:#06x}] TC_ENDBLOCKDATA")
                        break
                    self.stream.seek(p)
                    self.dump_content()
                self.indent -= 1
            self.indent -= 1
        self.indent -= 1
        self.indent -= 1

    def dump_field_value(self, type_code: str, field_name: str):
        start = self.pos()
        if type_code == 'B':
            val = self.read_byte()
            self.log(f"[{start:#06x}] .{field_name} (byte) = {val}")
        elif type_code == 'C':
            val = chr(self.read_ushort())
            self.log(f"[{start:#06x}] .{field_name} (char) = '{val}'")
        elif type_code == 'D':
            val = self.read_double()
            self.log(f"[{start:#06x}] .{field_name} (double) = {val}")
        elif type_code == 'F':
            val = self.read_float()
            self.log(f"[{start:#06x}] .{field_name} (float) = {val}")
        elif type_code == 'I':
            val = self.read_int()
            self.log(f"[{start:#06x}] .{field_name} (int) = {val}")
        elif type_code == 'J':
            val = self.read_long()
            self.log(f"[{start:#06x}] .{field_name} (long) = {val}")
        elif type_code == 'S':
            val = self.read_short()
            self.log(f"[{start:#06x}] .{field_name} (short) = {val}")
        elif type_code == 'Z':
            val = self.read_byte() != 0
            self.log(f"[{start:#06x}] .{field_name} (boolean) = {val}")
        elif type_code in ('L', '['):
            self.log(f"[{start:#06x}] .{field_name} (object):")
            self.indent += 1
            self.dump_content()
            self.indent -= 1

    def dump_new_string(self):
        handle = self.new_handle()
        s = self.read_utf()
        self.handles[handle] = s
        self.indent += 1
        s_display = s[:60] + "..." if len(s) > 60 else s
        self.log(f'String (handle={handle:#x}): "{s_display}"')
        self.indent -= 1

    def dump_new_array(self):
        self.indent += 1
        self.log("ClassDesc:")
        self.indent += 1
        class_info = self.dump_classdesc()
        self.indent -= 1

        handle = self.new_handle()
        size = self.read_int()
        if isinstance(class_info, ClassInfo):
            self.handles[handle] = ("Array", class_info.name, size)
        else:
            self.handles[handle] = ("Array", str(class_info), size)

        self.log(f"Array handle: {handle:#x}, size: {size}")

        if isinstance(class_info, ClassInfo) and class_info.name.startswith('['):
            elem_type = class_info.name[1]
        elif isinstance(class_info, str) and class_info.startswith('['):
            elem_type = class_info[1]
        else:
            elem_type = 'L'

        self.log(f"Elements (type={elem_type}):")
        self.indent += 1
        for i in range(min(size, 10)):  # Limit for readability
            start = self.pos()
            if elem_type == 'B':
                val = self.read_byte()
                self.log(f"[{start:#06x}] [{i}] = {val}")
            elif elem_type == 'I':
                val = self.read_int()
                self.log(f"[{start:#06x}] [{i}] = {val}")
            elif elem_type == 'J':
                val = self.read_long()
                self.log(f"[{start:#06x}] [{i}] = {val}")
            elif elem_type == 'Z':
                val = self.read_byte() != 0
                self.log(f"[{start:#06x}] [{i}] = {val}")
            else:
                self.log(f"[{start:#06x}] [{i}]:")
                self.indent += 1
                self.dump_content()
                self.indent -= 1

        if size > 10:
            # Skip remaining elements
            for i in range(10, size):
                if elem_type == 'B':
                    self.read_byte()
                elif elem_type == 'I':
                    self.read_int()
                elif elem_type == 'J':
                    self.read_long()
                elif elem_type == 'Z':
                    self.read_byte()
                else:
                    self.dump_content_silent()
            self.log(f"... ({size - 10} more elements)")

        self.indent -= 1
        self.indent -= 1

    def dump_content_silent(self):
        """Dump content without logging (for skipping)"""
        tc = self.read_byte()
        if tc == 0x70:  # TC_NULL
            pass
        elif tc == 0x71:  # TC_REFERENCE
            self.read_int()
        elif tc == 0x72:  # TC_CLASSDESC
            # Skip class desc - complex
            pass
        elif tc == 0x73:  # TC_OBJECT
            self.dump_content_silent()  # classdesc
            # Would need to read instance data - skip for now
            pass
        elif tc == 0x74:  # TC_STRING
            self.new_handle()
            self.read_utf()
        elif tc == 0x77:  # TC_BLOCKDATA
            size = self.read_byte()
            self.stream.read(size)
        elif tc == 0x7E:  # TC_ENUM
            self.dump_content_silent()  # classdesc
            self.dump_content_silent()  # constant name

    def dump_new_enum(self):
        self.indent += 1
        self.log("ClassDesc:")
        self.indent += 1
        class_info = self.dump_classdesc()
        self.indent -= 1

        handle = self.new_handle()
        if isinstance(class_info, ClassInfo):
            self.handles[handle] = ("Enum", class_info.name)
        else:
            self.handles[handle] = ("Enum", str(class_info))

        self.log(f"Enum handle: {handle:#x}")
        self.log("Constant name:")
        self.indent += 1
        self.dump_content()
        self.indent -= 1
        self.indent -= 1


def main():
    file_path = "/Users/hiroki-matsui/Robo-Pat/Robo-Pat-Create/script/extracted/main.bwn"

    with open(file_path, 'rb') as f:
        data = f.read()

    print(f"File: {file_path}")
    print(f"Size: {len(data)} bytes")
    print("=" * 80)

    dumper = JavaStreamDumper(data)

    try:
        output = dumper.dump()
        # Print first part
        lines = output.split('\n')
        for line in lines[:500]:
            print(line)
        if len(lines) > 500:
            print(f"\n... ({len(lines) - 500} more lines)")

        # Save full output
        with open("/Users/hiroki-matsui/Robo-Pat/Robo-Pat-Create/robopat-ai/bwn_dump.txt", 'w') as f:
            f.write(output)
        print(f"\nFull output saved to bwn_dump.txt")

    except Exception as e:
        import traceback
        print(f"\nError at offset {dumper.pos():#x}: {e}")
        traceback.print_exc()

        # Show context
        pos = dumper.pos()
        dumper.stream.seek(max(0, pos - 16))
        context = dumper.stream.read(48)
        print(f"\nBytes around error:")
        print(f"  {context.hex()}")

        # Print what we have so far
        print("\nPartial output:")
        for line in dumper.output_lines[-50:]:
            print(line)


if __name__ == "__main__":
    main()
