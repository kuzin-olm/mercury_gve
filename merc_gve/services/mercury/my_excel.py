# -*- coding: utf-8 -*-
import pandas as pd

pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)
pd.set_option("display.max_rows", None)


def refactoring_corp_name(enterprise_name):
    """
    выцепляет нормальное имя предприятия, отбрасывая локацию
    """

    if isinstance(enterprise_name, str):
        words = enterprise_name.split()

        for word in words:
            if "(" in word:
                pos = words.index(word)
                enterprise_name = " ".join(words[:pos])

            return enterprise_name
    else:
        return "Физ.лица"


def counter_docs(list_vet_doc):
    """
    считает количество типов вет документов для каждой организации (corp)

    :param list_vet_doc: list из словарей
    :return: pandas.DataFrame, кол-во документов
    """
    df = pd.DataFrame(list_vet_doc)
    df["name_corp"] = df["name_corp"].apply(refactoring_corp_name)
    df = df.drop_duplicates("vetDoc")

    all_doc_count = df["vetDoc"].count()

    # pandas way
    pivot = (
        pd.pivot_table(
            df,
            columns=["type_service"],
            index=["name_corp"],
            values=["vetDoc"],
            aggfunc="count",
        )
        .fillna(0)
        .reset_index()
    )
    pivot["quantity"] = pivot["vetDoc"].sum(axis=1)

    # rename columns
    my_columns = [x for _, x in pivot.columns]
    my_columns[0] = "Предприятие"
    my_columns[-1] = "Кол-во"
    pivot.columns = my_columns

    return pivot, all_doc_count
