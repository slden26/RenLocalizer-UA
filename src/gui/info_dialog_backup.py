"""
Info Dialog
==========

Multi-page information dialog with detailed help content.
"""

try:
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
        QTextEdit, QDialogButtonBox, QLabel, QScrollArea
    )
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont
except ImportError:
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
        QTextEdit, QDialogButtonBox, QLabel, QScrollArea
    )
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont

from src.utils.config import ConfigManager

class InfoDialog(QDialog):
    """Multi-page information dialog."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = ConfigManager()
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface."""
        # Get dialog data from JSON
        dialog_data = self.config_manager.get_ui_text("info_dialog")
        
        if isinstance(dialog_data, str):
            # Fallback if info_dialog data is not available
            self.setWindowTitle("Info")
            self.create_simple_dialog()
            return
        
        self.setWindowTitle(dialog_data.get("title", "Info"))
        self.setModal(True)
        self.resize(800, 650)  # Increased width and height
        
        layout = QVBoxLayout(self)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.create_formats_tab(dialog_data)
        self.create_performance_tab(dialog_data)
        self.create_features_tab(dialog_data)
        self.create_troubleshooting_tab(dialog_data)
        
        # Add close button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)
    
    def create_simple_dialog(self):
        """Create simple dialog if JSON data is not available."""
        layout = QVBoxLayout(self)
        
        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml("<h3>Info</h3><p>Information dialog is loading...</p>")
        layout.addWidget(text)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)
    
    def create_formats_tab(self, dialog_data):
        """Create output formats information tab."""
        formats_data = dialog_data.get("formats", {})
        tab_title = dialog_data.get("tabs", {}).get("formats", "Formats")
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Create text widget without scroll area (QTextEdit has its own scrolling)
        text_widget = QTextEdit()
        text_widget.setReadOnly(True)
        
        # Build HTML content with better formatting
        html_content = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.4;">
        <h2 style="color: #2c5282; margin-bottom: 15px;">{formats_data.get('title', 'Translation File Formats')}</h2>
        <p style="margin-bottom: 20px; color: #4a5568;">{formats_data.get('description', '')}</p>
        
        <div style="border: 2px solid #3182ce; border-radius: 8px; padding: 15px; margin-bottom: 20px; background-color: #ebf8ff;">
        <h3 style="color: #2b6cb0; margin-top: 0;">{formats_data.get('simple', {}).get('title', 'SIMPLE Format')}</h3>
        <p><b>Özellikler:</b></p>
        <ul style="margin-left: 20px;">
        """
        
        for feature in formats_data.get('simple', {}).get('features', []):
            html_content += f"<li style='margin-bottom: 5px;'>{feature}</li>"
        
        html_content += f"""
        </ul>
        <p><b>Örnek:</b></p>
        <pre style="background-color: #f7fafc; padding: 10px; border-radius: 5px; border: 1px solid #cbd5e0; font-family: 'Courier New', monospace; font-size: 12px; overflow-x: auto; white-space: pre-wrap;">
{formats_data.get('simple', {}).get('example', '')}
        </pre>
        <p><b>Önerilen:</b> <i>{formats_data.get('simple', {}).get('recommended_for', '')}</i></p>
        </div>
        
        <div style="border: 2px solid #38a169; border-radius: 8px; padding: 15px; margin-bottom: 20px; background-color: #f0fff4;">
        <h3 style="color: #2f855a; margin-top: 0;">{formats_data.get('old_new', {}).get('title', 'OLD_NEW Format')}</h3>
        <p><b>Özellikler:</b></p>
        <ul style="margin-left: 20px;">
        """
        
        for feature in formats_data.get('old_new', {}).get('features', []):
            html_content += f"<li style='margin-bottom: 5px;'>{feature}</li>"
        
        html_content += f"""
        </ul>
        <p><b>Örnek:</b></p>
        <pre style="background-color: #f7fafc; padding: 10px; border-radius: 5px; border: 1px solid #cbd5e0; font-family: 'Courier New', monospace; font-size: 12px; overflow-x: auto; white-space: pre-wrap;">
{formats_data.get('old_new', {}).get('example', '')}
        </pre>
        <p><b>Önerilen:</b> <i>{formats_data.get('old_new', {}).get('recommended_for', '')}</i></p>
        </div>
        
        <hr style="margin: 20px 0; border: 1px solid #e2e8f0;">
        <div style="background-color: #fffbeb; padding: 15px; border-radius: 8px; border-left: 4px solid #f6ad55;">
        <p><b>💡 Not:</b> {formats_data.get('note', '')}</p>
        <p><b>⚙️ Ayar:</b> <i>{formats_data.get('change_setting', '')}</i></p>
        </div>
        </div>
        """
        
        text_widget.setHtml(html_content)
        layout.addWidget(text_widget)
        
        self.tab_widget.addTab(widget, tab_title)
    
    def create_performance_tab(self, dialog_data):
        """Create performance settings information tab."""
        perf_data = dialog_data.get("performance", {})
        tab_title = dialog_data.get("tabs", {}).get("performance", "Performance")
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        text_widget = QTextEdit()
        text_widget.setReadOnly(True)
        text_widget.setWordWrapMode(text_widget.WordWrapMode.WidgetWidth)
        
        # Build HTML content with better formatting
        html_content = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.4;">
        <h2 style="color: #2c5282; margin-bottom: 15px;">{perf_data.get('title', 'Performance Settings')}</h2>
        <p style="margin-bottom: 20px; color: #4a5568;">{perf_data.get('description', '')}</p>
        """
        
        # Parser Workers
        parser_data = perf_data.get('parser_workers', {})
        html_content += f"""
        <div style="border: 2px solid #9f7aea; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #faf5ff;">
        <h3 style="color: #7c3aed; margin-top: 0;">🚀 {parser_data.get('title', 'Parser Workers')}</h3>
        <p>{parser_data.get('description', '')}</p>
        <p><b>İdeal Ayarlar:</b></p>
        <ul style="margin-left: 20px;">
        """
        for setting in parser_data.get('ideal_settings', []):
            html_content += f"<li style='margin-bottom: 5px;'>{setting}</li>"
        html_content += f"</ul><p style='background-color: #f3e8ff; padding: 8px; border-radius: 4px;'><i>💡 {parser_data.get('note', '')}</i></p></div>"
        
        # Concurrent Threads
        threads_data = perf_data.get('concurrent_threads', {})
        html_content += f"""
        <div style="border: 2px solid #f56565; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #fed7d7;">
        <h3 style="color: #e53e3e; margin-top: 0;">⚡ {threads_data.get('title', 'Concurrent Threads')}</h3>
        <p>{threads_data.get('description', '')}</p>
        <p><b>İdeal Ayarlar:</b></p>
        <ul style="margin-left: 20px;">
        """
        for setting in threads_data.get('ideal_settings', []):
            html_content += f"<li style='margin-bottom: 5px;'>{setting}</li>"
        html_content += f"</ul><p style='background-color: #fed7d7; padding: 8px; border-radius: 4px;'><i>⚠️ {threads_data.get('note', '')}</i></p></div>"
        
        # Batch Size
        batch_data = perf_data.get('batch_size', {})
        html_content += f"""
        <div style="border: 2px solid #38a169; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #c6f6d5;">
        <h3 style="color: #2f855a; margin-top: 0;">📦 {batch_data.get('title', 'Batch Size')}</h3>
        <p>{batch_data.get('description', '')}</p>
        <p><b>İdeal Ayarlar:</b></p>
        <ul style="margin-left: 20px;">
        """
        for setting in batch_data.get('ideal_settings', []):
            html_content += f"<li style='margin-bottom: 5px;'>{setting}</li>"
        html_content += f"</ul><p style='background-color: #c6f6d5; padding: 8px; border-radius: 4px;'><i>📊 {batch_data.get('note', '')}</i></p></div>"
        
        # Request Delay
        delay_data = perf_data.get('request_delay', {})
        html_content += f"""
        <div style="border: 2px solid #ed8936; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #fbb6ce;">
        <h3 style="color: #c05621; margin-top: 0;">⏱️ {delay_data.get('title', 'Request Delay')}</h3>
        <p>{delay_data.get('description', '')}</p>
        <p><b>İdeal Ayarlar:</b></p>
        <ul style="margin-left: 20px;">
        """
        for setting in delay_data.get('ideal_settings', []):
            html_content += f"<li style='margin-bottom: 5px;'>{setting}</li>"
        html_content += f"</ul><p style='background-color: #fbb6ce; padding: 8px; border-radius: 4px;'><i>🎯 {delay_data.get('note', '')}</i></p></div>"
        
        html_content += "</div>"
        
        text_widget.setHtml(html_content)
        layout.addWidget(text_widget)
        
        self.tab_widget.addTab(widget, tab_title)
    
    def create_features_tab(self, dialog_data):
        """Create features information tab."""
        features_data = dialog_data.get("features", {})
        tab_title = dialog_data.get("tabs", {}).get("features", "Features")
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        text_widget = QTextEdit()
        text_widget.setReadOnly(True)
        text_widget.setWordWrapMode(text_widget.WordWrapMode.WidgetWidth)
        
        # Build HTML content with better formatting
        html_content = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.4;">
        <h2 style="color: #2c5282; margin-bottom: 15px;">{features_data.get('title', 'Program Features')}</h2>
        <p style="margin-bottom: 20px; color: #4a5568;">{features_data.get('description', '')}</p>
        
        <h3 style="color: #38a169; margin-bottom: 15px;">✅ Mevcut Özellikler</h3>
        """
        
        for feature in features_data.get('current', []):
            html_content += f"""
            <div style="border: 2px solid #38a169; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #f0fff4;">
            <h4 style="color: #2f855a; margin-top: 0; margin-bottom: 8px;">{feature.get('title', '')}</h4>
            <p style="margin-bottom: 0;">{feature.get('description', '')}</p>
            </div>
            """
        
        html_content += """<h3 style="color: #ed8936; margin-bottom: 15px; margin-top: 25px;">🚀 Gelecek Özellikler</h3>"""
        
        for feature in features_data.get('upcoming', []):
            html_content += f"""
            <div style="border: 2px solid #ed8936; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #fffaf0;">
            <h4 style="color: #c05621; margin-top: 0; margin-bottom: 8px;">{feature.get('title', '')}</h4>
            <p style="margin-bottom: 0;">{feature.get('description', '')}</p>
            </div>
            """
        
        html_content += "</div>"
        
        text_widget.setHtml(html_content)
        layout.addWidget(text_widget)
        
        self.tab_widget.addTab(widget, tab_title)
    
    def create_troubleshooting_tab(self, dialog_data):
        """Create troubleshooting information tab."""
        trouble_data = dialog_data.get("troubleshooting", {})
        tab_title = dialog_data.get("tabs", {}).get("troubleshooting", "Troubleshooting")
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        text_widget = QTextEdit()
        text_widget.setReadOnly(True)
        text_widget.setWordWrapMode(text_widget.WordWrapMode.WidgetWidth)
        
        # Build HTML content with better formatting
        html_content = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.4;">
        <h2 style="color: #2c5282; margin-bottom: 15px;">{trouble_data.get('title', 'Troubleshooting')}</h2>
        <p style="margin-bottom: 20px; color: #4a5568;">{trouble_data.get('description', '')}</p>
        """
        
        colors = ['#e53e3e', '#d69e2e', '#38a169', '#3182ce']  # Different colors for each problem
        bg_colors = ['#fed7d7', '#faf089', '#c6f6d5', '#bee3f8']
        
        for i, issue in enumerate(trouble_data.get('common_issues', [])):
            color = colors[i % len(colors)]
            bg_color = bg_colors[i % len(bg_colors)]
            
            html_content += f"""
            <div style="border: 2px solid {color}; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: {bg_color};">
            <h3 style="color: {color}; margin-top: 0; margin-bottom: 10px;">❓ {issue.get('problem', '')}</h3>
            <p><b>🔧 Çözümler:</b></p>
            <ul style="margin-left: 20px;">
            """
            for solution in issue.get('solutions', []):
                html_content += f"<li style='margin-bottom: 5px;'>{solution}</li>"
            html_content += "</ul></div>"
        
        html_content += "</div>"
        
        text_widget.setHtml(html_content)
        layout.addWidget(text_widget)
        
        self.tab_widget.addTab(widget, tab_title)
