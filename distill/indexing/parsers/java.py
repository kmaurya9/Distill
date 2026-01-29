from tree_sitter import Node as TSNode

from distill.indexing.parsers.base import (
    CallSite,
    FileExtraction,
    LanguageExtractor,
    RawImport,
    Symbol,
    child_by_field,
    find_enclosing_function,
    node_text,
    walk,
)

CLASS_TYPES = ("class_declaration", "interface_declaration", "enum_declaration", "record_declaration")
METHOD_TYPES = ("method_declaration", "constructor_declaration")


class JavaExtractor(LanguageExtractor):
    language = "java"
    extensions = (".java",)

    def extract(self, source: bytes, tree_root: TSNode) -> FileExtraction:
        symbols: list[Symbol] = []
        classes: list[Symbol] = []

        for node in walk(tree_root):
            if node.type in CLASS_TYPES:
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
                symbols.append(sym)
                classes.append(sym)

        for node in walk(tree_root):
            if node.type in METHOD_TYPES:
                name_node = child_by_field(node, "name")
                if name_node is None:
                    continue
                parent_name, best_size = None, None
                for c in classes:
                    if c.node.start_byte <= node.start_byte and node.end_byte <= c.node.end_byte:
                        size = c.node.end_byte - c.node.start_byte
                        if best_size is None or size < best_size:
                            best_size, parent_name = size, c.name
                symbols.append(
                    Symbol(
                        kind="FUNCTION",
                        name=node_text(name_node, source),
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        node=node,
                        parent_name=parent_name,
                    )
                )

        calls: list[CallSite] = []
        for node in walk(tree_root):
            if node.type != "method_invocation":
                continue
            name_node = child_by_field(node, "name")
            if name_node is None:
                continue
            enclosing = find_enclosing_function(node, symbols)
            if enclosing is None:
                continue
            calls.append(CallSite(caller_name=enclosing.name, callee_name=node_text(name_node, source)))

        imports: list[RawImport] = []
        for node in walk(tree_root):
            if node.type == "import_declaration":
                for child in node.children:
                    if child.type == "scoped_identifier":
                        imports.append(RawImport(module=node_text(child, source)))
                        break

        return FileExtraction(symbols=symbols, calls=calls, imports=imports)
