import json
from pathlib import Path

import pandas as pd


THREATS_XLSX = Path("Threats_OWAPS_SBER.xlsx")
REQUIREMENTS_XLSX = Path("requirements.xlsx")

THREATS_JSON = Path("threats.json")
REQUIREMENTS_JSON = Path("requirements.json")


threats_df = pd.read_excel(
    THREATS_XLSX,
    sheet_name="Threats",
    dtype=str
)

threats = []

for _, row in threats_df.iterrows():
    threat_id = row["ID угрозы"].strip()
    source = row["Источник"].strip()
    name = row["Наименование угрозы"].strip()
    description = row["Описание"].strip()
    impact_object = row["Объект воздействия"].strip()

    threats.append(
        {
            "threat_id": threat_id,
            "source": source,
            "name": name,
            "description": description,
            "impact_object": impact_object,
            "embedding_text": (
                f"ID угрозы: {threat_id}. "
                f"Источник: {source}. "
                f"Угроза: {name}. "
                f"Описание: {description}. "
                f"Объект воздействия: {impact_object}."
            )
        }
    )

threats_data = {
    "schema_version": "1.0",
    "dataset_type": "threats",
    "language": "ru",
    "source_file": THREATS_XLSX.name,
    "threats": threats
}

with THREATS_JSON.open("w", encoding="utf-8") as file:
    json.dump(threats_data, file, ensure_ascii=False, indent=2)


requirements_df = pd.read_excel(
    REQUIREMENTS_XLSX,
    sheet_name="Лист1",
    dtype=str
)

requirements = []

for _, row in requirements_df.iterrows():
    requirement_id = row["ID требования"].strip()
    domain_id = row["ID Домена"].strip()
    domain_name = row["Домен"].strip()
    requirement_text = row["Требование"].strip()

    requirements.append(
        {
            "requirement_id": requirement_id,
            "domain_id": domain_id,
            "domain_name": domain_name,
            "requirement_text": requirement_text,
            "source": "AISVS",
            "embedding_text": (
                f"ID требования: {requirement_id}. "
                f"Домен: {domain_id} — {domain_name}. "
                f"Требование: {requirement_text}"
            )
        }
    )

requirements_data = {
    "schema_version": "1.0",
    "dataset_type": "requirements",
    "language": "ru",
    "source_file": REQUIREMENTS_XLSX.name,
    "requirements": requirements
}

with REQUIREMENTS_JSON.open("w", encoding="utf-8") as file:
    json.dump(requirements_data, file, ensure_ascii=False, indent=2)

print("Созданы файлы threats.json и requirements.json")
