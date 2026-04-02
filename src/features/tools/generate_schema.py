#!/usr/bin/env python3
"""
Auto-generate indicators_schema.yml from code.

This tool scans indicator group modules and extracts field names,
then generates a YAML schema file with placeholders for metadata.

Usage:
    python -m src.features.tools.generate_schema --output schema/indicators_schema.yml
    python -m src.features.tools.generate_schema --from-code --format yaml
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


class IndicatorFieldExtractor:
    """Extract indicator field names from indicator group modules."""

    def __init__(self):
        self.groups = {
            "ma": "indicator_groups/ma.py",
            "oscillators": "indicator_groups/oscillators.py",
            "volatility": "indicator_groups/volatility.py",
            "volume": "indicator_groups/volume.py",
            "trend": "indicator_groups/trend.py",
            "candles": "indicator_groups/candles.py",
            "overlap": "indicator_groups/overlap.py",
            "squeeze": "indicator_groups/squeeze.py",
            "statistics": "indicator_groups/statistics.py",
            "performance": "indicator_groups/performance.py",
        }
        self.base_path = Path(__file__).parent.parent

    def extract_fields_from_source(self, group_name: str) -> set[str]:
        """
        Extract field names from source code by parsing Python AST.

        Args:
            group_name: Name of the indicator group

        Returns:
            Set of field names
        """
        file_path = self.base_path / self.groups[group_name]

        if not file_path.exists():
            print(f"Warning: {file_path} not found")
            return set()

        with open(file_path, encoding="utf-8") as f:
            source = f.read()

        fields = set()

        # Pattern 1: result["field_name"] = ...
        pattern1 = r'result\["([a-z0-9_]+)"\]\s*='
        fields.update(re.findall(pattern1, source))

        # Pattern 2: key = f"field_{period}"
        pattern2 = r'key\s*=\s*f?"([a-z0-9_{}]+)"'
        for match in re.findall(pattern2, source):
            # Handle format strings like "ema_{period}"
            if "{" in match:
                # Extract the base pattern
                base = match.split("{")[0]
                # Common periods
                for period in [
                    8,
                    12,
                    13,
                    14,
                    20,
                    21,
                    26,
                    34,
                    50,
                    55,
                    89,
                    144,
                    200,
                    233,
                ]:
                    fields.add(f"{base}{period}")
            else:
                fields.add(match)

        # Pattern 3: if "field_name" in available:
        pattern3 = r'if\s+"([a-z0-9_]+)"\s+in\s+available'
        fields.update(re.findall(pattern3, source))

        return fields

    def infer_field_type(self, field_name: str) -> str:
        """
        Infer SQL type from field name.

        Args:
            field_name: Name of the field

        Returns:
            SQL type as string
        """
        # Boolean indicators
        if any(x in field_name for x in ["_on", "_off", "_signal", "_direction"]):
            return "BOOLEAN"

        # Most indicators are numeric
        return "NUMERIC"

    def determine_nullable(self, field_name: str) -> bool:
        """
        Determine if a field should be nullable.

        Args:
            field_name: Name of the field

        Returns:
            True if nullable
        """
        return field_name not in ["symbol", "timeframe", "timestamp"]

    def extract_all_fields(self) -> dict[str, dict[str, Any]]:
        """
        Extract all fields from all indicator groups.

        Returns:
            Dictionary mapping field names to metadata
        """
        all_fields = {}

        for group_name in self.groups:
            print(f"Extracting fields from {group_name}...")
            fields = self.extract_fields_from_source(group_name)

            for field in fields:
                if field not in all_fields:
                    all_fields[field] = {
                        "name": field,
                        "type": self.infer_field_type(field),
                        "nullable": self.determine_nullable(field),
                        "group": group_name,
                        "description": f"TODO: Add description for {field}",
                    }

            print(f"  Found {len(fields)} fields in {group_name}")

        return all_fields

    def generate_yaml_schema(self, fields: dict[str, dict[str, Any]]) -> str:
        """
        Generate YAML schema from field metadata.

        Args:
            fields: Dictionary of field metadata

        Returns:
            YAML schema as string
        """
        schema: dict[str, Any] = {
            "version": "1.0",
            "description": "Auto-generated indicator schema from code",
            "fields": [],
        }

        # Add system fields first
        system_fields = [
            {
                "name": "symbol",
                "type": "VARCHAR(20)",
                "nullable": False,
                "primary_key": True,
                "description": "Trading symbol",
            },
            {
                "name": "timeframe",
                "type": "VARCHAR(10)",
                "nullable": False,
                "primary_key": True,
                "description": "Timeframe",
            },
            {
                "name": "timestamp",
                "type": "BIGINT",
                "nullable": False,
                "primary_key": True,
                "description": "Unix timestamp in milliseconds",
            },
            {
                "name": "calculated_at",
                "type": "TIMESTAMP",
                "nullable": True,
                "description": "When the indicators were calculated",
            },
        ]

        schema["fields"].extend(system_fields)

        # Add indicator fields sorted by name
        for field_name in sorted(fields.keys()):
            field_meta = fields[field_name]
            schema["fields"].append(
                {
                    "name": field_meta["name"],
                    "type": field_meta["type"],
                    "nullable": field_meta["nullable"],
                    "group": field_meta["group"],
                    "description": field_meta["description"],
                }
            )

        result: str = yaml.dump(
            schema, default_flow_style=False, sort_keys=False, allow_unicode=True
        )
        return result

    def generate_markdown_table(self, fields: dict[str, dict[str, Any]]) -> str:
        """
        Generate markdown table of fields.

        Args:
            fields: Dictionary of field metadata

        Returns:
            Markdown table as string
        """
        lines = [
            "# Indicator Fields Reference",
            "",
            "Auto-generated list of all indicator fields.",
            "",
            "| Field Name | Type | Group | Nullable | Description |",
            "|------------|------|-------|----------|-------------|",
        ]

        for field_name in sorted(fields.keys()):
            field = fields[field_name]
            nullable = "Yes" if field["nullable"] else "No"
            lines.append(
                f"| `{field['name']}` | {field['type']} | {field['group']} | {nullable} | {field['description']} |"
            )

        return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate indicator schema from code")
    parser.add_argument(
        "--from-code",
        action="store_true",
        help="Generate schema by scanning source code",
    )
    parser.add_argument(
        "--format",
        choices=["yaml", "markdown", "both"],
        default="yaml",
        help="Output format",
    )
    parser.add_argument(
        "--output", type=str, default=None, help="Output file path (defaults to stdout)"
    )

    args = parser.parse_args()

    if not args.from_code:
        print("Error: --from-code is required", file=sys.stderr)
        sys.exit(1)

    # Extract fields
    extractor = IndicatorFieldExtractor()
    fields = extractor.extract_all_fields()

    print(f"\nExtracted {len(fields)} unique fields")

    # Generate output
    if args.format in ["yaml", "both"]:
        yaml_output = extractor.generate_yaml_schema(fields)

        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(yaml_output)
            print(f"✅ YAML schema written to {output_path}")
        else:
            print("\n--- YAML Schema ---")
            print(yaml_output)

    if args.format in ["markdown", "both"]:
        md_output = extractor.generate_markdown_table(fields)

        if args.output and args.format == "markdown":
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(md_output)
            print(f"✅ Markdown table written to {output_path}")
        elif args.format == "both":
            md_path = Path(args.output).with_suffix(".md") if args.output else None
            if md_path:
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(md_output)
                print(f"✅ Markdown table written to {md_path}")
        else:
            print("\n--- Markdown Table ---")
            print(md_output)

    print("\n✅ Schema generation complete!")
    print(f"📊 Total fields: {len(fields)}")

    # Group statistics
    groups = {}
    for field in fields.values():
        group = field["group"]
        groups[group] = groups.get(group, 0) + 1

    print("\n📈 Fields by group:")
    for group in sorted(groups.keys()):
        print(f"  {group}: {groups[group]} fields")


if __name__ == "__main__":
    main()
