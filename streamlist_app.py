# app.py (Streamlit version with Technical Analysis)
import streamlit as st
from datetime import date
from dateutil.relativedelta import relativedelta
import pandas as pd
import numpy as np

from utils.dates import ad_to_roc, parse_roc_date
from services.company import search_code
from services.market import fetch_range
from services.news import fetch_monthly_top_news

import plotly.express as px
import plotly.graph_objects as go

# ============ 技術指標 計算函數 ============
def calculate_ma(df, periods=[5, 20, 60]):
    """移動平均線 (MA)"""
    for period in periods:
        df[f'MA{period}'] = df['收盤價'].rolling(window=period).mean()
    return df

def calculate_rsi(df, period=14):
    """相對強弱指標 (RSI)"""
    delta = df['收盤價'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

def calculate_macd(df, fast=12, slow=26, signal=9):
    """MACD指標"""
    exp1 = df['收盤價'].ewm(span=fast, adjust=False).mean()
    exp2 = df['收盤價'].ewm(span=slow, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['MACD_Signal'] = df['MACD'].ewm(span=signal, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    return df

def calculate_bollinger_bands(df, period=20, std=2):
    """布林通道 (Bollinger Bands)"""
    df['BB_Middle'] = df['收盤價'].rolling(window=period).mean()
    rolling_std = df['收盤價'].rolling(window=period).std()
    df['BB_Upper'] = df['BB_Middle'] + (rolling_std * std)
    df['BB_Lower'] = df['BB_Middle'] - (rolling_std * std)
    return df

def calculate_volume_ma(df, periods=[5, 20]):
    """成交量移動平均"""
    for period in periods:
        df[f'VOL_MA{period}'] = df['成交股數'].rolling(window=period).mean()
    return df

# ============ Streamlit 기본 설정 ============
st.set_page_config(page_title="台股行情 + 新聞", layout="wide")

st.title("📈 台股行情查詢 + 技術分析 + Google News 時間軸")

# ============ Sidebar 검색 바 ============
st.sidebar.header("查詢條件")

today = date.today()

roc_years = list(range(114, 99, -1))
months = list(range(1, 13))

yy  = st.sidebar.selectbox("起始年份(民國)", roc_years, index=0)
mm  = st.sidebar.selectbox("起始月份", months, index=today.month - 1)

yy2 = st.sidebar.text_input("結束年份(民國, 可空白)", "")
mm2 = st.sidebar.text_input("結束月份(可空白)", "")

q   = st.sidebar.text_input("公司名稱 / 代碼", "台積電")

# 기술적 분석 옵션
st.sidebar.header("技術分析選項")
show_ma = st.sidebar.checkbox("移動平均線 (MA)", value=True)
show_bb = st.sidebar.checkbox("布林通道 (Bollinger Bands)", value=True)
show_rsi = st.sidebar.checkbox("RSI 指標", value=True)
show_macd = st.sidebar.checkbox("MACD 指標", value=True)

# ========= 날짜 계산 ==========
try:
    start_d = parse_roc_date(yy, mm, 1)
except:
    start_d = date(today.year, today.month, 1)

if yy2:
    try:
        yy2_i = int(yy2)
        if mm2:
            mm2_i = int(mm2)
            base = parse_roc_date(yy2_i, mm2_i, 1)
            end_d = base + relativedelta(months=1, days=-1)
        else:
            base = parse_roc_date(yy2_i, 12, 1)
            end_d = base + relativedelta(months=1, days=-1)
    except:
        end_d = today
else:
    end_d = today

st.write(f"📅 查詢期間：{start_d} ~ {end_d}")

# ========== 검색 실행 버튼 ==========
if st.sidebar.button("查詢資料"):
    st.session_state["go"] = True

if st.session_state.get("go"):

    # ========== 회사 검색 ==========
    matches = search_code(q)
    if matches.empty:
        st.error("❌ 未找到公司名稱/代碼")
        st.stop()

    if len(matches) == 1:
        stock_no = matches.iloc[0]["code"]
        stock_name = matches.iloc[0]["name"]
    else:
        st.info("找到多個匹配，請選擇：")
        pick = st.selectbox(
            "公司清單",
            matches["code"] + " - " + matches["name"]
        )
        stock_no = pick.split(" - ")[0]
        stock_name = pick.split(" - ")[1]

    st.subheader(f"📌 {stock_no} {stock_name}")

    # ========== 가격 데이터 ==========
    df = fetch_range(stock_no, start_d, end_d)

    if df.empty:
        st.error("❌ 無資料")
        st.stop()

    # ========== 技術指標 計算 ==========
    df = calculate_ma(df)
    df = calculate_rsi(df)
    df = calculate_macd(df)
    df = calculate_bollinger_bands(df)
    df = calculate_volume_ma(df)

    end_shown = df["日期_dt"].dt.date.max()

    # 최근 가격 정보
    last = df.iloc[-1]
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("收盤", f"{last['收盤價']:.2f}")
    col2.metric("最高", f"{last['最高價']:.2f}")
    col3.metric("最低", f"{last['最低價']:.2f}")
    col4.metric("成交量", f"{int(last['成交股數']):,}")
    col5.metric("RSI", f"{last['RSI']:.1f}" if not pd.isna(last['RSI']) else "N/A")

    # ========= 價格走勢 + 移動平均線 ==========
    st.markdown("### 📊 價格走勢與移動平均線")
    st.info("**說明**: 移動平均線可以幫助識別趨勢方向。MA5(短期)、MA20(中期)、MA60(長期)。當短期均線向上穿越長期均線時為「黃金交叉」(買入信號)，反之為「死亡交叉」(賣出信號)。")
    
    fig_ma = go.Figure()
    fig_ma.add_trace(go.Scatter(x=df["日期_dt"], y=df["收盤價"], 
                                name="收盤價", line=dict(color='blue', width=2)))
    
    if show_ma:
        fig_ma.add_trace(go.Scatter(x=df["日期_dt"], y=df["MA5"], 
                                    name="MA5", line=dict(color='orange', width=1)))
        fig_ma.add_trace(go.Scatter(x=df["日期_dt"], y=df["MA20"], 
                                    name="MA20", line=dict(color='red', width=1)))
        fig_ma.add_trace(go.Scatter(x=df["日期_dt"], y=df["MA60"], 
                                    name="MA60", line=dict(color='green', width=1)))
    
    fig_ma.update_layout(title="收盤價與移動平均線", xaxis_title="日期", yaxis_title="價格")
    st.plotly_chart(fig_ma, use_container_width=True)

    # ========= 布林通道 ==========
    if show_bb:
        st.markdown("### 📈 布林通道 (Bollinger Bands)")
        st.info("**說明**: 布林通道由中軌(20日均線)和上下軌(±2個標準差)組成。價格接近上軌表示超買，接近下軌表示超賣。通道收窄時表示波動率低，可能預示大行情來臨。")
        
        fig_bb = go.Figure()
        fig_bb.add_trace(go.Scatter(x=df["日期_dt"], y=df["BB_Upper"], 
                                    name="上軌", line=dict(color='red', dash='dash')))
        fig_bb.add_trace(go.Scatter(x=df["日期_dt"], y=df["BB_Middle"], 
                                    name="中軌", line=dict(color='orange')))
        fig_bb.add_trace(go.Scatter(x=df["日期_dt"], y=df["BB_Lower"], 
                                    name="下軌", line=dict(color='green', dash='dash')))
        fig_bb.add_trace(go.Scatter(x=df["日期_dt"], y=df["收盤價"], 
                                    name="收盤價", line=dict(color='blue', width=2)))
        
        fig_bb.update_layout(title="布林通道", xaxis_title="日期", yaxis_title="價格")
        st.plotly_chart(fig_bb, use_container_width=True)

    # ========= K線圖 ==========
    st.markdown("### 🕯️ K線圖")
    st.info("**說明**: K線圖顯示每日的開盤、收盤、最高、最低價。紅色(或空心)表示上漲，綠色(或實心)表示下跌。可用於識別價格形態和趨勢反轉信號。")
    
    fig_candle = go.Figure(
        data=[go.Candlestick(
            x=df["日期_dt"],
            open=df["開盤價"], high=df["最高價"],
            low=df["最低價"], close=df["收盤價"]
        )]
    )
    fig_candle.update_layout(title="K線圖", xaxis_title="日期", yaxis_title="價格")
    st.plotly_chart(fig_candle, use_container_width=True)

    # ========= RSI 指標 ==========
    if show_rsi:
        st.markdown("### 📉 RSI 相對強弱指標")
        st.info("**說明**: RSI範圍為0-100。一般認為RSI > 70為超買區(可能回調)，RSI < 30為超賣區(可能反彈)。RSI在50附近表示多空均衡。")
        
        fig_rsi = go.Figure()
        fig_rsi.add_trace(go.Scatter(x=df["日期_dt"], y=df["RSI"], 
                                     name="RSI", line=dict(color='purple', width=2)))
        fig_rsi.add_hline(y=70, line_dash="dash", line_color="red", 
                          annotation_text="超買區 (70)")
        fig_rsi.add_hline(y=30, line_dash="dash", line_color="green", 
                          annotation_text="超賣區 (30)")
        fig_rsi.add_hline(y=50, line_dash="dot", line_color="gray")
        
        fig_rsi.update_layout(title="RSI 指標", xaxis_title="日期", yaxis_title="RSI", 
                             yaxis=dict(range=[0, 100]))
        st.plotly_chart(fig_rsi, use_container_width=True)

    # ========= MACD 指標 ==========
    if show_macd:
        st.markdown("### 📊 MACD 指標")
        st.info("**說明**: MACD由快線(MACD)、慢線(Signal)和柱狀圖(Histogram)組成。當MACD線向上穿越信號線時為買入信號，向下穿越為賣出信號。柱狀圖正值擴大表示上漲動能增強。")
        
        fig_macd = go.Figure()
        fig_macd.add_trace(go.Scatter(x=df["日期_dt"], y=df["MACD"], 
                                      name="MACD", line=dict(color='blue')))
        fig_macd.add_trace(go.Scatter(x=df["日期_dt"], y=df["MACD_Signal"], 
                                      name="Signal", line=dict(color='red')))
        fig_macd.add_trace(go.Bar(x=df["日期_dt"], y=df["MACD_Hist"], 
                                  name="Histogram", marker_color='gray'))
        
        fig_macd.update_layout(title="MACD 指標", xaxis_title="日期", yaxis_title="MACD")
        st.plotly_chart(fig_macd, use_container_width=True)

    # ========= 成交量分析 ==========
    st.markdown("### 📊 成交量分析")
    st.info("**說明**: 成交量反映市場活躍度。價格上漲伴隨成交量放大表示上漲動能強勁；價格下跌伴隨成交量萎縮可能預示跌勢將盡。成交量均線可以幫助識別異常交易活動。")
    
    fig_vol = go.Figure()
    fig_vol.add_trace(go.Bar(x=df["日期_dt"], y=df["成交股數"], 
                             name="成交股數", marker_color='lightblue'))
    fig_vol.add_trace(go.Scatter(x=df["日期_dt"], y=df["VOL_MA5"], 
                                 name="5日均量", line=dict(color='orange')))
    fig_vol.add_trace(go.Scatter(x=df["日期_dt"], y=df["VOL_MA20"], 
                                 name="20日均量", line=dict(color='red')))
    
    fig_vol.update_layout(title="成交股數與均量", xaxis_title="日期", yaxis_title="成交股數")
    st.plotly_chart(fig_vol, use_container_width=True)

    # ========= 成交金額 ==========
    fig_amt = px.bar(df, x="日期_dt", y="成交金額", title="成交金額")
    st.plotly_chart(fig_amt, use_container_width=True)

    # ========= 技術分析總結 ==========
    st.markdown("### 🎯 技術分析總結")
    
    last_valid = df.dropna(subset=['RSI', 'MACD']).iloc[-1] if len(df.dropna(subset=['RSI', 'MACD'])) > 0 else None
    
    if last_valid is not None:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**趨勢判斷**")
            if last_valid['收盤價'] > last_valid['MA20']:
                st.success("✅ 價格在20日均線之上 (多頭趨勢)")
            else:
                st.warning("⚠️ 價格在20日均線之下 (空頭趨勢)")
            
            if last_valid['MA5'] > last_valid['MA20'] > last_valid['MA60']:
                st.success("✅ 均線多頭排列")
            elif last_valid['MA5'] < last_valid['MA20'] < last_valid['MA60']:
                st.error("❌ 均線空頭排列")
            else:
                st.info("ℹ️ 均線糾結中")
        
        with col2:
            st.markdown("**技術指標訊號**")
            if last_valid['RSI'] > 70:
                st.warning("⚠️ RSI超買 (>70)")
            elif last_valid['RSI'] < 30:
                st.success("✅ RSI超賣 (<30)")
            else:
                st.info(f"ℹ️ RSI正常 ({last_valid['RSI']:.1f})")
            
            if last_valid['MACD'] > last_valid['MACD_Signal']:
                st.success("✅ MACD多頭訊號")
            else:
                st.warning("⚠️ MACD空頭訊號")

    # ========= 표 출력 ==========
    st.markdown("### 📋 原始表格")
    show = df[["日期","成交股數","成交金額","開盤價","最高價","最低價","收盤價","漲跌價差","成交筆數"]]
    st.dataframe(show, use_container_width=True)

    # ========= 뉴스 타임라인 ==========
    st.markdown("### 📰 Google News 每月熱門新聞 (最多能輸出 10個月的)")
    try:
        news_timeline = fetch_monthly_top_news(
            stock_name, start_d, end_shown, per_month=5
        )
        for month, items in news_timeline.items():
            st.markdown(f"#### 📅 {month}")
            for n in items:
                st.write(f"**[{n['title']}]({n['link']})**")
                st.caption(n["published"])
                st.write(n["summary"])
                st.markdown("---")
    except Exception as e:
        st.warning(f"新聞讀取失敗：{e}")