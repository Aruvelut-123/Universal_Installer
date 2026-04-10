"""
Automated tests for Universal Installer logic.

These tests validate the core logic without depending on config files
(metadata.json / items.json) which may be altered by the user.

Tests cover:
- File type detection logic (mirrors the logic in main.py)
- Archive size calculation (zip and tar)
- File extension handling for non-archive files (.txt, .exe)
- Zip extraction and path tracking
- Tar extraction and path tracking
"""

import os
import shutil
import zipfile
import tarfile

import pytest


# ---------------------------------------------------------------------------
# File type detection logic (mirrors main.py)
# ---------------------------------------------------------------------------

def detect_file_type(filename):
    """Replicate the file type detection logic from main.py's run() method."""
    result = filename.split(".")
    ext = result[-1] if len(result) > 1 else ""
    if ext == "zip":
        return "zip"
    elif ext == "rar":
        return "rar"
    elif ext == "7z":
        return "7z"
    elif ext == "tar":
        return "tar"
    elif ext in ("txt", "exe"):
        return ext  # plain copy
    else:
        return None  # skip


class TestFileTypeDetection:
    @pytest.mark.parametrize("filename,expected", [
        ("pack/BBPC.zip", "zip"),
        ("pack/mod.rar", "rar"),
        ("pack/data.7z", "7z"),
        ("pack/archive.tar", "tar"),
        ("pack/readme.txt", "txt"),
        ("pack/Uninstall.exe", "exe"),
        ("pack/noextension", None),
        ("pack/unknown.xyz", None),
        ("pack/.hidden", None),
        ("my.multi.dot.zip", "zip"),
        ("path/to/file.name.7z", "7z"),
    ])
    def test_file_type_detection(self, filename, expected):
        assert detect_file_type(filename) == expected


# ---------------------------------------------------------------------------
# Archive size calculation (zip and tar — cross-platform)
# ---------------------------------------------------------------------------

class TestArchiveSize:
    def test_zip_size_calculation(self, tmp_path):
        """Create a test zip and verify size calculation."""
        test_content = b"Hello World! " * 100  # 1300 bytes
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(str(zip_path), "w") as zf:
            zf.writestr("file1.txt", test_content)
            zf.writestr("file2.txt", b"short")

        with zipfile.ZipFile(str(zip_path), "r") as zf:
            total = sum(info.file_size for info in zf.infolist())

        assert total == len(test_content) + len(b"short")

    def test_tar_size_calculation(self, tmp_path):
        """Create a test tar and verify size calculation."""
        test_file = tmp_path / "content.txt"
        test_file.write_text("Test content for tar archive")

        tar_path = tmp_path / "test.tar"
        with tarfile.open(str(tar_path), "w") as tf:
            tf.add(str(test_file), arcname="content.txt")

        with tarfile.open(str(tar_path), "r:*") as tf:
            total = sum(m.size for m in tf.getmembers() if m.isfile())

        assert total == len("Test content for tar archive")

    def test_zip_empty_archive(self, tmp_path):
        """Empty zip should return size 0."""
        zip_path = tmp_path / "empty.zip"
        with zipfile.ZipFile(str(zip_path), "w") as zf:
            pass  # empty

        with zipfile.ZipFile(str(zip_path), "r") as zf:
            total = sum(info.file_size for info in zf.infolist())

        assert total == 0

    def test_tar_gz_size_calculation(self, tmp_path):
        """Create a .tar.gz and verify size calculation with 'r:*' mode."""
        test_file = tmp_path / "data.txt"
        test_file.write_text("Compressed tar content")

        tar_path = tmp_path / "test.tar.gz"
        with tarfile.open(str(tar_path), "w:gz") as tf:
            tf.add(str(test_file), arcname="data.txt")

        with tarfile.open(str(tar_path), "r:*") as tf:
            total = sum(m.size for m in tf.getmembers() if m.isfile())

        assert total == len("Compressed tar content")

    def test_zip_multiple_files_size(self, tmp_path):
        """Zip with multiple files should sum all uncompressed sizes."""
        zip_path = tmp_path / "multi.zip"
        files = {"a.txt": b"aaa", "b.txt": b"bbbbb", "c.bin": b"\x00" * 100}
        with zipfile.ZipFile(str(zip_path), "w") as zf:
            for name, data in files.items():
                zf.writestr(name, data)

        with zipfile.ZipFile(str(zip_path), "r") as zf:
            total = sum(info.file_size for info in zf.infolist())

        assert total == sum(len(d) for d in files.values())


