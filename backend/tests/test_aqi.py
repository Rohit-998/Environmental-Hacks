from airday import aqi


def test_station_aqi_is_highest_sub_index():
    assert aqi.station_aqi({"PM2.5": 312, "PM10": 280, "NO2": 60}) == 312


def test_station_aqi_needs_three_pollutants_including_pm():
    assert aqi.station_aqi({"PM2.5": 312, "PM10": 280}) is None
    assert aqi.station_aqi({"NO2": 60, "SO2": 20, "CO": 90}) is None
    assert aqi.station_aqi({"PM2.5": 312, "PM10": None, "NO2": 60, "CO": 40}) == 312


def test_grap_thresholds():
    assert aqi.grap_stage(None) is None
    assert aqi.grap_stage(200) is None
    assert aqi.grap_stage(201) == "I"
    assert aqi.grap_stage(300) == "I"
    assert aqi.grap_stage(301) == "II"
    assert aqi.grap_stage(401) == "III"
    assert aqi.grap_stage(450) == "III"
    assert aqi.grap_stage(451) == "IV"


def test_aqi_band_and_city_average():
    assert aqi.aqi_band(284) == "poor"
    assert aqi.aqi_band(401) == "severe"
    assert aqi.city_average([300, None, 320]) == 310
    assert aqi.city_average([None]) is None
