import sys
import os
import subprocess
import ctypes
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget, QMessageBox, \
    QTextEdit, QDialog
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

def is_admin():
    """检查是否以管理员身份运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """以管理员身份重新运行程序"""
    if not is_admin():
        try:
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
            sys.exit(0)
        except Exception as e:
            QMessageBox.critical(None, "错误", f"无法提升权限: {str(e)}")
            sys.exit(1)

class CleanerThread(QThread):
    """清理任务的线程，发送终端输出"""
    output_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(float)  # 释放的空间（MB），-1 表示无空间计算

    def __init__(self, commands, calculate_space=False):
        super().__init__()
        self.commands = commands
        self.calculate_space = calculate_space
        self.free_space_before = 0

    def run(self):
        try:
            if self.calculate_space:
                self.free_space_before = self.get_free_space()

            for cmd in self.commands:
                try:
                    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                    while process.poll() is None:
                        line = process.stdout.readline().strip()
                        if line:
                            self.output_signal.emit(line)
                    # 获取最后几行输出
                    for line in process.stdout.readlines():
                        if line.strip():
                            self.output_signal.emit(line.strip())
                except Exception as e:
                    self.output_signal.emit(f"执行命令 '{cmd}' 出错: {str(e)}")

            freed_mb = -1
            if self.calculate_space:
                free_space_after = self.get_free_space()
                freed_mb = (free_space_after - self.free_space_before) / (1024 * 1024) if free_space_after >= 0 else -1

            self.finished_signal.emit(freed_mb)
        except Exception as e:
            self.output_signal.emit(f"清理过程中发生错误: {str(e)}")
            self.finished_signal.emit(-1)

    def get_free_space(self):
        """获取系统盘可用空间（字节），使用更可靠的方法"""
        try:
            # 使用 shutil.disk_usage 或 ctypes 获取可用空间，避免 dir 命令的语言依赖
            drive = os.environ["systemdrive"].rstrip("\\")
            free_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                ctypes.c_wchar_p(drive),
                None,
                None,
                ctypes.byref(free_bytes)
            )
            return free_bytes.value
        except Exception as e:
            self.output_signal.emit(f"获取磁盘空间失败: {str(e)}")
            return -1


class ProcessDialog(QDialog):
    """显示清理过程的对话框"""

    def __init__(self, parent, title, commands, calculate_space=False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setGeometry(150, 150, 600, 400)
        self.setStyleSheet("background-color: #ffffff;")

        # 布局
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 标题
        self.title_label = QLabel(title)
        self.title_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("color: #333; margin-bottom: 10px;")
        layout.addWidget(self.title_label)

        # 终端输出区域
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Consolas", 10))
        self.output_text.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ddd; padding: 5px;")
        layout.addWidget(self.output_text)

        # 在线程启动前立即显示提示
        self.append_output("正在进行清理，请稍等......")

        # 线程
        self.thread = CleanerThread(commands, calculate_space)
        self.thread.output_signal.connect(self.append_output)
        self.thread.finished_signal.connect(self.on_finished)
        self.thread.start()

    def append_output(self, text):
        """追加终端输出"""
        self.output_text.append(text)

    def on_finished(self, freed_mb):
        """清理完成"""
        if freed_mb >= 0:
            self.output_text.append(f"\n清理完成，释放空间约 {freed_mb:.2f} MB")
        else:
            self.output_text.append("\n清理完成！")
        self.accept()  # 关闭对话框


class DiskCleanerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("系统深度清理工具")
        self.setGeometry(100, 100, 500, 400)
        self.setStyleSheet("background-color: #f5f5f5;")  # 浅灰背景

        # 主布局
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setAlignment(Qt.AlignTop)
        self.layout.setSpacing(15)

        # 标题
        self.title_label = QLabel("系统深度清理工具")
        self.title_label.setFont(QFont("Arial", 20, QFont.Bold))
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("color: #333; margin-bottom: 20px;")
        self.layout.addWidget(self.title_label)

        # 创建清理按钮
        self.create_button("清理临时文件、缓存和日志", self.clean_temp, "#4CAF50")
        self.create_button("执行系统组件深度清理", self.clean_components, "#2196F3")
        self.create_button("删除旧的系统还原点", self.clean_shadows, "#FF5722")  # 修复颜色代码中的乱码
        self.create_button("清空回收站", self.clean_recyclebin, "#9C27B0")
        self.create_button("清理用户下载文件夹", self.clean_downloads, "#F44336")

    def create_button(self, text, callback, color):
        """创建美观的按钮"""
        btn = QPushButton(text)
        btn.setFont(QFont("Arial", 12))
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                padding: 10px;
                border-radius: 5px;
                margin: 5px 50px;
            }}
            QPushButton:hover {{
                background-color: {self.lighten_color(color)};
            }}
            QPushButton:disabled {{
                background-color: #cccccc;
            }}
        """)
        btn.clicked.connect(callback)
        self.layout.addWidget(btn)
        return btn

    def lighten_color(self, hex_color):
        """将颜色变浅，用于 hover 效果"""
        color = int(hex_color[1:], 16)
        r = min((color >> 16) + 50, 255)
        g = min(((color >> 8) & 0xFF) + 50, 255)
        b = min((color & 0xFF) + 50, 255)
        return f"#{r:02x}{g:02x}{b:02x}"

    def clean_temp(self):
        if QMessageBox.question(self, "确认", "是否清理临时文件、缓存和日志？",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            commands = [
                "del /f /s /q %systemdrive%\\*.tmp",
                "del /f /s /q %systemdrive%\\*._mp",
                "del /f /s /q %systemdrive%\\*.log",
                "del /f /s /q %systemdrive%\\*.gid",
                "del /f /s /q %systemdrive%\\*.chk",
                "del /f /s /q %systemdrive%\\*.old",
                "del /f /s /q %systemdrive%\\recycled\\*.*",
                "del /f /s /q %windir%\\*.bak",
                "del /f /s /q %windir%\\prefetch\\*.*",
                "rd /s /q %windir%\\temp & md %windir%\\temp",
                "del /f /q %userprofile%\\cookies\\*.*",
                "del /f /q %userprofile%\\recent\\*.*",
                "del /f /s /q \"%userprofile%\\Local Settings\\Temporary Internet Files\\*.*\"",
                "del /f /s /q \"%userprofile%\\Local Settings\\Temp\\*.*\""
            ]
            dialog = ProcessDialog(self, "清理临时文件", commands, calculate_space=True)
            dialog.exec_()

    def clean_components(self):
        if QMessageBox.question(self, "确认", "是否执行系统组件深度清理？",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            commands = [
                "Dism /Online /Cleanup-Image /StartComponentCleanup",
                "Dism /Online /Cleanup-Image /AnalyzeComponentStore"
            ]
            dialog = ProcessDialog(self, "清理系统组件", commands, calculate_space=True)
            dialog.exec_()

    def clean_shadows(self):
        if QMessageBox.question(self, "确认", "是否删除旧的系统还原点？",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            if QMessageBox.question(self, "再次确认", "此操作将删除所有还原点，确认执行吗？",
                                    QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                commands = ["vssadmin delete shadows /all /quiet"]
                dialog = ProcessDialog(self, "删除系统还原点", commands)
                dialog.exec_()

    def clean_recyclebin(self):
        if QMessageBox.question(self, "确认", "是否清空回收站？", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            commands = ["powershell -Command \"Clear-RecycleBin -Force\""]
            dialog = ProcessDialog(self, "清空回收站", commands)
            dialog.exec_()

    def clean_downloads(self):
        if QMessageBox.question(self, "确认", "是否清理用户下载文件夹？",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            if QMessageBox.question(self, "再次确认", "此操作将删除所有下载文件，确认执行吗？",
                                    QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                commands = ["del /f /s /q %userprofile%\\Downloads\\*.*"]
                dialog = ProcessDialog(self, "清理下载文件夹", commands)
                dialog.exec_()


if __name__ == "__main__":
    if not is_admin():
        run_as_admin()
    app = QApplication(sys.argv)
    window = DiskCleanerWindow()
    window.show()
    sys.exit(app.exec_())