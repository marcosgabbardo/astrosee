"""Tests for the scoring engine."""

import pytest

from astrosee.scoring.engine import ScoringEngine
from astrosee.scoring.components import (
    calculate_temperature_differential_score,
    calculate_wind_stability_score,
    calculate_humidity_score,
    calculate_cloud_cover_score,
    calculate_jet_stream_score,
    calculate_moon_penalty,
    calculate_airmass_penalty,
)
from astrosee.weather.models import WeatherData


class TestScoringComponents:
    """Test individual scoring components."""

    def test_temperature_differential_excellent(self, sample_weather: WeatherData):
        """High temp differential should give high score."""
        # sample_weather has temp=18.5, dew_point=10.0, diff=8.5
        score = calculate_temperature_differential_score(sample_weather)
        assert score >= 70  # Good score for 8.5 degree differential

    def test_temperature_differential_poor(self, poor_weather: WeatherData):
        """Low temp differential should give low score."""
        # poor_weather has temp=15.0, dew_point=14.0, diff=1.0
        score = calculate_temperature_differential_score(poor_weather)
        assert score < 50  # Poor score for 1 degree differential

    def test_wind_stability_calm(self, sample_weather: WeatherData):
        """Calm winds should give high score."""
        score = calculate_wind_stability_score(sample_weather)
        assert score >= 70

    def test_wind_stability_windy(self, poor_weather: WeatherData):
        """High winds should give low score."""
        score = calculate_wind_stability_score(poor_weather)
        assert score < 60

    def test_humidity_dry(self, sample_weather: WeatherData):
        """Low humidity should give high score."""
        score = calculate_humidity_score(sample_weather)
        assert score >= 70

    def test_humidity_wet(self, poor_weather: WeatherData):
        """High humidity should give low score."""
        score = calculate_humidity_score(poor_weather)
        assert score < 30

    def test_cloud_cover_clear(self, sample_weather: WeatherData):
        """Low cloud cover should give high score."""
        score = calculate_cloud_cover_score(sample_weather)
        assert score >= 80

    def test_cloud_cover_cloudy(self, poor_weather: WeatherData):
        """High cloud cover should give low score."""
        score = calculate_cloud_cover_score(poor_weather)
        assert score < 30

    def test_jet_stream_calm(self, sample_weather: WeatherData):
        """Low jet stream should give high score."""
        score = calculate_jet_stream_score(sample_weather)
        assert score >= 80

    def test_jet_stream_strong(self, poor_weather: WeatherData):
        """Strong jet stream should give low score."""
        score = calculate_jet_stream_score(poor_weather)
        assert score < 50


class TestPenalties:
    """Test penalty calculations."""

    def test_moon_penalty_new_moon(self):
        """New moon should have no penalty."""
        penalty = calculate_moon_penalty(
            illumination=0, moon_altitude=45, is_deep_sky=True
        )
        assert penalty == 1.0

    def test_moon_penalty_full_moon_deep_sky(self):
        """Full moon should penalize deep-sky."""
        penalty = calculate_moon_penalty(
            illumination=100, moon_altitude=45, is_deep_sky=True
        )
        assert penalty < 0.7  # Significant penalty

    def test_moon_penalty_full_moon_planet(self):
        """Full moon should not penalize planets."""
        penalty = calculate_moon_penalty(
            illumination=100, moon_altitude=45, is_deep_sky=False
        )
        assert penalty == 1.0

    def test_moon_penalty_below_horizon(self):
        """Moon below horizon should have no penalty."""
        penalty = calculate_moon_penalty(
            illumination=100, moon_altitude=-10, is_deep_sky=True
        )
        assert penalty == 1.0

    def test_airmass_penalty_zenith(self):
        """Object at zenith (airmass 1.0) should have no penalty."""
        penalty = calculate_airmass_penalty(1.0)
        assert penalty == 1.0

    def test_airmass_penalty_low_altitude(self):
        """Object at low altitude should have penalty."""
        penalty = calculate_airmass_penalty(3.0)
        assert penalty < 0.8


class TestScoringEngine:
    """Test the main scoring engine."""

    def test_good_conditions_score(self, sample_weather: WeatherData):
        """Good weather should produce good score."""
        engine = ScoringEngine()
        score = engine.calculate_score(
            sample_weather,
            moon_illumination=10,
            moon_altitude=-10,
        )
        assert score.total_score >= 65
        assert score.rating in ["Good", "Very Good", "Excellent"]

    def test_poor_conditions_score(self, poor_weather: WeatherData):
        """Poor weather should produce poor score."""
        engine = ScoringEngine()
        score = engine.calculate_score(
            poor_weather,
            moon_illumination=90,
            moon_altitude=45,
            is_deep_sky=True,
        )
        assert score.total_score < 40
        assert score.rating in ["Poor", "Bad", "Fair"]

    def test_score_range(self, sample_weather: WeatherData):
        """Score should always be 0-100."""
        engine = ScoringEngine()
        score = engine.calculate_score(sample_weather)
        assert 0 <= score.total_score <= 100

    def test_component_scores_present(self, sample_weather: WeatherData):
        """All component scores should be present."""
        engine = ScoringEngine()
        score = engine.calculate_score(sample_weather)

        assert "temperature_differential" in score.component_scores
        assert "wind_stability" in score.component_scores
        assert "humidity" in score.component_scores
        assert "cloud_cover" in score.component_scores
        assert "jet_stream" in score.component_scores

    def test_recommendations(self, sample_weather: WeatherData):
        """Engine should provide recommendations."""
        engine = ScoringEngine()
        score = engine.calculate_score(sample_weather)
        recommendations = engine.get_recommendations(score, sample_weather)

        assert len(recommendations) > 0
        assert isinstance(recommendations[0], str)

    def test_target_recommendations(self, sample_weather: WeatherData):
        """Engine should provide target type recommendations."""
        engine = ScoringEngine()
        score = engine.calculate_score(sample_weather)
        targets = engine.get_best_targets(score, sample_weather)

        assert "planets" in targets
        assert "moon" in targets
        assert "deep_sky" in targets
        assert "imaging" in targets
