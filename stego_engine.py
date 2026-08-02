#!/usr/bin/env python3
import os
import zlib
import hashlib
from struct import pack, unpack

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_SOI = b"\xff\xd8"
JPEG_EOI = b"\xff\xd9"
JPEG_COM = b"\xff\xfe"


class PNGChunkWriter:
    def __init__(self):
        self.chunks = []

    def add_chunk(self, chunk_type: bytes, data: bytes):
        length = pack(">I", len(data))
        crc = pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
        self.chunks.append(length + chunk_type + data + crc)

    def build(self) -> bytes:
        return PNG_MAGIC + b"".join(self.chunks)


class FileSteg:
    def __init__(self, password: str):
        self.password = password
        self.salt_size = 16
        self.key_iterations = 100000

    def _derive_key(self, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac('sha256', self.password.encode(), salt, self.key_iterations, 32)

    def _encrypt(self, data: bytes) -> tuple[bytes, bytes]:
        salt = os.urandom(self.salt_size)
        key = self._derive_key(salt)
        encrypted = bytes([data[i] ^ key[i % 32] for i in range(len(data))])
        return salt, encrypted

    def _decrypt(self, salt: bytes, encrypted: bytes) -> bytes:
        key = self._derive_key(salt)
        return bytes([encrypted[i] ^ key[i % 32] for i in range(len(encrypted))])

    def _create_payload(self, file_data: bytes) -> bytes:
        crc = zlib.crc32(file_data) & 0xFFFFFFFF
        salt, encrypted = self._encrypt(file_data)
        length = len(file_data)
        payload = pack(">I", length) + salt + encrypted + pack(">I", crc)
        return payload

    def _extract_payload(self, data: bytes) -> bytes | None:
        try:
            if len(data) < 24:
                return None
            length = unpack(">I", data[:4])[0]
            if length > 100000000 or length == 0:  # Allow up to 100MB files
                return None
            salt = data[4:20]
            encrypted = data[20:20 + length]
            stored_crc = unpack(">I", data[20 + length:24 + length])[0]
            decrypted = self._decrypt(salt, encrypted)
            if zlib.crc32(decrypted) & 0xFFFFFFFF != stored_crc:
                return None
            return decrypted
        except Exception:
            return None


class PNGDeflateFileSteg(FileSteg):
    MARKER = b'\xDE\xAD\xBE\xEF'

    def hide(self, file_data: bytes, input_path: str, output_path: str) -> bool:
        with open(input_path, 'rb') as f:
            png_data = f.read()

        if png_data[:8] != PNG_MAGIC:
            print("Error: Input must be PNG format")
            return False

        payload = self._create_payload(file_data)
        trailing_data = self.MARKER + pack(">I", len(payload)) + payload

        writer = PNGChunkWriter()
        pos = 8
        idat_bodies = []

        while pos < len(png_data):
            chunk_len = unpack(">I", png_data[pos:pos + 4])[0]
            chunk_type = png_data[pos + 4:pos + 8]
            chunk_body = png_data[pos + 8:pos + 8 + chunk_len]
            pos += 12 + chunk_len

            if chunk_type == b"IHDR":
                writer.add_chunk(chunk_type, chunk_body)
            elif chunk_type == b"PLTE":
                writer.add_chunk(chunk_type, chunk_body)
            elif chunk_type == b"IDAT":
                idat_bodies.append(chunk_body)
            elif chunk_type == b"IEND":
                combined_idat = b"".join(idat_bodies) + trailing_data
                writer.add_chunk(b"IDAT", combined_idat)
                writer.add_chunk(b"IEND", b"")
                break
            elif chunk_type[0:1].islower():
                continue
            else:
                writer.add_chunk(chunk_type, chunk_body)

        with open(output_path, 'wb') as f:
            f.write(writer.build())

        return True

    def reveal(self, input_path: str) -> bytes | None:
        with open(input_path, 'rb') as f:
            png_data = f.read()

        if png_data[:8] != PNG_MAGIC:
            return None

        pos = 8
        while pos < len(png_data):
            chunk_len = unpack(">I", png_data[pos:pos + 4])[0]
            chunk_type = png_data[pos + 4:pos + 8]
            chunk_body = png_data[pos + 8:pos + 8 + chunk_len]
            pos += 12 + chunk_len

            if chunk_type == b"IDAT":
                marker_pos = chunk_body.find(self.MARKER)
                if marker_pos != -1:
                    payload_len = unpack(">I", chunk_body[marker_pos + 4:marker_pos + 8])[0]
                    payload = chunk_body[marker_pos + 8:marker_pos + 8 + payload_len]
                    result = self._extract_payload(payload)
                    if result is not None:
                        return result

        return None


class RobustBlockFileSteg(FileSteg):
    def __init__(self, password: str, block_size: int = 8, redundancy: int = 3, strength: int = 25):
        super().__init__(password)
        self.block_size = block_size
        self.redundancy = redundancy
        self.strength = strength

    def _bytes_to_bits(self, data: bytes) -> str:
        return ''.join(f'{b:08b}' for b in data)

    def _bits_to_bytes(self, bits: str) -> bytes:
        return bytes(int(bits[i:i+8], 2) for i in range(0, len(bits) - 7, 8))

    def _hamming_encode(self, bits: str) -> str:
        encoded = []
        for i in range(0, len(bits), 4):
            chunk = bits[i:i+4].ljust(4, '0')
            d1, d2, d3, d4 = [int(b) for b in chunk]
            p1 = d1 ^ d2 ^ d4
            p2 = d1 ^ d3 ^ d4
            p3 = d2 ^ d3 ^ d4
            encoded.append(f'{p1}{p2}{d1}{p3}{d2}{d3}{d4}')
        return ''.join(encoded)

    def _hamming_decode(self, bits: str) -> str:
        decoded = []
        for i in range(0, len(bits) - 6, 7):
            chunk = bits[i:i+7]
            if len(chunk) < 7:
                break
            p1, p2, d1, p3, d2, d3, d4 = [int(b) for b in chunk]
            s1 = p1 ^ d1 ^ d2 ^ d4
            s2 = p2 ^ d1 ^ d3 ^ d4
            s3 = p3 ^ d2 ^ d3 ^ d4
            error_pos = s1 * 1 + s2 * 2 + s3 * 4
            bits_list = [p1, p2, d1, p3, d2, d3, d4]
            if error_pos > 0 and error_pos <= 7:
                bits_list[error_pos - 1] ^= 1
            decoded.append(f'{bits_list[2]}{bits_list[4]}{bits_list[5]}{bits_list[6]}')
        return ''.join(decoded)

    def get_max_capacity(self, width: int, height: int) -> int:
        blocks_h = height // self.block_size
        blocks_w = width // self.block_size
        total_blocks = blocks_h * blocks_w
        # bits_needed = len(encoded_bits) * redundancy
        # encoded_bits = bits * 7 / 4
        # bits = payload_bytes * 8
        # total_blocks >= (payload_bytes * 8 * 7 / 4) * redundancy
        # total_blocks >= payload_bytes * 14 * redundancy
        # payload_bytes <= total_blocks // (14 * redundancy)
        # file_bytes = payload_bytes - 24
        payload_bytes = total_blocks // (14 * self.redundancy)
        return max(0, payload_bytes - 24)

    def hide(self, file_data: bytes, input_path: str, output_path: str) -> bool:
        try:
            from PIL import Image
            import numpy as np
        except ImportError:
            print("Error: PIL and numpy are required. Install them first.")
            return False

        img = Image.open(input_path).convert('RGB')
        pixels = np.array(img, dtype=np.float64)
        h, w, _ = pixels.shape

        payload = self._create_payload(file_data)
        bits = self._bytes_to_bits(payload)
        encoded_bits = self._hamming_encode(bits)

        blocks_h = h // self.block_size
        blocks_w = w // self.block_size
        total_blocks = blocks_h * blocks_w
        bits_needed = len(encoded_bits) * self.redundancy

        if bits_needed > total_blocks:
            max_bytes = self.get_max_capacity(w, h)
            print(f"Error: Image too small. Max capacity for this image is {max_bytes} bytes. Payload is {len(file_data)} bytes.")
            return False

        seed = int.from_bytes(hashlib.sha256(self.password.encode()).digest()[:4], 'big')
        np.random.seed(seed)
        block_order = np.random.permutation(total_blocks)

        Y = 0.299 * pixels[:,:,0] + 0.587 * pixels[:,:,1] + 0.114 * pixels[:,:,2]

        bit_idx = 0
        for i, block_num in enumerate(block_order):
            if bit_idx >= len(encoded_bits):
                break

            by = (block_num // blocks_w) * self.block_size
            bx = (block_num % blocks_w) * self.block_size

            current_bit = encoded_bits[bit_idx]
            block_y = Y[by:by+self.block_size, bx:bx+self.block_size]
            avg_lum = np.mean(block_y)

            target_offset = self.strength if current_bit == '1' else -self.strength

            center_y = self.block_size // 4
            center_x = self.block_size // 4
            center_h = self.block_size // 2
            center_w = self.block_size // 2

            for c in range(3):
                block = pixels[by:by+self.block_size, bx:bx+self.block_size, c]
                center_slice = block[center_y:center_y+center_h, center_x:center_x+center_w]
                edge_mask = np.ones((self.block_size, self.block_size), dtype=bool)
                edge_mask[center_y:center_y+center_h, center_x:center_x+center_w] = False

                half_offset = target_offset * 0.5
                center_slice += half_offset
                block[edge_mask] -= half_offset

            if (i + 1) % self.redundancy == 0:
                bit_idx += 1

        pixels = np.clip(pixels, 0, 255).astype(np.uint8)
        result = Image.fromarray(pixels)

        ext = output_path.lower().split('.')[-1]
        if ext in ['jpg', 'jpeg']:
            result.save(output_path, 'JPEG', quality=92)
        else:
            result.save(output_path, 'PNG')

        return True

    def reveal(self, input_path: str) -> bytes | None:
        try:
            from PIL import Image
            import numpy as np
        except ImportError:
            return None

        img = Image.open(input_path).convert('RGB')
        pixels = np.array(img, dtype=np.float64)
        h, w, _ = pixels.shape

        blocks_h = h // self.block_size
        blocks_w = w // self.block_size
        total_blocks = blocks_h * blocks_w

        seed = int.from_bytes(hashlib.sha256(self.password.encode()).digest()[:4], 'big')
        np.random.seed(seed)
        block_order = np.random.permutation(total_blocks)

        Y = 0.299 * pixels[:,:,0] + 0.587 * pixels[:,:,1] + 0.114 * pixels[:,:,2]

        max_bits = min(total_blocks // self.redundancy, 100000)
        votes = {}

        for i, block_num in enumerate(block_order[:max_bits * self.redundancy]):
            by = (block_num // blocks_w) * self.block_size
            bx = (block_num % blocks_w) * self.block_size

            block_y = Y[by:by+self.block_size, bx:bx+self.block_size]

            center_y = self.block_size // 4
            center_x = self.block_size // 4
            center_h = self.block_size // 2
            center_w = self.block_size // 2

            center_lum = np.mean(block_y[center_y:center_y+center_h, center_x:center_x+center_w])
            edge_mask = np.ones_like(block_y, dtype=bool)
            edge_mask[center_y:center_y+center_h, center_x:center_x+center_w] = False
            edge_lum = np.mean(block_y[edge_mask])

            diff = center_lum - edge_lum

            bit_num = i // self.redundancy
            if bit_num not in votes:
                votes[bit_num] = []
            votes[bit_num].append(1 if diff > 0 else 0)

        bits = []
        for i in range(len(votes)):
            if i not in votes:
                break
            vote_sum = sum(votes[i])
            bit = 1 if vote_sum > len(votes[i]) / 2 else 0
            bits.append(str(bit))

        encoded_bits = ''.join(bits)
        decoded_bits = self._hamming_decode(encoded_bits)

        # Slide search in case of bit misalignment
        for start in range(0, min(32, len(decoded_bits)), 8):
            try:
                payload = self._bits_to_bytes(decoded_bits[start:])
                result = self._extract_payload(payload)
                if result is not None:
                    return result
            except Exception:
                continue

        return None


class MultiMethodFileSteg:
    def __init__(self, password: str):
        self.password = password
        self.png_steg = PNGDeflateFileSteg(password)
        self.robust_steg = RobustBlockFileSteg(password)

    def hide(self, file_data: bytes, input_path: str, output_path: str, method: str = "auto", **kwargs) -> bool:
        ext_in = input_path.lower().split('.')[-1]
        ext_out = output_path.lower().split('.')[-1]

        if method == "robust":
            # Pass advanced parameters if specified
            if "block_size" in kwargs:
                self.robust_steg.block_size = kwargs["block_size"]
            if "redundancy" in kwargs:
                self.robust_steg.redundancy = kwargs["redundancy"]
            if "strength" in kwargs:
                self.robust_steg.strength = kwargs["strength"]
            return self.robust_steg.hide(file_data, input_path, output_path)

        if method == "auto" or method == "deflate":
            if ext_in == "png" and ext_out == "png":
                return self.png_steg.hide(file_data, input_path, output_path)

        return False

    def reveal(self, input_path: str, **kwargs) -> bytes | None:
        with open(input_path, 'rb') as f:
            header = f.read(8)

        # Try PNG Deflate if PNG
        if header[:8] == PNG_MAGIC:
            result = self.png_steg.reveal(input_path)
            if result is not None:
                return result

        # Try Robust Block
        if "block_size" in kwargs:
            self.robust_steg.block_size = kwargs["block_size"]
        if "redundancy" in kwargs:
            self.robust_steg.redundancy = kwargs["redundancy"]
        
        return self.robust_steg.reveal(input_path)
