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


class PythonExtractor(LanguageExtractor):
    language = "python"
    extensions = (".py",)

    def extract(self, source: bytes, tree_root: TSNode) -> FileExtraction:
        symbols: list[Symbol] = []
        classes: list[Symbol] = []

        for node in walk(tree_root):
            if node.type == "class_definition":
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
            if node.type == "function_definition":
                name_node = child_by_field(node, "name")
                if name_node is None:
                    continue
                parent_class = None
                best_size = None
                for c in classes:
                    if c.node.start_byte <= node.start_byte and node.end_byte <= c.node.end_byte:
                        size = c.node.end_byte - c.node.start_byte
                        if best_size is None or size < best_size:
                            best_size = size
                            parent_class = c.name
                symbols.append(
                    Symbol(
                        kind="FUNCTION",
                        name=name_node and node_text(name_node, source),
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        node=node,
                        parent_name=parent_class,
                    )
                )

        calls: list[CallSite] = []
        for node in walk(tree_root):
            if node.type != "call":
                continue
            func_node = child_by_field(node, "function")
            if func_node is None:
                continue
            callee_name = None
            if func_node.type == "identifier":
                callee_name = node_text(func_node, source)
            elif func_node.type == "attribute":
                attr = child_by_field(func_node, "attribute")
                if attr is not None:
                    callee_name = node_text(attr, source)
            if callee_name is None:
                continue
            enclosing = find_enclosing_function(node, symbols)
            if enclosing is None:
                continue
            calls.append(CallSite(caller_name=enclosing.name, callee_name=callee_name))

        imports: list[RawImport] = []
        for node in walk(tree_root):
            if node.type == "import_from_statement":
                mod = child_by_field(node, "module_name")
                if mod is not None:
                    mod_text = node_text(mod, source)
                    imports.append(RawImport(module=mod_text))
                    for name_child in node.children_by_field_name("name"):
                        name_text = node_text(name_child, source)
                        imports.append(RawImport(module=f"{mod_text}.{name_text}"))
            elif node.type == "import_statement":
                for child in node.children:
                    if child.type == "dotted_name":
                        imports.append(RawImport(module=node_text(child, source)))

        return FileExtraction(symbols=symbols, calls=calls, imports=imports)
