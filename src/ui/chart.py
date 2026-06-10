"""Plotly grafik: candlestick + EMA + giris/cikis isaretleri + RSI/MACD panelleri."""
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.config import RSI_OVERBOUGHT, RSI_OVERSOLD

_GREEN = "#26a69a"
_RED = "#ef5350"


def build_panorama_chart(normalized: pd.DataFrame) -> go.Figure:
    """Donem basi = 100 endeksli karsilastirma grafigi — yukselen/dusen net gorunur."""
    fig = go.Figure()
    for name in normalized.columns:
        series = normalized[name].dropna()
        fig.add_trace(
            go.Scatter(x=series.index, y=series, name=name, mode="lines", line=dict(width=1.8))
        )
    fig.add_hline(y=100, line_dash="dash", line_color="gray", opacity=0.6)
    fig.update_layout(
        height=450,
        template="plotly_dark",
        margin=dict(l=10, r=10, t=30, b=10),
        yaxis_title="Donem basi = 100",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
    )
    return fig


def build_chart(df: pd.DataFrame, title: str, recommendation: dict | None = None) -> go.Figure:
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=(title, "RSI (14)", "MACD (12, 26, 9)"),
    )

    # ── Fiyat paneli ──
    fig.add_trace(
        go.Candlestick(
            x=df["time"], open=df["open"], high=df["high"],
            low=df["low"], close=df["close"],
            increasing_line_color=_GREEN, decreasing_line_color=_RED,
            name="Fiyat", showlegend=False,
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=df["time"], y=df["ema20"], name="EMA20",
                   line=dict(color="#42a5f5", width=1.2)),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=df["time"], y=df["ema50"], name="EMA50",
                   line=dict(color="#ffa726", width=1.2)),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=df["time"], y=df["hh20"], name="Kirilim bandi (20)",
                   line=dict(color="#78909c", width=1, dash="dot")),
        row=1, col=1,
    )

    # Giris/cikis isaretleri — sinyal uretilen mumlar
    buys = df[df["signal"] == "AL"]
    sells = df[df["signal"] == "SAT"]
    fig.add_trace(
        go.Scatter(
            x=buys["time"], y=buys["low"] * 0.995, mode="markers",
            marker=dict(symbol="triangle-up", size=13, color=_GREEN,
                        line=dict(width=1, color="white")),
            name="AL (kirilim girisi)",
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=sells["time"], y=sells["high"] * 1.005, mode="markers",
            marker=dict(symbol="triangle-down", size=13, color=_RED,
                        line=dict(width=1, color="white")),
            name="SAT (cikis)",
        ),
        row=1, col=1,
    )

    # Guncel oneri AL ise trailing stop seviyesi
    if recommendation and recommendation["action"] == "AL":
        fig.add_hline(y=recommendation["stop"], line_dash="dot", line_color=_RED,
                      annotation_text=f"Trailing stop {recommendation['stop']:,.2f}",
                      row=1, col=1)

    # ── RSI paneli ──
    fig.add_trace(
        go.Scatter(x=df["time"], y=df["rsi"], name="RSI",
                   line=dict(color="#ab47bc", width=1.2), showlegend=False),
        row=2, col=1,
    )
    fig.add_hline(y=RSI_OVERBOUGHT, line_dash="dash", line_color=_RED,
                  opacity=0.5, row=2, col=1)
    fig.add_hline(y=RSI_OVERSOLD, line_dash="dash", line_color=_GREEN,
                  opacity=0.5, row=2, col=1)

    # ── MACD paneli ──
    hist_colors = [(_GREEN if v >= 0 else _RED) for v in df["macd_hist"]]
    fig.add_trace(
        go.Bar(x=df["time"], y=df["macd_hist"], marker_color=hist_colors,
               name="Histogram", showlegend=False),
        row=3, col=1,
    )
    fig.add_trace(
        go.Scatter(x=df["time"], y=df["macd_line"], name="MACD",
                   line=dict(color="#42a5f5", width=1), showlegend=False),
        row=3, col=1,
    )
    fig.add_trace(
        go.Scatter(x=df["time"], y=df["macd_signal"], name="Sinyal",
                   line=dict(color="#ffa726", width=1), showlegend=False),
        row=3, col=1,
    )

    fig.update_layout(
        height=720,
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig
