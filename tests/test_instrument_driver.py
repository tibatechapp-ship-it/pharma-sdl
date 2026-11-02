"""اختبارات طبقة الأجهزة — محاكي SCPI ↔ سواقة FRET على TCP حقيقي (P10).

هذه ليست اختبارات mock: خادم TCP فعلي يُستمع، وأوامر SCPI فعلية تُرسَل
ويُقرأ ردها — عقد `InstrumentDriver` يُختبَر طرفاً-إلى-طرف. حواجز
السلامة (رمز الموافقة، حد الساعة) تُختبر كسلوك لا كنيّة.
"""

from __future__ import annotations

import socket
import threading
import time
from datetime import UTC, datetime

import pytest

from pharma_sdl.errors import (
    CalibrationError,
    InstrumentConnectionError,
    InstrumentError,
    SafetyViolation,
    ValidationError,
)
from pharma_sdl.lab.instruments import (
    FRETReaderDriver,
    InstrumentDriver,
    InstrumentReading,
    InstrumentStatus,
    make_instrument_driver,
    reading_to_payload,
)
from tools.fret_simulator import FRETSimulator

_REAL_TOKEN = "approval-gateway-token-001"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def simulator():
    """محاكي SCPI حقيقي على منفذ حر — step_delay=0 لسرعة CI."""
    port = _free_port()
    sim = FRETSimulator(host="127.0.0.1", port=port, noise=0.001, seed=42, step_delay=0.0)
    thread = threading.Thread(target=sim.start, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.05)
    else:
        pytest.fail("المحاكي لم يستمع خلال 5 ثوانٍ")
    yield sim, port
    sim.stop()


@pytest.fixture
def driver(simulator):
    """سواقة متصلة بالمحاكي — تُفصل بعد كل اختبار."""
    _, port = simulator
    drv = FRETReaderDriver(host="127.0.0.1", port=port, instrument_serial="TEST-SN")
    drv.connect()
    yield drv
    drv.disconnect()


# ── الاتصال والحالة ──────────────────────────────────────────────


class TestConnection:
    def test_connect_reports_idle_and_disconnect_cleans(self, simulator):
        _, port = simulator
        drv = FRETReaderDriver(host="127.0.0.1", port=port)
        drv.connect()
        assert drv.get_status() is InstrumentStatus.IDLE
        drv.disconnect()
        assert drv.get_status() is InstrumentStatus.OFFLINE

    def test_connect_to_dead_port_raises_connection_error(self):
        drv = FRETReaderDriver(host="127.0.0.1", port=_free_port(), timeout_seconds=2.0)
        with pytest.raises(InstrumentConnectionError):
            drv.connect()

    def test_command_without_connect_is_explicit_error(self, simulator):
        _, port = simulator
        drv = FRETReaderDriver(host="127.0.0.1", port=port)
        with pytest.raises(InstrumentConnectionError):
            drv._send_command("*IDN?")


# ── إصلاح buffer الاستقبال الدائم (الأجهزة تدفع ردوداً مجمعة) ────


class TestReceiveBuffer:
    def test_pipelined_commands_both_answered_in_order(self, simulator):
        """أمران في حزمة واحدة — الردان يُقرآن بالترتيب بلا فقد."""
        _, port = simulator
        with socket.create_connection(("127.0.0.1", port), timeout=2.0) as sock:
            sock.sendall(b"*IDN?\nSYST:STAT?\n")
            buffer = b""
            deadline = time.monotonic() + 3.0
            while buffer.count(b"\n") < 2 and time.monotonic() < deadline:
                buffer += sock.recv(1024)
        lines = buffer.decode("ascii").strip().splitlines()
        assert lines[0].startswith("PharmaSDL,FRET-SIM")
        assert lines[1] in {"0", "1", "2", "3"}

    def test_driver_read_leftovers_not_lost_between_commands(self, driver):
        """رد متأخر يبقى في الـbuffer — الأمر التالي يقرأ رده هو لا بقايا غيره."""
        first = driver._send_command("*IDN?")
        second = driver._send_command("SYST:STAT?")
        assert first.startswith("PharmaSDL,FRET-SIM")
        assert second in {"0", "1", "2", "3"}