# ---------------------------------------------------------------------------
# Plain file handling (.txt, .exe)
# ---------------------------------------------------------------------------

class TestPlainFileCopy:
    def test_exe_file_size(self, tmp_path):
        """os.path.getsize should correctly report .exe file size."""
        exe_path = tmp_path / "Uninstall.exe"
        content = b"\x00" * 1024  # 1KB fake exe
        exe_path.write_bytes(content)
        assert os.path.getsize(str(exe_path)) == 1024

    def test_txt_file_size(self, tmp_path):
        """os.path.getsize should correctly report .txt file size."""
        txt_path = tmp_path / "readme.txt"
        content = "Hello readme"
        txt_path.write_text(content)
        assert os.path.getsize(str(txt_path)) == len(content)

    def test_exe_copy_to_directory(self, tmp_path):
        """shutil.copy should copy .exe to destination with correct name."""
        src = tmp_path / "src"
        src.mkdir()
        dest = tmp_path / "dest"
        dest.mkdir()

        exe_src = src / "Uninstall.exe"
        exe_src.write_bytes(b"\x00" * 512)

        dest_path = os.path.join(str(dest), os.path.basename(str(exe_src)))
        shutil.copy(str(exe_src), dest_path)

        assert os.path.exists(dest_path)
        assert os.path.getsize(dest_path) == 512

    def test_txt_copy_to_directory(self, tmp_path):
        """shutil.copy should copy .txt to destination with correct name."""
        src = tmp_path / "src"
        src.mkdir()
        dest = tmp_path / "dest"
        dest.mkdir()

        txt_src = src / "readme.txt"
        txt_src.write_text("readme content")

        dest_path = os.path.join(str(dest), os.path.basename(str(txt_src)))
        shutil.copy(str(txt_src), dest_path)

        assert os.path.exists(dest_path)
        with open(dest_path) as f:
            assert f.read() == "readme content"


# ---------------------------------------------------------------------------
# Extraction path tracking (mirrors run_extract logic)
# ---------------------------------------------------------------------------

class TestExtractionPathTracking:
    def test_zip_extracted_paths(self, tmp_path):
        """Verify that zip extraction returns correct list of extracted paths."""
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(str(zip_path), "w") as zf:
            zf.writestr("dir/file1.txt", b"content1")
            zf.writestr("file2.txt", b"content2")

        extract_dir = tmp_path / "out"
        extract_dir.mkdir()

        with zipfile.ZipFile(str(zip_path), "r") as archive:
            paths = [os.path.join(str(extract_dir), n) for n in archive.namelist()]
            archive.extractall(str(extract_dir))

        assert len(paths) == 2
        assert all(str(extract_dir) in p for p in paths)

    def test_tar_extracted_paths(self, tmp_path):
        """Verify that tar extraction returns correct list of extracted paths."""
        content_file = tmp_path / "hello.txt"
        content_file.write_text("hello")

        tar_path = tmp_path / "test.tar"
        with tarfile.open(str(tar_path), "w") as tf:
            tf.add(str(content_file), arcname="hello.txt")

        extract_dir = tmp_path / "out"
        extract_dir.mkdir()

        with tarfile.open(str(tar_path), "r") as archive:
            paths = [os.path.join(str(extract_dir), n) for n in archive.getnames()]
            archive.extractall(str(extract_dir))

        assert len(paths) == 1
        assert os.path.exists(paths[0])
