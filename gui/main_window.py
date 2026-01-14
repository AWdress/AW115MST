"""
GUI主窗口
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QTextEdit,
    QCheckBox, QGroupBox, QProgressBar, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from modules.controller import RapidUploadController


class WorkerThread(QThread):
    """工作线程"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    
    def __init__(self, controller, input_path, target_path, recursive, move_files):
        super().__init__()
        self.controller = controller
        self.input_path = input_path
        self.target_path = target_path
        self.recursive = recursive
        self.move_files = move_files
    
    def run(self):
        """执行任务"""
        try:
            result = self.controller.process_directory(
                input_path=self.input_path,
                target_path=self.target_path,
                recursive=self.recursive,
                move_files=self.move_files
            )
            self.finished.emit(result)
        except Exception as e:
            self.finished.emit({'success': False, 'error': str(e)})


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.controller = None
        self.worker = None
        self.init_ui()
        self.load_controller()
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle('115秒传文件检查与自动移动工具 v1.0.0')
        self.setGeometry(100, 100, 800, 600)
        
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # 标题
        title_label = QLabel('115秒传文件检查与自动移动工具')
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # 输入路径组
        input_group = QGroupBox('输入设置')
        input_layout = QVBoxLayout()
        
        # 输入路径
        input_path_layout = QHBoxLayout()
        input_path_layout.addWidget(QLabel('输入路径:'))
        self.input_path_edit = QLineEdit()
        self.input_path_edit.setPlaceholderText('选择文件或文件夹...')
        input_path_layout.addWidget(self.input_path_edit)
        
        self.browse_file_btn = QPushButton('选择文件')
        self.browse_file_btn.clicked.connect(self.browse_file)
        input_path_layout.addWidget(self.browse_file_btn)
        
        self.browse_folder_btn = QPushButton('选择文件夹')
        self.browse_folder_btn.clicked.connect(self.browse_folder)
        input_path_layout.addWidget(self.browse_folder_btn)
        
        input_layout.addLayout(input_path_layout)
        
        # 递归选项
        self.recursive_checkbox = QCheckBox('递归处理子目录')
        self.recursive_checkbox.setChecked(True)
        input_layout.addWidget(self.recursive_checkbox)
        
        input_group.setLayout(input_layout)
        main_layout.addWidget(input_group)
        
        # 输出路径组
        output_group = QGroupBox('输出设置')
        output_layout = QVBoxLayout()
        
        # 目标路径
        target_path_layout = QHBoxLayout()
        target_path_layout.addWidget(QLabel('目标目录:'))
        self.target_path_edit = QLineEdit()
        self.target_path_edit.setPlaceholderText('可秒传文件的目标目录（留空使用配置文件默认值）')
        target_path_layout.addWidget(self.target_path_edit)
        
        self.browse_target_btn = QPushButton('选择目录')
        self.browse_target_btn.clicked.connect(self.browse_target)
        target_path_layout.addWidget(self.browse_target_btn)
        
        output_layout.addLayout(target_path_layout)
        
        # 移动选项
        self.move_files_checkbox = QCheckBox('移动可秒传文件到目标目录')
        self.move_files_checkbox.setChecked(True)
        output_layout.addWidget(self.move_files_checkbox)
        
        output_group.setLayout(output_layout)
        main_layout.addWidget(output_group)
        
        # 操作按钮
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton('开始处理')
        self.start_btn.clicked.connect(self.start_processing)
        self.start_btn.setStyleSheet('QPushButton { background-color: #4CAF50; color: white; padding: 10px; font-size: 14px; }')
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton('停止')
        self.stop_btn.clicked.connect(self.stop_processing)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet('QPushButton { background-color: #f44336; color: white; padding: 10px; font-size: 14px; }')
        button_layout.addWidget(self.stop_btn)
        
        main_layout.addLayout(button_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # 日志输出
        log_label = QLabel('处理日志:')
        main_layout.addWidget(log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet('QTextEdit { font-family: Consolas, monospace; }')
        main_layout.addWidget(self.log_text)
        
        # 状态栏
        self.statusBar().showMessage('就绪')
    
    def load_controller(self):
        """加载控制器"""
        try:
            self.controller = RapidUploadController('config/config.yaml')
            self.log('控制器加载成功')
            
            # 检查登录状态
            if self.controller.check_login():
                self.log('115登录状态: 正常')
            else:
                self.log('警告: 115登录失败，请检查cookies配置', 'warning')
                
        except Exception as e:
            self.log(f'错误: 加载控制器失败 - {str(e)}', 'error')
            QMessageBox.critical(self, '错误', f'加载控制器失败:\n{str(e)}')
    
    def browse_file(self):
        """选择文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, '选择文件', '', 'All Files (*.*)'
        )
        if file_path:
            self.input_path_edit.setText(file_path)
    
    def browse_folder(self):
        """选择文件夹"""
        folder_path = QFileDialog.getExistingDirectory(
            self, '选择文件夹'
        )
        if folder_path:
            self.input_path_edit.setText(folder_path)
    
    def browse_target(self):
        """选择目标目录"""
        folder_path = QFileDialog.getExistingDirectory(
            self, '选择目标目录'
        )
        if folder_path:
            self.target_path_edit.setText(folder_path)
    
    def log(self, message: str, level: str = 'info'):
        """添加日志"""
        colors = {
            'info': 'black',
            'success': 'green',
            'warning': 'orange',
            'error': 'red',
        }
        color = colors.get(level, 'black')
        self.log_text.append(f'<span style="color: {color};">{message}</span>')
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
    
    def start_processing(self):
        """开始处理"""
        # 验证输入
        input_path = self.input_path_edit.text().strip()
        if not input_path:
            QMessageBox.warning(self, '警告', '请选择输入路径')
            return
        
        if not Path(input_path).exists():
            QMessageBox.warning(self, '警告', '输入路径不存在')
            return
        
        # 获取参数
        target_path = self.target_path_edit.text().strip() or None
        recursive = self.recursive_checkbox.isChecked()
        move_files = self.move_files_checkbox.isChecked()
        
        # 清空日志
        self.log_text.clear()
        self.log('=' * 60)
        self.log('开始处理...')
        self.log(f'输入路径: {input_path}')
        if target_path:
            self.log(f'目标目录: {target_path}')
        self.log(f'递归处理: {"是" if recursive else "否"}')
        self.log(f'移动文件: {"是" if move_files else "否"}')
        self.log('=' * 60)
        
        # 禁用按钮
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 不确定进度
        
        # 创建工作线程
        self.worker = WorkerThread(
            self.controller, input_path, target_path, recursive, move_files
        )
        self.worker.finished.connect(self.on_processing_finished)
        self.worker.start()
        
        self.statusBar().showMessage('处理中...')
    
    def stop_processing(self):
        """停止处理"""
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
            self.log('处理已停止', 'warning')
            self.on_processing_finished({'success': False, 'error': '用户中断'})
    
    def on_processing_finished(self, result: dict):
        """处理完成"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        
        if result.get('success'):
            self.log('=' * 60, 'success')
            self.log('处理完成！', 'success')
            self.log(f"总文件数: {result.get('total', 0)}", 'success')
            self.log(f"可秒传: {result.get('rapid_count', 0)} 个", 'success')
            self.log(f"不可秒传: {result.get('non_rapid_count', 0)} 个", 'warning')
            self.log(f"失败: {result.get('failed_count', 0)} 个", 'error')
            self.log(f"已移动: {result.get('moved_count', 0)} 个", 'success')
            self.log('=' * 60, 'success')
            
            self.statusBar().showMessage('处理完成')
            QMessageBox.information(self, '完成', '文件处理完成！')
        else:
            error_msg = result.get('error', '未知错误')
            self.log(f'处理失败: {error_msg}', 'error')
            self.statusBar().showMessage('处理失败')
            QMessageBox.critical(self, '错误', f'处理失败:\n{error_msg}')


def run_gui():
    """运行GUI"""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    run_gui()
