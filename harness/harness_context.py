#!/usr/bin/env python3
"""Object-oriented converter for Harness context documents."""

from __future__ import annotations

import argparse
import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterable, Sequence

JsonObject = dict[str, Any]


class Text:
    """Shared text helpers and document punctuation."""

    COLON = "\uff1a"
    SEMICOLON = "\uff1b"
    PERIOD = "\u3002"

    @staticmethod
    def lines(value: str) -> list[str]:
        return value.replace("\r\n", "\n").splitlines()

    @staticmethod
    def strip_suffix(value: str, suffix: str) -> str:
        return value.removesuffix(suffix)

    @staticmethod
    def require_fields(data: JsonObject, fields: set[str], document: str) -> None:
        missing = fields - data.keys()
        if missing:
            raise ValueError(f"{document} JSON missing fields: {', '.join(sorted(missing))}")

    @staticmethod
    def require_string_list(value: Any, field: str, *, non_empty: bool = False) -> list[str]:
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            raise ValueError(f"{field} must be a string array")
        if non_empty and not value:
            raise ValueError(f"{field} must not be empty")
        return value


class DocumentHandler(ABC):
    """Base class for one fixed Harness Markdown format."""

    document_type: str

    @abstractmethod
    def format(self, data: JsonObject) -> str:
        raise NotImplementedError

    @abstractmethod
    def parse(self, markdown: str) -> JsonObject:
        raise NotImplementedError


class ArchitectureHandler(DocumentHandler):
    document_type = "architecture"
    title = "# ARCHITECTURE.md"
    module_heading = "## \u6a21\u5757\u8bf4\u660e"
    tree_heading = "## \u76ee\u5f55\u7ed3\u6784"
    constraints_heading = "## \u8bbe\u8ba1\u7ea6\u675f"

    def format(self, data: JsonObject) -> str:
        Text.require_fields(
            data,
            {"module_description", "directory_structure", "design_constraints"},
            self.document_type,
        )
        module_description = str(data["module_description"])
        description_lines = Text.lines(module_description)
        lines = [
            self.title,
            "",
            self.module_heading,
            *description_lines,
            "",
            self.tree_heading,
        ]
        for item in data["directory_structure"]:
            if not isinstance(item, dict) or "path" not in item or "description" not in item:
                raise ValueError("directory_structure items need path and description")
            lines.append(
                f"- `{item['path']}`{Text.COLON}{item['description']}{Text.SEMICOLON}"
            )
        lines.extend(["", self.constraints_heading])
        for constraint in data["design_constraints"]:
            lines.append(f"- {constraint}{Text.SEMICOLON}")
        return "\n".join(lines) + "\n"

    def parse(self, markdown: str) -> JsonObject:
        lines = Text.lines(markdown)
        if not lines or lines[0].lstrip("\ufeff") != self.title:
            raise ValueError("invalid ARCHITECTURE.md title")
        try:
            module_index = lines.index(self.module_heading)
            tree_index = lines.index(self.tree_heading)
            constraints_index = lines.index(self.constraints_heading)
        except ValueError as exc:
            raise ValueError("ARCHITECTURE.md sections are invalid") from exc

        description_lines = lines[module_index + 1 : tree_index]
        while description_lines and not description_lines[0]:
            description_lines.pop(0)
        while description_lines and not description_lines[-1]:
            description_lines.pop()
        if not description_lines:
            raise ValueError("module description must not be empty")
        description = "\n".join(description_lines)

        directory_pattern = re.compile(
            rf"^- `([^`]+)`{re.escape(Text.COLON)}(.+?)(?:{re.escape(Text.SEMICOLON)})?$"
        )
        directory_structure = []
        for line in lines[tree_index + 1 : constraints_index]:
            if not line:
                continue
            match = directory_pattern.fullmatch(line)
            if not match:
                raise ValueError(f"invalid directory line: {line}")
            directory_structure.append(
                {"path": match.group(1), "description": match.group(2)}
            )

        design_constraints = []
        for line in lines[constraints_index + 1 :]:
            if not line:
                continue
            if not line.startswith("- "):
                raise ValueError(f"invalid constraint line: {line}")
            design_constraints.append(line[2:].removesuffix(Text.SEMICOLON))

        return {
            "module_description": description,
            "directory_structure": directory_structure,
            "design_constraints": design_constraints,
        }


