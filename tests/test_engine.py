import re
from unittest.mock import patch, MagicMock, PropertyMock
from io import StringIO

import pytest

from engine import ShogiEngine, EngineError, INFO_PATTERN, MATE_SCORE


class TestParseInfoCp:
  def test_parse_info_cp(self):
    line = "info depth 20 seldepth 30 multipv 1 score cp 450 nodes 1234567 nps 500000 pv 7g7f 8c8d 2g2f"
    match = INFO_PATTERN.search(line)
    assert match is not None
    multipv, score_type, score_val, pv = match.groups()
    assert score_type == "cp"
    assert score_val == "450"
    assert multipv == "1"
    assert pv == "7g7f 8c8d 2g2f"

  def test_parse_info_cp_negative(self):
    line = "info depth 15 seldepth 20 multipv 2 score cp -120 nodes 1000000 nps 400000 pv 2g2f 8c8d"
    match = INFO_PATTERN.search(line)
    assert match is not None
    _, score_type, score_val, _ = match.groups()
    assert score_type == "cp"
    assert score_val == "-120"


class TestParseInfoMate:
  def test_parse_info_mate_positive(self):
    line = "info depth 20 seldepth 5 multipv 1 score mate 5 nodes 100 nps 1000 pv 7g7f 8c8d 2g2f"
    match = INFO_PATTERN.search(line)
    assert match is not None
    _, score_type, score_val, _ = match.groups()
    assert score_type == "mate"
    assert int(score_val) > 0

  def test_parse_info_mate_negative(self):
    line = "info depth 20 seldepth 5 multipv 1 score mate -3 nodes 100 nps 1000 pv 7g7f 8c8d"
    match = INFO_PATTERN.search(line)
    assert match is not None
    _, score_type, score_val, _ = match.groups()
    assert score_type == "mate"
    assert int(score_val) < 0


def _make_engine_output(lines: list[str]) -> str:
  return "\n".join(lines) + "\n"


def _mock_popen(stdout_lines: list[str]):
  """Create a mock Popen that returns given stdout lines."""
  mock_proc = MagicMock()
  mock_proc.stdin = MagicMock()

  stdout_iter = iter([line + "\n" for line in stdout_lines] + [""])
  mock_proc.stdout.readline.side_effect = lambda: next(stdout_iter)
  mock_proc.wait.return_value = 0

  return mock_proc


class TestParseMultipv:
  def test_parse_multipv(self):
    engine = ShogiEngine("/dummy/path")
    lines = [
      "info depth 20 seldepth 30 multipv 2 score cp 420 nodes 100 nps 1000 pv 2g2f 8c8d 7g7f",
      "info depth 20 seldepth 28 multipv 3 score cp 380 nodes 100 nps 1000 pv 5i6h 8c8d 7g7f",
      "info depth 20 seldepth 32 multipv 1 score cp 450 nodes 100 nps 1000 pv 7g7f 8c8d 2g2f",
      "bestmove 7g7f",
    ]

    mock_proc = _mock_popen(lines)
    engine._proc = mock_proc

    candidates = engine.analyze(
      "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1",
      3000,
    )

    assert len(candidates) == 3
    assert candidates[0]["rank"] == 1
    assert candidates[1]["rank"] == 2
    assert candidates[2]["rank"] == 3
    assert candidates[0]["score"] == 450
    assert candidates[1]["score"] == 420
    assert candidates[2]["score"] == 380


class TestEngineStartAndQuit:
  @patch("engine.subprocess.Popen")
  def test_engine_start_and_quit(self, mock_popen_cls):
    usi_lines = [
      "id name YaneuraOu",
      "usiok",
    ]
    ready_lines = [
      "readyok",
    ]
    all_lines = usi_lines + ready_lines

    mock_proc = _mock_popen(all_lines)
    mock_popen_cls.return_value = mock_proc

    engine = ShogiEngine("/dummy/path")
    engine.start()

    # Verify USI initialization commands were sent
    calls = [
      call.args[0] if call.args else call.kwargs
      for call in mock_proc.stdin.write.call_args_list
    ]
    sent_commands = [c.strip() for c in calls if isinstance(c, str)]
    assert "usi" in sent_commands
    assert "setoption name MultiPV value 3" in sent_commands
    assert "isready" in sent_commands

    engine.quit()
    # Verify quit was sent
    quit_calls = [
      c.strip() for c in
      [call.args[0] if call.args else "" for call in mock_proc.stdin.write.call_args_list]
      if isinstance(c, str)
    ]
    assert "quit" in quit_calls


class TestAnalyzeSuccess:
  def test_analyze_success(self):
    engine = ShogiEngine("/dummy/path")

    lines = [
      "info depth 10 seldepth 15 multipv 1 score cp 300 nodes 50000 nps 500000 pv 7g7f 8c8d",
      "info depth 10 seldepth 14 multipv 2 score cp 280 nodes 50000 nps 500000 pv 2g2f 3c3d",
      "info depth 10 seldepth 13 multipv 3 score cp 250 nodes 50000 nps 500000 pv 5i6h 5a4b",
      "bestmove 7g7f",
    ]
    mock_proc = _mock_popen(lines)
    engine._proc = mock_proc

    candidates = engine.analyze(
      "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1",
      3000,
    )

    assert len(candidates) == 3
    assert candidates[0]["pv"] == "7g7f 8c8d"
    assert candidates[0]["score"] == 300

  def test_analyze_with_mate(self):
    engine = ShogiEngine("/dummy/path")

    lines = [
      "info depth 20 seldepth 5 multipv 1 score mate 5 nodes 100 nps 1000 pv 7g7f 8c8d 2g2f",
      "info depth 20 seldepth 10 multipv 2 score cp 200 nodes 100 nps 1000 pv 2g2f 3c3d",
      "info depth 20 seldepth 8 multipv 3 score mate -3 nodes 100 nps 1000 pv 5i6h 5a4b",
      "bestmove 7g7f",
    ]
    mock_proc = _mock_popen(lines)
    engine._proc = mock_proc

    candidates = engine.analyze(
      "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1",
      3000,
    )

    assert candidates[0]["score"] == MATE_SCORE
    assert candidates[1]["score"] == 200
    assert candidates[2]["score"] == -MATE_SCORE


class TestAnalyzeTimeout:
  def test_analyze_timeout(self):
    import time as time_mod

    engine = ShogiEngine("/dummy/path")

    # Mock proc where readline blocks until killed
    mock_proc = MagicMock()
    mock_proc.stdin = MagicMock()

    def blocking_readline():
      # Simulate blocking read - sleep longer than timeout
      time_mod.sleep(1)
      return ""

    mock_proc.stdout.readline.side_effect = blocking_readline
    mock_proc.kill.return_value = None
    mock_proc.wait.return_value = 0
    engine._proc = mock_proc

    # Directly call _read_until with a very short timeout to speed up the test
    with pytest.raises(EngineError, match="timed out"):
      engine._send("go movetime 100")
      engine._read_until("bestmove", timeout=0.1)


class TestEngineStartupFailure:
  @patch("engine.subprocess.Popen")
  def test_engine_startup_failure(self, mock_popen_cls):
    mock_popen_cls.side_effect = FileNotFoundError("No such file")

    engine = ShogiEngine("/nonexistent/path")
    with pytest.raises(EngineError, match="Engine startup failed"):
      engine.start()
