#!/usr/bin/env python3
"""
Complete analysis and Python structure for the .bwn Java serialized file.

This file documents the complete binary structure of the Robo-Pat BWN file format.
"""

# ============================================================================
# JAVA SERIALIZATION PROTOCOL CONSTANTS
# ============================================================================

STREAM_MAGIC = 0xACED
STREAM_VERSION = 0x0005

# Type codes (TC_*)
TC_CODES = {
    0x70: "TC_NULL",           # Null reference
    0x71: "TC_REFERENCE",      # Reference to previously defined handle
    0x72: "TC_CLASSDESC",      # New class descriptor
    0x73: "TC_OBJECT",         # New object
    0x74: "TC_STRING",         # New string
    0x75: "TC_ARRAY",          # New array
    0x76: "TC_CLASS",          # Reference to a Class
    0x77: "TC_BLOCKDATA",      # Block data (writeObject annotations, <256 bytes)
    0x78: "TC_ENDBLOCKDATA",   # End of block data / annotations
    0x79: "TC_RESET",          # Reset stream
    0x7A: "TC_BLOCKDATALONG",  # Block data (>256 bytes)
    0x7B: "TC_EXCEPTION",      # Exception during stream
    0x7C: "TC_LONGSTRING",     # Long string (>64KB)
    0x7D: "TC_PROXYCLASSDESC", # Proxy class descriptor
    0x7E: "TC_ENUM",           # Enum constant
}

# Stream constants (SC_*)
SC_FLAGS = {
    0x01: "SC_WRITE_METHOD",   # Class has custom writeObject method
    0x02: "SC_SERIALIZABLE",   # Class is Serializable
    0x04: "SC_EXTERNALIZABLE", # Class is Externalizable
    0x08: "SC_BLOCK_DATA",     # Block data mode for externalizable
    0x10: "SC_ENUM",           # Class is an Enum
}

# Primitive type codes (for fields)
PRIMITIVE_TYPES = {
    'B': ('byte', 1),
    'C': ('char', 2),
    'D': ('double', 8),
    'F': ('float', 4),
    'I': ('int', 4),
    'J': ('long', 8),
    'S': ('short', 2),
    'Z': ('boolean', 1),
    'L': ('object', 'variable'),
    '[': ('array', 'variable'),
}

# ============================================================================
# BWN FILE STRUCTURE
# ============================================================================

