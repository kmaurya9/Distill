from tree_sitter import Node as TSNode

from distill.indexing.parsers.base import (
    CallSite,
    FileExtraction,
    LanguageExtractor,
    RawImport,
    Symbol,
    child_by_field,
    find_enclosing_function,
    innermost_identifier,
    node_text,
    walk,
)


class CExtractor(LanguageExtractor):
    language = "c"
    extensions = (".c", ".h")

    struct_type = "struct_specifier"

    def extract(self, source: bytes, tree_root: TSNode) -> FileExtraction:
        symbols: list[Symbol] = []
        classes: list[Symbol] = []

        for node in walk(tree_root):
            if node.type == self.struct_type:
                name_node = child_by_field(node, "name")
                body = child_by_field(node, "body")
                if name_node is None or body is None:
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
            if node.type != "function_definition":
                continue
            declarator = child_by_field(node, "declarator")
            name = innermost_identifier(declarator, source)
            if name is None:
                continue
            symbols.append(
                Symbol(
                    kind="FUNCTION",
                    name=name,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    node=node,
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
            if callee_name is None:
                continue
            enclosing = find_enclosing_function(node, symbols)
            if enclosing is None:
                continue
            calls.append(CallSite(caller_name=enclosing.name, callee_name=callee_name))

        imports: list[RawImport] = []
        for node in walk(tree_root):
            if node.type == "preproc_include":
                path_node = child_by_field(node, "path")
                if path_node is not None:
                    text = node_text(path_node, source).strip('"<>')
                    imports.append(RawImport(module=text))

        return FileExtraction(symbols=symbols, calls=calls, imports=imports)
