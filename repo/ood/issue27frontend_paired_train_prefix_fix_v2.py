"""Exact historical F4 prefix identity envelope; never reads a file."""
import struct
import issue27frontend_paired_train_support_v1 as original


def prefix_digest(raw, event):
    original.require(isinstance(raw, bytes) and len(raw) % 524 == 0 and 1 <= len(raw)//524 <= 256,
                     'PREFIX_BYTE_SHAPE')
    original.require(type(event) is int and 0 <= event < len(raw)//524, 'PREFIX_EVENT_RANGE')
    n = event + 1
    return original.digest(b'F4_INPUT_V1\0' + struct.pack('<II', n, 131) + raw[:n*524])
