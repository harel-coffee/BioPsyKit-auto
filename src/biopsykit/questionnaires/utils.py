"""Module containing utility functions for manipulating and processing questionnaire data."""
import warnings
from typing import Optional, Union, Sequence, Tuple, Dict, Literal

import numpy as np
import pandas as pd

__all__ = [
    "bin_scale",
    "compute_scores",
    "crop_scale",
    "convert_scale",
    "find_cols",
    "fill_col_leading_zeros",
    "invert",
    "to_idx",
    "wide_to_long",
]

from biopsykit.utils.dataframe_handling import wide_to_long as wide_to_long_utils
from inspect import getmembers, isfunction
from biopsykit.questionnaires import questionnaires


def find_cols(
    df: pd.DataFrame,
    starts_with: Optional[str] = None,
    ends_with: Optional[str] = None,
    contains: Optional[str] = None,
    fill_zeros: Optional[bool] = True,
) -> Tuple[pd.DataFrame, Sequence[str]]:
    df_filt = df.copy()

    if starts_with:
        df_filt = df_filt.filter(regex="^" + starts_with)
    if ends_with:
        df_filt = df_filt.filter(regex=ends_with + "$")
    if contains:
        df_filt = df_filt.filter(regex=contains)

    cols = df_filt.columns

    if fill_zeros:
        cols = df_filt.columns
        df_filt = fill_col_leading_zeros(df_filt)
    df_filt = df_filt.reindex(sorted(df_filt.columns), axis="columns")

    if not fill_zeros:
        cols = df_filt.columns

    return df_filt, cols


def fill_col_leading_zeros(df: pd.DataFrame, inplace: Optional[bool] = False) -> Union[pd.DataFrame, None]:
    import re

    if not inplace:
        df = df.copy()

    df.columns = [re.sub(r"(\d+)$", lambda m: m.group(1).zfill(2), c) for c in df.columns]

    if not inplace:
        return df


def to_idx(col_idxs: Union[np.array, Sequence[int]]) -> np.array:
    return np.array(col_idxs) - 1


def invert(
    data: Union[pd.DataFrame, pd.Series],
    score_range: Sequence[int],
    cols: Optional[Union[Sequence[int], Sequence[str]]] = None,
    inplace: Optional[bool] = False,
) -> Union[pd.DataFrame, pd.Series, None]:
    if inplace:
        if isinstance(data, pd.DataFrame):
            if cols is not None:
                if isinstance(cols[0], str):
                    data.loc[:, cols] = score_range[1] - data.loc[:, cols] + score_range[0]
                else:
                    data.iloc[:, cols] = score_range[1] - data.iloc[:, cols] + score_range[0]
            else:
                data.iloc[:, :] = score_range[1] - data.iloc[:, :] + score_range[0]
        elif isinstance(data, pd.Series):
            data.iloc[:] = score_range[1] - data.iloc[:] + score_range[0]
        else:
            raise ValueError("Only pd.DataFrame and pd.Series supported!")
    else:
        return score_range[1] - data + score_range[0]


def _invert_subscales(
    data: Union[pd.DataFrame, pd.Series],
    subscales: Union[Sequence[str], Dict[str, Sequence[str]]],
    idx_dict: Dict[str, Sequence[int]],
    score_range: Sequence[int],
):
    for subscale, idxs in idx_dict.items():
        if subscale in subscales:
            data = invert(data, cols=to_idx(idxs), score_range=score_range)

    return data


def convert_scale(
    data: Union[pd.DataFrame, pd.Series],
    offset: int,
    cols: Optional[Union[pd.DataFrame, pd.Series]] = None,
    inplace: Optional[bool] = False,
) -> Union[pd.DataFrame, pd.Series, None]:
    if inplace:
        if isinstance(data, pd.DataFrame):
            if cols is None:
                data.iloc[:, :] = data.iloc[:, :] + offset
            else:
                if isinstance(cols[0], int):
                    data.iloc[:, cols] = data.iloc[:, cols] + offset
                elif isinstance(cols[0], str):
                    data.loc[:, cols] = data.loc[:, cols] + offset
        elif isinstance(data, pd.Series):
            data.iloc[:] = data.iloc[:] + offset
        else:
            raise ValueError("Only pd.DataFrame and pd.Series supported!")
    else:
        data = data.copy()
        if cols is not None:
            data[cols] = data[cols] + offset
            return data
        else:
            return data + offset


