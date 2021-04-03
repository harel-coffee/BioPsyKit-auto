from typing import Union, Tuple

import numpy as np
import pandas as pd

import biopsykit.utils.array_handling


class WearDetection:
    sampling_rate: int

    def __init__(self, sampling_rate: int):
        self.sampling_rate = sampling_rate

    def predict(self, data: Union[pd.DataFrame, pd.Series, np.array]) -> pd.DataFrame:

        index = None
        index_resample = None
        if isinstance(data, (pd.DataFrame, pd.Series)):
            index = data.index

        if isinstance(data, pd.DataFrame):
            data = data.filter(like="acc")
        else:
            data = pd.DataFrame(data)

        window = 60  # min
        overlap = 15  # min
        overlap_percent = 1.0 - (overlap / window)

        acc_sliding = {
            col: biopsykit.utils.array_handling.sliding_window(
                data[col].values,
                window_sec=window * 60,
                sampling_rate=self.sampling_rate,
                overlap_percent=overlap_percent,
            )
            for col in data
        }

        if index is not None:
            index_resample = biopsykit.utils.array_handling.sliding_window(
                np.arange(0, len(index)),
                window_sec=window * 60,
                sampling_rate=self.sampling_rate,
                overlap_percent=overlap_percent,
            )[:, :]
            start_end = index_resample[:, [0, -1]]
            if np.isnan(start_end[-1, -1]):
                last_idx = index_resample[
                    -1, np.where(~np.isnan(index_resample[-1, :]))[0][-1]
                ]
                start_end[-1, -1] = last_idx

            start_end = start_end.astype(int)

            if isinstance(index, pd.DatetimeIndex):
                index_resample = pd.DataFrame(
                    index.values[start_end], columns=["start", "end"]
                )
                index_resample = index_resample.apply(
                    lambda df: pd.to_datetime(df)
                    .dt.tz_localize("UTC")
                    .dt.tz_convert(index.tzinfo)
                )

        acc_std = pd.DataFrame(
            {axis: np.nanstd(acc_sliding[axis], ddof=1, axis=1) for axis in acc_sliding}
        )

        acc_std[acc_std >= 0.013] = 1
        acc_std[acc_std < 0.013] = 0
        acc_std = np.nansum(acc_std, axis=1)

        acc_range = pd.DataFrame(
            {
                axis: np.nanmax(acc_sliding[axis], axis=1)
                - np.nanmin(acc_sliding[axis], axis=1)
                for axis in acc_sliding
            }
        )

        acc_range[acc_range >= 0.15] = 1
        acc_range[acc_range < 0.15] = 0
        acc_range = np.nansum(acc_range, axis=1)

        wear = np.ones(shape=acc_std.shape)
        wear[np.logical_or(acc_std < 1.0, acc_range < 1.0)] = 0.0

        wear = pd.DataFrame(wear, columns=["wear"])
        if index_resample is not None:
            wear = wear.join(index_resample)

        # apply rescoring three times
        wear = self._rescore_wear_detection(wear)
        wear = self._rescore_wear_detection(wear)
        wear = self._rescore_wear_detection(wear)

        return wear

    @staticmethod
    def _rescore_wear_detection(data: pd.DataFrame) -> pd.DataFrame:
        # group classifications into wear and non-wear blocks
        data["block"] = data["wear"].diff().ne(0).cumsum()
        blocks = list(data.groupby("block"))

        # iterate through blocks
        for (idx_prev, prev), (idx_curr, curr), (idx_post, post) in zip(
            blocks[0:-2], blocks[1:-1], blocks[2:]
        ):
            if curr["wear"].unique():
                # get hour lengths of the previous, current, and next blocks
                dur_prev, dur_curr, dur_post = (
                    len(dur) * 0.25 for dur in [prev, curr, post]
                )

                if dur_curr < 3 and dur_curr / (dur_prev + dur_post) < 0.8:
                    # if the current block is less than 3 hours and the ratio to previous and post blocks is
                    # less than 80% rescore the wear period as non-wear
                    data.loc[data["block"] == idx_curr, "wear"] = 0
                elif dur_curr < 6 and dur_curr / (dur_prev + dur_post) < 0.3:
                    # if the current block is less than 6 hours and the ratio to previous and post blocks is
                    # less than 30% rescore the wear period as non-wear
                    data.loc[data["block"] == idx_curr, "wear"] = 0
        data.drop(columns=["block"], inplace=True)
        return data

    @staticmethod
    def get_major_wear_block(wear_data: pd.DataFrame) -> Tuple:
        wear_data = wear_data.copy()
        wear_data["block"] = wear_data["wear"].diff().ne(0).cumsum()
        wear_blocks = list(
            wear_data.groupby("block")
            .filter(lambda x: (x["wear"] == 1.0).all())
            .groupby("block")
        )
        max_block = wear_blocks[np.argmax([len(b) for i, b in wear_blocks])][1]
        max_block = (max_block["start"].iloc[0], max_block["end"].iloc[-1])
        return max_block
