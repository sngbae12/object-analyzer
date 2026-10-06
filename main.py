"""이미지 크기/컬러 조정 앱 진입점."""

import os
import sys
import traceback


def _prepare_path() -> None:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    if os.getcwd() not in sys.path:
        sys.path.insert(0, os.getcwd())


def _setup_qt_env() -> None:
    """현재 Python(가상환경) 기준으로 PyQt5 플러그인 경로를 잡는다."""
    py_ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
    candidates = [
        os.path.join(sys.prefix, "Lib", "site-packages", "PyQt5", "Qt5"),
        os.path.join(sys.prefix, "lib", "site-packages", "PyQt5", "Qt5"),
        os.path.join(sys.prefix, "lib", py_ver, "site-packages", "PyQt5", "Qt5"),
    ]
    for qt_root in candidates:
        bin_dir = os.path.join(qt_root, "bin")
        plugins = os.path.join(qt_root, "plugins")
        if os.path.isdir(bin_dir):
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
        if os.path.isdir(plugins):
            os.environ["QT_PLUGIN_PATH"] = plugins
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(plugins, "platforms")
            break
    os.environ.pop("QT_QPA_PLATFORM", None)


def main() -> None:
    _prepare_path()
    _setup_qt_env()

    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("이미지 크기 · 컬러 조정")

    from main_window import MainWindow

    window = MainWindow()
    window.show()
    window.raise_()
    window.activateWindow()
    sys.exit(app.exec_())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        detail = traceback.format_exc()
        print(detail, file=sys.stderr)
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "실행오류.txt")
        with open(log_path, "w", encoding="utf-8") as file:
            file.write(detail)
        try:
            from PyQt5.QtWidgets import QApplication, QMessageBox

            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, "실행 오류", detail)
        except Exception:
            pass
        sys.exit(1)
