from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter

class PerformanceMetricsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.response_times = []
        self.token_usage = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        self.response_time_label = QLabel("Average Response Time: N/A")
        layout.addWidget(self.response_time_label)

        self.token_usage_label = QLabel("Total Token Usage: 0")
        layout.addWidget(self.token_usage_label)

        self.chart_view = QChartView()
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        layout.addWidget(self.chart_view)

        self.update_chart()

    def update_metrics(self, response_time=None, tokens_used=None):
        if response_time is not None:
            self.response_times.append(response_time)
            avg_time = sum(self.response_times) / len(self.response_times)
            self.response_time_label.setText(f"Average Response Time: {avg_time:.2f}s")

        if tokens_used is not None:
            self.token_usage.append(tokens_used)
            total_tokens = sum(self.token_usage)
            self.token_usage_label.setText(f"Total Token Usage: {total_tokens}")

        self.update_chart()

    def update_chart(self):
        chart = QChart()
        chart.setTitle("Performance Metrics")

        response_time_series = QLineSeries()
        response_time_series.setName("Response Time")
        for i, time in enumerate(self.response_times):
            response_time_series.append(i, time)

        token_usage_series = QLineSeries()
        token_usage_series.setName("Token Usage")
        for i, tokens in enumerate(self.token_usage):
            token_usage_series.append(i, tokens)

        chart.addSeries(response_time_series)
        chart.addSeries(token_usage_series)

        axis_x = QValueAxis()
        axis_x.setTitleText("Interactions")
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        response_time_series.attachAxis(axis_x)
        token_usage_series.attachAxis(axis_x)

        axis_y_time = QValueAxis()
        axis_y_time.setTitleText("Response Time (s)")
        chart.addAxis(axis_y_time, Qt.AlignmentFlag.AlignLeft)
        response_time_series.attachAxis(axis_y_time)

        axis_y_tokens = QValueAxis()
        axis_y_tokens.setTitleText("Token Usage")
        chart.addAxis(axis_y_tokens, Qt.AlignmentFlag.AlignRight)
        token_usage_series.attachAxis(axis_y_tokens)

        self.chart_view.setChart(chart)

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = PerformanceMetricsWidget()
    widget.show()
    widget.update_metrics(response_time=1.5, tokens_used=100)
    widget.update_metrics(response_time=2.0, tokens_used=150)
    widget.update_metrics(response_time=1.8, tokens_used=120)
    sys.exit(app.exec())