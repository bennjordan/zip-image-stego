#!/usr/bin/env python3
import os
import io
import zipfile
import shutil
from flask import Flask, request, render_template, send_file, jsonify, flash, redirect, url_for
from werkzeug.utils import secure_filename
from stego_engine import MultiMethodFileSteg, RobustBlockFileSteg

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Create workspaces directories for file uploads and processing
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB max upload size


def is_zip_bytes(data: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            return zf.testzip() is None
    except zipfile.BadZipFile:
        return False


def zip_single_file(file_bytes: bytes, filename: str) -> bytes:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(filename, file_bytes)
    return zip_buffer.getvalue()


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/check-capacity", methods=["POST"])
def check_capacity():
    data = request.get_json() or {}
    width = data.get("width")
    height = data.get("height")
    block_size = data.get("block_size", 8)
    redundancy = data.get("redundancy", 3)

    if not width or not height:
        return jsonify({"error": "Missing dimensions"}), 400

    try:
        width = int(width)
        height = int(height)
        block_size = int(block_size)
        redundancy = int(redundancy)
    except ValueError:
        return jsonify({"error": "Invalid dimensions"}), 400

    # Instantiate RobustBlockFileSteg just to compute capacity
    robust_steg = RobustBlockFileSteg(password="", block_size=block_size, redundancy=redundancy)
    capacity = robust_steg.get_max_capacity(width, height)

    return jsonify({"capacity_bytes": capacity})


@app.route("/hide", methods=["POST"])
def hide():
    if "cover" not in request.files or "payload" not in request.files:
        return jsonify({"error": "Cover image and payload file are required"}), 400

    cover_file = request.files["cover"]
    payload_file = request.files["payload"]
    password = request.form.get("password", "")
    method = request.form.get("method", "auto")

    # Advanced params
    try:
        block_size = int(request.form.get("block_size", 8))
        redundancy = int(request.form.get("redundancy", 3))
        strength = int(request.form.get("strength", 25))
    except ValueError:
        return jsonify({"error": "Invalid advanced parameters"}), 400

    if not password:
        return jsonify({"error": "Password is required"}), 400

    if cover_file.filename == "" or payload_file.filename == "":
        return jsonify({"error": "Empty filenames selected"}), 400

    cover_filename = secure_filename(cover_file.filename)
    payload_filename = secure_filename(payload_file.filename)

    cover_path = os.path.join(app.config["UPLOAD_FOLDER"], cover_filename)
    output_filename = "stego_" + cover_filename
    # Force output extension to PNG if it's png or auto png, or keep jpg/png
    ext_in = cover_filename.lower().split('.')[-1]
    if method == "deflate" and ext_in not in ["png"]:
        output_filename = output_filename.rsplit('.', 1)[0] + ".png"

    output_path = os.path.join(app.config["UPLOAD_FOLDER"], output_filename)

    try:
        cover_file.save(cover_path)
        payload_data = payload_file.read()

        # If it's not a zip, compress it to a zip automatically
        is_zip = is_zip_bytes(payload_data) or payload_filename.endswith(".zip")
        if not is_zip:
            payload_data = zip_single_file(payload_data, payload_filename)
            payload_filename = payload_filename + ".zip"

        steg = MultiMethodFileSteg(password)
        success = steg.hide(
            payload_data,
            cover_path,
            output_path,
            method=method,
            block_size=block_size,
            redundancy=redundancy,
            strength=strength
        )

        if success:
            return send_file(
                output_path,
                as_attachment=True,
                download_name=output_filename
            )
        else:
            return jsonify({"error": "Failed to hide payload. If using Robust Block, the image might be too small for this file size."}), 400

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
    finally:
        # Clean up files
        if os.path.exists(cover_path):
            os.remove(cover_path)


@app.route("/reveal", methods=["POST"])
def reveal():
    if "stego" not in request.files:
        return jsonify({"error": "Stego image is required"}), 400

    stego_file = request.files["stego"]
    password = request.form.get("password", "")

    # Advanced params
    try:
        block_size = int(request.form.get("block_size", 8))
        redundancy = int(request.form.get("redundancy", 3))
    except ValueError:
        return jsonify({"error": "Invalid advanced parameters"}), 400

    if not password:
        return jsonify({"error": "Password is required"}), 400

    if stego_file.filename == "":
        return jsonify({"error": "No image selected"}), 400

    stego_filename = secure_filename(stego_file.filename)
    stego_path = os.path.join(app.config["UPLOAD_FOLDER"], stego_filename)

    try:
        stego_file.save(stego_path)

        steg = MultiMethodFileSteg(password)
        decrypted_data = steg.reveal(
            stego_path,
            block_size=block_size,
            redundancy=redundancy
        )

        if decrypted_data is None:
            return jsonify({"error": "Extraction failed. Wrong password, corrupted image, or no hidden data found."}), 400

        # Check if the extracted data is a zip archive
        if is_zip_bytes(decrypted_data):
            # Inspect the zip
            zip_buffer = io.BytesIO(decrypted_data)
            with zipfile.ZipFile(zip_buffer) as zf:
                namelist = zf.namelist()
                if len(namelist) == 1:
                    # Single file: extract it and return directly
                    inner_filename = namelist[0]
                    inner_data = zf.read(inner_filename)
                    return send_file(
                        io.BytesIO(inner_data),
                        as_attachment=True,
                        download_name=inner_filename
                    )

            # Multiple files: return the zip file
            return send_file(
                io.BytesIO(decrypted_data),
                as_attachment=True,
                download_name="extracted_archive.zip"
            )
        else:
            # Fallback (should not happen if auto-zipped, but in case)
            return send_file(
                io.BytesIO(decrypted_data),
                as_attachment=True,
                download_name="extracted_file.bin"
            )

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
    finally:
        if os.path.exists(stego_path):
            os.remove(stego_path)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
