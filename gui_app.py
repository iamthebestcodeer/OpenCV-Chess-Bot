import os
import json
import sys
from typing import List, Optional
from PySide6 import QtCore, QtGui, QtWidgets

WORKSPACE_ROOT = os.path.dirname(os.path.abspath(__file__))
BOT_SCRIPT = os.path.join(WORKSPACE_ROOT, "bot-offline.py")
SETTINGS_FILE = os.path.join(WORKSPACE_ROOT, ".gui_settings.json")


class LogViewer(QtWidgets.QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setWordWrapMode(QtGui.QTextOption.NoWrap)
        self.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        font = QtGui.QFont("Fira Code, Consolas, Monospace")
        font.setStyleHint(QtGui.QFont.Monospace)
        font.setPointSize(10)
        self.setFont(font)

    def append_text(self, text: str):
        self.moveCursor(QtGui.QTextCursor.End)
        self.insertPlainText(text)
        self.moveCursor(QtGui.QTextCursor.End)


class Header(QtWidgets.QFrame):
    def __init__(self, title: str, subtitle: str = ""):
        super().__init__()
        self.setObjectName("Header")
        layout = QtWidgets.QVBoxLayout(self)
        title_lbl = QtWidgets.QLabel(title)
        title_lbl.setObjectName("HeaderTitle")
        subtitle_lbl = QtWidgets.QLabel(subtitle)
        subtitle_lbl.setObjectName("HeaderSubtitle")
        layout.addWidget(title_lbl)
        if subtitle:
            layout.addWidget(subtitle_lbl)
        layout.addStretch(1)


class LabeledField(QtWidgets.QWidget):
    def __init__(self, label: str, field: QtWidgets.QWidget, stretch: int = 0):
        super().__init__()
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        lbl = QtWidgets.QLabel(label)
        lbl.setMinimumWidth(140)
        layout.addWidget(lbl)
        layout.addWidget(field, stretch)


class EngineMode:
    TIME_PER_MOVE = "Time per move"
    DEPTH = "Depth"
    CLASSICAL = "Classical 40/X"


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenCV Chess Bot - GUI")
        self.setMinimumSize(1120, 720)
        self.process: Optional[QtCore.QProcess] = None

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(12)

        root.addWidget(Header("OpenCV Chess Bot", "Configure and launch the offline bot with ease"))

        content = QtWidgets.QSplitter()
        content.setOrientation(QtCore.Qt.Horizontal)
        root.addWidget(content, 1)

        # Left panel: controls
        self.controls = QtWidgets.QWidget()
        controls_layout = QtWidgets.QVBoxLayout(self.controls)
        controls_layout.setSpacing(10)

        # Engine settings
        engine_group = QtWidgets.QGroupBox("Engine")
        eg_l = QtWidgets.QVBoxLayout(engine_group)
        self.engine_path = QtWidgets.QLineEdit()
        self.engine_browse = QtWidgets.QPushButton("Browse…")
        self.engine_browse.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DirOpenIcon))
        hb = QtWidgets.QHBoxLayout()
        hb.addWidget(self.engine_path, 1)
        hb.addWidget(self.engine_browse)
        eg_l.addLayout(hb)
        self.spin_threads = QtWidgets.QSpinBox()
        self.spin_threads.setRange(1, 64)
        self.spin_threads.setValue(1)
        eg_l.addWidget(LabeledField("Threads", self.spin_threads))
        self.spin_hash = QtWidgets.QSpinBox()
        self.spin_hash.setRange(16, 4096)
        self.spin_hash.setValue(128)
        self.spin_hash.setSingleStep(16)
        eg_l.addWidget(LabeledField("Hash (MB)", self.spin_hash))
        controls_layout.addWidget(engine_group)

        # Play settings
        play_group = QtWidgets.QGroupBox("Play Settings")
        pg_l = QtWidgets.QVBoxLayout(play_group)

        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems([EngineMode.TIME_PER_MOVE, EngineMode.DEPTH, EngineMode.CLASSICAL])
        pg_l.addWidget(LabeledField("Mode", self.mode_combo))

        self.spin_depth = QtWidgets.QSpinBox()
        self.spin_depth.setRange(1, 99)
        self.spin_depth.setValue(12)
        pg_l.addWidget(LabeledField("Depth", self.spin_depth))

        self.spin_time = QtWidgets.QDoubleSpinBox()
        self.spin_time.setRange(0.01, 60.0)
        self.spin_time.setDecimals(2)
        self.spin_time.setSingleStep(0.05)
        self.spin_time.setValue(2.0)
        pg_l.addWidget(LabeledField("Time per move (s)", self.spin_time))

        tc_row = QtWidgets.QHBoxLayout()
        self.spin_tc_value = QtWidgets.QDoubleSpinBox()
        self.spin_tc_value.setRange(1, 1_000_000)
        self.spin_tc_value.setValue(300.0)
        self.tc_unit_combo = QtWidgets.QComboBox()
        self.tc_unit_combo.addItems(["s", "m", "h", "ms"])  # seconds, minutes, hours, milliseconds
        tc_row.addWidget(QtWidgets.QLabel("40/"))
        tc_row.addWidget(self.spin_tc_value, 1)
        tc_row.addWidget(self.tc_unit_combo)
        tc_row_w = QtWidgets.QWidget()
        tc_row_w.setLayout(tc_row)
        pg_l.addWidget(LabeledField("Classical", tc_row_w))

        controls_layout.addWidget(play_group)

        # Timing window
        timing_group = QtWidgets.QGroupBox("Human-like Timing")
        tg_l = QtWidgets.QVBoxLayout(timing_group)
        self.timing_mode = QtWidgets.QComboBox()
        self.timing_mode.addItems(["Off", "delay", "engine", "both"])  # maps later
        tg_l.addWidget(LabeledField("Timing mode", self.timing_mode))
        self.timing_min = QtWidgets.QDoubleSpinBox()
        self.timing_min.setRange(0.0, 120.0)
        self.timing_min.setDecimals(2)
        self.timing_min.setValue(0.5)
        self.timing_max = QtWidgets.QDoubleSpinBox()
        self.timing_max.setRange(0.0, 120.0)
        self.timing_max.setDecimals(2)
        self.timing_max.setValue(1.5)
        tg_l.addWidget(LabeledField("Min (s)", self.timing_min))
        tg_l.addWidget(LabeledField("Max (s)", self.timing_max))
        controls_layout.addWidget(timing_group)

        # Actions
        action_row = QtWidgets.QHBoxLayout()
        self.btn_start = QtWidgets.QPushButton("Start")
        self.btn_start.setObjectName("PrimaryButton")
        self.btn_stop = QtWidgets.QPushButton("Stop")
        self.btn_stop.setEnabled(False)
        self.btn_clear = QtWidgets.QPushButton("Clear Log")
        action_row.addWidget(self.btn_start)
        action_row.addWidget(self.btn_stop)
        action_row.addStretch(1)
        action_row.addWidget(self.btn_clear)
        controls_layout.addLayout(action_row)

        controls_layout.addStretch(1)

        # Right panel: log viewer
        right_panel = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_panel)
        right_layout.setSpacing(8)
        self.status_label = QtWidgets.QLabel("Idle")
        self.status_label.setObjectName("StatusLabel")
        self.log = LogViewer()
        right_layout.addWidget(self.status_label)
        right_layout.addWidget(self.log, 1)

        content.addWidget(self.controls)
        content.addWidget(right_panel)
        content.setStretchFactor(0, 0)
        content.setStretchFactor(1, 1)

        # Wire up
        self.engine_browse.clicked.connect(self.on_browse_engine)
        self.btn_start.clicked.connect(self.on_start)
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_clear.clicked.connect(lambda: self.log.setPlainText(""))
        self.mode_combo.currentIndexChanged.connect(self.update_mode_visibility)
        self.timing_mode.currentIndexChanged.connect(self.update_timing_visibility)

        self.update_mode_visibility()
        self.update_timing_visibility()
        self.apply_style()
        self.load_settings()

    def apply_style(self):
        self.setStyleSheet(
            """
            QMainWindow { background: #0f1117; }
            QWidget { color: #e6e6e6; font-size: 14px; }
            QGroupBox { border: 1px solid #23262e; border-radius: 8px; margin-top: 12px; padding: 6px 8px 8px 8px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0px 3px; color: #93c5fd; }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit { background: #111827; border: 1px solid #23262e; border-radius: 6px; padding: 5px 6px; }
            QPushButton { background: #1f2937; border: 1px solid #374151; border-radius: 8px; padding: 8px 12px; color: #e5e7eb; }
            QPushButton:hover { background: #273244; }
            QPushButton#PrimaryButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #60a5fa, stop:1 #34d399); border: none; color: #051014; font-weight: 600; }
            QPushButton#PrimaryButton:hover { filter: brightness(1.1); }
            QLabel#HeaderTitle { font-size: 22px; font-weight: 700; color: #e5e7eb; }
            QLabel#HeaderSubtitle { font-size: 13px; color: #9ca3af; }
            QLabel#StatusLabel { color: #9ca3af; font-style: italic; }
            QSplitter::handle { background: #1f2937; width: 6px; }
            QHeaderView::section { background: #111827; }
            """
        )

    def update_mode_visibility(self):
        mode = self.mode_combo.currentText()
        is_depth = mode == EngineMode.DEPTH
        is_time = mode == EngineMode.TIME_PER_MOVE
        is_classical = mode == EngineMode.CLASSICAL
        self.spin_depth.parentWidget().setVisible(True)
        self.spin_time.parentWidget().setVisible(True)
        # Depth relevant
        self.spin_depth.setEnabled(is_depth)
        # Time-per-move relevant
        self.spin_time.setEnabled(is_time)
        # Classical row visibility
        self.spin_tc_value.parentWidget().parentWidget().setEnabled(is_classical)
        self.spin_tc_value.parentWidget().parentWidget().setVisible(is_classical)

    def update_timing_visibility(self):
        mode = self.timing_mode.currentText()
        on = mode != "Off"
        self.timing_min.setEnabled(on)
        self.timing_max.setEnabled(on)

    def on_browse_engine(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select UCI engine (stockfish)")
        if path:
            self.engine_path.setText(path)

    def build_args(self) -> List[str]:
        args: List[str] = [BOT_SCRIPT]
        # Engine settings
        if self.engine_path.text().strip():
            args += ["--engine-path", self.engine_path.text().strip()]
        args += ["--threads", str(self.spin_threads.value())]
        args += ["--hash", str(self.spin_hash.value())]

        mode = self.mode_combo.currentText()
        if mode == EngineMode.DEPTH:
            args += ["--depth-mode", "--depth", str(self.spin_depth.value())]
        elif mode == EngineMode.TIME_PER_MOVE:
            # Emulate per-move time using timing engine mode with fixed window
            t = self.spin_time.value()
            args += ["--timing-mode", "engine", "--timing-min", f"{t}", "--timing-max", f"{t}"]
        elif mode == EngineMode.CLASSICAL:
            val = self.spin_tc_value.value()
            unit = self.tc_unit_combo.currentText()
            args += ["--tc", f"40/{val}{unit}"]

        # Optional human-like timing overlay
        tm = self.timing_mode.currentText()
        if tm != "Off":
            args += ["--timing-mode", tm, "--timing-min", f"{self.timing_min.value()}", "--timing-max", f"{self.timing_max.value()}"]

        return args

    def set_running(self, running: bool):
        self.controls.setEnabled(not running)
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.status_label.setText("Running" if running else "Idle")

    def on_start(self):
        if not os.path.exists(BOT_SCRIPT):
            QtWidgets.QMessageBox.critical(self, "Error", f"Cannot find script: {BOT_SCRIPT}")
            return
        args = self.build_args()
        self.log.append_text("$ python3 " + " ".join(map(self._shell_quote, args)) + "\n")
        self.process = QtCore.QProcess(self)
        self.process.setProgram(sys.executable)
        self.process.setArguments(args)
        self.process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.on_ready_read)
        self.process.readyReadStandardError.connect(self.on_ready_read)
        self.process.finished.connect(self.on_finished)
        self.process.errorOccurred.connect(self.on_error)
        self.process.start()
        self.set_running(True)
        self.save_settings()

    def on_stop(self):
        if self.process and self.process.state() != QtCore.QProcess.NotRunning:
            self.process.terminate()
            if not self.process.waitForFinished(2000):
                self.process.kill()
        self.set_running(False)

    def on_ready_read(self):
        if not self.process:
            return
        data = bytes(self.process.readAllStandardOutput()).decode(errors="ignore")
        if data:
            self.log.append_text(data)

    def on_finished(self):
        self.log.append_text("\n[process finished]\n")
        self.set_running(False)

    def on_error(self, err: QtCore.QProcess.ProcessError):
        self.log.append_text(f"\n[error] {err}\n")
        self.set_running(False)

    def _shell_quote(self, s: str) -> str:
        if " " in s or "\t" in s:
            return f'"{s}"'
        return s

    def load_settings(self):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return
        self.engine_path.setText(data.get("engine_path", ""))
        self.spin_threads.setValue(int(data.get("threads", 1)))
        self.spin_hash.setValue(int(data.get("hash", 128)))
        self.mode_combo.setCurrentText(data.get("mode", EngineMode.TIME_PER_MOVE))
        self.spin_depth.setValue(int(data.get("depth", 12)))
        self.spin_time.setValue(float(data.get("time_per_move", 2.0)))
        self.spin_tc_value.setValue(float(data.get("classical_value", 300.0)))
        self.tc_unit_combo.setCurrentText(data.get("classical_unit", "s"))
        self.timing_mode.setCurrentText(data.get("timing_mode", "Off"))
        self.timing_min.setValue(float(data.get("timing_min", 0.5)))
        self.timing_max.setValue(float(data.get("timing_max", 1.5)))

    def save_settings(self):
        data = dict(
            engine_path=self.engine_path.text().strip(),
            threads=self.spin_threads.value(),
            hash=self.spin_hash.value(),
            mode=self.mode_combo.currentText(),
            depth=self.spin_depth.value(),
            time_per_move=self.spin_time.value(),
            classical_value=self.spin_tc_value.value(),
            classical_unit=self.tc_unit_combo.currentText(),
            timing_mode=self.timing_mode.currentText(),
            timing_min=self.timing_min.value(),
            timing_max=self.timing_max.value(),
        )
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def closeEvent(self, e: QtGui.QCloseEvent) -> None:
        try:
            self.save_settings()
        finally:
            return super().closeEvent(e)


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("OpenCV Chess Bot GUI")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()