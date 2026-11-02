"""سواقة قارئ FRET — SCPI عبر TCP: المحاكي اليوم، والجهاز الحقيقي غداً.

نفس الكود يقود الاثنين؛ الفرق الوحيد علم `simulated`:

- محاكي (`tools/fret_simulator.py`) ⇒ قراءات `simulated=True` برمز
  تتبع `SIMULATED-…` تلقائي — التمرين الميداني بلا عتاد.
- جهاز حقيقي (Tecan/BMG/PerkinElmer أو أي مستجيب لـSCPI) ⇒
  `simulated=False` ورمز موافقة بشرية إلزامي (≥ 16 حرفاً) — وبدونه
  `SafetyViolation` رفض صريح لا تحذير يُتجاهل.

تفاصيل النقل المهمة: **buffer استقبال دائم على مستوى الاتصال** —
الأجهزة الحقيقية قد تدفع عدة ردود في حزمة شبكية واحدة، وكود يرمي
البقايا بعد أول سطر يفسد جلسة القياس كلها بهدوء. هنا تُحفظ البقايا
وتُقرأ بالترتيب.
"""

from __future__ import annotations

import logging
import os
import socket
import time
import uuid
from datetime import UTC, datetime

from pharma_sdl.errors import (
    CalibrationError,
    InstrumentConnectionError,
    InstrumentError,
    SafetyViolation,
)
from pharma_sdl.lab.instruments.base import InstrumentReading, InstrumentStatus

logger = logging.getLogger(__name__)

_STATUS_BY_CODE = {
    "0": InstrumentStatus.IDLE,
    "1": InstrumentStatus.BUSY,
    "2": InstrumentStatus.ERROR,
    "3": InstrumentStatus.CALIBRATING,
}


