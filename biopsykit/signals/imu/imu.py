from typing import Union, Optional

import pandas as pd
import numpy as np

from biopsykit.utils.time import utc
from biopsykit.utils.array_handling import sliding_window


def convert_acc_data_to_g(data: Union[pd.DataFrame], inplace: Optional[bool] = False) -> Union[None, pd.DataFrame]:
    acc_cols = data.filter(like='acc').columns
    if not inplace:
        data = data.copy()
    data.loc[:, acc_cols] = data.loc[:, acc_cols] / 9.81

    if not inplace:
        return data


def get_windows(data: Union[np.array, pd.Series, pd.DataFrame],
                window_samples: Optional[int] = None,
                window_sec: Optional[int] = None,
                sampling_rate: Optional[Union[int, float]] = 0,
                overlap_samples: Optional[int] = None,
                overlap_percent: Optional[float] = None) -> pd.DataFrame:
    index = None
    index_resample = None
    if isinstance(data, (pd.DataFrame, pd.Series)):
        index = data.index

    data_window = sliding_window(data,
                                 window_samples=window_samples, window_sec=window_sec,
                                 sampling_rate=sampling_rate, overlap_samples=overlap_samples,
                                 overlap_percent=overlap_percent)
    if index is not None:
        index_resample = sliding_window(index.values,
                                        window_samples=window_samples, window_sec=window_sec,
                                        sampling_rate=sampling_rate, overlap_samples=overlap_samples,
                                        overlap_percent=overlap_percent)[:, 0]
        if isinstance(index, pd.DatetimeIndex):
            index_resample = pd.DatetimeIndex(index_resample)
            index_resample = index_resample.tz_localize(utc).tz_convert(index.tzinfo)

    data_window = np.transpose(data_window)
    data_window = {axis: pd.DataFrame(np.transpose(data), index=index_resample) for axis, data in
                   zip(['x', 'y', 'z'], data_window)}
    data_window = pd.concat(data_window, axis=1)
    data_window.columns.names = ['axis', 'samples']
    return data_window


def get_var_norm(data: pd.DataFrame) -> pd.DataFrame:
    var = data.groupby(axis=1, level='axis').apply(lambda x: np.var(x, axis=1))
    norm = pd.DataFrame(np.linalg.norm(var, axis=1), index=var.index, columns=['var_norm'])
    return norm