class ProgressHandler(DocumentHandler):
    document_type = "progress"
    title = "# PROGRESS.md"
    project_heading = "## \u9879\u76ee\u8fdb\u5ea6"
    current_heading = "### \u5f53\u524d\u72b6\u6001"
    completed_heading = "### \u5df2\u5b8c\u6210"
    active_heading = "### \u8fdb\u884c\u4e2d"
    issues_heading = "### \u5df2\u77e5\u95ee\u9898"
    next_heading = "### \u4e0b\u4e00\u6b65"

    def format(self, data: JsonObject) -> str:
        Text.require_fields(
            data,
            {"current_status", "completed", "in_progress", "known_issues", "next_steps"},
            self.document_type,
        )
        status = data["current_status"]
        if not isinstance(status, dict):
            raise ValueError("current_status must be an object")
        Text.require_fields(status, {"latest_commit", "test_status", "lint"}, "current_status")
        commit = status["latest_commit"]
        if not isinstance(commit, dict):
            raise ValueError("latest_commit must be an object")
        Text.require_fields(commit, {"hash", "message"}, "latest_commit")

        lines = [
            self.title,
            "",
            self.project_heading,
            "",
            self.current_heading,
            f"- \u6700\u65b0 commit: `{commit['hash']}`\uff08{commit['message']}\uff09",
            f"- \u6d4b\u8bd5\u72b6\u6001{Text.COLON}{status['test_status']}",
            f"- Lint{Text.COLON}{status['lint']}",
            "",
            self.completed_heading,
        ]
        lines.extend(f"- [x] {item}" for item in data["completed"])
        lines.extend(["", self.active_heading])
        lines.extend(f"- [ ] {item}" for item in data["in_progress"])
        lines.extend(["", self.issues_heading])
        known_issues = data["known_issues"]
        for index, item in enumerate(known_issues):
            punctuation = Text.SEMICOLON if index < len(known_issues) - 1 else Text.PERIOD
            lines.append(f"- {item}{punctuation}")
        lines.extend(["", self.next_heading])
        next_steps = data["next_steps"]
        for index, item in enumerate(next_steps, start=1):
            punctuation = Text.SEMICOLON if index < len(next_steps) else Text.PERIOD
            lines.append(f"{index}. {item}{punctuation}")
        return "\n".join(lines) + "\n"

    def parse(self, markdown: str) -> JsonObject:
        lines = Text.lines(markdown)
        if not lines or lines[0].lstrip("\ufeff") != self.title:
            raise ValueError("invalid PROGRESS.md title")
        sections = [
            self.project_heading,
            self.current_heading,
            self.completed_heading,
            self.active_heading,
            self.issues_heading,
            self.next_heading,
        ]
        try:
            _, current, completed, active, issues, next_step = [lines.index(x) for x in sections]
        except ValueError as exc:
            raise ValueError("PROGRESS.md sections are invalid") from exc

        status_lines = [line for line in lines[current + 1 : completed] if line]
        if len(status_lines) != 3:
            raise ValueError("current status must contain three lines")
        commit_match = re.fullmatch(
            rf"- \u6700\u65b0 commit: `([^`]+)`\uff08(.+)\uff09", status_lines[0]
        )
        test_match = re.fullmatch(
            rf"- \u6d4b\u8bd5\u72b6\u6001{re.escape(Text.COLON)}(.+)", status_lines[1]
        )
        lint_match = re.fullmatch(
            rf"- Lint{re.escape(Text.COLON)}(.+)", status_lines[2]
        )
        if not commit_match or not test_match or not lint_match:
            raise ValueError("current status format is invalid")

        def parse_checkbox(start: int, end: int, prefix: str) -> list[str]:
            values = []
            for line in lines[start:end]:
                if not line:
                    continue
                if not line.startswith(prefix):
                    raise ValueError(f"invalid checkbox line: {line}")
                values.append(line[len(prefix) :])
            return values

        known_issues = [
            Text.strip_suffix(
                Text.strip_suffix(line[2:], Text.SEMICOLON),
                Text.PERIOD,
            )
            for line in lines[issues + 1 : next_step]
            if line
        ]
        next_steps = []
        for expected, line in enumerate(
            (line for line in lines[next_step + 1 :] if line), start=1
        ):
            match = re.fullmatch(
                rf"{expected}\. (.+?)(?:{re.escape(Text.SEMICOLON)}|{re.escape(Text.PERIOD)})?", line
            )
            if not match:
                raise ValueError(f"invalid next step line: {line}")
            next_steps.append(match.group(1))

        return {
            "current_status": {
                "latest_commit": {
                    "hash": commit_match.group(1),
                    "message": commit_match.group(2),
                },
                "test_status": test_match.group(1),
                "lint": lint_match.group(1),
            },
            "completed": parse_checkbox(completed + 1, active, "- [x] "),
            "in_progress": parse_checkbox(active + 1, issues, "- [ ] "),
            "known_issues": known_issues,
            "next_steps": next_steps,
        }


