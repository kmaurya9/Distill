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


def _string_content(node: TSNode, source: bytes) -> str | None:
    for child in node.children:
        if child.type == "string_fragment":
            return node_text(child, source)
    return None


class JavaScriptExtractor(LanguageExtractor):
    language = "javascript"
    extensions = (".js", ".jsx", ".mjs", ".cjs")

    function_decl_types = ("function_declaration", "generator_function_declaration")

    def extract(self, source: bytes, tree_root: TSNode) -> FileExtraction:
        symbols: list[Symbol] = []
        classes: list[Symbol] = []

        for node in walk(tree_root):
            if node.type == "class_declaration":
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

        def parent_class_of(node: TSNode) -> str | None:
            best_name, best_size = None, None
            for c in classes:
                if c.node.start_byte <= node.start_byte and node.end_byte <= c.node.end_byte:
                    size = c.node.end_byte - c.node.start_byte
                    if best_size is None or size < best_size:
                        best_size, best_name = size, c.name
            return best_name

        for node in walk(tree_root):
            if node.type in self.function_decl_types:
                name_node = child_by_field(node, "name")
                if name_node is None:
                    continue
                symbols.append(
                    Symbol(
                        kind="FUNCTION",
                        name=node_text(name_node, source),
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        node=node,
                        parent_name=parent_class_of(node),
                    )
                )
            elif node.type == "method_definition":
                name_node = child_by_field(node, "name")
                if name_node is None:
                    continue
                symbols.append(
                    Symbol(
                        kind="FUNCTION",
                        name=node_text(name_node, source),
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        node=node,
                        parent_name=parent_class_of(node),
                    )
                )
            elif node.type == "variable_declarator":
                value = child_by_field(node, "value")
                name_node = child_by_field(node, "name")
                if value is not None and name_node is not None and value.type in (
                    "arrow_function",
                    "function",
                    "function_expression",
                ):
                    symbols.append(
                        Symbol(
                            kind="FUNCTION",
                            name=node_text(name_node, source),
                            start_line=node.start_point[0] + 1,
                            end_line=node.end_point[0] + 1,
                            node=node,
                            parent_name=parent_class_of(node),
                        )
                    )

        calls: list[CallSite] = []
        imports: list[RawImport] = []
        for node in walk(tree_root):
            if node.type == "call_expression":
                func_node = child_by_field(node, "function")
                if func_node is None:
                    continue
                callee_name = None
                if func_node.type == "identifier":
                    callee_name = node_text(func_node, source)
                elif func_node.type == "member_expression":
                    prop = child_by_field(func_node, "property")
                    if prop is not None:
                        callee_name = node_text(prop, source)
                if callee_name == "require":
                    args = child_by_field(node, "arguments")
                    if args is not None:
                        for arg in args.children:
                            if arg.type == "string":
                                mod = _string_content(arg, source)
                                if mod is not None:
                                    imports.append(RawImport(module=mod))
                    continue
                if callee_name is None:
                    continue
                enclosing = find_enclosing_function(node, symbols)
                if enclosing is None:
                    continue
                calls.append(CallSite(caller_name=enclosing.name, callee_name=callee_name))
            elif node.type == "import_statement":
                source_node = child_by_field(node, "source")
                if source_node is not None:
                    mod = _string_content(source_node, source)
                    if mod is not None:
                        imports.append(RawImport(module=mod))

        return FileExtraction(symbols=symbols, calls=calls, imports=imports)
