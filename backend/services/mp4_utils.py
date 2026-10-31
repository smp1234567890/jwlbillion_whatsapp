"""
Pure-Python MP4 faststart utility (zero external dependencies).
Relocates the 'moov' atom before the 'mdat' atom so videos can be streamed
and played immediately by players without waiting for full download.
"""

import struct
import logging

logger = logging.getLogger("mp4_faststart")


def optimize_mp4_faststart(data: bytes) -> bytes:
    """
    Takes raw bytes of an MP4 file.
    If the 'moov' atom is located after the 'mdat' atom, moves 'moov' to the front
    (after 'ftyp') and adjusts 32-bit ('stco') and 64-bit ('co64') chunk offsets.
    Returns optimized bytes ready for streaming and WhatsApp playback.
    """
    size = len(data)
    pos = 0
    atoms = []
    moov_data = None
    moov_pos = -1
    mdat_pos = -1

    try:
        while pos < size:
            if pos + 8 > size:
                break
            atom_size, tag = struct.unpack('>I4s', data[pos:pos+8])
            if atom_size == 1:
                atom_size = struct.unpack('>Q', data[pos+8:pos+16])[0]
            elif atom_size == 0:
                atom_size = size - pos

            tag_str = tag.decode('latin1', errors='replace')
            atoms.append((tag_str, pos, atom_size))
            if tag_str == 'moov':
                moov_data = bytearray(data[pos:pos+atom_size])
                moov_pos = pos
            elif tag_str == 'mdat':
                mdat_pos = pos
            pos += atom_size

        # If moov is after mdat, relocate
        if moov_pos > mdat_pos and moov_data:
            offset = len(moov_data)

            # Patch 32-bit chunk offsets (stco)
            idx = 0
            while True:
                idx = moov_data.find(b'stco', idx)
                if idx == -1:
                    break
                entry_count = struct.unpack('>I', moov_data[idx+8:idx+12])[0]
                for e in range(entry_count):
                    entry_offset = idx + 12 + e * 4
                    old_val = struct.unpack('>I', moov_data[entry_offset:entry_offset+4])[0]
                    new_val = old_val + offset
                    moov_data[entry_offset:entry_offset+4] = struct.pack('>I', new_val)
                idx += 4

            # Patch 64-bit chunk offsets (co64) if present
            idx = 0
            while True:
                idx = moov_data.find(b'co64', idx)
                if idx == -1:
                    break
                entry_count = struct.unpack('>I', moov_data[idx+8:idx+12])[0]
                for e in range(entry_count):
                    entry_offset = idx + 12 + e * 8
                    old_val = struct.unpack('>Q', moov_data[entry_offset:entry_offset+8])[0]
                    new_val = old_val + offset
                    moov_data[entry_offset:entry_offset+8] = struct.pack('>Q', new_val)
                idx += 4

            ftyp_list = [a for a in atoms if a[0] == 'ftyp']
            if not ftyp_list:
                return data
            ftyp_atom = ftyp_list[0]
            ftyp_data = data[ftyp_atom[1]:ftyp_atom[1]+ftyp_atom[2]]

            mdat_list = [a for a in atoms if a[0] == 'mdat']
            if not mdat_list:
                return data
            mdat_atom = mdat_list[0]
            mdat_data = data[mdat_atom[1]:mdat_atom[1]+mdat_atom[2]]

            out = bytearray()
            out.extend(ftyp_data)
            out.extend(moov_data)
            out.extend(mdat_data)
            logger.info(f"Faststart optimization applied: moved moov atom (+{offset} bytes) before mdat.")
            return bytes(out)

    except Exception as e:
        logger.warning(f"Faststart optimization failed, using original data: {e}")

    return data
