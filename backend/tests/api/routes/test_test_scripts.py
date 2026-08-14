from io import BytesIO
from zipfile import ZipFile

import pytest

from app.api.routes.test_scripts import _document_chunks


def test_small_documents_are_uploaded_unchanged() -> None:
    content = b"URS-001: The system shall display status."

    assert _document_chunks("urs.txt", content, max_bytes=100) == [("urs.txt", content)]


def test_large_text_documents_are_split_below_limit() -> None:
    content = b"paragraph one\n\nparagraph two\n\nparagraph three"

    chunks = _document_chunks("design.txt", content, max_bytes=20)

    assert [filename for filename, _ in chunks] == [
        "design.txt.part-001.txt",
        "design.txt.part-002.txt",
        "design.txt.part-003.txt",
    ]
    assert all(len(chunk) <= 20 for _, chunk in chunks)
    assert b"paragraph one" in chunks[0][1]
    assert b"paragraph three" in chunks[-1][1]


def test_large_docx_is_converted_to_text_chunks() -> None:
    document_xml = (
        b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        b"<w:body><w:p><w:r><w:t>URS-001</w:t></w:r></w:p>"
        b"<w:p><w:r><w:t>The system shall display status.</w:t></w:r></w:p></w:body></w:document>"
    )
    content_buffer = BytesIO()
    with ZipFile(content_buffer, "w") as archive:
        archive.writestr("word/document.xml", document_xml)

    chunks = _document_chunks("specification.docx", content_buffer.getvalue(), max_bytes=20)

    assert len(chunks) == 2
    assert all(filename.endswith(".txt") for filename, _ in chunks)
    assert b"URS-001" in b"".join(chunk for _, chunk in chunks)


def test_large_binary_documents_fail_with_actionable_error() -> None:
    with pytest.raises(Exception, match="cannot be safely chunked"):
        _document_chunks("scan.pdf", b"not really a pdf", max_bytes=2)
