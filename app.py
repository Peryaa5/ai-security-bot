import streamlit as st


st.set_page_config(
    page_title="Анализ угроз ИИ-системы",
    page_icon="🛡️",
    layout="wide",
)


# Настройка ширины страницы и размера заголовка
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


# Состояние поля описания
if "description" not in st.session_state:
    st.session_state.description = ""


def clear_description():
    st.session_state.description = ""


# Заголовок страницы
st.markdown(
    """
    <div class="main-title">
        Формирование профиля угроз ИИ-системы и соответствующих
        требований по их закрытию
    </div>
    """,
    unsafe_allow_html=True,
)


# Режимы работы
description_tab, add_threat_tab = st.tabs(
    [
        "Описание системы",
        "Добавление угрозы",
    ]
)


# Первый режим — описание системы
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
            st.success("Описание принято для анализа.")


# Второй режим — добавление угрозы
with add_threat_tab:
    st.subheader("Добавление угрозы")
    st.info("Раздел находится в разработке.")
