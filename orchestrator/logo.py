"""Logo production contract and dependency-free validation of opaque RGB PNGs."""
import hashlib
import struct
import zlib

LOGO_PATH = "public/logo-600x600.png"
LOGO_RULES = """Create an original app logo based on PRD.md, communicating the service at a glance.
Use a simple distinctive silhouette readable at 24, 32 and 48px. Check it on light and dark backgrounds.
Deliver public/logo-600x600.png: exactly 600 x 600 pixels, square, full-bleed opaque background,
no rounded outer corners or rounded-square frame, no transparency. Export as 8-bit RGB,
non-interlaced PNG without tRNS (the factory's supported submission format).
Never use Toss-provided icons or image resources, including modified derivatives.
Do not use human faces, including AI-generated photorealistic faces. Prefer abstract service symbols.
Do not copy other apps, brands, characters or copyrighted artwork. Record the creation method,
source files, any resource origins/licenses, and similar-logo comparisons. Do not assert legal clearance.
Save editable source and LOGO.md with concept, colors, provenance, small-size/light/dark inspection
evidence, and remaining human checks. Inspect actual rendered images; do not claim unseen checks.
If image generation is unavailable, render your own original geometric vector design to PNG.
If rendering or image inspection is unavailable, fail explicitly instead of substituting a placeholder.
Update local app icon references to this asset where supported; document console upload separately.
Do not upload or invent a hosted logo URL. Preserve unrelated app files.
"""


def validate_png(path):
    """Verify CRCs, full pixel stream and a deliberately narrow opaque PNG format."""
    data = path.read_bytes()
    if len(data) > 10_000_000 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Logo must be a PNG under 10 MB")
    offset, kinds, compressed = 8, [], bytearray()
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError("Truncated logo PNG")
        length, kind = struct.unpack(">I4s", data[offset:offset + 8])
        end = offset + 12 + length
        if end > len(data):
            raise ValueError("Truncated logo PNG chunk")
        body = data[offset + 8:end - 4]
        crc = struct.unpack(">I", data[end - 4:end])[0]
        if zlib.crc32(kind + body) & 0xffffffff != crc:
            raise ValueError("Invalid logo PNG checksum")
        if not kinds and kind != b"IHDR":
            raise ValueError("Logo PNG must start with IHDR")
        if kind == b"IHDR":
            if kinds or body != struct.pack(">IIBBBBB", 600, 600, 8, 2, 0, 0, 0):
                raise ValueError("Logo must be 600x600, opaque 8-bit RGB, non-interlaced PNG")
        elif kind == b"IDAT":
            if b"IDAT" in kinds and kinds[-1] != b"IDAT":
                raise ValueError("Nonconsecutive PNG image data")
            compressed.extend(body)
        elif kind == b"IEND":
            if body or end != len(data):
                raise ValueError("Invalid PNG end")
        elif kind in (b"tRNS", b"acTL") or not kind[0] & 32:
            raise ValueError("Unsupported or transparent logo PNG")
        kinds.append(kind)
        offset = end
    if not kinds or kinds[-1] != b"IEND" or b"IDAT" not in kinds:
        raise ValueError("Incomplete logo PNG")
    expected = 600 * (600 * 3 + 1)
    try:
        decoder = zlib.decompressobj()
        pixels = decoder.decompress(compressed, expected + 1)
    except zlib.error as exc:
        raise ValueError("Invalid PNG pixel stream") from exc
    if len(pixels) != expected or not decoder.eof or decoder.unused_data:
        raise ValueError("Invalid PNG pixel data size")
    if any(pixels[row * 1801] > 4 for row in range(600)):
        raise ValueError("Invalid PNG row filter")
    return hashlib.sha256(data).hexdigest()