class DecisionsHandler(DocumentHandler):
    document_type = "decisions"
    title = "# DECISIONS.md"
    labels = [
        "\u7d22\u5f15",
        "\u65e5\u671f",
        "\u72b6\u6001",
        "\u51b3\u7b56",
        "\u539f\u56e0",
        "\u653e\u5f03\u65b9\u6848",
        "\u5f71\u54cd",
    ]
    keys = [
        "keywords",
        "date",
        "status",
        "decision",
        "reason",
        "rejected_alternative",
        "impact",
    ]

    def format(self, data: JsonObject) -> str:
        decisions = data.get("decisions")
        if not isinstance(decisions, list) or not decisions:
            raise ValueError("decisions JSON must contain a non-empty decisions array")
        required = {
            "title",
            "keywords",
            "date",
            "status",
            "decision",
            "reason",
            "rejected_alternative",
            "impact",
        }
        lines = [self.title, ""]
        for index, item in enumerate(decisions):
            if not isinstance(item, dict):
                raise ValueError("each decision must be an object")
            Text.require_fields(item, required, "decision")
            keywords = Text.require_string_list(item["keywords"], "keywords", non_empty=True)
            if index:
                lines.append("")
            lines.extend([f"## {item['title']}", ""])
            for label, key in zip(self.labels, self.keys):
                value = ", ".join(keywords) if key == "keywords" else item[key]
                lines.append(f"- {label}{Text.COLON}{value}")
        return "\n".join(lines) + "\n"

    def parse(self, markdown: str) -> JsonObject:
        lines = Text.lines(markdown)
        if not lines or lines[0].lstrip("\ufeff") != self.title:
            raise ValueError("invalid DECISIONS.md title")
        title_indexes = [index for index, line in enumerate(lines) if line.startswith("## ")]
        if not title_indexes:
            raise ValueError("DECISIONS.md must contain at least one decision")

        decisions = []
        for position, start in enumerate(title_indexes):
            end = title_indexes[position + 1] if position + 1 < len(title_indexes) else len(lines)
            block = lines[start:end]
            while block and block[-1] == "":
                block.pop()
            if len(block) != 9 or block[1] != "":
                raise ValueError("each decision must contain one title and seven fields")
            item: JsonObject = {"title": block[0][3:]}
            for offset, (label, key) in enumerate(zip(self.labels, self.keys), start=2):
                prefix = f"- {label}{Text.COLON}"
                if not block[offset].startswith(prefix) or not block[offset][len(prefix) :]:
                    raise ValueError(f"invalid DECISIONS.md field: {block[offset]}")
                value = block[offset][len(prefix) :]
                item[key] = (
                    [part.strip() for part in value.split(",") if part.strip()]
                    if key == "keywords"
                    else value
                )
            decisions.append(item)
        return {"decisions": decisions}


