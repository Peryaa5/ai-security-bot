import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole


BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
SYSTEM_PROMPT_FILE = BASE_DIR / "system_prompt.txt"
RESULT_FILE = BASE_DIR / "result.json"
UNKNOWN_ANSWER = "Не знаю"

# В рабочем проекте contract лежит рядом с main.py. Второй путь нужен только
# для случая, когда загруженные файлы находятся в подпапке upload.
CRITERIA_CONTRACT_FILES = (
    BASE_DIR / "criteria_contract.json",
    BASE_DIR.parent / "criteria_contract.json",
)

load_dotenv(ENV_FILE)


def get_required_env(name: str) -> str:
    """Получить обязательную переменную окружения."""

    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"В файле .env отсутствует переменная {name}")
    return value


def get_ca_bundle_path() -> Path:
    """Получить и проверить путь к сертификату."""

    configured_path = get_required_env("GIGACHAT_CA_BUNDLE_FILE")
    ca_path = Path(configured_path)

    if not ca_path.is_absolute():
        ca_path = BASE_DIR / ca_path

    ca_path = ca_path.resolve()
    if not ca_path.is_file():
        raise FileNotFoundError(f"Сертификат не найден: {ca_path}")
    return ca_path


def read_text_file(file_path: Path, description: str) -> str:
    """Прочитать обязательный непустой текстовый файл."""

    if not file_path.is_file():
        raise FileNotFoundError(f"{description} не найден: {file_path}")

    text = file_path.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(f"Файл {file_path.name} пустой")
    return text


def get_criteria_contract_path() -> Path:
    """Найти JSON-контракт критериев."""

    for candidate in CRITERIA_CONTRACT_FILES:
        if candidate.is_file():
            return candidate

    expected_paths = "\n".join(str(path) for path in CRITERIA_CONTRACT_FILES)
    raise FileNotFoundError(
        "Файл criteria_contract.json не найден. Проверены пути:\n"
        f"{expected_paths}"
    )


def read_criteria_contract() -> dict[str, Any]:
    """Прочитать и минимально проверить контракт критериев."""

    contract_path = get_criteria_contract_path()
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Файл {contract_path.name} содержит невалидный JSON"
        ) from error

    criteria = contract.get("criteria")
    if not isinstance(criteria, list) or len(criteria) != 24:
        raise ValueError(
            "criteria_contract.json должен содержать ровно 24 критерия"
        )

    ids = [item.get("id") for item in criteria if isinstance(item, dict)]
    if len(ids) != 24 or len(set(ids)) != 24:
        raise ValueError("ID критериев должны быть заполнены и уникальны")

    return contract


def build_system_prompt() -> str:
    """Добавить к инструкции актуальный каталог критериев."""

    instructions = read_text_file(
        SYSTEM_PROMPT_FILE,
        "Системный промпт",
    )
    contract = read_criteria_contract()
    catalog = {
        "criteria": [
            {
                "id": item["id"],
                "category": item["category"],
                "criterion": item["criterion"],
                "allowed_answers": item["allowed_answers"],
                **(
                    {"depends_on": item["depends_on"]}
                    if "depends_on" in item
                    else {}
                ),
                "default_clarifying_question": item[
                    "clarifying_question"
                ],
            }
            for item in contract["criteria"]
        ]
    }

    return (
        f"{instructions}\n\n"
        "КАТАЛОГ КРИТЕРИЕВ:\n"
        f"{json.dumps(catalog, ensure_ascii=False, indent=2)}"
    )


def send_to_gigachat(system_prompt: str, user_prompt: str) -> str:
    """Отправить запрос в GigaChat."""

    credentials = get_required_env("GIGACHAT_CREDENTIALS")
    scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    model = os.getenv("GIGACHAT_MODEL", "GigaChat")
    ca_bundle_path = get_ca_bundle_path()

    request = Chat(
        messages=[
            Messages(role=MessagesRole.SYSTEM, content=system_prompt),
            Messages(role=MessagesRole.USER, content=user_prompt),
        ],
        temperature=0.1,
    )

    with GigaChat(
        credentials=credentials,
        scope=scope,
        model=model,
        ca_bundle_file=str(ca_bundle_path),
        verify_ssl_certs=True,
    ) as client:
        response = client.chat(request)

    return response.choices[0].message.content.strip()