BWN_FILE_STRUCTURE = {
    "description": "Robo-Pat BWN Script File (Java Serialized HashMap)",
    "format_version": "Java Object Serialization Stream Protocol",
    "magic": "0xACED",
    "version": "0x0005",

    "root_object": {
        "class": "java.util.HashMap",
        "serialVersionUID": "0x507dac1c31660d1",
        "flags": ["SC_WRITE_METHOD", "SC_SERIALIZABLE"],
        "fields": [
            {"name": "loadFactor", "type": "float", "typical_value": 0.75},
            {"name": "threshold", "type": "int", "typical_value": 12},
        ],
        "writeObject_data": {
            "description": "Custom HashMap serialization format",
            "format": [
                {"name": "capacity", "type": "int", "description": "Hash table capacity"},
                {"name": "size", "type": "int", "description": "Number of key-value pairs"},
                {"name": "entries", "type": "sequence", "description": "key-value pairs alternating"},
            ]
        },
        "top_level_keys": {
            "projectName": {
                "type": "String",
                "description": "Name of the Robo-Pat project",
                "example": "反響記録ロボット"
            },
            "scriptData": {
                "type": "java.util.concurrent.CopyOnWriteArrayList",
                "description": "List of script tabs",
                "contains": "java.util.Collections$SynchronizedMap"
            }
        }
    },

    "script_tab_structure": {
        "class": "java.util.Collections$SynchronizedMap",
        "contains": {
            "MergeInfoData": {
                "type": "java.util.ArrayList",
                "description": "Merge information"
            },
            "tabTitle": {
                "type": "String",
                "description": "Tab display name",
                "example": "実行タブ"
            },
            "commandData": {
                "type": "java.util.Collections$SynchronizedList",
                "description": "List of commands in this tab",
                "contains": "BrownieCommand subclasses"
            }
        }
    },

    "command_hierarchy": {
        "base_classes": [
            {
                "class": "com.asirrera.brownie.ide.command.Argument",
                "serialVersionUID": "-0x7276c5582f234b2b",
                "fields": [
                    {"name": "object", "type": "Object"},
                    {"name": "sourceCode", "type": "String"},
                ]
            },
            {
                "class": "com.asirrera.brownie.ide.command.BrownieCommand",
                "extends": "Argument",
                "serialVersionUID": "-0x18cf0ec0",
                "fields": [
                    {"name": "enabled", "type": "boolean"},
                    {"name": "isAddTableCommandIconSelected", "type": "boolean"},
                    {"name": "isChangeWaitTime", "type": "boolean"},
                    {"name": "privateWaitTimeSecond", "type": "double"},
                    {"name": "arguments", "type": "Arguments"},
                    {"name": "findModelOfOption", "type": "FindOptionModel"},
                    {"name": "metadata", "type": "HashMap", "contains": "Metadata enum -> value"},
                    {"name": "object", "type": "Object"},
                    {"name": "retryIf", "type": "RetryIf"},
                ]
            },
            {
                "class": "com.asirrera.brownie.ide.command.FlowCommand",
                "extends": "BrownieCommand",
                "fields": [
                    {"name": "isRetriable", "type": "boolean"},
                    {"name": "comment", "type": "String"},
                ]
            },
        ],

        "command_types_found": [
            "com.asirrera.brownie.ide.command.screen.record.ScreenRecordStart",
            "com.asirrera.brownie.ide.command.screen.record.ScreenRecordEnd",
            "com.asirrera.brownie.ide.command.GoToTab",
            "com.asirrera.brownie.ide.command.Comment",
            "com.asirrera.brownie.ide.plugin.PluginCommandFactory$PluginCommand",
            "com.asirrera.brownie.ide.web.command.inputText.InputText",
            "com.asirrera.brownie.ide.web.command.FindElementCommand",
            "com.asirrera.brownie.ide.web.command.WebCommand",
            # ... many more
        ]
    },

    "metadata_enum": {
        "class": "com.asirrera.brownie.ide.command.Metadata",
        "extends": "java.lang.Enum",
        "values": [
            "TAB_TITLE",
            "LINE_NUMBER",
            "CREATED_VERSION",
            "COMMENT",
            # ... more
        ]
    },

    "option_types": {
        "base": "com.asirrera.brownie.ide.command.option.AbstractCommandOption",
        "types": [
            "TextFieldOption",
            "VariableOption",
            "FileOptionFileOnly",
            "ListOption",
            "BooleanOption",
            # ... more
        ]
    },

    "web_command_structure": {
        "class": "com.asirrera.brownie.ide.web.command.WebCommand",
        "extends": "BrownieCommand",
        "fields": [
            {"name": "commandName", "type": "String"},
            {"name": "metaData", "type": "MetaData"},
            {"name": "webElementImage", "type": "WebElementImage"},
        ],
        "subclass_FindElementCommand": {
            "class": "com.asirrera.brownie.ide.web.command.FindElementCommand",
            "extends": "WebCommand",
            "fields": [
                {"name": "isInterruptableByKillingThread", "type": "boolean"},
                {"name": "isRunManagerPaused", "type": "boolean"},
                {"name": "isRunManagerStopped", "type": "boolean"},
                {"name": "commandName", "type": "String"},
                {"name": "findElementBy", "type": "FindElementBy"},
                {"name": "findElementByList", "type": "FindElementBy[]"},
                {"name": "findElementInsideLoopFlg", "type": "Boolean"},
                {"name": "findElementWaitSec", "type": "Integer"},
                {"name": "frameCssSelector", "type": "String"},
                {"name": "noSuchElementIgnoreFlg", "type": "Boolean"},
                {"name": "scrollType", "type": "ScrollType"},
            ]
        }
    },

    "meta_data_structure": {
        "class": "com.asirrera.brownie.ide.web.command.meta.MetaData",
        "fields": [
            {"name": "elementMetaData", "type": "ElementMetaData"},
            {"name": "pageMetaData", "type": "PageMetaData"},
            {"name": "settingMetaData", "type": "SettingMetaData"},
            # ... more
        ],
        "PageMetaData_fields": [
            {"name": "screenHeight", "type": "String"},
            {"name": "screenWidth", "type": "String"},
            {"name": "timestamp", "type": "String"},
            {"name": "url", "type": "String"},
            {"name": "userAgent", "type": "String"},
            {"name": "webBrowserType", "type": "WebBrowserType"},
            {"name": "windowInnerHeight", "type": "String"},
            {"name": "windowInnerWidth", "type": "String"},
            {"name": "windowPageXOffset", "type": "String"},
            {"name": "windowPageYOffset", "type": "String"},
        ]
    }
}

# ============================================================================
# BYTE-BY-BYTE PARSING RULES
# ============================================================================