def crop_scale(
    data: Union[pd.DataFrame, pd.Series],
    score_scale: Sequence[int],
    inplace: Optional[bool] = True,
    set_nan: Optional[bool] = True,
) -> Union[pd.DataFrame, pd.Series, None]:
    if set_nan:
        if inplace:
            data.mask((data < score_scale[0]) | (data > score_scale[1]), inplace=True)
        else:
            return data.mask((data < score_scale[0]) | (data > score_scale[1]))
    else:
        if inplace:
            data.mask((data < score_scale[0]), other=score_scale[0], inplace=True)
            data.mask((data > score_scale[1]), other=score_scale[1], inplace=True)
        else:
            tmp = data.mask((data < score_scale[0]), other=score_scale[0])
            return tmp.mask((tmp > score_scale[1]), other=score_scale[1])


def bin_scale(
    data: Union[pd.DataFrame, pd.Series],
    bins: Sequence[float],
    col: Optional[Union[int, str]] = None,
    last_max: Optional[bool] = False,
    inplace: Optional[bool] = False,
    right: Optional[bool] = True,
) -> Union[pd.Series, None]:
    if last_max:
        if isinstance(col, int):
            max_val = data.iloc[:, col].max()
        elif isinstance(col, str):
            max_val = data[col].max()
        else:
            max_val = data.max()

        if max_val > max(bins):
            bins = bins + [max_val + 1]

    if isinstance(data, pd.Series):
        c = pd.cut(data.iloc[:], bins=bins, labels=False, right=right)
        if inplace:
            data.iloc[:] = c
        else:
            return c

    elif isinstance(data, pd.DataFrame):
        if col is None:
            if len(data.columns) > 1:
                raise ValueError("Column must be specified when passing dataframe!")
            else:
                c = pd.cut(data.iloc[:, 0], bins=bins, labels=False, right=right)
                if inplace:
                    data.iloc[:, 0] = c
                else:
                    return c

        if isinstance(col, int):
            c = pd.cut(data.iloc[:, col], bins=bins, labels=False, right=right)
            if inplace:
                data.iloc[:, col] = c
            else:
                return c

        if isinstance(col, str):
            c = pd.cut(data.loc[:, col], bins=bins, labels=False, right=right)
            if inplace:
                data.loc[:, col] = c
            else:
                return c


def wide_to_long(data: pd.DataFrame, quest_name: str, levels: Union[str, Sequence[str]]) -> pd.DataFrame:
    warnings.warn(
        "'biopsykit.questionnaires.utils.wide_to_long()' is deprecated! "
        "Please update your code to use 'biopsykit.utils.dataframe_handling.wide_to_long()' in the future.",
        category=DeprecationWarning,
    )
    return wide_to_long_utils(data=data, stubname=quest_name, levels=levels)


def compute_scores(data: pd.DataFrame, quest_dict: Dict[str, Union[Sequence[str], pd.Index]]) -> pd.DataFrame:
    df_scores = pd.DataFrame(index=data.index)

    quest_funcs = dict(getmembers(questionnaires, isfunction))

    for score, columns in quest_dict.items():
        score = score.lower()
        suffix = None
        if "-" in score:
            score_split = score.split("-")
            score = score_split[0]
            suffix = score_split[1]
        df = quest_funcs[score](data[columns])
        if suffix is not None:
            df.columns = ["{}_{}".format(col, suffix) for col in df.columns]
        df_scores = df_scores.join(df)

    return df_scores


def _compute_questionnaire_subscales(
    data: pd.DataFrame,
    score_name: str,
    subscales: Dict[str, Sequence[Union[str, int]]],
    agg_type: Optional[Literal["sum", "mean"]] = "sum",
) -> Dict[str, pd.Series]:
    out = {}
    for key, items in subscales.items():
        if all(isinstance(i, int) for i in items):
            # assume column indices, starting at 1 (-> convert to 0-indexed indices first)
            if agg_type == "sum":
                score = data.iloc[:, to_idx(items)].sum(axis=1)
            else:
                score = data.iloc[:, to_idx(items)].mean(axis=1)
        elif all(isinstance(i, int) for i in items):
            # assume column names
            if agg_type == "sum":
                score = data.loc[:, items].sum(axis=1)
            else:
                score = data.loc[:, items].mean(axis=1)
        else:
            raise ValueError(
                "Subscale columns are either expected as column names (list of strings) or "
                "column indices (list of integers)!"
            )

        out["{}_{}".format(score_name, key)] = score

    return out
