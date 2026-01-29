"""Golden-file tests: one per tree-sitter-supported language (claim #10).

Each fixture is parsed and we assert the expected symbol list (functions,
classes/structs), the expected CALLS edges (claim #11 - program analysis),
and the expected raw imports.
"""

from pathlib import Path

import pytest
from tree_sitter_language_pack import get_parser

from distill.indexing.parsers.c import CExtractor
from distill.indexing.parsers.cpp import CppExtractor
from distill.indexing.parsers.go import GoExtractor
from distill.indexing.parsers.java import JavaExtractor
from distill.indexing.parsers.javascript import JavaScriptExtractor
from distill.indexing.parsers.python import PythonExtractor
from distill.indexing.parsers.rust import RustExtractor
from distill.indexing.parsers.typescript import TypeScriptExtractor

FIXTURES = Path(__file__).parent / "fixtures"


def _extract(extractor, filename: str):
    source = (FIXTURES / filename).read_bytes()
    parser = get_parser(extractor.language)
    tree = parser.parse(source)
    return extractor.extract(source, tree.root_node)


def _symbol_set(extraction):
    return {(s.kind, s.name, s.parent_name) for s in extraction.symbols}


def _call_set(extraction):
    return {(c.caller_name, c.callee_name) for c in extraction.calls}


def _import_set(extraction):
    return {i.module for i in extraction.imports}


def test_python_parser():
    extraction = _extract(PythonExtractor(), "sample.py")
    assert _symbol_set(extraction) == {
        ("CLASS", "Foo", None),
        ("FUNCTION", "bar", "Foo"),
        ("FUNCTION", "helper", None),
    }
    assert _call_set(extraction) == {("bar", "helper"), ("helper", "join")}
    assert _import_set(extraction) >= {"os", "collections"}


def test_javascript_parser():
    extraction = _extract(JavaScriptExtractor(), "sample.js")
    assert _symbol_set(extraction) == {
        ("CLASS", "Foo", None),
        ("FUNCTION", "bar", "Foo"),
        ("FUNCTION", "helper", None),
        ("FUNCTION", "arrow", None),
    }
    assert _call_set(extraction) == {
        ("bar", "helper"),
        ("helper", "existsSync"),
        ("arrow", "helper"),
    }
    assert _import_set(extraction) == {"fs"}


def test_typescript_parser():
    extraction = _extract(TypeScriptExtractor(), "sample.ts")
    assert _symbol_set(extraction) == {
        ("CLASS", "Foo", None),
        ("FUNCTION", "bar", "Foo"),
        ("FUNCTION", "helper", None),
        ("FUNCTION", "arrow", None),
    }
    assert _call_set(extraction) == {("bar", "helper"), ("arrow", "helper")}
    assert _import_set(extraction) == {"fs"}


def test_java_parser():
    extraction = _extract(JavaExtractor(), "sample.java")
    assert _symbol_set(extraction) == {
        ("CLASS", "Foo", None),
        ("FUNCTION", "bar", "Foo"),
        ("CLASS", "Helper", None),
        ("FUNCTION", "help", "Helper"),
    }
    assert _call_set(extraction) == {("bar", "help")}
    assert _import_set(extraction) == {"java.util.List"}


def test_go_parser():
    extraction = _extract(GoExtractor(), "sample.go")
    assert _symbol_set(extraction) == {
        ("CLASS", "Foo", None),
        ("FUNCTION", "Bar", "Foo"),
        ("FUNCTION", "helper", None),
        ("FUNCTION", "main", None),
    }
    assert _call_set(extraction) == {
        ("Bar", "helper"),
        ("main", "Println"),
        ("main", "helper"),
    }
    assert _import_set(extraction) == {"fmt"}


def test_rust_parser():
    extraction = _extract(RustExtractor(), "sample.rs")
    assert _symbol_set(extraction) == {
        ("CLASS", "Foo", None),
        ("FUNCTION", "bar", "Foo"),
        ("FUNCTION", "helper", None),
    }
    assert _call_set(extraction) == {("bar", "helper")}
    assert _import_set(extraction) == {"std::collections::HashMap"}


def test_c_parser():
    extraction = _extract(CExtractor(), "sample.c")
    assert _symbol_set(extraction) == {
        ("FUNCTION", "helper", None),
        ("FUNCTION", "bar", None),
    }
    assert _call_set(extraction) == {("bar", "helper")}
    assert _import_set(extraction) == {"stdio.h"}


def test_cpp_parser():
    extraction = _extract(CppExtractor(), "sample.cpp")
    assert _symbol_set(extraction) == {
        ("FUNCTION", "helper", None),
        ("CLASS", "Foo", None),
        ("FUNCTION", "bar", "Foo"),
    }
    assert _call_set(extraction) == {("bar", "helper")}
    assert _import_set(extraction) == {"iostream"}
