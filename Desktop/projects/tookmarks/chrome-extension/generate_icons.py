"""Generate simple SVG-based PNG icons for the Chrome extension."""
import struct
import zlib

def create_png(width, height, pixels):
    """Create a minimal PNG from RGBA pixel data."""
    def chunk(chunk_type, data):
        c = chunk_type + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)

    raw = b''
    for y in range(height):
        raw += b'\x00'  # filter byte
        for x in range(width):
            raw += bytes(pixels[y][x])

    header = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    return (b'\x89PNG\r\n\x1a\n' +
            chunk(b'IHDR', header) +
            chunk(b'IDAT', zlib.compress(raw)) +
            chunk(b'IEND', b''))

def draw_icon(size):
    """Draw a bookmark icon."""
    pixels = [[(0, 0, 0, 0)] * size for _ in range(size)]
    pad = max(1, size // 8)
    left = pad + size // 8
    right = size - pad - size // 8
    top = pad
    bottom = size - pad - size // 6
    mid_x = size // 2
    notch_y = bottom - size // 5

    # Blue color
    color = (88, 166, 255, 255)

    for y in range(top, bottom + 1):
        for x in range(left, right + 1):
            # Check if inside bookmark shape
            if y <= notch_y:
                pixels[y][x] = color
            else:
                # V-notch at bottom
                dist_from_center = abs(x - mid_x)
                max_dist = (right - left) // 2
                notch_depth = bottom - notch_y
                threshold = notch_depth * (1 - dist_from_center / max(max_dist, 1))
                if y - notch_y > threshold:
                    continue
                pixels[y][x] = color

    return create_png(size, size, pixels)

for s in [16, 48, 128]:
    with open(f'icon{s}.png', 'wb') as f:
        f.write(draw_icon(s))
    print(f'Generated icon{s}.png')
