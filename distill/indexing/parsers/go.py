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


def _string_literal_content(node: TSNode, source: bytes) -> str:
    text = node_text(node, source)
    return text.strip('"')


class GoExtractor(LanguageExtractor):
    language = "go"
    extensions = (".go",)

    def extract(self, source: bytes, tree_root: TSNode) -> FileExtraction:
        symbols: list[Symbol] = []
        classes: list[Symbol] = []

        for node in walk(tree_root):
            if node.type == "type_declaration":
                for spec in node.children:
                    if spec.type != "type_spec":
                        continue
                    type_node = child_by_field(spec, "type")
                    if type_node is None or type_node.type not in ("struct_type", "interface_type"):
                        continue
                    name_node = child_by_field(spec, "name")
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
            if node.type == "function_declaration":
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
                    )
                )
            elif node.type == "method_declaration":
                name_node = child_by_field(node, "name")
                if name_node is None:
                    continue
                receiver = child_by_field(node, "receiver")
                parent_name = None
                if receiver is not None:
                    for param in walk(receiver):
                        if param.type == "type_identifier":
                            parent_name = node_text(param, source)
                            break
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
            elif func_node.type == "selector_expression":
                field_node = child_by_field(func_node, "field")
                if field_node is not None:
                    callee_name = node_text(field_node, source)
            if callee_name is None:
                continue
            enclosing = find_enclosing_function(node, symbols)
            if enclosing is None:
                continue
            calls.append(CallSite(caller_name=enclosing.name, callee_name=callee_name))

        imports: list[RawImport] = []
        for node in walk(tree_root):
            if node.type == "import_spec":
                path_node = child_by_field(node, "path")
                if path_node is not None:
                    imports.append(RawImport(module=_string_literal_content(path_node, source)))

        return FileExtraction(symbols=symbols, calls=calls, imports=imports)
