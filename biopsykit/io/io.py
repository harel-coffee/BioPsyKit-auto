import datetime
from pathlib import Path
from typing import Optional, Union, Sequence, Dict, List, Tuple

import pandas as pd
import pytz

from biopsykit.utils import path_t, utc, tz


def load_dataset_nilspod(file_path: Optional[path_t] = None, dataset: Optional['Dataset'] = None,
                         datastreams: Optional[Sequence[str]] = None,
                         timezone: Optional[Union[pytz.timezone, str]] = tz) -> Tuple[pd.DataFrame, int]:
    """
    Converts a recorded by NilsPod into a dataframe.

    You can either pass a Dataset object obtained from `nilspodlib` or directly pass the path to the file to load 
    and convert the file at once.

    Parameters
    ----------
    file_path : str or path, optional
        path to dataset object to converted
    dataset : Dataset
        Dataset object to convert
    datastreams : list of str, optional
        list of datastreams of the Dataset if only specific ones should be included or `None` to load all datastreams.
        Datastreams that are not part of the current dataset will be silently ignored.
    timezone : str or pytz.timezone, optional
            timezone of the acquired data to convert, either as string of as pytz object (default: 'Europe/Berlin')

    Returns
    -------
    tuple
        tuple of pandas dataframe with sensor data and sampling rate

    # TODO add examples
    """
    from nilspodlib import Dataset

    if file_path:
        dataset = Dataset.from_bin_file(file_path)
    if isinstance(timezone, str):
        # convert to pytz object
        timezone = pytz.timezone(timezone)
    # convert dataset to dataframe and localize timestamp
    df = dataset.data_as_df(datastreams, index="utc_datetime").tz_localize(tz=utc).tz_convert(tz=timezone)
    return df, int(dataset.info.sampling_rate_hz)


def load_csv_nilspod(file_path: Optional[path_t] = None, datastreams: Optional[Sequence[str]] = None,
                     timezone: Optional[Union[pytz.timezone, str]] = tz) -> Tuple[pd.DataFrame, int]:
    """
    TODO: add documentation
    Parameters
    ----------
    file_path
    datastreams
    timezone

    Returns
    -------

    """
    import re

    df = pd.read_csv(file_path, header=1, index_col="timestamp")
    header = pd.read_csv(file_path, header=None, nrows=1)

    # infer start time from filename
    start_time = re.findall(r"NilsPodX-[^\s]{4}_(.*?).csv", str(file_path.name))[0]
    start_time = pd.to_datetime(start_time, format="%Y%m%d_%H%M%S").to_datetime64().astype(int)
    # sampling rate is in second column of header
    sampling_rate = int(header.iloc[0, 1])
    # convert index to nanoseconds
    df.index = ((df.index / sampling_rate) * 1e9).astype(int)
    # add start time as offset and convert into datetime index
    df.index = pd.to_datetime(df.index + start_time)
    df.index.name = "date"

    df_filt = pd.DataFrame(index=df.index)
    if datastreams is None:
        df_filt = df
    else:
        # filter only desired datastreams
        for ds in datastreams:
            df_filt = df_filt.join(df.filter(like=ds))

    if isinstance(timezone, str):
        # convert to pytz object
        timezone = pytz.timezone(timezone)
    # localize timezone (is already in correct timezone since start time is inferred from file name)
    df_filt = df_filt.tz_localize(tz=timezone)
    return df_filt, sampling_rate


def load_folder_nilspod(folder_path: path_t, phase_names: Optional[Sequence[str]] = None,
                        datastreams: Optional[Sequence[str]] = None,
                        timezone: Optional[Union[pytz.timezone, str]] = tz) -> Tuple[Dict[str, pd.DataFrame], int]:
    """
    Loads all NilsPod datasets from one folder, converts them into dataframes and combines them into one dictionary.

    Parameters
    ----------
    folder_path : str or path
        path to folder containing data
    phase_names: list, optional
        list of phase names corresponding to the files in the folder. Must match the number of recordings
    datastreams : list of str, optional
        list of datastreams of the Dataset if only specific ones should be included or `None` to load all datastreams.
        Datastreams that are not part of the current dataset will be silently ignored.
    timezone : str or pytz.timezone, optional
            timezone of the acquired data to convert, either as string of as pytz object (default: 'Europe/Berlin')

    Returns
    -------
    tuple
        tuple of dictionary with phase names as keys and pandas dataframes with sensor data as values and sampling rate

    Raises
    ------
    ValueError
        if number of phases does not match the number of datasets in the folder

    # TODO add examples
    """
    # ensure pathlib
    folder_path = Path(folder_path)
    # look for all NilsPod binary files in the folder
    dataset_list = list(sorted(folder_path.glob("*.bin")))
    if phase_names is None:
        phase_names = ["Part{}".format(i) for i in range(len(dataset_list))]

    if len(phase_names) != len(dataset_list):
        raise ValueError("Number of phases does not match number of datasets in the folder!")

    dataset_dict = {phase: load_dataset_nilspod(file_path=dataset_path, datastreams=datastreams, timezone=timezone) for
                    phase, dataset_path in zip(phase_names, dataset_list)}
    # assume equal sampling rates for all datasets in folder => take sampling rate from first dataset
    sampling_rate = list(dataset_dict.values())[0].info.sampling_rate_hz
    return dataset_dict, sampling_rate


def load_time_log(file_path: path_t, index_cols: Optional[Union[str, Sequence[str]]] = None,
                  phase_cols: Optional[Sequence[str]] = None) -> pd.DataFrame:
    """
    Loads time log file.

    Parameters
    ----------
    file_path : str or path
        path to time log file, either Excel or csv file
    index_cols : str list, optional
        column name (or list of column names) that should be used for dataframe index or ``None`` for no index.
        Default: ``None``
    phase_cols : list, optional
        list of column names that contain time log information or ``None`` to use all columns. Default: ``None``

    Returns
    -------
    pd.DataFrame
        pandas dataframe with time log information

    Raises
    ------
    ValueError
        if file format is none of [.xls, .xlsx, .csv]

    TODO: add examples
    """
    # ensure pathlib
    file_path = Path(file_path)
    if file_path.suffix in ['.xls', '.xlsx']:
        df_time_log = pd.read_excel(file_path)
    elif file_path.suffix in ['.csv']:
        df_time_log = pd.read_csv(file_path)
    else:
        raise ValueError("Unrecognized file format {}!".format(file_path.suffix))

    if isinstance(index_cols, str):
        index_cols = [index_cols]

    if index_cols:
        df_time_log.set_index(index_cols, inplace=True)
    if phase_cols:
        df_time_log = df_time_log.loc[:, phase_cols]
    return df_time_log


def convert_time_log_datetime(time_log: pd.DataFrame, dataset: Optional['Dataset'] = None,
                              date: Optional[Union[str, 'datetime']] = None,
                              timezone: Optional[str] = "Europe/Berlin") -> pd.DataFrame:
    """
    TODO: add documentation

    Parameters
    ----------
    time_log
    dataset
    date
    timezone

    Returns
    -------

    Raises
    ------
    ValueError
        if none of `dataset` and `date` is supplied as argument
    """
    if dataset is None and date is None:
        raise ValueError("Either `dataset` or `date` must be supplied as argument!")

    if dataset is not None:
        date = dataset.info.utc_datetime_start.date()
    if isinstance(date, str):
        # ensure datetime
        date = datetime.datetime(date)
    time_log = time_log.applymap(lambda x: pytz.timezone(timezone).localize(datetime.datetime.combine(date, x)))
    return time_log