PARSING_RULES = """
Java Object Serialization Stream Protocol Parsing Rules:

1. STREAM HEADER (4 bytes)
   - 2 bytes: Magic (0xACED)
   - 2 bytes: Version (0x0005)

2. CONTENT PARSING
   Read 1 byte Type Code (TC_*), then parse according to type:

   TC_NULL (0x70):
     - No additional data
     - Represents null reference

   TC_REFERENCE (0x71):
     - 4 bytes: Handle (int, big-endian)
     - References a previously serialized object/class

   TC_STRING (0x74):
     - Allocate new handle
     - 2 bytes: UTF length
     - N bytes: UTF-8 encoded string data

   TC_CLASSDESC (0x72):
     - Allocate new handle
     - 2 bytes: Class name length
     - N bytes: Class name (UTF-8)
     - 8 bytes: Serial version UID (long)
     - 1 byte: Flags (SC_*)
     - 2 bytes: Field count
     - For each field:
       - 1 byte: Type code (B/C/D/F/I/J/S/Z for primitives, L/[ for objects)
       - 2 bytes: Field name length
       - N bytes: Field name (UTF-8)
       - If L or [:
         - TC_STRING or TC_REFERENCE for type descriptor
     - Class annotation (contents until TC_ENDBLOCKDATA)
     - Super class descriptor (TC_CLASSDESC, TC_NULL, or TC_REFERENCE)

   TC_OBJECT (0x73):
     - Class descriptor (TC_CLASSDESC or TC_REFERENCE)
     - Allocate new handle
     - For each class in hierarchy (super to sub):
       - For each field: read field value according to type
       - If SC_WRITE_METHOD flag: read object annotation until TC_ENDBLOCKDATA

   TC_ARRAY (0x75):
     - Class descriptor for array type
     - Allocate new handle
     - 4 bytes: Array length
     - For each element: read value according to array element type

   TC_ENUM (0x7E):
     - Class descriptor (TC_CLASSDESC or TC_REFERENCE)
     - Allocate new handle
     - Constant name (TC_STRING or TC_REFERENCE)

   TC_BLOCKDATA (0x77):
     - 1 byte: Block length (0-255)
     - N bytes: Raw block data

   TC_BLOCKDATALONG (0x7A):
     - 4 bytes: Block length (int)
     - N bytes: Raw block data

   TC_ENDBLOCKDATA (0x78):
     - Marks end of annotations/block data section

3. HANDLE ALLOCATION
   - Handles start at 0x7E0000
   - Allocated to: Objects, Class descriptors, Strings, Arrays, Enums
   - Used for back-references via TC_REFERENCE

4. CLASS HIERARCHY
   - Fields are read in order from superclass to subclass
   - Each class in hierarchy contributes its own declared fields
   - writeObject annotations come after all fields for each class

5. SPECIAL COLLECTIONS
   HashMap:
     - Fields: loadFactor (float), threshold (int)
     - Annotations: BlockData(8 bytes: capacity, size), then key-value pairs

   ArrayList:
     - Fields: size (int)
     - Annotations: BlockData(4 bytes: capacity), then elements

   CopyOnWriteArrayList:
     - No fields
     - Annotations: BlockData(4 bytes: length), then elements
"""

# ============================================================================
# SAMPLE PARSED STRUCTURE
# ============================================================================

SAMPLE_STRUCTURE = {
    "__class__": "java.util.HashMap",
    "loadFactor": 0.75,
    "threshold": 12,
    "__annotations__": [
        {"__blockdata__": "0000001000000003"},  # capacity=16, size=3
        "projectName",
        "反響記録ロボット",
        "scriptData",
        {
            "__class__": "java.util.concurrent.CopyOnWriteArrayList",
            "__annotations__": [
                {"__blockdata__": "00000005"},  # 5 tabs
                {
                    "__class__": "java.util.Collections$SynchronizedMap",
                    "m": {
                        "__class__": "java.util.HashMap",
                        "__annotations__": [
                            "MergeInfoData", [],
                            "tabTitle", "実行タブ",
                            "commandData", {
                                "__class__": "java.util.Collections$SynchronizedList",
                                "list": {
                                    "__class__": "java.util.ArrayList",
                                    "size": 5,
                                    "__annotations__": [
                                        {
                                            "__class__": "com.asirrera.brownie.ide.command.screen.record.ScreenRecordStart",
                                            "enabled": True,
                                            "keyword": "ide.command.screen.record.ScreenRecordStart.commandName",
                                            "outputFilePath": "C:\\Program Files\\robopat\\log\\^%now%^_record.mp4",
                                            "recordQuality": {"__enum__": "RecordQualityOptions.PROPERTIES_VALUE"},
                                        },
                                        {
                                            "__class__": "com.asirrera.brownie.ide.command.GoToTab",
                                            "enabled": True,
                                            "fixedTabTitle": "初回起動",
                                        },
                                        # ... more commands
                                    ]
                                }
                            }
                        ]
                    }
                },
                # ... more tabs
            ]
        }
    ]
}


def print_structure():
    """Print the complete structure documentation."""
    import json

    print("=" * 80)
    print("BWN FILE FORMAT ANALYSIS")
    print("=" * 80)
    print()

    print("1. PROTOCOL CONSTANTS")
    print("-" * 40)
    print(f"Stream Magic: {STREAM_MAGIC:#06x}")
    print(f"Stream Version: {STREAM_VERSION:#06x}")
    print()

    print("Type Codes:")
    for code, name in sorted(TC_CODES.items()):
        print(f"  {code:#04x}: {name}")
    print()

    print("Flags:")
    for flag, name in sorted(SC_FLAGS.items()):
        print(f"  {flag:#04x}: {name}")
    print()

    print("2. FILE STRUCTURE")
    print("-" * 40)
    print(json.dumps(BWN_FILE_STRUCTURE, indent=2, ensure_ascii=False, default=str))
    print()

    print("3. PARSING RULES")
    print("-" * 40)
    print(PARSING_RULES)
    print()

    print("4. SAMPLE STRUCTURE")
    print("-" * 40)
    print(json.dumps(SAMPLE_STRUCTURE, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    print_structure()
