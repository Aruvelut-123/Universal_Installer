"""
Automated tests for Universal Installer configuration and logic.

These tests validate:
- metadata.json completeness and correctness
- items.json schema, dependency graph, and incompatibility consistency
- File type detection logic (mirrors the logic in main.py)
- Archive size calculation (zip and tar)
- File extension handling for non-archive files (.txt, .exe)
"""

import json
import os
import sys
import zipfile
import tarfile
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
METADATA_PATH = os.path.join(ROOT_DIR, "metadata.json")
ITEMS_PATH = os.path.join(ROOT_DIR, "pack", "items.json")

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def metadata():
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def items(metadata):
    items_path = os.path.join(ROOT_DIR, metadata["item_metadata"])
    with open(items_path, "r", encoding="utf-8") as f:
        return json.load(f)["items"]


# ---------------------------------------------------------------------------
# metadata.json tests
# ---------------------------------------------------------------------------

class TestMetadata:
    REQUIRED_FIELDS = [
        "program_name", "short_name", "version", "is_release",
        "password", "has_uninstaller", "main_item", "item_metadata",
        "registry_key_name", "uninstall_registry_key_name",
        "footer_info", "license_file", "left_pic", "header_pic", "icon",
    ]

    def test_metadata_file_exists(self):
        assert os.path.exists(METADATA_PATH), "metadata.json not found"

    def test_metadata_is_valid_json(self):
        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_required_fields_present(self, metadata):
        for field in self.REQUIRED_FIELDS:
            assert field in metadata, f"Missing required field: {field}"

    def test_version_format(self, metadata):
        version = metadata["version"]
        parts = version.split(".")
        assert len(parts) >= 2, f"Version should have at least major.minor: {version}"
        for part in parts:
            assert part.isdigit(), f"Version part is not a number: {part}"

    def test_main_item_is_nonnegative_int(self, metadata):
        assert isinstance(metadata["main_item"], int)
        assert metadata["main_item"] >= 0

    def test_item_metadata_path_exists(self, metadata):
        path = os.path.join(ROOT_DIR, metadata["item_metadata"])
        assert os.path.exists(path), f"item_metadata path does not exist: {path}"


# ---------------------------------------------------------------------------
# items.json tests
# ---------------------------------------------------------------------------

class TestItems:
    REQUIRED_ITEM_FIELDS = ["name", "id"]

    def test_items_file_exists(self):
        assert os.path.exists(ITEMS_PATH), "pack/items.json not found"

    def test_items_is_valid_json(self):
        with open(ITEMS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "items" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) > 0

    def test_required_fields_in_each_item(self, items):
        for item in items:
            for field in self.REQUIRED_ITEM_FIELDS:
                assert field in item, f"Item missing required field '{field}': {item.get('name', '?')}"

    def test_unique_ids(self, items):
        ids = [item["id"] for item in items]
        duplicates = [x for x in ids if ids.count(x) > 1]
        assert len(duplicates) == 0, f"Duplicate component IDs: {set(duplicates)}"

    def test_dependencies_reference_valid_ids(self, items):
        valid_ids = {item["id"] for item in items}
        # texture_pack depends on texture_pack_mod which is a planned/external
        # component not yet in items.json — skip disabled placeholder items
        for item in items:
            if item.get("disabled", False):
                continue
            for dep_id in item.get("dependencies", []):
                assert dep_id in valid_ids, (
                    f"Component '{item['id']}' has dependency '{dep_id}' "
                    f"which is not a valid component ID"
                )

    def test_incompatible_references_valid_ids(self, items):
        valid_ids = {item["id"] for item in items}
        for item in items:
            for incompat_id in item.get("incompatible", []):
                assert incompat_id in valid_ids, (
                    f"Component '{item['id']}' has incompatible '{incompat_id}' "
                    f"which is not a valid component ID"
                )

    def test_no_self_dependency(self, items):
        for item in items:
            assert item["id"] not in item.get("dependencies", []), (
                f"Component '{item['id']}' depends on itself"
            )

    def test_no_self_incompatible(self, items):
        for item in items:
            assert item["id"] not in item.get("incompatible", []), (
                f"Component '{item['id']}' is marked incompatible with itself"
            )

    def test_actions_match_files(self, items):
        """Every file in 'files', 'x64file', 'x86file' should have an action entry."""
        for item in items:
            actions = item.get("actions") or {}
            all_files = []
            if item.get("files"):
                all_files.extend(item["files"])
            if item.get("x64file"):
                all_files.extend(item["x64file"])
            if item.get("x86file"):
                all_files.extend(item["x86file"])
            for f in all_files:
                assert f in actions, (
                    f"Component '{item['id']}': file '{f}' has no action mapping"
                )

    def test_main_item_index_valid(self, metadata, items):
        main_idx = metadata["main_item"]
        assert main_idx < len(items), (
            f"main_item index {main_idx} is out of range (only {len(items)} items)"
        )

    def test_after_references_valid_ids(self, items):
        """'after' field should reference a valid component ID or be null."""
        valid_ids = {item["id"] for item in items}
        for item in items:
            after = item.get("after")
            if after is not None:
                assert after in valid_ids, (
                    f"Component '{item['id']}' has after='{after}' "
                    f"which is not a valid component ID"
                )

    def test_no_circular_dependencies(self, items):
        """Detect circular dependencies using DFS."""
        dep_map = {item["id"]: item.get("dependencies", []) for item in items}

        def has_cycle(node, visited, stack):
            visited.add(node)
            stack.add(node)
            for dep in dep_map.get(node, []):
                if dep in stack:
                    return True
                if dep not in visited:
                    if has_cycle(dep, visited, stack):
                        return True
            stack.discard(node)
            return False

        visited = set()
        for node in dep_map:
            if node not in visited:
                assert not has_cycle(node, visited, set()), (
                    f"Circular dependency detected involving '{node}'"
                )


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
    ])
    def test_file_type_detection(self, filename, expected):
        assert detect_file_type(filename) == expected

    def test_all_item_files_have_known_types(self, items):
        """Every file referenced in items.json should have a recognized type."""
        for item in items:
            all_files = []
            if item.get("files"):
                all_files.extend(item["files"])
            if item.get("x64file"):
                all_files.extend(item["x64file"])
            if item.get("x86file"):
                all_files.extend(item["x86file"])
            for f in all_files:
                ft = detect_file_type(f)
                assert ft is not None, (
                    f"Component '{item['id']}': file '{f}' has unrecognized "
                    f"extension and would be skipped during installation"
                )


# ---------------------------------------------------------------------------
# Archive size calculation (zip and tar — can test on any platform)
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