class FeaturesHandler(DocumentHandler):
    document_type = "features"
    title = "# FEATURES.md"
    rules_heading = "## \u529f\u80fd\u6e05\u5355\u89c4\u5219"
    labels = {
        "index": "\u7d22\u5f15",
        "date": "\u65e5\u671f",
        "priority": "\u4f18\u5148\u7ea7",
        "area": "\u6240\u5c5e\u533a\u57df",
        "behavior": "\u7528\u6237\u53ef\u89c1\u884c\u4e3a",
        "status": "\u72b6\u6001",
        "steps": "\u9a8c\u8bc1\u6b65\u9aa4",
        "evidence": "\u9a8c\u8bc1\u8bc1\u636e",
        "notes": "\u5907\u6ce8",
    }

    RULES = (
        "\u6bcf\u6b21\u53ea\u6fc0\u6d3b\u4e00\u4e2a\u529f\u80fd\u9879\uff1b",
        "\u529f\u80fd\u72b6\u6001\u901a\u5e38\u5305\u62ec\uff1a`not_started`\u3001`in_progress`\u3001`blocked` \u548c `passing`\u3002\u540c\u4e00\u65f6\u95f4\u53ea\u80fd\u6709\u4e00\u4e2a\u529f\u80fd\u5904\u4e8e `in_progress` \u72b6\u6001\u3002\u529f\u80fd\u53ea\u6709\u5728\u9a8c\u8bc1\u547d\u4ee4\u901a\u8fc7\u5e76\u7559\u4e0b\u8bc1\u636e\u540e\uff0c\u624d\u80fd\u6807\u8bb0\u4e3a `passing`\u3002",
        "\u529f\u80fd\u72b6\u6001\u5e94\u6839\u636e\u9a8c\u8bc1\u7ed3\u679c\u66f4\u65b0\uff0c\u4e0d\u80fd\u4ec5\u51ed\u4e3b\u89c2\u5224\u65ad\u6807\u8bb0\u5b8c\u6210\u3002",
    )
    ALLOWED_STATUSES = frozenset({"not_started", "in_progress", "blocked", "passing"})
    @classmethod
    def _validate_features(cls, features: list[JsonObject]) -> None:
        in_progress_count = 0
        for item in features:
            status = item["status"]
            if not isinstance(status, str) or status not in cls.ALLOWED_STATUSES:
                allowed = ", ".join(sorted(cls.ALLOWED_STATUSES))
                raise ValueError(f"feature status must be one of: {allowed}")
            if status == "in_progress":
                in_progress_count += 1
            if status == "passing":
                evidence = item["verification_evidence"]
                if not isinstance(evidence, str) or not evidence.strip():
                    raise ValueError("passing feature must contain verification_evidence")
        if in_progress_count > 1:
            raise ValueError("only one feature may be in_progress")

    def format(self, data: JsonObject) -> str:
        rules = Text.require_string_list(data.get("rules"), "rules")
        if rules != list(self.RULES):
            raise ValueError("FEATURES.md rules are fixed and cannot be modified")
        features = data.get("features")
        if not isinstance(features, list):
            raise ValueError("features must be an array")
        required = {
            "id",
            "title",
            "keywords",
            "date",
            "priority",
            "area",
            "user_visible_behavior",
            "status",
            "verification_steps",
            "verification_evidence",
            "notes",
        }
        lines = [self.title, "", self.rules_heading, ""]
        lines.extend(f"- {rule}" for rule in rules)
        for item in features:
            if not isinstance(item, dict):
                raise ValueError("each feature must be an object")
            Text.require_fields(item, required, "feature")
            keywords = Text.require_string_list(item["keywords"], "feature keywords", non_empty=True)
            steps = Text.require_string_list(item["verification_steps"], "verification_steps", non_empty=True)
            lines.extend(["", f"## {item['id']}{Text.COLON}{item['title']}", ""])
            lines.append(f"- {self.labels['index']}{Text.COLON}{', '.join(keywords)}")
            lines.append(f"- {self.labels['date']}{Text.COLON}{item['date']}")
            lines.append(f"- {self.labels['priority']}{Text.COLON}{item['priority']}")
            lines.append(f"- {self.labels['area']}{Text.COLON}`{item['area']}`")
            lines.append(
                f"- {self.labels['behavior']}{Text.COLON}{item['user_visible_behavior']}{Text.PERIOD}"
            )
            lines.append(f"- {self.labels['status']}{Text.COLON}`{item['status']}`")
            lines.append(f"- {self.labels['steps']}{Text.COLON}")
            for number, step in enumerate(steps, start=1):
                punctuation = Text.SEMICOLON if number < len(steps) else Text.PERIOD
                lines.append(f"  {number}. {step}{punctuation}")
            lines.append(
                f"- {self.labels['evidence']}{Text.COLON}{item['verification_evidence']}{Text.PERIOD}"
            )
            lines.append(f"- {self.labels['notes']}{Text.COLON}{item['notes']}{Text.PERIOD}")
        self._validate_features(features)
        return "\n".join(lines) + "\n"

    def parse(self, markdown: str) -> JsonObject:
        lines = Text.lines(markdown)
        if not lines or lines[0].lstrip("\ufeff") != self.title:
            raise ValueError("invalid FEATURES.md title")
        try:
            rules_index = lines.index(self.rules_heading)
        except ValueError as exc:
            raise ValueError("FEATURES.md rules section is missing") from exc

        feature_heading_pattern = re.compile(
            rf"## ([^{re.escape(Text.COLON)}]+){re.escape(Text.COLON)}.+"
        )
        feature_indexes = [
            index for index, line in enumerate(lines) if feature_heading_pattern.fullmatch(line)
        ]
        rules_end = feature_indexes[0] if feature_indexes else len(lines)
        rule_lines = [line for line in lines[rules_index + 1 : rules_end] if line]
        if any(not line.startswith("- ") for line in rule_lines):
            raise ValueError("invalid feature rule")
        rules = [line[2:] for line in rule_lines]
        if rules != list(self.RULES):
            raise ValueError("FEATURES.md rules are fixed and cannot be modified")

        features = []
        for position, start in enumerate(feature_indexes):
            end = feature_indexes[position + 1] if position + 1 < len(feature_indexes) else len(lines)
            block = lines[start:end]
            while block and block[-1] == "":
                block.pop()
            heading = feature_heading_pattern.fullmatch(block[0])
            if not heading or len(block) < 12 or block[1] != "":
                raise ValueError("invalid feature block")
            item: JsonObject = {"id": heading.group(1), "title": heading.group(0).split(Text.COLON, 1)[1]}
            field_sequence = [
                (self.labels["index"], "keywords"),
                (self.labels["date"], "date"),
                (self.labels["priority"], "priority"),
                (self.labels["area"], "area"),
                (self.labels["behavior"], "user_visible_behavior"),
                (self.labels["status"], "status"),
            ]
            cursor = 2
            for label, key in field_sequence:
                prefix = f"- {label}{Text.COLON}"
                if cursor >= len(block) or not block[cursor].startswith(prefix):
                    raise ValueError(
                        f"invalid feature field: {block[cursor] if cursor < len(block) else key}"
                    )
                value = block[cursor][len(prefix) :]
                if key == "keywords":
                    item[key] = [part.strip() for part in value.split(",") if part.strip()]
                elif key == "priority":
                    item[key] = int(value)
                elif key == "area" or key == "status":
                    if not (value.startswith("`") and value.endswith("`")):
                        raise ValueError(f"{key} must use backticks")
                    item[key] = value[1:-1]
                else:
                    item[key] = value.removesuffix(Text.PERIOD)
                cursor += 1

            steps_prefix = f"- {self.labels['steps']}{Text.COLON}"
            if cursor >= len(block) or block[cursor] != steps_prefix:
                raise ValueError("verification steps field is missing")
            cursor += 1
            steps = []
            step_pattern = re.compile(rf"  (\d+)\. (.+?)[{re.escape(Text.SEMICOLON)}{re.escape(Text.PERIOD)}]")
            while cursor < len(block):
                match = step_pattern.fullmatch(block[cursor])
                if not match:
                    break
                if int(match.group(1)) != len(steps) + 1:
                    raise ValueError("verification step numbers are invalid")
                steps.append(match.group(2))
                cursor += 1
            if not steps:
                raise ValueError("verification_steps must not be empty")
            item["verification_steps"] = steps

            for key in ("verification_evidence", "notes"):
                label = self.labels["evidence"] if key == "verification_evidence" else self.labels["notes"]
                prefix = f"- {label}{Text.COLON}"
                if cursor >= len(block) or not block[cursor].startswith(prefix):
                    raise ValueError(f"invalid feature field: {key}")
                item[key] = block[cursor][len(prefix) :].removesuffix(Text.PERIOD)
                cursor += 1
            if cursor != len(block):
                raise ValueError("unexpected content in feature block")
            features.append(item)
        self._validate_features(features)
        return {"rules": list(self.RULES), "features": features}


