from tree_sitter import Node as TSNode

from distill.indexing.parsers.base import (
    FileExtraction,
    Symbol,
    child_by_field,
    node_text,
    walk,
)
from distill.indexing.parsers.c import CExtractor


class CppExtractor(CExtractor):
    language = "cpp"
    extensions = (".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx")

    def extract(self, source: bytes, tree_root: TSNode) -> FileExtraction:
        extraction = super().extract(source, tree_root)

        classes: list[Symbol] = []
        for node in walk(tree_root):
            if node.type == "class_specifier":
                name_node = child_by_field(node, "name")
                if name_node is None:
                    continue
                sym = Symbol(
                    kind="CLASS",
                    name=node_text(name_node, source),
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    node=node,
                )
                extraction.symbols.append(sym)
                classes.append(sym)

        for sym in extraction.symbols:
            if sym.kind != "FUNCTION" or sym.parent_name is not None:
                continue
            best_name, best_size = None, None
            for c in classes:
                if c.node.start_byte <= sym.node.start_byte and sym.node.end_byte <= c.node.end_byte:
                    size = c.node.end_byte - c.node.start_byte
                    if best_size is None or size < best_size:
                        best_size, best_name = size, c.name
            sym.parent_name = best_name

        return extraction
