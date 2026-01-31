"""Best-effort resolution of raw import/include strings to indexed file paths.

Cross-language import resolution without a full build system is inherently
best-effort: we normalize the written module string a few common ways (dotted
-> path, relative-to-importer, path separator variants) and look it up against
an index of every indexed file's path (with and without extension). External
/ stdlib imports that don't correspond to a file in the indexed corpus simply
fail to resolve, which is correct behavior (no edge, rather than a wrong one).
"""

from __future__ import annotations

from collections import defaultdict
from posixpath import normpath
from pathlib import PurePosixPath


class ImportIndex:
    def __init__(self, rel_paths: list[str]) -> None:
        self.stem_index: dict[str, list[str]] = defaultdict(list)
        self.basename_index: dict[str, list[str]] = defaultdict(list)
        for rel_path in rel_paths:
            p = PurePosixPath(rel_path)
            stem = str(p.with_suffix(""))
            self.stem_index[stem].append(rel_path)
            self.stem_index[stem.replace("/", ".")].append(rel_path)
            self.basename_index[p.stem].append(rel_path)
            if p.stem in ("__init__", "index", "mod"):
                self.stem_index[str(p.parent)].append(rel_path)

    def resolve(self, module: str, importer_rel_path: str) -> str | None:
        module = module.strip()
        if not module:
            return None

        importer_dir = str(PurePosixPath(importer_rel_path).parent)
        normalized_forms = {
            module,
            module.replace(".", "/"),
            module.replace("::", "/"),
            module.lstrip("./"),
        }
        joined_forms = set()
        for form in normalized_forms:
            if form.startswith("/"):
                joined_forms.add(form.lstrip("/"))
            else:
                joined_forms.add(normpath(str(PurePosixPath(importer_dir, form))))
        normalized_forms |= joined_forms

        candidates: list[str] = []
        for form in normalized_forms:
            if form in self.stem_index:
                candidates.extend(self.stem_index[form])

        if not candidates:
            last_segment = module.replace(".", "/").replace("::", "/").rstrip("/").split("/")[-1]
            if last_segment and last_segment in self.basename_index:
                candidates.extend(self.basename_index[last_segment])

        for candidate in candidates:
            if candidate != importer_rel_path:
                return candidate
        return None
