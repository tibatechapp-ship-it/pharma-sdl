"""محاكي جهاز FRET — خادم SCPI عبر TCP: عتاد الوهم لاختبار جهة الميدان.

يستعمل في:
- تطوير واختبار `FRETReaderDriver` بلا جهاز حقيقي (CI included).
- تدريب المشغلين على بروتوكول الجلسة الميدانية قبل الدمج.
- قياس زمن الاستجابة لطبقة النقل (من المتوقع < 2 ثانية للقياس الكامل).

⚠️ صدقه معلن: كل قراءة تخرج من سواقة موصولة بهذا المحاكي تحمل
`simulated=True` — بيانات المحاكي لا تعبر إلى مسار الفيزياء أبداً
(عقد ADR-0013 يرفضها من جهة العميل، و`MeasurementIngestor` يرفضها
من جهة الذاكرة).

تشغيل: `pharma-sdl simulator --port 10001` أو
`python -m tools.fret_simulator --port 10001`.
"""

from __future__ import annotations

import argparse
import logging
import random
import socket
import threading
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fret_simulator")

_IDENTITY = "PharmaSDL,FRET-SIM,SN-SIM-001,1.0.0"
_CALIBRATION_HASH = "sim-cal-7c1f3a9d2b"

#: أوامر القراءة المقبولة → القيمة الأساس المحاكاة (قناة المتبرع/المستقبل).
_READING_BASES = {"MEAS:DATA? 520": 0.80, "MEAS:DATA? 580": 0.50}
_CONTROL_BASES = {"MEAS:CTRL? POS": 0.15, "MEAS:CTRL? NEG": 0.95}


class FRETSimulator:
    """محاكي جهاز FRET — يستمع على TCP ويجيب على مجموعة SCPI شائعة.

    كل حالة الجهاز (الحالة، الحرارة، المعايرة) **على مستوى الكائن** —
    نسختان من المحاكي مستقلتان تماماً (كانت سابقاً على مستوى الصنف
    فتسربت الحالة بين الجلسات — عيب مُصلَح ومُختبَر).
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 10001,
        noise: float = 0.02,
        seed: int | None = None,
        step_delay: float = 0.3,
    ) -> None:
        self.host = host
        self.port = port
        self.noise = max(0.0, noise)
        self.step_delay = max(0.0, step_delay)
        self._rng = random.Random(seed)
        # حالة الجهاز — لكل كائن حالته (لا متغيرات صنف مشتركة أبداً)
        self._status_code = "0"  # 0=idle 1=busy 2=error 3=calibrating
        self._temperature = 25.0
        self._calibrated = False
        self._server_socket: socket.socket | None = None
        self._running = False
        self._lock = threading.Lock()

    # ── دورة الحياة ──────────────────────────────────────────────

    def start(self) -> None:
        """بدء الاستماع (حاجب) — خيط لكل عميل."""
        self._running = True
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen(5)
        self._server_socket = server
        logger.info("محاكي FRET يستمع على %s:%d (noise=%.3f)", self.host, self.port, self.noise)
        try:
            while self._running:
                try:
                    conn, addr = server.accept()
                except OSError:
                    break
                logger.info("اتصال من %s:%d", addr[0], addr[1])
                threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()
        finally:
            self.stop()

    def stop(self) -> None:
        """إيقاف المحاكي وإغلاق المنصت."""
        self._running = False
        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except OSError:
                pass
            self._server_socket = None

    # ── معالجة العميل ────────────────────────────────────────────

    def _handle_client(self, conn: socket.socket) -> None:
        """جلسة عميل واحدة — أسطر مفصولة بـ\\n، ورد لكل سطر."""
        buffer = b""
        try:
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    command = line.decode("ascii", errors="replace").strip()
                    if not command:
                        continue
                    try:
                        with self._lock:
                            response = self._process_command(command)
                    except Exception as exc:
                        logger.exception("فشل معالجة الأمر: %s", command)
                        response = f"ERROR: {exc}"
                    conn.sendall(f"{response}\n".encode("ascii"))
        except OSError as exc:
            logger.warning("انقطع اتصال عميل: %s", exc)
        finally:
            try:
                conn.close()
            except OSError:
                pass

    # ── بروتوكول SCPI المحاكى ────────────────────────────────────

    def _process_command(self, command: str) -> str:
        """أمر واحد → رد سطر واحد (أو ERROR: …)."""
        upper = command.upper()

        if upper == "*IDN?":
            return _IDENTITY
        if upper == "SYST:STAT?":
            return self._status_code
        if upper == "TEMP:MEAS?":
            return f"{self._temperature:.2f}"
        if upper.startswith("TEMP:SET "):
            try:
                value = float(command.split(None, 1)[1])
            except (IndexError, ValueError):
                return "ERROR: invalid temperature"
            if not 0.0 <= value <= 99.0:
                return "ERROR: temperature out of range"
            self._temperature = value
            return "OK"
        if upper.startswith("PLATE:LOAD"):
            return self._busy_step()
        if upper.startswith("MEAS:START"):
            return self._busy_step()
        if upper in _READING_BASES:
            return self._gaussian(_READING_BASES[upper], self.noise)
        if upper in _CONTROL_BASES:
            return self._gaussian(_CONTROL_BASES[upper], 0.005)
        if upper == "CAL:START":
            if not self._calibrated:
                self._status_code = "3"
                time.sleep(self.step_delay)
                self._status_code = "0"
                self._calibrated = True
            return "OK"
        if upper == "CAL:HASH?":
            return _CALIBRATION_HASH
        if upper == "CAL:DATA?":
            return "sim-cal-curve-v1"
        if upper.startswith("CAL:STD "):
            return "OK"
        return f"ERROR: unknown command '{command}'"

    def _busy_step(self) -> str:
        """محاكاة خطوة ميكانيكية: مشغول → مهلة → خمول."""
        self._status_code = "1"
        time.sleep(self.step_delay)
        self._status_code = "0"
        return "OK"

    def _gaussian(self, base: float, sigma: float) -> str:
        """قراءة ضوضائية حول قيمة أساس، مقصوصة على النطاق الفيزيائي [0,1]."""
        value = base + self._rng.gauss(0.0, sigma)
        return f"{max(0.0, min(1.0, value)):.6f}"


def main() -> None:
    parser = argparse.ArgumentParser(description="محاكي جهاز FRET — SCPI عبر TCP")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=10001)
    parser.add_argument("--noise", type=float, default=0.02)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--step-delay", type=float, default=0.3)
    args = parser.parse_args()
    simulator = FRETSimulator(
        host=args.host,
        port=args.port,
        noise=args.noise,
        seed=args.seed,
        step_delay=args.step_delay,
    )
    try:
        simulator.start()
    except KeyboardInterrupt:
        logger.info("إيقاف المحاكي")
        simulator.stop()


if __name__ == "__main__":  # pragma: no cover — أداة سطر أوامر
    main()
