import re
import subprocess
import threading
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

INFO_PATTERN = re.compile(
  r"multipv (\d+).*score (cp|mate) (-?\d+).*pv (.+)"
)

MATE_SCORE = 30000


class EngineError(Exception):
  """Raised when the engine encounters an error."""


class ShogiEngine:
  """YaneuraOu engine wrapper using USI protocol."""

  def __init__(self, engine_path: str, multipv: int = 3):
    self._engine_path = engine_path
    self._multipv = multipv
    self._proc: subprocess.Popen | None = None

  def start(self) -> None:
    """Start the engine process and initialize via USI protocol."""
    try:
      self._proc = subprocess.Popen(
        [self._engine_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd="/var/task/Engine",
      )
    except (FileNotFoundError, PermissionError) as e:
      raise EngineError("Engine startup failed") from e

    self._send("usi")
    self._read_until("usiok")
    self._send(f"setoption name MultiPV value {self._multipv}")
    self._send("isready")
    self._read_until("readyok")

  def analyze(self, sfen: str, movetime: int) -> list[dict]:
    """Analyze a position and return candidates."""
    self._send(f"position sfen {sfen}")
    self._send(f"go movetime {movetime}")

    timeout_sec = (movetime + 5000) / 1000
    lines = self._read_until("bestmove", timeout=timeout_sec)

    candidates: dict[int, dict] = {}
    for line in lines:
      match = INFO_PATTERN.search(line)
      if match:
        multipv, score_type, score_val, pv = match.groups()
        rank = int(multipv)
        if score_type == "mate":
          score = MATE_SCORE if int(score_val) > 0 else -MATE_SCORE
        else:
          score = int(score_val)
        candidates[rank] = {"rank": rank, "score": score, "pv": pv}

    return sorted(candidates.values(), key=lambda c: c["rank"])

  def quit(self) -> None:
    """Terminate the engine process."""
    if self._proc is None:
      return
    try:
      self._send("quit")
      self._proc.wait(timeout=5)
    except (subprocess.TimeoutExpired, OSError):
      self._proc.kill()
      self._proc.wait()
    finally:
      self._proc = None

  def _send(self, command: str) -> None:
    logger.info(f">>> {command}")
    self._proc.stdin.write(command + "\n")
    self._proc.stdin.flush()

  def _read_until(self, stopword: str, timeout: float = 30) -> list[str]:
    lines: list[str] = []
    timed_out = threading.Event()

    def _timeout_handler():
      timed_out.set()
      if self._proc:
        self._proc.kill()

    timer = threading.Timer(timeout, _timeout_handler)
    timer.start()
    try:
      while True:
        if timed_out.is_set():
          raise EngineError("Engine process timed out")
        line = self._proc.stdout.readline()
        if not line:
          break
        line = line.strip()
        if line:
          logger.info(line)
          lines.append(line)
        if stopword in line:
          break
    finally:
      timer.cancel()

    if timed_out.is_set():
      raise EngineError("Engine process timed out")

    return lines