def parse_json_response(raw_response: str) -> dict[str, Any]:
    """Проверить и преобразовать ответ GigaChat в JSON-объект."""

    cleaned_response = raw_response.strip()
    if cleaned_response.startswith("```") and cleaned_response.endswith("```"):
        lines = cleaned_response.splitlines()
        cleaned_response = "\n".join(lines[1:-1]).strip()

    try:
        parsed_response = json.loads(cleaned_response)
    except json.JSONDecodeError as first_error:
        # Иногда модель пропускает последнюю закрывающую скобку. Исправляем
        # только баланс структурных скобок; содержимое ответа не изменяем.
        repaired_response = repair_json_delimiters(cleaned_response)
        try:
            parsed_response = json.loads(repaired_response)
        except json.JSONDecodeError as second_error:
            raise ValueError(
                "GigaChat вернул JSON с синтаксической ошибкой. "
                "Повторите анализ."
            ) from second_error

    if not isinstance(parsed_response, dict):
        raise ValueError("GigaChat должен вернуть JSON-объект")
    return parsed_response


def repair_json_delimiters(raw_json: str) -> str:
    """Восстановить пропущенные закрывающие } и ] вне строк.

    Функция не исправляет значения, запятые или кавычки. Нормализация ниже
    всё равно проверит ID критериев и допустимые ответы.
    """

    closing_for = {"{": "}", "[": "]"}
    opening_for = {"}": "{", "]": "["}
    stack: list[str] = []
    repaired: list[str] = []
    in_string = False
    escaped = False

    for character in raw_json:
        if in_string:
            repaired.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue

        if character == '"':
            in_string = True
            repaired.append(character)
        elif character in closing_for:
            stack.append(character)
            repaired.append(character)
        elif character in opening_for:
            # Если встретилась ], а последний объект не закрыт, вставляем }
            # непосредственно перед ].
            while stack and stack[-1] != opening_for[character]:
                repaired.append(closing_for[stack.pop()])

            if stack and stack[-1] == opening_for[character]:
                stack.pop()
                repaired.append(character)
            else:
                # Лишнюю закрывающую скобку не маскируем.
                repaired.append(character)
        else:
            repaired.append(character)

    while stack:
        repaired.append(closing_for[stack.pop()])

    return "".join(repaired)


def _text_or_none(value: Any) -> str | None:
    """Нормализовать необязательное текстовое значение."""

    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def build_embedding_text(criteria: list[dict[str, Any]]) -> str:
    """Сформировать осмысленный текст только из определённых критериев."""

    lines: list[str] = []
    for item in criteria:
        if item.get("status") != "determined":
            continue

        criterion = str(item["criterion"]).strip().rstrip("?").strip()
        answer = str(item["answer"]).strip()
        line = f"Критерий {item['id']}. {criterion}. Ответ: {answer}."

        evidence = _text_or_none(item.get("evidence"))
        if evidence and not evidence.startswith(
            "Ответ пользователя в анкете:"
        ):
            line += f" Основание: {evidence}"

        lines.append(line)

    return "\n".join(lines)


def update_result_readiness(result: dict[str, Any]) -> dict[str, Any]:
    """Обновить полноту результата и готовность к векторизации."""

    criteria = result["criteria"]
    missing_ids = [
        item["id"] for item in criteria if item["status"] == "missing"
    ]
    unknown_ids = [
        item["id"] for item in criteria if item["status"] == "unknown"
    ]
    analysis_complete = not missing_ids and not unknown_ids

    result["missing_criteria_ids"] = missing_ids
    result["unknown_criteria_ids"] = unknown_ids
    result["analysis_complete"] = analysis_complete
    result["vectorization_ready"] = analysis_complete
    result["embedding_text"] = (
        build_embedding_text(criteria) if analysis_complete else None
    )
    return result


