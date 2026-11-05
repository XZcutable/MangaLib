"""Database structure kept up to date on existing servers."""
import sqlite3

import pymupdf

from mymangalib import create_app
from mymangalib.models import Chapter
from mymangalib.server import scanner

from conftest import PNG, make_app

def indexes(db_path):
    with sqlite3.connect(db_path) as connection:
        return {name for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}

def plan(db_path, query):
    with sqlite3.connect(db_path) as connection:
        return " ".join(row[-1] for row in connection.execute(f"EXPLAIN QUERY PLAN {query}"))

def test_page_lookups_use_an_index(tmp_path):
    make_app(tmp_path)
    db_path = tmp_path / "test.db"
    assert {"ix_page_chapter", "ix_manga_path"} <= indexes(db_path)
    query_plan = plan(db_path, "SELECT * FROM page WHERE manga_id = 1 AND chapter_number = 2")
    assert "USING INDEX ix_page_chapter" in query_plan and "SCAN page" not in query_plan
    assert "USING INDEX ix_manga_path" in plan(db_path, "SELECT * FROM manga WHERE path = 'x'")

def test_existing_database_gets_the_indexes(tmp_path):
    """A database made by an older version, without the indexes, gets them on the next start."""
    make_app(tmp_path)
    db_path = tmp_path / "test.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute("DROP INDEX ix_page_chapter")
        connection.execute("DROP INDEX ix_manga_path")
        pages = connection.execute("SELECT count(*) FROM page").fetchone()[0]
    assert not {"ix_page_chapter", "ix_manga_path"} & indexes(db_path)

    create_app(str(tmp_path / "config.toml"))  # Restart with the same config and database
    assert {"ix_page_chapter", "ix_manga_path"} <= indexes(db_path)
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT count(*) FROM page").fetchone()[0] == pages  # No data changed

def test_pdf_pages_are_found(tmp_path):
    """add_archive_pages, moved from database.py to the scanner, still reads PDFs."""
    pdf_path = tmp_path / "Volume.pdf"
    with pymupdf.open() as pdf:
        for _ in range(2):
            pdf.new_page().insert_image(pymupdf.Rect(0, 0, 10, 10), stream=PNG)
        pdf.save(str(pdf_path))
    app = make_app(tmp_path / "app")
    with app.app_context():
        chapter = Chapter(number=1, path=str(pdf_path), archive_type=".pdf")
        assert scanner.add_archive_pages(chapter, str(pdf_path), ".pdf") == 2
        assert [page.number for page in chapter.pages] == [1, 2]
