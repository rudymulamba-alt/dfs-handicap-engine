"""
Tests for the run-date resolution logic in main.py.

No network calls are made; no real credentials are required.
"""

import os
from datetime import date as _date
from unittest.mock import patch

import pytest

from main import resolve_run_date


class TestResolvRunDate:
    def test_cli_date_takes_highest_precedence(self, monkeypatch):
        monkeypatch.setenv("MODEL_DATE", "2026-01-01")
        assert resolve_run_date("2026-08-20") == "2026-08-20"

    def test_env_var_used_when_no_cli_date(self, monkeypatch):
        monkeypatch.setenv("MODEL_DATE", "2026-08-20")
        assert resolve_run_date() == "2026-08-20"

    def test_env_var_ignored_when_cli_date_provided(self, monkeypatch):
        monkeypatch.setenv("MODEL_DATE", "2026-01-01")
        assert resolve_run_date("2026-09-01") == "2026-09-01"

    def test_falls_back_to_today_when_neither_set(self, monkeypatch):
        monkeypatch.delenv("MODEL_DATE", raising=False)
        today = _date.today().strftime("%Y-%m-%d")
        assert resolve_run_date() == today

    def test_env_var_whitespace_stripped(self, monkeypatch):
        monkeypatch.setenv("MODEL_DATE", "  2026-08-20  ")
        assert resolve_run_date() == "2026-08-20"

    def test_empty_env_var_falls_back_to_today(self, monkeypatch):
        monkeypatch.setenv("MODEL_DATE", "")
        today = _date.today().strftime("%Y-%m-%d")
        assert resolve_run_date() == today

    def test_invalid_cli_date_raises_value_error(self, monkeypatch):
        monkeypatch.delenv("MODEL_DATE", raising=False)
        with pytest.raises(ValueError):
            resolve_run_date("not-a-date")

    def test_invalid_env_var_raises_value_error(self, monkeypatch):
        monkeypatch.setenv("MODEL_DATE", "20260820")  # missing hyphens
        with pytest.raises(ValueError):
            resolve_run_date()

    def test_returns_string(self, monkeypatch):
        monkeypatch.delenv("MODEL_DATE", raising=False)
        result = resolve_run_date("2026-08-20")
        assert isinstance(result, str)

    def test_format_is_yyyy_mm_dd(self, monkeypatch):
        monkeypatch.delenv("MODEL_DATE", raising=False)
        result = resolve_run_date("2026-08-20")
        parts = result.split("-")
        assert len(parts) == 3
        assert len(parts[0]) == 4  # year
        assert len(parts[1]) == 2  # month
        assert len(parts[2]) == 2  # day