# ── المعايرة ─────────────────────────────────────────────────────


class TestCalibration:
    def test_calibration_returns_curve_hash(self, driver):
        assert driver.calibrate([0.0, 0.1, 0.5, 1.0]) == "sim-cal-7c1f3a9d2b"

    def test_device_back_to_idle_after_calibration(self, driver):
        driver.calibrate([0.0, 1.0])
        assert driver.get_status() is InstrumentStatus.IDLE

    def test_empty_standards_rejected(self, driver):
        with pytest.raises(CalibrationError):
            driver.calibrate([])


# ── القياس ───────────────────────────────────────────────────────


class TestRunAssay:
    def test_assay_returns_signed_simulated_reading(self, driver):
        reading = driver.run_assay("CMP-001", "7VH8_A", "FRET_Mpro_v1", "")
        assert isinstance(reading, InstrumentReading)
        assert reading.simulated is True
        assert reading.approval_token.startswith("SIMULATED-")
        assert reading.instrument_serial == "TEST-SN"

    def test_values_are_physical(self, driver):
        reading = driver.run_assay("CMP-002", "7VH8_A", "FRET_Mpro_v1", "")
        assert 0.0 <= reading.raw_value <= 1.0
        assert 0.0 <= reading.control_positive <= 1.0
        assert 0.0 <= reading.control_negative <= 1.0

    def test_reading_falls_between_controls(self, driver):
        """donor≈0.8 وacceptor≈0.5 ⇒ نسبة ≈0.625 بين الضابطين [0.15, 0.95]."""
        reading = driver.run_assay("CMP-003", "7VH8_A", "FRET_Mpro_v1", "")
        assert reading.verify_against_controls() is True

    def test_content_hash_is_stable_sha256(self, driver):
        reading = driver.run_assay("CMP-004", "7VH8_A", "FRET_Mpro_v1", "")
        assert reading.content_hash() == reading.content_hash()
        assert len(reading.content_hash()) == 64

    def test_to_dict_roundtrip_has_full_identity(self, driver):
        payload = driver.run_assay("CMP-005", "7VH8_A", "FRET_Mpro_v1", "").to_dict()
        for key in ("experiment_id", "instrument_serial", "calibration_curve_hash", "simulated"):
            assert key in payload


# ── حواجز السلامة ────────────────────────────────────────────────


class TestSafety:
    def test_real_device_without_token_is_rejected(self, simulator):
        _, port = simulator
        drv = FRETReaderDriver(host="127.0.0.1", port=port, simulated=False)
        drv.connect()
        try:
            with pytest.raises(SafetyViolation):
                drv.run_assay("CMP-REAL", "7VH8_A", "FRET_Mpro_v1", "")
        finally:
            drv.disconnect()

    def test_real_device_short_token_is_rejected(self, simulator):
        _, port = simulator
        drv = FRETReaderDriver(host="127.0.0.1", port=port, simulated=False)
        drv.connect()
        try:
            with pytest.raises(SafetyViolation):
                drv.run_assay("CMP-REAL", "7VH8_A", "FRET_Mpro_v1", "short")
        finally:
            drv.disconnect()

    def test_real_device_with_valid_token_passes(self, simulator):
        _, port = simulator
        drv = FRETReaderDriver(host="127.0.0.1", port=port, simulated=False)
        drv.connect()
        try:
            reading = drv.run_assay("CMP-REAL", "7VH8_A", "FRET_Mpro_v1", _REAL_TOKEN)
            assert reading.simulated is False
            assert reading.approval_token == _REAL_TOKEN
        finally:
            drv.disconnect()

    def test_hourly_limit_blocks_and_is_explicit(self, driver):
        driver._reads_this_hour = FRETReaderDriver.MAX_PLATE_READS_PER_HOUR
        with pytest.raises(SafetyViolation):
            driver.run_assay("CMP-006", "7VH8_A", "FRET_Mpro_v1", "")


