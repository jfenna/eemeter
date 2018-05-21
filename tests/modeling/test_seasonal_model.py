import tempfile
from datetime import datetime

import pytest
import pandas as pd
import numpy as np
from numpy.testing import assert_allclose
import pytz

from eemeter.modeling.formatters import ModelDataFormatter
from eemeter.structures import EnergyTrace
from eemeter.modeling.models import SeasonalElasticNetCVModel
from eemeter.weather import WeatherSource


def _fake_temps(usaf_id, start, end, normalized, use_cz2010):
    # sinusoidal fake temperatures in degC
    dates = pd.date_range(start, end, freq='H', tz=pytz.UTC)
    num_years = end.year - start.year + 1
    n = dates.shape[0]
    avg_temp = 15
    temp_range = 15
    period_offset = - (2 * np.pi / 3)
    temp_offsets = np.sin(
        (2 * np.pi * num_years * np.arange(n) / n) + period_offset)
    temps = avg_temp + (temp_range * temp_offsets)
    return pd.Series(temps, index=dates, dtype=float)


@pytest.fixture
def monkeypatch_temperature_data(monkeypatch):
    monkeypatch.setattr(
        'eemeter.weather.eeweather_wrapper._get_temperature_data_eeweather',
        _fake_temps
    )


@pytest.fixture
def mock_isd_weather_source():
    ws = WeatherSource('722880', False, False)
    return ws


@pytest.fixture
def daily_trace():
    data = {
        "value": np.tile(1, (365,)),
        "estimated": np.tile(False, (365,)),
    }
    columns = ["value", "estimated"]
    index = pd.date_range('2000-01-01', periods=365, freq='D', tz=pytz.UTC)
    df = pd.DataFrame(data, index=index, columns=columns)
    return EnergyTrace("ELECTRICITY_CONSUMPTION_SUPPLIED", df, unit="KWH")


@pytest.fixture
def input_df(monkeypatch_temperature_data, daily_trace,
    mock_isd_weather_source):
    mdf = ModelDataFormatter("D")
    return mdf.create_input(daily_trace, mock_isd_weather_source)


def test_basic(input_df):
    m = SeasonalElasticNetCVModel(65, 65)
    assert str(m).startswith("SeasonalElasticNetCVModel(")
    assert m.cooling_base_temp == 65
    assert m.heating_base_temp == 65
    assert m.n_bootstrap == 100
    assert m.n is None
    assert m.params is None
    assert m.r2 is None
    assert m.rmse is None
    assert m.y is None

    output = m.fit(input_df)

    assert "r2" in output
    assert "rmse" in output
    assert "cvrmse" in output
    assert "model_params" in output
    assert "upper" in output
    assert "lower" in output
    assert "n" in output

    assert m.n == 365
    assert 'formula' in m.params
    assert 'X_design_info' in m.params
    assert 'intercept' in m.params
    assert 'coefficients' in m.params
    assert m.r2 == 0.0
    assert_allclose(m.rmse, 0.024082522582335276, rtol=1e-5, atol=1e-5)
    assert m.y.shape == (365, 1)

    predict, variance = m.predict(input_df, summed=False)

    assert predict.shape == (365,)
    assert_allclose(predict[datetime(2000, 1, 1, tzinfo=pytz.UTC)], 1.003148368585324)
    assert variance > 0

    assert m.n == 365
    assert 'formula' in m.params
    assert 'X_design_info' in m.params
    assert 'intercept' in m.params
    assert 'coefficients' in m.params
    assert m.r2 == 0.0
    assert_allclose(m.rmse, 0.024082522582335276, rtol=1e-5, atol=1e-5)
    assert m.y.shape == (365, 1)

    # predict w/ error bootstrapping
    predict, variance = m.predict(input_df)

    assert_allclose(predict, 361.2063769041264)
    assert variance > 0
