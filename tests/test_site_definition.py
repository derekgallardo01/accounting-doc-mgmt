import json
import tempfile
from pathlib import Path

import pytest

from accounting_doc_mgmt.site_definition import (
    DEFAULT_SITE,
    LibraryDefinition,
    MetadataColumn,
    SiteDefinition,
    load_site_definition,
    validate_site_definition,
)


def test_default_site_is_valid():
    assert validate_site_definition(DEFAULT_SITE) == []


def test_default_site_has_four_libraries():
    assert len(DEFAULT_SITE.libraries) == 4
    names = {lib.name for lib in DEFAULT_SITE.libraries}
    assert names == {"Source Documents", "Workpapers", "Deliverables", "Correspondence"}


def test_every_library_has_matter_id_column():
    for lib in DEFAULT_SITE.libraries:
        assert any(c.name == "matter_id" and c.required for c in lib.metadata_columns)


def test_deliverables_has_approval_config():
    lib = DEFAULT_SITE.get_library("Deliverables")
    assert lib is not None
    assert "tax_return" in lib.approval_required_for


def test_load_from_json_roundtrip():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "site.json"
        p.write_text(json.dumps({
            "site_name": "Test Site",
            "site_owner_upn": "owner@test.com",
            "libraries": [
                {
                    "name": "Docs",
                    "metadata_columns": [
                        {"name": "matter_id", "type": "text", "required": True}
                    ],
                    "default_folders_per_matter": ["Received"],
                    "retention_years": 5,
                }
            ],
            "roles": [{"name": "Partner", "permissions": ["read", "write"]}],
            "matter_types": ["tax_return"],
        }), encoding="utf-8")
        site = load_site_definition(p)
    assert site.site_name == "Test Site"
    assert len(site.libraries) == 1
    assert site.libraries[0].retention_years == 5


def test_validation_catches_missing_owner():
    site = SiteDefinition(site_name="X", site_owner_upn="", libraries=[])
    issues = validate_site_definition(site)
    assert any("site_owner_upn" in i for i in issues)
    assert any("library" in i for i in issues)


def test_validation_catches_duplicate_library_names():
    lib = LibraryDefinition(name="X", metadata_columns=[
        MetadataColumn("matter_id", "text", required=True)
    ])
    site = SiteDefinition(
        site_name="X", site_owner_upn="a@b.com",
        libraries=[lib, lib],
    )
    issues = validate_site_definition(site)
    assert any("unique" in i for i in issues)


def test_validation_catches_missing_matter_id_column():
    lib = LibraryDefinition(name="X", metadata_columns=[
        MetadataColumn("other", "text", required=True)
    ])
    site = SiteDefinition(
        site_name="X", site_owner_upn="a@b.com",
        libraries=[lib],
    )
    issues = validate_site_definition(site)
    assert any("matter_id" in i for i in issues)
