import io
from PIL import Image

def createBytesIo(image_binary: list[bytes]):
    return [io.BytesIO(binary) for binary in image_binary]

def BytesIoImageOpen(bytes_io_list: list[io.BytesIO]):
    return [Image.open(bytes_io) for bytes_io in bytes_io_list]