"""
Info Dialog
==========

Multi-page information dialog with detailed help content.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QTextEdit, QDialogButtonBox, QLabel, QScrollArea
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon

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
        
        # Set dialog icon
        from pathlib import Path
        import sys
        # PyInstaller için exe çalışma zamanında doğru yolu bulma
        if getattr(sys, 'frozen', False):
            # PyInstaller ile paketlenmiş exe durumu - temporary dizinde icon var
            icon_path = Path(sys._MEIPASS) / "icon.ico"
        else:
            # Normal Python çalışma zamanı
            icon_path = Path(__file__).parent.parent.parent / "icon.ico"
        
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        
        layout = QVBoxLayout(self)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.create_formats_tab(dialog_data)
        self.create_multi_endpoint_tab(dialog_data)
        self.create_performance_tab(dialog_data)
        self.create_features_tab(dialog_data)
        self.create_troubleshooting_tab(dialog_data)
        self.create_unren_tab(dialog_data)
        
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
        
        # Create text widget (QTextEdit has its own scrolling and word wrap)
        text_widget = QTextEdit()
        text_widget.setReadOnly(True)
        
        # Build HTML content with dark theme compatible colors
        html_content = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.4; color: #ffffff;">
        <h2 style="color: #60a5fa; margin-bottom: 15px;">{formats_data.get('title', 'Translation File Formats')}</h2>
        <p style="margin-bottom: 20px; color: #d1d5db;">{formats_data.get('description', '')}</p>
        
        <div style="border: 2px solid #3b82f6; border-radius: 8px; padding: 15px; margin-bottom: 20px; background-color: #1e3a8a; color: #ffffff;">
        <h3 style="color: #93c5fd; margin-top: 0;">{formats_data.get('simple', {}).get('title', 'SIMPLE Format')}</h3>
        <p style="color: #e5e7eb;"><b>Özellikler:</b></p>
        <ul style="margin-left: 20px; color: #f3f4f6;">
        """
        
        for feature in formats_data.get('simple', {}).get('features', []):
            html_content += f"<li style='margin-bottom: 5px; color: #f3f4f6;'>{feature}</li>"
        
        html_content += f"""
        </ul>
        <p style="color: #e5e7eb;"><b>Örnek:</b></p>
        <pre style="background-color: #374151; color: #f9fafb; padding: 10px; border-radius: 5px; border: 1px solid #6b7280; font-family: 'Courier New', monospace; font-size: 12px; overflow-x: auto; white-space: pre-wrap;">
{formats_data.get('simple', {}).get('example', '')}
        </pre>
        <p style="color: #e5e7eb;"><b>Önerilen:</b> <i style="color: #d1d5db;">{formats_data.get('simple', {}).get('recommended_for', '')}</i></p>
        </div>
        
        <div style="border: 2px solid #10b981; border-radius: 8px; padding: 15px; margin-bottom: 20px; background-color: #065f46; color: #ffffff;">
        <h3 style="color: #6ee7b7; margin-top: 0;">{formats_data.get('old_new', {}).get('title', 'OLD_NEW Format')}</h3>
        <p style="color: #e5e7eb;"><b>Özellikler:</b></p>
        <ul style="margin-left: 20px; color: #f3f4f6;">
        """
        
        for feature in formats_data.get('old_new', {}).get('features', []):
            html_content += f"<li style='margin-bottom: 5px; color: #f3f4f6;'>{feature}</li>"
        
        html_content += f"""
        </ul>
        <p style="color: #e5e7eb;"><b>Örnek:</b></p>
        <pre style="background-color: #374151; color: #f9fafb; padding: 10px; border-radius: 5px; border: 1px solid #6b7280; font-family: 'Courier New', monospace; font-size: 12px; overflow-x: auto; white-space: pre-wrap;">
{formats_data.get('old_new', {}).get('example', '')}
        </pre>
        <p style="color: #e5e7eb;"><b>Önerilen:</b> <i style="color: #d1d5db;">{formats_data.get('old_new', {}).get('recommended_for', '')}</i></p>
        </div>
        
        <hr style="margin: 20px 0; border: 1px solid #4b5563;">
        <div style="background-color: #451a03; color: #fef3c7; padding: 15px; border-radius: 8px; border-left: 4px solid #f59e0b;">
        <p style="color: #fef3c7;"><b>💡 Not:</b> {formats_data.get('note', '')}</p>
        <p style="color: #fde68a;"><b>⚙️ Ayar:</b> <i>{formats_data.get('change_setting', '')}</i></p>
        </div>
        </div>
        """
        
        text_widget.setHtml(html_content)
        layout.addWidget(text_widget)
        
        self.tab_widget.addTab(widget, tab_title)
    
    def create_multi_endpoint_tab(self, dialog_data):
        """Create Multi-Endpoint Google Translator information tab (v2.1.0)."""
        me_data = dialog_data.get("multi_endpoint", {})
        if not me_data:
            return
        
        tab_title = dialog_data.get("tabs", {}).get("multi_endpoint", "Multi-Endpoint")
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        text_widget = QTextEdit()
        text_widget.setReadOnly(True)
        
        # How it works steps
        how_steps = "".join(
            f"<li style='margin-bottom:6px;color:#e5e7eb;'>{step}</li>"
            for step in me_data.get("how_it_works", {}).get("steps", [])
        )
        
        # Endpoints
        google_eps = "".join(
            f"<li style='margin-bottom:4px;color:#86efac;'>{ep}</li>"
            for ep in me_data.get("endpoints", {}).get("google", [])
        )
        lingva_eps = "".join(
            f"<li style='margin-bottom:4px;color:#fde68a;'>{ep}</li>"
            for ep in me_data.get("endpoints", {}).get("lingva", [])
        )
        
        # Settings items
        settings_items = ""
        for item in me_data.get("settings", {}).get("items", []):
            settings_items += f"""
            <div style="border: 1px solid #3b82f6; border-radius: 6px; padding: 10px; margin-bottom: 8px; background-color: #1e3a5f;">
                <b style="color: #93c5fd;">{item.get('name', '')}</b>
                <p style="margin: 5px 0 0 0; color: #e5e7eb;">{item.get('description', '')}</p>
            </div>
            """
        
        # Tips
        tips_items = "".join(
            f"<li style='margin-bottom:6px;color:#a7f3d0;'>{tip}</li>"
            for tip in me_data.get("tips", {}).get("items", [])
        )
        
        perf_data = me_data.get("performance", {})
        
        html_content = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.45; color: #e5e7eb;">
            <h2 style="color: #60a5fa; margin-bottom: 10px;">{me_data.get('title', 'Multi-Endpoint Google Translator')}</h2>
            <p style="margin-bottom: 20px; color: #d1d5db;">{me_data.get('description', '')}</p>
            
            <!-- How it works -->
            <div style="border: 2px solid #3b82f6; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #1e3a8a;">
                <h3 style="color: #93c5fd; margin-top: 0;">🔧 {me_data.get('how_it_works', {}).get('title', 'How It Works')}</h3>
                <ol style="margin-left: 18px; color: #e5e7eb;">
                    {how_steps}
                </ol>
            </div>
            
            <!-- Endpoints -->
            <div style="border: 2px solid #10b981; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #065f46;">
                <h3 style="color: #6ee7b7; margin-top: 0;">🌐 {me_data.get('endpoints', {}).get('title', 'Endpoints Used')}</h3>
                <div style="display: flex; gap: 20px;">
                    <div style="flex: 1;">
                        <b style="color: #86efac;">Google Endpoints:</b>
                        <ul style="margin-left: 18px;">{google_eps}</ul>
                    </div>
                    <div style="flex: 1;">
                        <b style="color: #fde68a;">Lingva Fallback:</b>
                        <ul style="margin-left: 18px;">{lingva_eps}</ul>
                    </div>
                </div>
            </div>
            
            <!-- Settings -->
            <div style="border: 2px solid #8b5cf6; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #2e1065;">
                <h3 style="color: #c4b5fd; margin-top: 0;">⚙️ {me_data.get('settings', {}).get('title', 'Settings Explained')}</h3>
                {settings_items}
            </div>
            
            <!-- Performance -->
            <div style="border: 2px solid #f59e0b; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #451a03;">
                <h3 style="color: #fcd34d; margin-top: 0;">📊 {perf_data.get('title', 'Performance Comparison')}</h3>
                <p style="color: #fecaca;"><b>❌ {perf_data.get('before', 'Before')}</b></p>
                <p style="color: #bbf7d0;"><b>✅ {perf_data.get('after', 'After')}</b></p>
                <p style="color: #fef3c7; margin-top: 10px;"><i>📌 {perf_data.get('note', '')}</i></p>
            </div>
            
            <!-- Tips -->
            <div style="border-left: 4px solid #22c55e; padding: 12px 15px; background-color: #052e16; border-radius: 6px;">
                <h4 style="color: #86efac; margin-top: 0;">💡 {me_data.get('tips', {}).get('title', 'Tips')}</h4>
                <ul style="margin-left: 18px;">
                    {tips_items}
                </ul>
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
        
        # Build HTML content with better formatting
        html_content = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.4;">
        <h2 style="color: #81c784; margin-bottom: 15px;">{perf_data.get('title', 'Performance Settings')}</h2>
        <p style="margin-bottom: 20px; color: #e0e0e0;">{perf_data.get('description', '')}</p>
        """
        
        # Parser Workers
        parser_data = perf_data.get('parser_workers', {})
        html_content += f"""
        <div style="border: 2px solid #9c27b0; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #2a1b3d;">
        <h3 style="color: #ce93d8; margin-top: 0;">🚀 {parser_data.get('title', 'Parser Workers')}</h3>
        <p style="color: #e0e0e0;">{parser_data.get('description', '')}</p>
        <p style="color: #e0e0e0;"><b>İdeal Ayarlar:</b></p>
        <ul style="margin-left: 20px; color: #e0e0e0;">
        """
        for setting in parser_data.get('ideal_settings', []):
            html_content += f"<li style='margin-bottom: 5px; color: #e0e0e0;'>{setting}</li>"
        html_content += f"</ul><p style='background-color: #3a2859; padding: 8px; border-radius: 4px; color: #d1c4e9;'><i>💡 {parser_data.get('note', '')}</i></p></div>"
        
        # Concurrent Threads
        threads_data = perf_data.get('concurrent_threads', {})
        html_content += f"""
        <div style="border: 2px solid #f44336; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #3d1a1a;">
        <h3 style="color: #ef9a9a; margin-top: 0;">⚡ {threads_data.get('title', 'Concurrent Threads')}</h3>
        <p style="color: #e0e0e0;">{threads_data.get('description', '')}</p>
        <p style="color: #e0e0e0;"><b>İdeal Ayarlar:</b></p>
        <ul style="margin-left: 20px; color: #e0e0e0;">
        """
        for setting in threads_data.get('ideal_settings', []):
            html_content += f"<li style='margin-bottom: 5px; color: #e0e0e0;'>{setting}</li>"
        html_content += f"</ul><p style='background-color: #4d2626; padding: 8px; border-radius: 4px; color: #ffcdd2;'><i>⚠️ {threads_data.get('note', '')}</i></p></div>"
        
        # Batch Size
        batch_data = perf_data.get('batch_size', {})
        html_content += f"""
        <div style="border: 2px solid #4caf50; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #1b3d1b;">
        <h3 style="color: #a5d6a7; margin-top: 0;">📦 {batch_data.get('title', 'Batch Size')}</h3>
        <p style="color: #e0e0e0;">{batch_data.get('description', '')}</p>
        <p style="color: #e0e0e0;"><b>İdeal Ayarlar:</b></p>
        <ul style="margin-left: 20px; color: #e0e0e0;">
        """
        for setting in batch_data.get('ideal_settings', []):
            html_content += f"<li style='margin-bottom: 5px; color: #e0e0e0;'>{setting}</li>"
        html_content += f"</ul><p style='background-color: #2d5016; padding: 8px; border-radius: 4px; color: #c8e6c9;'><i>📊 {batch_data.get('note', '')}</i></p></div>"
        
        # Request Delay
        delay_data = perf_data.get('request_delay', {})
        html_content += f"""
        <div style="border: 2px solid #ff9800; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #3d2a1a;">
        <h3 style="color: #ffcc80; margin-top: 0;">⏱️ {delay_data.get('title', 'Request Delay')}</h3>
        <p style="color: #e0e0e0;">{delay_data.get('description', '')}</p>
        <p style="color: #e0e0e0;"><b>İdeal Ayarlar:</b></p>
        <ul style="margin-left: 20px; color: #e0e0e0;">
        """
        for setting in delay_data.get('ideal_settings', []):
            html_content += f"<li style='margin-bottom: 5px; color: #e0e0e0;'>{setting}</li>"
        html_content += f"</ul><p style='background-color: #4d3319; padding: 8px; border-radius: 4px; color: #ffe0b2;'><i>🎯 {delay_data.get('note', '')}</i></p></div>"
        
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
        
        # Build HTML content with better formatting
        html_content = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.4;">
        <h2 style="color: #81c784; margin-bottom: 15px;">{features_data.get('title', 'Program Features')}</h2>
        <p style="margin-bottom: 20px; color: #e0e0e0;">{features_data.get('description', '')}</p>
        
        <h3 style="color: #a5d6a7; margin-bottom: 15px;">✅ Mevcut Özellikler</h3>
        """
        
        for feature in features_data.get('current', []):
            html_content += f"""
            <div style="border: 2px solid #4caf50; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #1b3d1b;">
            <h4 style="color: #a5d6a7; margin-top: 0; margin-bottom: 8px;">{feature.get('title', '')}</h4>
            <p style="margin-bottom: 0; color: #e0e0e0;">{feature.get('description', '')}</p>
            </div>
            """
        
        html_content += """<h3 style="color: #ffcc80; margin-bottom: 15px; margin-top: 25px;">🚀 Gelecek Özellikler</h3>"""
        
        for feature in features_data.get('upcoming', []):
            html_content += f"""
            <div style="border: 2px solid #ff9800; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #3d2a1a;">
            <h4 style="color: #ffcc80; margin-top: 0; margin-bottom: 8px;">{feature.get('title', '')}</h4>
            <p style="margin-bottom: 0; color: #e0e0e0;">{feature.get('description', '')}</p>
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
        
        # Build HTML content with better formatting
        html_content = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.4;">
        <h2 style="color: #81c784; margin-bottom: 15px;">{trouble_data.get('title', 'Troubleshooting')}</h2>
        <p style="margin-bottom: 20px; color: #e0e0e0;">{trouble_data.get('description', '')}</p>
        """
        
        colors = ['#f44336', '#ff9800', '#4caf50', '#2196f3']  # Different colors for each problem
        bg_colors = ['#3d1a1a', '#3d2a1a', '#1b3d1b', '#1a2a3d']
        text_colors = ['#ef9a9a', '#ffcc80', '#a5d6a7', '#90caf9']
        
        for i, issue in enumerate(trouble_data.get('common_issues', [])):
            color = colors[i % len(colors)]
            bg_color = bg_colors[i % len(bg_colors)]
            text_color = text_colors[i % len(text_colors)]
            
            html_content += f"""
            <div style="border: 2px solid {color}; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: {bg_color};">
            <h3 style="color: {text_color}; margin-top: 0; margin-bottom: 10px;">❓ {issue.get('problem', '')}</h3>
            <p style="color: #e0e0e0;"><b>🔧 Çözümler:</b></p>
            <ul style="margin-left: 20px; color: #e0e0e0;">
            """
            for solution in issue.get('solutions', []):
                html_content += f"<li style='margin-bottom: 5px; color: #e0e0e0;'>{solution}</li>"
            html_content += "</ul></div>"
        
        html_content += "</div>"
        
        text_widget.setHtml(html_content)
        layout.addWidget(text_widget)
        
        self.tab_widget.addTab(widget, tab_title)

    def create_unren_tab(self, dialog_data):
        """Create UnRen integration tab."""
        unren_data = dialog_data.get("unren")
        if not unren_data:
            return

        tab_title = dialog_data.get("tabs", {}).get("unren", "UnRen")
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)

        text_widget = QTextEdit()
        text_widget.setReadOnly(True)

        auto_section = "".join(
            f"<li style='margin-bottom:6px;color:#e5e7eb;'>{point}</li>"
            for point in unren_data.get("automatic", {}).get("points", [])
        )
        manual_section = "".join(
            f"<li style='margin-bottom:6px;color:#e5e7eb;'>{point}</li>"
            for point in unren_data.get("manual", {}).get("points", [])
        )
        tip_list = "".join(
            f"<li style='margin-bottom:4px;'>{tip}</li>"
            for tip in unren_data.get("tips", [])
        )
        version_section = ""
        versions_data = unren_data.get("versions")
        if versions_data:
            version_cards = "".join(
                f"""
                <div style='border: 1px solid #1d4ed8; border-radius: 8px; padding: 12px; margin-bottom: 10px; background-color: #0f172a;'>
                    <h4 style='color: #93c5fd; margin: 0 0 6px 0;'>{option.get('title', '')}</h4>
                    <p style='margin: 0 0 4px 0; color: #e2e8f0;'>{option.get('description', '')}</p>
                    <p style='margin: 0; color: #bfdbfe;'><b>{option.get('versions_label', '')}</b> {option.get('versions', '')}</p>
                    <p style='margin: 4px 0 0 0; color: #cbd5f5; font-size: 12px;'>{option.get('note', '')}</p>
                </div>
                """
                for option in versions_data.get("options", [])
            )
            version_section = f"""
            <div style=\"border-left: 4px solid #2563eb; padding: 12px 15px; background-color: #0b1120; border-radius: 6px; margin-bottom: 15px;\">
                <h3 style=\"color: #bfdbfe; margin-top: 0;\">{versions_data.get('title', '')}</h3>
                <p style=\"color: #e5e7eb; margin-bottom: 12px;\">{versions_data.get('description', '')}</p>
                {version_cards}
            </div>
            """

        checklist_section = ""
        checklist_data = unren_data.get("checklist", {})
        checklist_items = "".join(
            f"<li style='margin-bottom:4px;color:#e0f2fe;'>{item}</li>"
            for item in checklist_data.get("items", [])
        )
        if checklist_items:
            checklist_section = f"""
            <div style=\"border-left: 4px solid #22d3ee; padding: 12px 15px; background-color: #083344; border-radius: 6px; margin-bottom: 15px;\">
                <h4 style=\"color: #67e8f9; margin-top: 0;\">{checklist_data.get('title', '')}</h4>
                <ul style=\"margin-left: 18px;\">{checklist_items}</ul>
            </div>
            """

        manual_flow_section = ""
        manual_flow_data = unren_data.get("manual_flow", {})
        manual_flow_steps = "".join(
            f"<li style='margin-bottom:8px;'>"
            f"<span style='color:#bfdbfe;font-weight:600;'>{step.get('title', '')}</span><br>"
            f"<span style='color:#cbd5f5;'>{step.get('detail', '')}</span>"
            "</li>"
            for step in manual_flow_data.get("steps", [])
        )
        if manual_flow_steps:
            manual_flow_note = manual_flow_data.get("note")
            manual_flow_note_html = ""
            if manual_flow_note:
                manual_flow_note_html = f"<p style=\"margin-top: 10px; color: #fcd34d;\">{manual_flow_note}</p>"
            manual_flow_section = f"""
            <div style=\"border: 2px dashed #fbbf24; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #1c1917;\">
                <h3 style=\"color: #fde68a; margin-top: 0;\">{manual_flow_data.get('title', '')}</h3>
                <ol style=\"margin-left: 18px;\">{manual_flow_steps}</ol>
                {manual_flow_note_html}
            </div>
            """

        verification_section = ""
        verification_data = unren_data.get("verification", {})
        verification_items = "".join(
            f"<li style='margin-bottom:4px;color:#bbf7d0;'>{item}</li>"
            for item in verification_data.get("items", [])
        )
        if verification_items:
            verification_section = f"""
            <div style=\"border-left: 4px solid #22c55e; padding: 12px 15px; background-color: #052e16; border-radius: 6px; margin-bottom: 15px;\">
                <h4 style=\"color: #86efac; margin-top: 0;\">{verification_data.get('title', '')}</h4>
                <ul style=\"margin-left: 18px;\">{verification_items}</ul>
            </div>
            """

        troubleshooting_section = ""
        troubleshooting_data = unren_data.get("troubleshooting", {})
        troubleshooting_items = "".join(
            f"<li style='margin-bottom:6px;'><b style='color:#fecaca;'>{item.get('issue', '')}</b><br><span style='color:#fee2e2;'>{item.get('resolution', '')}</span></li>"
            for item in troubleshooting_data.get("items", [])
        )
        if troubleshooting_items:
            troubleshooting_section = f"""
            <div style=\"border: 1px solid #f87171; border-radius: 8px; padding: 15px; margin-top: 15px; background-color: #450a0a;\">
                <h4 style=\"color: #fecaca; margin-top: 0;\">{troubleshooting_data.get('title', '')}</h4>
                <ul style=\"margin-left: 18px;\">{troubleshooting_items}</ul>
            </div>
            """

        html_content = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.45; color: #e5e7eb;">
            <h2 style="color: #93c5fd;">{unren_data.get('title', 'UnRen Integration')}</h2>
            <p style="margin-bottom: 15px;">{unren_data.get('description', '')}</p>
            {version_section}
            {checklist_section}

            <div style="border: 2px solid #60a5fa; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #0f172a;">
                <h3 style="color: #bae6fd; margin-top: 0;">{unren_data.get('automatic', {}).get('title', 'Automatic Mode')}</h3>
                <ul style="margin-left: 18px; list-style: disc;">
                    {auto_section}
                </ul>
            </div>

            <div style="border: 2px solid #fbbf24; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #422006;">
                <h3 style="color: #fde68a; margin-top: 0;">{unren_data.get('manual', {}).get('title', 'Manual Mode')}</h3>
                <ul style="margin-left: 18px; list-style: disc;">
                    {manual_section}
                </ul>
                <p style="margin-top: 10px; color: #fef3c7;"><b>⚠️ {unren_data.get('manual', {}).get('warning', '')}</b></p>
            </div>
            {manual_flow_section}
            {verification_section}

            <div style="border-left: 4px solid #34d399; padding: 12px 15px; background-color: #064e3b; border-radius: 6px;">
                <h4 style="color: #6ee7b7; margin-top: 0;">{unren_data.get('tips_title', 'Quick Reminders')}</h4>
                <ul style="margin-left: 18px;">
                    {tip_list}
                </ul>
                <p style="margin-top: 10px; color: #a7f3d0;">{unren_data.get('footer', '')}</p>
            </div>
            {troubleshooting_section}
        </div>
        """

        text_widget.setHtml(html_content)
        layout.addWidget(text_widget)

        self.tab_widget.addTab(widget, tab_title)
