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

TYPE_ITEM_TYPES = ("struct_item", "enum_item", "trait_item")


class RustExtractor(LanguageExtractor):
    language = "rust"
    extensions = (".rs",)

    def extract(self, source: bytes, tree_root: TSNode) -> FileExtraction:
        symbols: list[Symbol] = []
        classes: list[Symbol] = []

        for node in walk(tree_root):
            if node.type in TYPE_ITEM_TYPES:
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

        impl_blocks = []
        for node in walk(tree_root):
            if node.type == "impl_item":
                type_node = child_by_field(node, "type")
                if type_node is not None:
                    impl_blocks.append((node, node_text(type_node, source)))

        for node in walk(tree_root):
            if node.type != "function_item":
                continue
            name_node = child_by_field(node, "name")
            if name_node is None:
                continue
            parent_name, best_size = None, None
            for impl_node, type_name in impl_blocks:
                if impl_node.start_byte <= node.start_byte and node.end_byte <= impl_node.end_byte:
                    size = impl_node.end_byte - impl_node.start_byte
                    if best_size is None or size < best_size:
                        best_size, parent_name = size, type_name
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
            if node.type != "call_expression":
                continue
            func_node = child_by_field(node, "function")
            if func_node is None:
                continue
            callee_name = None
            if func_node.type == "identifier":
                callee_name = node_text(func_node, source)
            elif func_node.type == "field_expression":
                field_node = child_by_field(func_node, "field")
                if field_node is not None:
                    callee_name = node_text(field_node, source)
            elif func_node.type == "scoped_identifier":
                name_node = child_by_field(func_node, "name")
                if name_node is not None:
                    callee_name = node_text(name_node, source)
            if callee_name is None:
                continue
            enclosing = find_enclosing_function(node, symbols)
            if enclosing is None:
                continue
            calls.append(CallSite(caller_name=enclosing.name, callee_name=callee_name))

        imports: list[RawImport] = []
        for node in walk(tree_root):
            if node.type == "use_declaration":
                arg = child_by_field(node, "argument")
                if arg is not None:
                    imports.append(RawImport(module=node_text(arg, source)))

        return FileExtraction(symbols=symbols, calls=calls, imports=imports)