def normalize_analysis_result(
    raw_result: dict[str, Any],
) -> dict[str, Any]:
    """Собрать безопасный результат со всеми 24 критериями.

    Модель не может превратить отсутствие сведений в ответ «Нет». Если ответ
    не входит в разрешённый список или не имеет основания, критерий считается
    недостающим и для него формируется уточняющий вопрос.
    """

    contract = read_criteria_contract()
    raw_criteria = raw_result.get("criteria", [])
    if not isinstance(raw_criteria, list):
        raw_criteria = []

    raw_by_id = {
        item.get("id"): item
        for item in raw_criteria
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }

    normalized: list[dict[str, Any]] = []
    for expected in contract["criteria"]:
        item = raw_by_id.get(expected["id"], {})
        status = item.get("status")
        answer = _text_or_none(item.get("answer"))
        evidence = _text_or_none(item.get("evidence"))
        question = _text_or_none(item.get("clarifying_question"))

        if (
            status in (None, "determined")
            and answer in expected["allowed_answers"]
            and answer != "n/a"
            and evidence
        ):
            normalized_status = "determined"
            normalized_answer = answer
            normalized_evidence = evidence
            normalized_question = None
        elif status == "not_applicable" and answer == "n/a":
            normalized_status = "not_applicable"
            normalized_answer = "n/a"
            normalized_evidence = evidence
            normalized_question = None
        else:
            normalized_status = "missing"
            normalized_answer = None
            normalized_evidence = None
            normalized_question = question or expected[
                "clarifying_question"
            ]

        normalized.append(
            {
                "id": expected["id"],
                "category": expected["category"],
                "criterion": expected["criterion"],
                "status": normalized_status,
                "answer": normalized_answer,
                "evidence": normalized_evidence,
                "clarifying_question": normalized_question,
            }
        )

    by_id = {item["id"]: item for item in normalized}

    # Зависимые вопросы неприменимы, когда родительский критерий равен «Нет».
    for expected in contract["criteria"]:
        dependency = expected.get("depends_on")
        if not dependency:
            continue

        item = by_id[expected["id"]]
        parent = by_id[dependency["id"]]

        if parent["status"] == "determined" and parent["answer"] == "Нет":
            item.update(
                status="not_applicable",
                answer="n/a",
                evidence=(
                    f"Неприменимо: критерий {parent['id']} имеет ответ «Нет»."
                ),
                clarifying_question=None,
            )
        elif parent["status"] == "missing":
            # Сначала нужно узнать ответ на родительский вопрос.
            item.update(
                status="missing",
                answer=None,
                evidence=None,
                clarifying_question=None,
            )

    result = {
        "schema_version": contract.get("schema_version", "1.0"),
        "criteria": normalized,
    }
    update_result_readiness(result)

    if result["analysis_complete"]:
        message_to_user = "Описание системы содержит все необходимые данные."
    else:
        message_to_user = (
            "Для продолжения анализа необходимо уточнить недостающие "
            "сведения о системе."
        )
    result["message_to_user"] = message_to_user
    return result


def analyze_system_description(
    description: str,
    additional_information: str = "",
) -> dict[str, Any]:
    """Проанализировать описание и вернуть внутренний расширенный JSON."""

    description = description.strip()
    additional_information = additional_information.strip()
    if not description:
        raise ValueError("Описание системы не может быть пустым")

    user_prompt = f"ОПИСАНИЕ СИСТЕМЫ:\n{description}"
    if additional_information:
        user_prompt += (
            "\n\nДОПОЛНИТЕЛЬНЫЕ СВЕДЕНИЯ ПОЛЬЗОВАТЕЛЯ:\n"
            f"{additional_information}"
        )

    raw_response = send_to_gigachat(
        system_prompt=build_system_prompt(),
        user_prompt=user_prompt,
    )
    return normalize_analysis_result(parse_json_response(raw_response))


