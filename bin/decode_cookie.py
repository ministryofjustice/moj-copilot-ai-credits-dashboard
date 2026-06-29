import argparse
import base64
import zlib

def decrypt_cookie(payload):
    binary_data = base64.urlsafe_b64decode(payload + "===")

    decoded_text = zlib.decompress(binary_data).decode('utf-8')

    print(decoded_text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Decrypt Flask session cookie"
    )
    parser.add_argument("payload", type=str, help="Payload section of session cookie base64 encoded")

    args = parser.parse_args()

    decrypt_cookie(args.payload)