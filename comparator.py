import json
from datetime import date


def compare_snapshots(
    table_name: str,
    yesterday: dict[str, dict],   # pk_json_str -> {col: str_value}
    today: dict[str, dict],        # pk_json_str -> {col: str_value}
    value_columns: list[str],
    change_date: date,
) -> list[dict]:
    changes = []
    yesterday_keys = set(yesterday)
    today_keys = set(today)

    for pk in today_keys - yesterday_keys:
        changes.append({
            "change_date": change_date.isoformat(),
            "table_name": table_name,
            "pk_json": pk,
            "change_type": "INSERT",
            "column_name": None,
            "old_value": None,
            "new_value": json.dumps(today[pk], sort_keys=True),
        })

    for pk in yesterday_keys - today_keys:
        changes.append({
            "change_date": change_date.isoformat(),
            "table_name": table_name,
            "pk_json": pk,
            "change_type": "DELETE",
            "column_name": None,
            "old_value": json.dumps(yesterday[pk], sort_keys=True),
            "new_value": None,
        })

    for pk in yesterday_keys & today_keys:
        for col in value_columns:
            old_val = str(yesterday[pk].get(col, ""))
            new_val = str(today[pk].get(col, ""))
            if old_val != new_val:
                changes.append({
                    "change_date": change_date.isoformat(),
                    "table_name": table_name,
                    "pk_json": pk,
                    "change_type": "UPDATE",
                    "column_name": col,
                    "old_value": old_val,
                    "new_value": new_val,
                })

    return changes