def analyze_questionnaire_answers(
    answers: dict[str, str],
) -> dict[str, Any]:
    """Обработать заполненную анкету через GigaChat.

    Явные ответы пользователя являются приоритетным источником. GigaChat
    анализирует анкету тем же способом, что и обычное описание, после чего
    Python проверяет допустимые значения и не превращает «Не знаю» в «Нет».
    """

    contract = read_criteria_contract()
    expected_by_id = {
        item["id"]: item for item in contract["criteria"]
    }

    missing_ids = [
        criterion_id
        for criterion_id in expected_by_id
        if criterion_id not in answers
    ]
    if missing_ids:
        raise ValueError(
            "В анкете отсутствуют ответы на критерии: "
            + ", ".join(missing_ids)
        )

    questionnaire_lines = []
    for criterion_id, expected in expected_by_id.items():
        answer = answers[criterion_id]
        if answer != UNKNOWN_ANSWER and answer not in expected[
            "allowed_answers"
        ]:
            raise ValueError(
                f"Недопустимый ответ для критерия {criterion_id}: {answer}"
            )

        questionnaire_lines.append(
            f"{criterion_id}. {expected['criterion']} Ответ: {answer}."
        )

    model_result = analyze_system_description(
        "Пользователь заполнил анкету по критериям системы.\n"
        + "\n".join(questionnaire_lines)
    )
    model_by_id = {
        item["id"]: item for item in model_result["criteria"]
    }

    # Явные ответы из формы важнее интерпретации модели. При совпадении
    # сохраняем более содержательное основание GigaChat.
    raw_criteria: list[dict[str, Any]] = []
    for criterion_id, expected in expected_by_id.items():
        user_answer = answers[criterion_id]
        if user_answer == UNKNOWN_ANSWER:
            continue

        model_item = model_by_id.get(criterion_id, {})
        if (
            model_item.get("status") == "determined"
            and model_item.get("answer") == user_answer
            and model_item.get("evidence")
        ):
            evidence = model_item["evidence"]
        else:
            evidence = f"Ответ пользователя в анкете: «{user_answer}»."

        if user_answer == "n/a":
            raw_criteria.append(
                {
                    "id": criterion_id,
                    "status": "not_applicable",
                    "answer": "n/a",
                    "evidence": evidence,
                }
            )
        else:
            raw_criteria.append(
                {
                    "id": criterion_id,
                    "status": "determined",
                    "answer": user_answer,
                    "evidence": evidence,
                }
            )

    result = normalize_analysis_result({"criteria": raw_criteria})
    result["analysis_source"] = "questionnaire"

    result_by_id = {
        item["id"]: item for item in result["criteria"]
    }
    for criterion_id, user_answer in answers.items():
        result_by_id[criterion_id]["user_answer"] = user_answer

    for item in result["criteria"]:
        if (
            item.get("user_answer") == UNKNOWN_ANSWER
            and item["status"] == "missing"
        ):
            item.update(
                status="unknown",
                answer=None,
                evidence=None,
            )

    update_result_readiness(result)
    unknown_ids = result["unknown_criteria_ids"]

    if unknown_ids:
        result["message_to_user"] = (
            "Анкета обработана, но для части критериев выбран ответ "
            "«Не знаю». Эти ответы сохранены со статусом unknown и не будут "
            "переданы в векторизацию как отрицательные ответы."
        )
    elif result["analysis_complete"]:
        result["message_to_user"] = (
            "Анкета заполнена и успешно обработана."
        )

    return result


def save_result(result: dict[str, Any]) -> None:
    """Атомарно сохранить результат в JSON-файл."""

    temporary_file = RESULT_FILE.with_suffix(".json.tmp")
    temporary_file.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_file.replace(RESULT_FILE)


def main() -> None:
    """Локальная проверка без запуска Streamlit."""

    print("Подключение к GigaChat настроено.\n")
    user_prompt = input("Введите описание системы: ").strip()
    result = analyze_system_description(user_prompt)
    save_result(result)

    print(f"\nРезультат сохранён: {RESULT_FILE}")
    print(result["message_to_user"])

    questions = [
        item["clarifying_question"]
        for item in result["criteria"]
        if item["status"] == "missing" and item["clarifying_question"]
    ]
    for number, question in enumerate(questions, start=1):
        print(f"{number}. {question}")


if __name__ == "__main__":
    main()