# ── القراءة الصارمة والجسر الصادق ────────────────────────────────


class TestReadingContract:
    def _reading(self, **overrides):
        base = {
            "experiment_id": "EXP-X",
            "compound_id": "CMP-X",
            "target_id": "7VH8_A",
            "instrument_serial": "SN-1",
            "timestamp": datetime.now(UTC),
            "raw_value": 0.65,
            "standard_error": 0.02,
            "control_positive": 0.15,
            "control_negative": 0.95,
            "calibration_curve_hash": "h",
            "operator_id": "op",
            "approval_token": "SIMULATED-abc",
            "simulated": True,
        }
        base.update(overrides)
        return InstrumentReading(**base)

    def test_reading_without_token_rejected(self):
        with pytest.raises(ValidationError):
            self._reading(approval_token="")

    def test_real_reading_with_short_token_rejected_at_dataclass_level(self):
        with pytest.raises(ValidationError):
            self._reading(approval_token="short", simulated=False)

    def test_non_finite_raw_value_rejected(self):
        with pytest.raises(ValidationError):
            self._reading(raw_value=float("nan"))

    def test_payload_bridge_requires_measured_ic50(self):
        with pytest.raises(ValidationError):
            reading_to_payload(self._reading(), smiles="CCO", ic50_um=-3.0)

    def test_payload_bridge_requires_smiles(self):
        with pytest.raises(ValidationError):
            reading_to_payload(self._reading(), smiles="  ", ic50_um=12.0)

    def test_payload_bridge_keeps_truth_about_origin(self):
        """قراءة محاكي ⇒ صف simulated=True — لا تسلل بيانات تدريب إلى الفيزياء."""
        payload = reading_to_payload(self._reading(), smiles="CCO", ic50_um=0.5)
        assert payload["simulated"] is True
        assert payload["ic50_um"] == 0.5
        assert abs(payload["pic50"] - (6.0 - -0.301)) < 0.02  # -log10(0.5e-6)

    def test_payload_bridge_for_real_reading_is_false(self):
        payload = reading_to_payload(
            self._reading(simulated=False, approval_token=_REAL_TOKEN),
            smiles="O=C(N)c1ccccc1",
            ic50_um=12.5,
        )
        assert payload["simulated"] is False
        assert payload["pic50"] == round(-__import__("math").log10(12.5 * 1e-6), 2)


# ── العقد والمصنع ────────────────────────────────────────────────


class TestProtocolAndFactory:
    def test_driver_satisfies_protocol(self, driver):
        assert isinstance(driver, InstrumentDriver)
        assert driver.serial_number == "TEST-SN"
        assert driver.is_simulated is True

    def test_two_simulators_have_independent_state(self):
        """انحلال عيب متغيرات الصنف المشتركة — حالة كل محاكي له وحده."""
        sim_a = FRETSimulator(port=_free_port(), seed=1)
        sim_b = FRETSimulator(port=_free_port(), seed=2)
        sim_a._temperature = 41.5
        sim_a._status_code = "2"
        assert sim_b._temperature == 25.0
        assert sim_b._status_code == "0"

    def test_factory_returns_none_when_unconfigured(self, monkeypatch):
        monkeypatch.delenv("PHARMA_SDL_INSTRUMENT_HOST", raising=False)
        from pharma_sdl.config import Settings

        assert make_instrument_driver(Settings()) is None

    def test_factory_builds_driver_from_settings(self):
        from pharma_sdl.config import Settings

        drv = make_instrument_driver(Settings(instrument_host="10.0.0.8", instrument_port=9000))
        assert drv is not None
        assert drv.host == "10.0.0.8"
        assert drv.port == 9000
        assert drv.is_simulated is True  # الافتراضي الآمن — الحقيقي قرار بشري

    def test_unknown_command_is_explicit_instrument_error(self, driver):
        with pytest.raises(InstrumentError):
            driver._send_command("DO:MAGIC")