class DocumentRegistry:
    """Registry that maps a document type to its handler."""

    def __init__(self, handlers: Iterable[DocumentHandler]) -> None:
        self._handlers = {handler.document_type: handler for handler in handlers}

    def get(self, document_type: str) -> DocumentHandler:
        try:
            return self._handlers[document_type]
        except KeyError as exc:
            raise ValueError(f"unsupported document type: {document_type}") from exc

    def choices(self) -> list[str]:
        return sorted(self._handlers)


class IndexService:
    """Index and recency queries for decision and feature records."""

    @staticmethod
    def _matches(data: JsonObject, collection: str, keyword: str) -> list[JsonObject]:
        normalized = keyword.strip().casefold()
        if not normalized:
            raise ValueError("keyword must not be empty")
        return [
            item
            for item in data.get(collection, [])
            if any(normalized in entry.casefold() for entry in item.get("keywords", []))
        ]

    def search(self, document_type: str, data: JsonObject, keyword: str) -> list[JsonObject]:
        if document_type == "decisions":
            return self._matches(data, "decisions", keyword)
        if document_type == "features":
            return self._matches(data, "features", keyword)
        raise ValueError("search is only supported for decisions and features")

    @staticmethod
    def _latest(
        data: JsonObject,
        collection: str,
        record_name: str,
        limit: int,
    ) -> list[JsonObject]:
        if limit < 1:
            raise ValueError("limit must be greater than zero")
        records = data.get(collection, [])
        date_pattern = re.compile(r"\d{4}-\d{2}-\d{2}")
        for item in records:
            date = str(item.get("date", ""))
            if not date_pattern.fullmatch(date):
                raise ValueError(f"{record_name} date must use YYYY-MM-DD")
        return sorted(records, key=lambda item: item["date"], reverse=True)[:limit]

    def latest_decisions(self, data: JsonObject, limit: int = 5) -> list[JsonObject]:
        return self._latest(data, "decisions", "decision", limit)

    def latest_features(self, data: JsonObject, limit: int = 5) -> list[JsonObject]:
        return self._latest(data, "features", "feature", limit)


