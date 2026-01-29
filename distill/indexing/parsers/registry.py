from distill.indexing.parsers.base import LanguageExtractor
from distill.indexing.parsers.c import CExtractor
from distill.indexing.parsers.cpp import CppExtractor
from distill.indexing.parsers.go import GoExtractor
from distill.indexing.parsers.java import JavaExtractor
from distill.indexing.parsers.javascript import JavaScriptExtractor
from distill.indexing.parsers.python import PythonExtractor
from distill.indexing.parsers.rust import RustExtractor
from distill.indexing.parsers.typescript import TypeScriptExtractor

# tree-sitter-language-pack grammar name -> extractor. Order matters: more
# specific extensions (.hpp before .h etc.) are handled by dict override below.
EXTRACTORS: list[LanguageExtractor] = [
    PythonExtractor(),
    TypeScriptExtractor(),
    JavaScriptExtractor(),
    JavaExtractor(),
    GoExtractor(),
    RustExtractor(),
    CppExtractor(),
    CExtractor(),
]

EXTENSION_TO_EXTRACTOR: dict[str, LanguageExtractor] = {}
for _extractor in EXTRACTORS:
    for _ext in _extractor.extensions:
        EXTENSION_TO_EXTRACTOR.setdefault(_ext, _extractor)


def get_extractor(extension: str) -> LanguageExtractor | None:
    return EXTENSION_TO_EXTRACTOR.get(extension)