class FRETReaderDriver:
    """سواقة قارئ FRET عبر SCPI-over-TCP — تنفّذ عقد `InstrumentDriver`.

    الاستخدام الميداني:
        driver = FRETReaderDriver(host="192.168.1.50", simulated=False)
        driver.connect()
        reading = driver.run_assay(
            compound_id="CMP-042", target_id="7VH8_A",
            protocol_name="FRET_Mpro_v1",
            approval_token=approval_gateway_token,  # بشري إلزامي
        )
    """

    #: حد قراءات الصفائح بالساعة — حماية مورد فيزيائي نادر من الاستهلاك الأعمى.
    MAX_PLATE_READS_PER_HOUR: int = 10
    #: σ المعلنة لبروتوكول القياس (تُستبدل بتكرارات حقيقية n≥3 لاحقاً).
    DECLARED_NOISE_SD: float = 0.02
    #: مهلة انتظار عودة الجهاز إلى الخمول.
    IDLE_TIMEOUT_S: float = 120.0
    #: سماحية استقرار الحرارة حول الهدف.
    TEMP_TOLERANCE_C: float = 0.5

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 10001,
        instrument_serial: str = "FRET-SIM-001",
        timeout_seconds: float = 30.0,
        simulated: bool = True,
        poll_interval_s: float = 0.2,
    ) -> None:
        self.host = host
        self.port = port
        self._serial = instrument_serial
        self.timeout_seconds = timeout_seconds
        self._simulated = bool(simulated)
        self.poll_interval_s = poll_interval_s
        self._socket: socket.socket | None = None
        self._rx_buffer = b""
        self._reads_this_hour = 0
        self._hour_started_at = datetime.now(UTC)

    # ── هوية السواقة (عقد InstrumentDriver) ──────────────────────

    @property
    def serial_number(self) -> str:
        return self._serial

    @property
    def is_simulated(self) -> bool:
        return self._simulated

    # ── دورة الحياة ──────────────────────────────────────────────

    def connect(self) -> None:
        """فتح TCP والتحقق من هوية الجهاز عبر `*IDN?`.

        Raises:
            InstrumentConnectionError: فشل الاتصال أو صمت الجهاز.
        """
        if self._socket is not None:
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout_seconds)
        try:
            sock.connect((self.host, self.port))
        except OSError as exc:
            sock.close()
            raise InstrumentConnectionError(
                f"فشل الاتصال بالجهاز {self.host}:{self.port} — {exc}",
                f"Cannot connect to instrument {self.host}:{self.port} — {exc}",
            ) from exc
        self._socket = sock
        self._rx_buffer = b""
        try:
            identity = self._send_command("*IDN?")
        except InstrumentError:
            self.disconnect()
            raise
        logger.info("متصل بالجهاز: %s", identity)

    def disconnect(self) -> None:
        """إغلاق الاتصال وتفريغ buffer الاستقبال."""
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None
        self._rx_buffer = b""

    def get_status(self) -> InstrumentStatus:
        """حالة الجهاز — بلا اتصال ⇒ OFFLINE، وفشل الاستطلاع ⇒ OFFLINE."""
        if self._socket is None:
            return InstrumentStatus.OFFLINE
        try:
            raw = self._send_command("SYST:STAT?").strip()
        except InstrumentError:
            return InstrumentStatus.OFFLINE
        return _STATUS_BY_CODE.get(raw, InstrumentStatus.OFFLINE)

    # ── المعايرة والقياس ─────────────────────────────────────────

    def calibrate(self, standards: list[float]) -> str:
        """معايرة بمعايير معلومة — يعيد بصمة منحنى المعايرة للقراءات.

        Raises:
            InstrumentError: الجهاز ليس في حالة خمول.
            CalibrationError: لا معايير ممررة — معايرة بلا معايير ليست معايرة.
        """
        if not standards:
            raise CalibrationError(
                "المعايرة تتطلب معايير معلومة — القائمة الفارغة رفض",
                "Calibration requires known standards — empty list rejected",
            )
        if self.get_status() is not InstrumentStatus.IDLE:
            raise InstrumentError(
                "الجهاز ليس في حالة خمول — لا معايرة على جهاز مشغول",
                "Instrument is not idle — cannot calibrate a busy device",
            )
        for i, value in enumerate(standards):
            self._send_command(f"CAL:STD {i},{float(value):.6f}")
        self._send_command("CAL:START")
        self._wait_for_idle()
        return self._send_command("CAL:HASH?").strip()

    def run_assay(
        self,
        compound_id: str,
        target_id: str,
        protocol_name: str,
        approval_token: str,
    ) -> InstrumentReading:
        """قياس FRET كامل ببروتوكول معلن — قراءة موقّعة أو فشل صريح.

        Raises:
            SafetyViolation: رمز موافقة غير ملائم أو تجاوز حد الساعة.
            InstrumentError: الجهاز مشغول أو قارئ المتبرع صفر (خلل بصريات).
        """
        token = self._verify_approval(approval_token)
        self._check_usage_limits()
        if self.get_status() is not InstrumentStatus.IDLE:
            raise InstrumentError(
                "الجهاز مشغول — لا قياس متزامن على جهاز واحد",
                "Instrument is busy — no concurrent assays on one device",
            )

        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        experiment_id = f"EXP-{stamp}-{compound_id[:8]}-{target_id[:8]}"

        self._send_command(f"PLATE:LOAD {experiment_id}")
        self._send_command("TEMP:SET 37.0")
        self._wait_for_temperature(37.0)
        self._send_command("MEAS:START 485,520,580,3")
        self._wait_for_idle()

        donor = float(self._send_command("MEAS:DATA? 520"))
        acceptor = float(self._send_command("MEAS:DATA? 580"))
        if donor <= 1e-9:
            raise InstrumentError(
                "قراءة المتبرع صفر/سالبة — خلل بصريات أو صفيحة فارغة؛ لا نسبة تُحسب",
                "Donor channel reads zero/negative — optics fault or empty well; no ratio",
            )
        control_pos = float(self._send_command("MEAS:CTRL? POS"))
        control_neg = float(self._send_command("MEAS:CTRL? NEG"))
        calibration_hash = self._send_command("CAL:HASH?").strip()

        self._reads_this_hour += 1
        return InstrumentReading(
            experiment_id=experiment_id,
            compound_id=compound_id,
            target_id=target_id,
            instrument_serial=self._serial,
            timestamp=datetime.now(UTC),
            raw_value=acceptor / donor,
            standard_error=self.DECLARED_NOISE_SD,
            control_positive=control_pos,
            control_negative=control_neg,
            calibration_curve_hash=calibration_hash,
            operator_id=os.environ.get("LAB_OPERATOR_ID", "bench-operator"),
            approval_token=token,
            protocol_name=protocol_name,
            simulated=self._simulated,
        )

    # ── أدوات النقل الداخلية ─────────────────────────────────────

    def _send_command(self, command: str) -> str:
        """إرسال أمر SCPI وقراءة سطر الرد — والبقايا تبقى في الـbuffer.

        الأجهزة الحقيقية قد تدفع `OK\\nREADY\\n` في حزمة واحدة؛ رمي
        البقايا بعد أول سطر يفقد الرد التالي بهدوء ويفسد الجلسة.
        """
        if self._socket is None:
            raise InstrumentConnectionError(
                "الجهاز غير متصل — نادِ connect() أولًا",
                "Instrument not connected — call connect() first",
            )
        try:
            self._socket.sendall(f"{command}\n".encode("ascii"))
        except OSError as exc:
            raise InstrumentConnectionError(
                f"فشل إرسال «{command}» — {exc}",
                f"Failed to send “{command}” — {exc}",
            ) from exc
        while b"\n" not in self._rx_buffer:
            try:
                chunk = self._socket.recv(4096)
            except OSError as exc:
                self.disconnect()
                raise InstrumentConnectionError(
                    f"انقطع الاتصال أثناء انتظار رد «{command}» — {exc}",
                    f"Connection lost while awaiting “{command}” — {exc}",
                ) from exc
            if not chunk:
                self.disconnect()
                raise InstrumentConnectionError(
                    "أغلق الجهاز الاتصال دون رد",
                    "Instrument closed the connection without a response",
                )
            self._rx_buffer += chunk
        line, self._rx_buffer = self._rx_buffer.split(b"\n", 1)
        response = line.decode("ascii", errors="replace").strip()
        if response.startswith("ERROR"):
            raise InstrumentError(
                f"الجهاز رفض «{command}»: {response}",
                f"Instrument rejected “{command}”: {response}",
            )
        return response

    def _wait_for_idle(self) -> None:
        """انتظار عودة الجهاز إلى الخمول حتى مهلة IDLE_TIMEOUT_S."""
        deadline = time.monotonic() + self.IDLE_TIMEOUT_S
        while time.monotonic() < deadline:
            if self.get_status() is InstrumentStatus.IDLE:
                return
            time.sleep(self.poll_interval_s)
        raise InstrumentError(
            "انتهت المهلة بانتظار خمول الجهاز",
            "Timed out waiting for the instrument to go idle",
        )

    def _wait_for_temperature(self, target: float) -> None:
        """انتظار استقرار الحرارة حول الهدف ضمن السماحية."""
        for _ in range(120):
            try:
                current = float(self._send_command("TEMP:MEAS?"))
            except ValueError as exc:
                raise InstrumentError(
                    f"قراءة حرارة غير رقمية من الجهاز — {exc}",
                    f"Non-numeric temperature reading — {exc}",
                ) from exc
            if abs(current - target) <= self.TEMP_TOLERANCE_C:
                return
            time.sleep(self.poll_interval_s)
        raise InstrumentError(
            f"الحرارة لم تستقر حول {target}°C",
            f"Temperature never stabilized near {target}°C",
        )

    def _check_usage_limits(self) -> None:
        """حد الاستخدام بالساعة — تجاوزه رفض صريح يحمي الجهاز."""
        now = datetime.now(UTC)
        if (now - self._hour_started_at).total_seconds() >= 3600:
            self._reads_this_hour = 0
            self._hour_started_at = now
        if self._reads_this_hour >= self.MAX_PLATE_READS_PER_HOUR:
            raise SafetyViolation(
                f"تجاوز حد القياسات ({self.MAX_PLATE_READS_PER_HOUR}/ساعة) — "
                "انتظر النافذة التالية؛ الجهاز الفيزيائي ليس مجانياً",
                f"Hourly assay limit reached ({self.MAX_PLATE_READS_PER_HOUR}/h) — "
                "wait for the next window",
            )

    def _verify_approval(self, approval_token: str) -> str:
        """انضباط الموافقة: محاكاة ⇒ رمز تتبع تلقائي؛ حقيقي ⇒ بشري إلزامي."""
        if self._simulated:
            return approval_token or f"SIMULATED-{uuid.uuid4().hex}"
        if not approval_token or len(approval_token) < 16:
            raise SafetyViolation(
                "القياس على جهاز حقيقي يتطلب رمز موافقة بشرية "
                "(≥ 16 حرفاً) من بوابة الاعتماد — لا قياس بلا إذن موثق",
                "Real-instrument assays require a human approval token "
                "(≥ 16 chars) — no measurement without documented consent",
            )
        return approval_token


def main() -> int:
    """جلسة ميدانية دنيا: قراءة واحدة من الجهاز المضبوط بيئياً — تشخيص سريع."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    driver = FRETReaderDriver(
        host=os.environ.get("PHARMA_SDL_INSTRUMENT_HOST", "127.0.0.1"),
        port=int(os.environ.get("PHARMA_SDL_INSTRUMENT_PORT", "10001")),
        simulated=os.environ.get("PHARMA_SDL_INSTRUMENT_SIMULATED", "true").lower()
        in {"1", "true", "yes", "on"},
    )
    driver.connect()
    try:
        reading = driver.run_assay(
            compound_id="BENCH-CHECK",
            target_id="7VH8_A",
            protocol_name="FRET_Mpro_v1",
            approval_token="",  # المحاكاة تولّد SIMULATED-…؛ الحقيقي يرفض
        )
    finally:
        driver.disconnect()
    import json

    print(json.dumps(reading.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover — أداة تشخيص ميدانية
    raise SystemExit(main())
