from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

TARGET_FILENAMES = ("PROGRESS.md", "DECISIONS.md", "FEATURES.md", "ARCHITECTURE.md")


@dataclass(frozen=True)
class Document:
    path: Path
    name: str
    content: str


@dataclass(frozen=True)
class CheckIssue:
    file_path: Path
    message: str

    def format(self) -> str:
        return f"{self.file_path}: {self.message}"


@dataclass(frozen=True)
class CheckContext:
    root_dir: Path
    documents: Sequence[Document]


class DocumentScanner:
    def scan(self, root_dir: Path, target_filenames: Sequence[str]) -> list[Document]:
        target_set = set(target_filenames)
        documents: list[Document] = []
        for dirpath, _, filenames in os.walk(root_dir):
            for filename in filenames:
                if filename not in target_set:
                    continue
                path = Path(dirpath) / filename
                try:
                    content = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    content = path.read_text(encoding="utf-8", errors="replace")
                documents.append(Document(path=path, name=filename, content=content))
        documents.sort(key=lambda doc: (TARGET_FILENAMES.index(doc.name), str(doc.path).lower()))
        return documents


class GarbleDetector:
    _question_mark_run = re.compile(r"\?{3,}")

    def find(self, text: str) -> bool:
        if "\ufffd" in text:
            return True
        if self._question_mark_run.search(text):
            return True
        return False


class CheckItem:
    def supports(self, document: Document) -> bool:
        raise NotImplementedError

    def check(self, document: Document, context: CheckContext) -> list[CheckIssue]:
        raise NotImplementedError


class GarbleOnlyCheckItem(CheckItem):
    def __init__(self) -> None:
        self._garble_detector = GarbleDetector()

    def supports(self, document: Document) -> bool:
        return document.name in {"DECISIONS.md", "FEATURES.md", "ARCHITECTURE.md"}

    def check(self, document: Document, context: CheckContext) -> list[CheckIssue]:
        issues: list[CheckIssue] = []
        if self._garble_detector.find(document.content):
            issues.append(CheckIssue(document.path, "检测到乱码"))
        return issues


class ProgressSectionParser:
    def count_items(self, content: str, heading: str) -> int:
        pattern = re.compile(rf"^###\s*{re.escape(heading)}\s*$", re.MULTILINE)
        match = pattern.search(content)
        if not match:
            return 0
        start = match.end()
        end = len(content)
        next_heading = re.search(r"^###\s+.+$", content[start:], re.MULTILINE)
        if next_heading:
            end = start + next_heading.start()
        section = content[start:end]
        count = 0
        for line in section.splitlines():
            if re.match(r"^\s*(?:[-*]\s+\[.*?\]\s+|\d+\.\s+)", line):
                count += 1
        return count


class ProgressCheckItem(CheckItem):
    def __init__(self) -> None:
        self._garble_detector = GarbleDetector()
        self._parser = ProgressSectionParser()

    def supports(self, document: Document) -> bool:
        return document.name == "PROGRESS.md"

    def check(self, document: Document, context: CheckContext) -> list[CheckIssue]:
        issues: list[CheckIssue] = []
        content = document.content
        if self._garble_detector.find(content):
            issues.append(CheckIssue(document.path, "检测到乱码"))

        section_limits = [
            ("已完成", 5, True),
            ("进行中", 5, False),
            ("已知问题", 5, True),
            ("下一步", 5, True),
        ]
        for heading, limit, allow_zero in section_limits:
            count = self._parser.count_items(content, heading)
            if count > limit:
                issues.append(CheckIssue(document.path, f"{heading}条目超过 {limit} 条，当前为 {count} 条"))
            if heading == "进行中" and not allow_zero and count == 0:
                issues.append(CheckIssue(document.path, "进行中至少需要 1 条，当前为 0 条"))
        return issues


class CheckPipeline:
    def __init__(self, items: Sequence[CheckItem]) -> None:
        self._items = list(items)

    def run(self, context: CheckContext) -> list[CheckIssue]:
        issues: list[CheckIssue] = []
        for document in context.documents:
            for item in self._items:
                if item.supports(document):
                    issues.extend(item.check(document, context))
                    break
        return issues


class CheckApplication:
    def __init__(self) -> None:
        self._scanner = DocumentScanner()
        self._pipeline = CheckPipeline([
            ProgressCheckItem(),
            GarbleOnlyCheckItem(),
        ])

    def run(self, argv: Sequence[str]) -> int:
        if len(argv) != 2:
            print("用法: python check.py <指定目录>")
            return 2

        root_dir = Path(argv[1]).resolve()
        if not root_dir.exists() or not root_dir.is_dir():
            print(f"目录不存在: {root_dir}")
            return 2

        documents = self._scanner.scan(root_dir, TARGET_FILENAMES)
        missing = [name for name in TARGET_FILENAMES if not any(doc.name == name for doc in documents)]
        issues: list[CheckIssue] = []
        for name in missing:
            issues.append(CheckIssue(root_dir / name, "未找到目标文件"))

        context = CheckContext(root_dir=root_dir, documents=documents)
        issues.extend(self._pipeline.run(context))

        if issues:
            print("检查未通过，原因如下:")
            for issue in issues:
                print(f"- {issue.format()}")
            return 1

        print("检查通过")
        return 0


def main() -> int:
    return CheckApplication().run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())