class FileStore:
    """UTF-8 file input and output."""

    @staticmethod
    def read_text(path: Path) -> str:
        return path.read_text(encoding="utf-8-sig")

    @staticmethod
    def read_json(path: Path) -> JsonObject:
        data = json.loads(FileStore.read_text(path))
        if not isinstance(data, dict):
            raise ValueError("JSON root must be an object")
        return data

    @staticmethod
    def write_text(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


class ConversionService:
    """Application service for conversion and index operations."""

    def __init__(self, registry: DocumentRegistry, index_service: IndexService) -> None:
        self.registry = registry
        self.index_service = index_service

    def json_to_markdown(self, document_type: str, data: JsonObject) -> str:
        return self.registry.get(document_type).format(data)

    def markdown_to_json(self, document_type: str, markdown: str) -> JsonObject:
        return self.registry.get(document_type).parse(markdown)

    def search(self, document_type: str, data: JsonObject, keyword: str) -> list[JsonObject]:
        return self.index_service.search(document_type, data, keyword)

    def latest(self, document_type: str, data: JsonObject, limit: int) -> list[JsonObject]:
        if document_type == "decisions":
            return self.index_service.latest_decisions(data, limit)
        if document_type == "features":
            return self.index_service.latest_features(data, limit)
        raise ValueError("latest is only supported for decisions and features")


class CliApplication:
    """Command-line adapter for the conversion service."""

    def __init__(self, service: ConversionService) -> None:
        self.service = service

    def build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description="Harness context converter")
        parser.add_argument("--type", choices=self.service.registry.choices(), required=True)
        parser.add_argument(
            "--direction",
            choices=("json-to-md", "md-to-json", "search", "latest"),
            required=True,
        )
        parser.add_argument("--keyword", help="search keyword, used with --direction search")
        parser.add_argument("--limit", type=int, default=5, help="result limit for latest")
        parser.add_argument("--input", type=Path, required=True)
        parser.add_argument("--output", type=Path, required=True)
        return parser

    def run(self, argv: Sequence[str] | None = None) -> None:
        args = self.build_parser().parse_args(argv)
        if args.direction == "json-to-md":
            result = self.service.json_to_markdown(args.type, FileStore.read_json(args.input))
            FileStore.write_text(args.output, result)
            return
        if args.direction == "md-to-json":
            data = self.service.markdown_to_json(args.type, FileStore.read_text(args.input))
            FileStore.write_text(args.output, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
            return

        data = (
            FileStore.read_json(args.input)
            if args.input.suffix.lower() == ".json"
            else self.service.markdown_to_json(args.type, FileStore.read_text(args.input))
        )
        if args.direction == "search":
            if not args.keyword:
                raise ValueError("--direction search requires --keyword")
            matches = self.service.search(args.type, data, args.keyword)
        else:
            matches = self.service.latest(args.type, data, args.limit)
        FileStore.write_text(args.output, json.dumps(matches, ensure_ascii=False, indent=2) + "\n")


def create_application() -> CliApplication:
    registry = DocumentRegistry(
        [
            ArchitectureHandler(),
            ProgressHandler(),
            DecisionsHandler(),
            FeaturesHandler(),
        ]
    )
    return CliApplication(ConversionService(registry, IndexService()))


# Backward-compatible function API.
def format_architecture(data: JsonObject) -> str:
    return ArchitectureHandler().format(data)


def parse_architecture(markdown: str) -> JsonObject:
    return ArchitectureHandler().parse(markdown)


def format_progress(data: JsonObject) -> str:
    return ProgressHandler().format(data)


def parse_progress(markdown: str) -> JsonObject:
    return ProgressHandler().parse(markdown)


def format_decisions(data: JsonObject) -> str:
    return DecisionsHandler().format(data)


def parse_decisions(markdown: str) -> JsonObject:
    return DecisionsHandler().parse(markdown)


def format_features(data: JsonObject) -> str:
    return FeaturesHandler().format(data)


def parse_features(markdown: str) -> JsonObject:
    return FeaturesHandler().parse(markdown)


def search_decisions(data: JsonObject, keyword: str) -> list[JsonObject]:
    return IndexService().search("decisions", data, keyword)


def search_features(data: JsonObject, keyword: str) -> list[JsonObject]:
    return IndexService().search("features", data, keyword)


def latest_decisions(data: JsonObject, limit: int = 5) -> list[JsonObject]:
    return IndexService().latest_decisions(data, limit)


def latest_features(data: JsonObject, limit: int = 5) -> list[JsonObject]:
    return IndexService().latest_features(data, limit)


if __name__ == "__main__":
    create_application().run()
