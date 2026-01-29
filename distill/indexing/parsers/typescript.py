from tree_sitter import Node as TSNode

from distill.indexing.parsers.base import (
    FileExtraction,
    Symbol,
    child_by_field,
    node_text,
    walk,
)
from distill.indexing.parsers.javascript import JavaScriptExtractor


class TypeScriptExtractor(JavaScriptExtractor):
    language = "typescript"
    extensions = (".ts", ".tsx")

    def extract(self, source: bytes, tree_root: TSNode) -> FileExtraction:
        extraction = super().extract(source, tree_root)
        for node in walk(tree_root):
            if node.type == "interface_declaration":
                name_node = child_by_field(node, "name")
                if name_node is None:
                    continue
                extraction.symbols.append(
                    Symbol(
                        kind="CLASS",
                        name=node_text(name_node, source),
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        node=node,
                    )
                )
        return extraction
