import streamlit as st

from main import (
    UNKNOWN_ANSWER,
    analyze_questionnaire_answers,
    analyze_system_description,
    read_criteria_contract,
    save_result,
)


st.set_page_config(
    page_title="Анализ угроз ИИ-системы",
    page_icon="🛡️",
    layout="wide",
)


st.markdown(
    """
    <style>
        .block-container {
            max-width: 1350px;
            padding-top: 2.5rem;
            padding-left: 3rem;
            padding-right: 3rem;
        }

        .main-title {
            font-size: 38px;
            line-height: 1.2;
            font-weight: 700;
            margin-bottom: 24px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


NOT_SELECTED = "— Выберите ответ —"
QUESTIONNAIRE_CRITERIA = read_criteria_contract()["criteria"]

STATE_DEFAULTS = {
    "description": "",
    "analysis_base_description": "",
    "analysis_result": None,
    "clarifications": [],
    "clarification_version": 0,
    "questionnaire_result": None,
    "criteria_json_for_backend": None,
}

for state_name, default_value in STATE_DEFAULTS.items():
    if state_name not in st.session_state:
        st.session_state[state_name] = default_value


def questionnaire_widget_key(criterion_id: str) -> str:
    """Получить безопасный ключ виджета для ID вида 2.3.1."""

    return "questionnaire_" + criterion_id.replace(".", "_")


def clear_description() -> None:
    st.session_state.description = ""
    st.session_state.analysis_base_description = ""
    st.session_state.analysis_result = None
    st.session_state.clarifications = []
    st.session_state.clarification_version += 1
    st.session_state.criteria_json_for_backend = None


def clear_questionnaire() -> None:
    """Очистить ответы анкеты и связанный результат."""

    for criterion in QUESTIONNAIRE_CRITERIA:
        st.session_state.pop(
            questionnaire_widget_key(criterion["id"]),
            None,
        )
    st.session_state.questionnaire_result = None
    st.session_state.criteria_json_for_backend = None


def run_criteria_analysis() -> dict:
    """Отправить исходное описание и все уточнения в GigaChat."""

    additional_information = "\n\n".join(
        st.session_state.clarifications
    )
    result = analyze_system_description(
        description=st.session_state.analysis_base_description,
        additional_information=additional_information,
    )
    save_result(result)
    return result


def questionnaire_options(criterion: dict) -> list[str]:
    """Сформировать варианты ответа для вопроса анкеты."""

    if criterion["id"] == "1.1":
        return [
            NOT_SELECTED,
            *criterion["allowed_answers"],
            UNKNOWN_ANSWER,
        ]
    return [NOT_SELECTED, "Да", "Нет", UNKNOWN_ANSWER]


def prepare_questionnaire_answers(
    raw_answers: dict[str, str],
) -> tuple[dict[str, str], list[dict]]:
    """Проверить обязательные ответы и применить зависимости."""

    prepared: dict[str, str] = {}
    missing: list[dict] = []

    for criterion in QUESTIONNAIRE_CRITERIA:
        criterion_id = criterion["id"]
        answer = raw_answers[criterion_id]
        dependency = criterion.get("depends_on")

        if dependency:
            parent_answer = prepared.get(dependency["id"])
            if parent_answer == "Нет":
                prepared[criterion_id] = "n/a"
                continue
            if parent_answer == UNKNOWN_ANSWER:
                prepared[criterion_id] = UNKNOWN_ANSWER
                continue
            if parent_answer in (None, NOT_SELECTED):
                prepared[criterion_id] = UNKNOWN_ANSWER
                continue

        if answer == NOT_SELECTED:
            missing.append(criterion)
        else:
            prepared[criterion_id] = answer

    return prepared, missing


def short_error(error: Exception) -> str:
    """Не выводить на страницу полный внутренний ответ модели."""

    return str(error).splitlines()[0]


st.markdown(
    """
    <div class="main-title">
        Формирование профиля угроз ИИ-системы и соответствующих
        требований по их закрытию
    </div>
    """,
    unsafe_allow_html=True,
)


description_tab, questionnaire_tab = st.tabs(
    ["Описание системы", "Анкета"]
)


with description_tab:
    st.write(
        "Опишите назначение, архитектуру и особенности "
        "анализируемой системы на базе ИИ."
    )

    with st.expander("Подсказка"):
        st.write("В описании желательно указать:")
        st.markdown(
            """
            - назначение системы;
            - пользователей системы;
            - обрабатываемые данные;
            - используемую ИИ-модель;
            - наличие RAG и векторной базы;
            - интеграции с другими сервисами;
            - наличие веб-интерфейса и API;
            - возможности ИИ-агентов;
            - способы авторизации;
            - журналирование запросов и ответов.
            """
        )

    st.text_area(
        "Описание системы",
        key="description",
        height=260,
        placeholder="Введите описание системы...",
        label_visibility="collapsed",
    )

    clear_column, empty_column, analyze_column = st.columns(
        [1.2, 5.8, 1.8]
    )

    with clear_column:
        st.button(
            "Очистить",
            on_click=clear_description,
            use_container_width=True,
        )

    with analyze_column:
        analyze_button = st.button(
            "Проанализировать",
            type="primary",
            use_container_width=True,
        )

    if analyze_button:
        if not st.session_state.description.strip():
            st.warning("Введите описание системы.")
        else:
            st.session_state.analysis_base_description = (
                st.session_state.description.strip()
            )
            st.session_state.clarifications = []
            st.session_state.criteria_json_for_backend = None

            try:
                with st.spinner("Анализируем описание системы..."):
                    st.session_state.analysis_result = (
                        run_criteria_analysis()
                    )
            except Exception as error:
                st.session_state.analysis_result = None
                st.error(
                    "Не удалось выполнить анализ. "
                    f"{short_error(error)}"
                )

    analysis_result = st.session_state.analysis_result

    if analysis_result:
        if analysis_result["vectorization_ready"]:
            st.session_state.criteria_json_for_backend = analysis_result
            st.success(
                "Описание содержит все необходимые сведения. "
                "Переходим к формированию профиля угроз."
            )
        else:
            st.warning(analysis_result["message_to_user"])

            questions = [
                item["clarifying_question"]
                for item in analysis_result["criteria"]
                if item["status"] == "missing"
                and item["clarifying_question"]
            ]

            st.markdown("**Пожалуйста, уточните:**")
            for number, question in enumerate(questions, start=1):
                st.write(f"{number}. {question}")

            clarification_key = (
                "clarification_input_"
                f"{st.session_state.clarification_version}"
            )
            clarification = st.text_area(
                "Дополнительные сведения",
                key=clarification_key,
                height=160,
                placeholder=(
                    "Ответьте на перечисленные вопросы одним сообщением..."
                ),
            )

            if st.button(
                "Отправить уточнение",
                type="primary",
                use_container_width=True,
            ):
                if not clarification.strip():
                    st.warning("Введите недостающие сведения.")
                else:
                    st.session_state.clarifications.append(
                        clarification.strip()
                    )

                    try:
                        with st.spinner(
                            "Проверяем дополнительные сведения..."
                        ):
                            st.session_state.analysis_result = (
                                run_criteria_analysis()
                            )
                        st.session_state.clarification_version += 1
                        st.rerun()
                    except Exception as error:
                        st.error(
                            "Не удалось обработать уточнение: "
                            f"{short_error(error)}"
                        )


with questionnaire_tab:
    st.subheader("Анкета по критериям системы")
    st.write(
        "Ответьте на вопросы анкеты. Если точный ответ неизвестен, "
        "выберите «Не знаю» — этот вариант не будет интерпретирован как «Нет»."
    )

    raw_answers: dict[str, str] = {}
    with st.form("system_questionnaire"):
        for category in ("Общие", "Технические"):
            st.markdown(f"### {category} критерии")

            for criterion in QUESTIONNAIRE_CRITERIA:
                if criterion["category"] != category:
                    continue

                dependency = criterion.get("depends_on")
                help_text = None
                if dependency:
                    help_text = (
                        "Если ответ на связанный критерий "
                        f"{dependency['id']} — «Нет», этот пункт будет "
                        "автоматически отмечен как n/a."
                    )

                raw_answers[criterion["id"]] = st.selectbox(
                    f"{criterion['id']}. {criterion['criterion']}",
                    options=questionnaire_options(criterion),
                    key=questionnaire_widget_key(criterion["id"]),
                    help=help_text,
                )

        questionnaire_submitted = st.form_submit_button(
            "Сформировать профиль",
            type="primary",
            use_container_width=True,
        )

    st.button(
        "Очистить анкету",
        on_click=clear_questionnaire,
        use_container_width=False,
    )

    if questionnaire_submitted:
        prepared_answers, missing_questions = (
            prepare_questionnaire_answers(raw_answers)
        )

        if missing_questions:
            st.session_state.questionnaire_result = None
            st.warning(
                "Анкета не отправлена: заполните все обязательные пункты."
            )
            for criterion in missing_questions:
                st.write(
                    f"• {criterion['id']}. {criterion['criterion']}"
                )
        else:
            try:
                with st.spinner("Обрабатываем ответы анкеты..."):
                    questionnaire_result = (
                        analyze_questionnaire_answers(prepared_answers)
                    )
                    save_result(questionnaire_result)

                st.session_state.questionnaire_result = (
                    questionnaire_result
                )
                st.session_state.criteria_json_for_backend = (
                    questionnaire_result
                    if questionnaire_result["vectorization_ready"]
                    else None
                )
            except Exception as error:
                st.session_state.questionnaire_result = None
                st.error(
                    "Не удалось обработать анкету. "
                    f"{short_error(error)}"
                )

    questionnaire_result = st.session_state.questionnaire_result
    if questionnaire_result:
        if questionnaire_result["vectorization_ready"]:
            st.success("Анкета успешно обработана.")
        else:
            st.success("Анкета успешно сохранена.")