"""Guards for the two CNN-BiLSTM training bugs: fake time and label leakage."""

import numpy as np
import pandas as pd

from projects.shared_libs.data_processor import FeatureExtractor
from scripts.data.load_cicddos import (
    TemporalLeakError,
    assert_no_split_leakage,
    reshape_for_cnn_bilstm,
    windows_from_frame,
    _time_split,
    _stack,
)


def test_label_and_inbound_are_not_features():
    frame = pd.DataFrame(
        {
            "Unnamed: 0": [0, 1, 2, 3],
            "Flow Duration": [10, 20, 30, 40],
            "Inbound": [0, 1, 1, 0],
            "Class": ["Benign", "Syn", "Syn", "Benign"],
            "Label": ["Benign", "Syn", "Syn", "Benign"],
        }
    )
    extractor = FeatureExtractor()
    features, labels = extractor.preprocess(frame, fit=True)
    assert features.shape == (4, 1)
    assert extractor.feature_names == ["Flow Duration"]
    assert len(np.unique(labels)) == 2


def test_flat_rows_are_not_turned_into_timesteps():
    flat = np.zeros((8, 40), dtype=np.float32)
    try:
        reshape_for_cnn_bilstm(flat, timesteps=10)
    except TemporalLeakError:
        return
    raise AssertionError("flat features were accepted as a time series")


def test_windows_are_real_seconds_and_do_not_cross_the_split():
    seconds = pd.date_range("2018-11-03 09:00:00", periods=40, freq="s")
    frame = pd.DataFrame(
        {
            "Source IP": ["172.16.0.5"] * 40,
            "Timestamp": seconds,
            "Label": ["Syn"] * 40,
            "Flow Duration": np.arange(40, dtype=np.float32),
        }
    )
    built = windows_from_frame(
        frame,
        timeline_id="Syn.csv",
        feature_list=["Flow Duration"],
        labels={"Benign": 0, "Syn": 12},
        timesteps=10,
        stride=10,
    )
    assert len(built) == 4
    starts = [row["start_sec"] for row in built]
    assert starts == sorted(starts)
    assert all(b - a == 10 for a, b in zip(starts, starts[1:]))
    # The value at each second is the second index, so timestep t differs.
    assert not np.allclose(built[0]["X"][0], built[0]["X"][1])

    parts = _time_split(built)
    splits = {name: _stack(rows) for name, rows in parts.items()}
    assert_no_split_leakage(splits, timesteps=10)
    assert len(splits["test"]["X"]) >= 1
    assert int(splits["train"]["start_sec"].max()) < int(splits["test"]["start_sec"].min())

    # A quiet source still contributes ordered seconds. Those seconds are not copied.
    sparse_times = pd.date_range("2018-11-03 10:00:00", periods=10, freq="5s")
    sparse = pd.DataFrame(
        {
            "Source IP": ["192.168.50.8"] * 10,
            "Timestamp": sparse_times,
            "Label": ["Benign"] * 10,
            "Flow Duration": np.arange(10, dtype=np.float32),
        }
    )
    sparse_windows = windows_from_frame(
        sparse,
        timeline_id="BENIGN.csv",
        feature_list=["Flow Duration"],
        labels={"Benign": 0, "Syn": 12},
        timesteps=10,
        stride=10,
    )
    assert len(sparse_windows) == 1
    assert sparse_windows[0]["y"] == 0
    assert np.all(np.diff(sparse_windows[0]["X"][:, 0]) > 0)
