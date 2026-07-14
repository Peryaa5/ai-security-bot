import json
from pathlib import Path

import pandas as pd


MAPPING_XLSX = Path("Mapping_threats_OWASP_SBER.xlsx")
THREATS_JSON = Path("threats.json")
OUTPUT_JSON = Path("mapping_threats_owasp_sber.json")


with THREATS_JSON.open("r", encoding="utf-8") as file:
    threats_data = json.load(file)

threat_names = {
    threat["threat_id"]: threat["name"]
    for threat in threats_data["threats"]
}

mapping_df = pd.read_excel(
    MAPPING_XLSX,
    sheet_name="Лист1",
    dtype=str
)

mappings = []

for _, row in mapping_df.iterrows():
    owasp_id = row["ID OWASP"].strip()
    sber_id = row["ID SBER"].strip()

    mappings.append(
        {
            "owasp_id": owasp_id,
            "owasp_name": threat_names[owasp_id],
            "sber_id": sber_id,
            "sber_name": threat_names[sber_id],
            "relation_type": row["Тип связи"].strip(),
            "rationale": row["Обоснование"].strip()
        }
    )

mapped_sber_ids = {
    mapping["sber_id"]
    for mapping in mappings
}

unmapped_sber = [
    {
        "sber_id": threat["threat_id"],
        "sber_name": threat["name"],
        "status": "Соответствие OWASP не определено"
    }
    for threat in threats_data["threats"]
    if threat["source"] == "Сбер"
    and threat["threat_id"] not in mapped_sber_ids
]

result = {
    "schema_version": "1.0",
    "dataset_type": "threat_mapping",
    "language": "ru",
    "source_file": MAPPING_XLSX.name,
    "mappings": mappings,
    "unmapped_sber": unmapped_sber
}

with OUTPUT_JSON.open("w", encoding="utf-8") as file:
    json.dump(result, file, ensure_ascii=False, indent=2)

print("Создан файл mapping_threats_owasp_sber.json")
