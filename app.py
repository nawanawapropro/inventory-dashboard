"""
製造指示ダッシュボード - クラウド対応版
ローカルとクラウド両方で動作します
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import os
import io

st.set_page_config(
    page_title="製造指示ダッシュボード",
    page_icon="🏭",
    layout="wide"
)

# ========================================
# 環境判定
# ========================================
# 環境変数またはフォルダ存在で判定
LOCAL_BASE_DIR = Path(r"Z:\Users\fujinawa\Documents\進行中プロジェクト\味のちぬや\inventory_dashboard")
IS_LOCAL = LOCAL_BASE_DIR.exists()

if IS_LOCAL:
    DATA_DIR = LOCAL_BASE_DIR / "data"
    FOLDERS = {
        '出荷実績': DATA_DIR / "01_出荷実績",
        '特売情報': DATA_DIR / "02_特売情報",
        '販売実績': DATA_DIR / "03_販売実績",
        '製造予定': DATA_DIR / "04_製造予定",
        '製造実績': DATA_DIR / "05_製造実績",
    }


def get_single_file(folder_path, extensions=['.xlsx', '.csv']):
    if not folder_path.exists():
        return None, "フォルダなし"
    files = []
    for ext in extensions:
        files.extend(list(folder_path.glob(f"*{ext}")))
    if len(files) == 0:
        return None, "ファイルなし"
    elif len(files) > 1:
        return None, "複数ファイル"
    return files[0], None


def load_data_from_folder():
    """フォルダからデータ読み込み（ローカル用）"""
    raw_data = {}
    daily_raw = {}
    file_info = {}
    errors = []
    
    # 出荷実績
    fp, err = get_single_file(FOLDERS['出荷実績'], ['.xlsx'])
    if err:
        errors.append(f"出荷実績: {err}")
        return None, None, None, errors
    df = pd.read_excel(fp)
    df['商品コード'] = df['商品コード'].astype(str)
    if '納品日' in df.columns:
        df['日付'] = pd.to_datetime(df['納品日'], errors='coerce')
    raw_data['出荷実績'] = df
    dates = df['日付'].dropna() if '日付' in df.columns else pd.Series()
    file_info['出荷実績'] = {'file_name': fp.name, 'rows': len(df),
                           'min_date': dates.min() if len(dates) else None,
                           'max_date': dates.max() if len(dates) else None}
    if '日付' in df.columns:
        daily_raw['出荷実績'] = df.groupby(['商品コード', '日付']).agg({'売上数荷': 'sum', '商品名１': 'first'}).reset_index()
        daily_raw['出荷実績'].columns = ['商品コード', '日付', '出荷実績', '商品名']
    
    # 特売情報
    fp, err = get_single_file(FOLDERS['特売情報'], ['.csv'])
    if fp:
        df = pd.read_csv(fp, encoding='cp932').iloc[1:]
        df['商品コード'] = df['商品コード'].astype(str)
        df['特売数量'] = pd.to_numeric(df['特売数量'], errors='coerce').fillna(0)
        if 'デポ出庫日' in df.columns:
            df['日付'] = pd.to_datetime(df['デポ出庫日'], errors='coerce')
        raw_data['特売情報'] = df
        dates = df['日付'].dropna() if '日付' in df.columns else pd.Series()
        file_info['特売情報'] = {'file_name': fp.name, 'rows': len(df),
                               'min_date': dates.min() if len(dates) else None,
                               'max_date': dates.max() if len(dates) else None}
        if '日付' in df.columns:
            daily_raw['特売情報'] = df.groupby(['商品コード', '日付']).agg({'特売数量': 'sum'}).reset_index()
            daily_raw['特売情報'].columns = ['商品コード', '日付', '特売予測']
    else:
        file_info['特売情報'] = {'file_name': None}
    
    # 販売実績
    fp, err = get_single_file(FOLDERS['販売実績'], ['.xlsx'])
    if fp:
        df = pd.read_excel(fp, sheet_name='販売経過(25.11月)', header=2)
        df['商品コード'] = df['商品コード'].astype(str)
        for col in ['25.10月', '25.9月', '25.8月']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        df['過去3ヶ月平均'] = df[['25.10月', '25.9月', '25.8月']].mean(axis=1)
        df['日次予測'] = df['過去3ヶ月平均'] / 30
        raw_data['販売実績'] = df
        file_info['販売実績'] = {'file_name': fp.name, 'rows': len(df)}
    else:
        file_info['販売実績'] = {'file_name': None}
    
    # 製造予定
    fp, err = get_single_file(FOLDERS['製造予定'], ['.xlsx'])
    if err:
        errors.append(f"製造予定: {err}")
        return None, None, None, errors
    df = pd.read_excel(fp)
    df['商品コード'] = df['商品コード'].astype(str)
    if '入庫予定日' in df.columns:
        df['日付'] = pd.to_datetime(df['入庫予定日'], errors='coerce')
    raw_data['製造予定'] = df
    dates = df['日付'].dropna() if '日付' in df.columns else pd.Series()
    file_info['製造予定'] = {'file_name': fp.name, 'rows': len(df),
                           'min_date': dates.min() if len(dates) else None,
                           'max_date': dates.max() if len(dates) else None}
    if '日付' in df.columns:
        daily_raw['製造予定'] = df.groupby(['商品コード', '日付']).agg({'入庫予定数': 'sum'}).reset_index()
        daily_raw['製造予定'].columns = ['商品コード', '日付', '製造予定']
    
    # 製造実績
    fp, err = get_single_file(FOLDERS['製造実績'], ['.xlsx'])
    if err:
        errors.append(f"製造実績: {err}")
        return None, None, None, errors
    df = pd.read_excel(fp)
    df['商品コード'] = df['商品コード'].astype(str)
    if '伝票日付' in df.columns:
        df['日付'] = pd.to_datetime(df['伝票日付'], errors='coerce')
    raw_data['製造実績'] = df
    dates = df['日付'].dropna() if '日付' in df.columns else pd.Series()
    file_info['製造実績'] = {'file_name': fp.name, 'rows': len(df),
                           'min_date': dates.min() if len(dates) else None,
                           'max_date': dates.max() if len(dates) else None}
    if '日付' in df.columns:
        daily_raw['製造実績'] = df.groupby(['商品コード', '日付']).agg({'荷合数量': 'sum'}).reset_index()
        daily_raw['製造実績'].columns = ['商品コード', '日付', '製造実績']
    
    return raw_data, daily_raw, file_info, []


def load_data_from_upload(uploaded_files):
    """アップロードされたファイルからデータ読み込み（クラウド用）"""
    raw_data = {}
    daily_raw = {}
    file_info = {}
    errors = []
    
    # 出荷実績
    if uploaded_files.get('出荷実績'):
        df = pd.read_excel(uploaded_files['出荷実績'])
        df['商品コード'] = df['商品コード'].astype(str)
        if '納品日' in df.columns:
            df['日付'] = pd.to_datetime(df['納品日'], errors='coerce')
        raw_data['出荷実績'] = df
        dates = df['日付'].dropna() if '日付' in df.columns else pd.Series()
        file_info['出荷実績'] = {'file_name': uploaded_files['出荷実績'].name, 'rows': len(df),
                               'min_date': dates.min() if len(dates) else None,
                               'max_date': dates.max() if len(dates) else None}
        if '日付' in df.columns:
            daily_raw['出荷実績'] = df.groupby(['商品コード', '日付']).agg({'売上数荷': 'sum', '商品名１': 'first'}).reset_index()
            daily_raw['出荷実績'].columns = ['商品コード', '日付', '出荷実績', '商品名']
    else:
        errors.append("出荷実績ファイルが必要です")
    
    # 特売情報
    if uploaded_files.get('特売情報'):
        df = pd.read_csv(uploaded_files['特売情報'], encoding='cp932').iloc[1:]
        df['商品コード'] = df['商品コード'].astype(str)
        df['特売数量'] = pd.to_numeric(df['特売数量'], errors='coerce').fillna(0)
        if 'デポ出庫日' in df.columns:
            df['日付'] = pd.to_datetime(df['デポ出庫日'], errors='coerce')
        raw_data['特売情報'] = df
        dates = df['日付'].dropna() if '日付' in df.columns else pd.Series()
        file_info['特売情報'] = {'file_name': uploaded_files['特売情報'].name, 'rows': len(df),
                               'min_date': dates.min() if len(dates) else None,
                               'max_date': dates.max() if len(dates) else None}
        if '日付' in df.columns:
            daily_raw['特売情報'] = df.groupby(['商品コード', '日付']).agg({'特売数量': 'sum'}).reset_index()
            daily_raw['特売情報'].columns = ['商品コード', '日付', '特売予測']
    else:
        file_info['特売情報'] = {'file_name': None}
    
    # 販売実績
    if uploaded_files.get('販売実績'):
        df = pd.read_excel(uploaded_files['販売実績'], sheet_name='販売経過(25.11月)', header=2)
        df['商品コード'] = df['商品コード'].astype(str)
        for col in ['25.10月', '25.9月', '25.8月']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        df['過去3ヶ月平均'] = df[['25.10月', '25.9月', '25.8月']].mean(axis=1)
        df['日次予測'] = df['過去3ヶ月平均'] / 30
        raw_data['販売実績'] = df
        file_info['販売実績'] = {'file_name': uploaded_files['販売実績'].name, 'rows': len(df)}
    else:
        file_info['販売実績'] = {'file_name': None}
    
    # 製造予定
    if uploaded_files.get('製造予定'):
        df = pd.read_excel(uploaded_files['製造予定'])
        df['商品コード'] = df['商品コード'].astype(str)
        if '入庫予定日' in df.columns:
            df['日付'] = pd.to_datetime(df['入庫予定日'], errors='coerce')
        raw_data['製造予定'] = df
        dates = df['日付'].dropna() if '日付' in df.columns else pd.Series()
        file_info['製造予定'] = {'file_name': uploaded_files['製造予定'].name, 'rows': len(df),
                               'min_date': dates.min() if len(dates) else None,
                               'max_date': dates.max() if len(dates) else None}
        if '日付' in df.columns:
            daily_raw['製造予定'] = df.groupby(['商品コード', '日付']).agg({'入庫予定数': 'sum'}).reset_index()
            daily_raw['製造予定'].columns = ['商品コード', '日付', '製造予定']
    else:
        errors.append("製造予定ファイルが必要です")
    
    # 製造実績
    if uploaded_files.get('製造実績'):
        df = pd.read_excel(uploaded_files['製造実績'])
        df['商品コード'] = df['商品コード'].astype(str)
        if '伝票日付' in df.columns:
            df['日付'] = pd.to_datetime(df['伝票日付'], errors='coerce')
        raw_data['製造実績'] = df
        dates = df['日付'].dropna() if '日付' in df.columns else pd.Series()
        file_info['製造実績'] = {'file_name': uploaded_files['製造実績'].name, 'rows': len(df),
                               'min_date': dates.min() if len(dates) else None,
                               'max_date': dates.max() if len(dates) else None}
        if '日付' in df.columns:
            daily_raw['製造実績'] = df.groupby(['商品コード', '日付']).agg({'荷合数量': 'sum'}).reset_index()
            daily_raw['製造実績'].columns = ['商品コード', '日付', '製造実績']
    else:
        errors.append("製造実績ファイルが必要です")
    
    if errors:
        return None, None, None, errors
    
    return raw_data, daily_raw, file_info, []


def process_data(raw_data, daily_raw, file_info, date_filters):
    """データ処理（共通）"""
    all_products = {}
    
    def apply_filter(df, data_name):
        if '日付' not in df.columns:
            return df.copy()
        filters = date_filters.get(data_name, {})
        start, end = filters.get('start'), filters.get('end')
        if start and end:
            mask = (df['日付'] >= pd.Timestamp(start)) & (df['日付'] <= pd.Timestamp(end))
            return df[mask].copy()
        return df.copy()
    
    # 出荷実績
    df_ship = apply_filter(raw_data['出荷実績'], '出荷実績')
    for _, row in df_ship.iterrows():
        code = str(row['商品コード'])
        if code not in all_products:
            all_products[code] = {'商品名': row.get('商品名１', ''), '規格': row.get('商品名２', '')}
    ship_summary = df_ship.groupby('商品コード').agg({'売上数荷': 'sum'}).reset_index()
    ship_summary.columns = ['商品コード', '出荷実績']
    
    daily_ship = pd.DataFrame()
    if '日付' in df_ship.columns:
        daily_ship = df_ship.groupby('日付').agg({'売上数荷': 'sum'}).reset_index()
        daily_ship.columns = ['日付', '出荷実績']
    
    # 特売情報
    special_summary = pd.DataFrame({'商品コード': [], '特売予測': []})
    daily_special = pd.DataFrame()
    daily_normal_rate = 0
    
    if '特売情報' in raw_data:
        df_special = apply_filter(raw_data['特売情報'], '特売情報')
        special_summary = df_special.groupby('商品コード').agg({'特売数量': 'sum'}).reset_index()
        special_summary.columns = ['商品コード', '特売予測']
        if '日付' in df_special.columns:
            daily_special = df_special.groupby('日付').agg({'特売数量': 'sum'}).reset_index()
            daily_special.columns = ['日付', '特売予測']
    
    # 販売実績
    sales_summary = pd.DataFrame({'商品コード': [], '通常出荷予測': []})
    if '販売実績' in raw_data:
        df_sales = raw_data['販売実績']
        sales_summary = df_sales[['商品コード', '日次予測']].copy()
        sales_summary.columns = ['商品コード', '通常出荷予測']
        daily_normal_rate = df_sales['日次予測'].sum()
    
    # 製造予定
    df_prod_plan = apply_filter(raw_data['製造予定'], '製造予定')
    prod_plan_summary = df_prod_plan.groupby('商品コード').agg({'入庫予定数': 'sum'}).reset_index()
    prod_plan_summary.columns = ['商品コード', '製造予定']
    daily_prod_plan = pd.DataFrame()
    if '日付' in df_prod_plan.columns:
        daily_prod_plan = df_prod_plan.groupby('日付').agg({'入庫予定数': 'sum'}).reset_index()
        daily_prod_plan.columns = ['日付', '製造予定']
    
    # 製造実績
    df_prod_actual = apply_filter(raw_data['製造実績'], '製造実績')
    prod_actual_summary = df_prod_actual.groupby('商品コード').agg({'ケース数': 'sum', '荷合数量': 'sum'}).reset_index()
    prod_actual_summary.columns = ['商品コード', '製造予定数_実績', '製造実績']
    daily_prod_actual = pd.DataFrame()
    if '日付' in df_prod_actual.columns:
        daily_prod_actual = df_prod_actual.groupby('日付').agg({'荷合数量': 'sum'}).reset_index()
        daily_prod_actual.columns = ['日付', '製造実績']
    
    # マスタ統合
    master = pd.DataFrame([{'商品コード': c, '商品名': i['商品名'], '規格': i['規格']} for c, i in all_products.items()])
    master = master.merge(ship_summary, on='商品コード', how='left')
    master = master.merge(special_summary, on='商品コード', how='left')
    master = master.merge(sales_summary, on='商品コード', how='left')
    master = master.merge(prod_plan_summary, on='商品コード', how='left')
    master = master.merge(prod_actual_summary, on='商品コード', how='left')
    
    for col in ['出荷実績', '特売予測', '通常出荷予測', '製造予定', '製造予定数_実績', '製造実績']:
        if col in master.columns:
            master[col] = master[col].fillna(0)
    
    master['出荷予測'] = master['特売予測'] + master['通常出荷予測']
    master['出荷ズレ'] = master['出荷実績'] - master['出荷予測']
    master['出荷ズレ率'] = np.where(master['出荷予測'] != 0, master['出荷ズレ'] / master['出荷予測'] * 100, 0)
    master['製造ズレ'] = master['製造実績'] - master['製造予定']
    master['製造ズレ率'] = np.where(master['製造予定'] != 0, master['製造ズレ'] / master['製造予定'] * 100, 0)
    
    def get_instruction(row):
        ins = []
        if row['出荷ズレ率'] > 30: ins.append("⬆️ 製造増")
        elif row['出荷ズレ率'] < -30: ins.append("⬇️ 製造減")
        if row['製造ズレ率'] < -20: ins.append("⚠️ 遅れ")
        elif row['製造ズレ率'] > 20: ins.append("✅ 順調")
        return ' / '.join(ins) if ins else "➡️ 様子見"
    master['製造指示'] = master.apply(get_instruction, axis=1)
    
    # 日別統合
    all_dates = set()
    for df in [daily_ship, daily_special, daily_prod_plan, daily_prod_actual]:
        if len(df) > 0 and '日付' in df.columns:
            all_dates.update(df['日付'].dropna().tolist())
    
    daily_master = pd.DataFrame()
    if all_dates:
        date_range = pd.date_range(start=min(all_dates), end=max(all_dates), freq='D')
        daily_master = pd.DataFrame({'日付': date_range})
        for df, col in [(daily_ship, '出荷実績'), (daily_special, '特売予測'), (daily_prod_plan, '製造予定'), (daily_prod_actual, '製造実績')]:
            if len(df) > 0:
                daily_master = daily_master.merge(df, on='日付', how='left')
        for col in ['出荷実績', '特売予測', '製造予定', '製造実績']:
            if col not in daily_master.columns:
                daily_master[col] = 0
            daily_master[col] = daily_master[col].fillna(0)
        daily_master['通常出荷予測'] = daily_normal_rate
        daily_master['出荷予測'] = daily_master['特売予測'] + daily_master['通常出荷予測']
        daily_master['出荷ズレ'] = daily_master['出荷実績'] - daily_master['出荷予測']
        daily_master['製造ズレ'] = daily_master['製造実績'] - daily_master['製造予定']
        daily_master['出荷実績_累計'] = daily_master['出荷実績'].cumsum()
        daily_master['出荷予測_累計'] = daily_master['出荷予測'].cumsum()
        daily_master['製造予定_累計'] = daily_master['製造予定'].cumsum()
        daily_master['製造実績_累計'] = daily_master['製造実績'].cumsum()
    
    totals = {'出荷実績': master['出荷実績'].sum(), '製造予定': master['製造予定'].sum(), '製造実績': master['製造実績'].sum()}
    
    return master.sort_values('商品コード').reset_index(drop=True), daily_master, totals


def generate_alerts(master, th_ship, th_prod):
    alerts = []
    for _, r in master.iterrows():
        if r['出荷ズレ率'] > th_ship:
            alerts.append({'優先度': '🔴 高', '商品コード': r['商品コード'], '商品名': r['商品名'],
                          '指示': '⬆️ 製造増加', '出荷予測': f"{r['出荷予測']:.0f}", '出荷実績': f"{r['出荷実績']:.0f}"})
        elif r['出荷ズレ率'] < -th_ship:
            alerts.append({'優先度': '🟡 中', '商品コード': r['商品コード'], '商品名': r['商品名'],
                          '指示': '⬇️ 製造減少', '出荷予測': f"{r['出荷予測']:.0f}", '出荷実績': f"{r['出荷実績']:.0f}"})
        if r['製造ズレ率'] < -th_prod and r['製造予定'] > 0:
            alerts.append({'優先度': '🔴 高', '商品コード': r['商品コード'], '商品名': r['商品名'],
                          '指示': '⚠️ 製造遅れ', '製造予定': f"{r['製造予定']:.0f}", '製造実績': f"{r['製造実績']:.0f}"})
    df = pd.DataFrame(alerts)
    if len(df) > 0:
        df['sort'] = df['優先度'].map({'🔴 高': 0, '🟡 中': 1})
        df = df.sort_values('sort').drop('sort', axis=1)
    return df


# ========================================
# アプリ本体
# ========================================
st.title("🏭 製造指示ダッシュボード")

if IS_LOCAL:
    st.success("📁 ローカルモード: フォルダからデータを自動読み込み")
else:
    st.info("☁️ クラウドモード: ファイルをアップロードしてください")

st.markdown("---")

# データ読み込み
raw_data, daily_raw, file_info, errors = None, None, None, []

if IS_LOCAL:
    raw_data, daily_raw, file_info, errors = load_data_from_folder()
else:
    # アップロードUI
    st.sidebar.header("📁 ファイルアップロード")
    uploaded = {}
    uploaded['出荷実績'] = st.sidebar.file_uploader("① 出荷実績 (.xlsx)", type=['xlsx'], key='u1')
    uploaded['特売情報'] = st.sidebar.file_uploader("② 特売情報 (.csv)", type=['csv'], key='u2')
    uploaded['販売実績'] = st.sidebar.file_uploader("③ 販売実績 (.xlsx)", type=['xlsx'], key='u3')
    uploaded['製造予定'] = st.sidebar.file_uploader("④ 製造予定 (.xlsx)", type=['xlsx'], key='u4')
    uploaded['製造実績'] = st.sidebar.file_uploader("⑤ 製造実績 (.xlsx)", type=['xlsx'], key='u5')
    
    if uploaded['出荷実績'] and uploaded['製造予定'] and uploaded['製造実績']:
        raw_data, daily_raw, file_info, errors = load_data_from_upload(uploaded)

if errors:
    for e in errors:
        st.error(e)
    st.stop()

if raw_data is None:
    st.warning("データを読み込んでください")
    st.stop()

# サイドバー: 期間設定
st.sidebar.header("📅 期間設定")
date_filters = {}
for name in ['出荷実績', '特売情報', '製造予定', '製造実績']:
    info = file_info.get(name, {})
    if info.get('min_date') and info.get('max_date'):
        with st.sidebar.expander(f"{name}"):
            c1, c2 = st.columns(2)
            with c1:
                s = st.date_input("開始", value=info['min_date'].date(), key=f"{name}_s")
            with c2:
                e = st.date_input("終了", value=info['max_date'].date(), key=f"{name}_e")
            date_filters[name] = {'start': s, 'end': e}

st.sidebar.header("⚙️ 設定")
th_ship = st.sidebar.slider("出荷ズレ警告%", 10, 100, 30)
th_prod = st.sidebar.slider("製造ズレ警告%", 10, 100, 20)

# データ処理
master, daily_master, totals = process_data(raw_data, daily_raw, file_info, date_filters)
alerts_df = generate_alerts(master, th_ship, th_prod)

# サマリー
cols = st.columns(4)
cols[0].metric("商品数", f"{len(master):,}")
cols[1].metric("🔴 要対応", f"{len(alerts_df[alerts_df['優先度']=='🔴 高']) if len(alerts_df) else 0}件")
cols[2].metric("出荷実績", f"{totals['出荷実績']:,.0f}")
cols[3].metric("製造実績", f"{totals['製造実績']:,.0f}")

st.markdown("---")

# タブ
tab1, tab2, tab3, tab4 = st.tabs(["🚨 アラート", "📈 日別推移", "📊 分析", "📋 全商品"])

with tab1:
    if len(alerts_df) > 0:
        def hl(row):
            c = '#ff6b6b' if row['優先度'] == '🔴 高' else '#ffd93d'
            return [f'background-color:{c};color:#000;font-weight:bold'] * len(row)
        st.dataframe(alerts_df.style.apply(hl, axis=1), use_container_width=True, height=400)
    else:
        st.success("✅ アラートなし")

with tab2:
    if len(daily_master) > 0:
        view = st.radio("表示", ["日別", "累計"], horizontal=True)
        c1, c2 = st.columns(2)
        with c1:
            fig = go.Figure()
            if view == "日別":
                fig.add_trace(go.Scatter(x=daily_master['日付'], y=daily_master['出荷予測'], name='予測'))
                fig.add_trace(go.Scatter(x=daily_master['日付'], y=daily_master['出荷実績'], name='実績'))
            else:
                fig.add_trace(go.Scatter(x=daily_master['日付'], y=daily_master['出荷予測_累計'], name='予測累計', fill='tozeroy'))
                fig.add_trace(go.Scatter(x=daily_master['日付'], y=daily_master['出荷実績_累計'], name='実績累計'))
            fig.update_layout(height=300, title="出荷")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = go.Figure()
            if view == "日別":
                fig.add_trace(go.Scatter(x=daily_master['日付'], y=daily_master['製造予定'], name='予定'))
                fig.add_trace(go.Scatter(x=daily_master['日付'], y=daily_master['製造実績'], name='実績'))
            else:
                fig.add_trace(go.Scatter(x=daily_master['日付'], y=daily_master['製造予定_累計'], name='予定累計', fill='tozeroy'))
                fig.add_trace(go.Scatter(x=daily_master['日付'], y=daily_master['製造実績_累計'], name='実績累計'))
            fig.update_layout(height=300, title="製造")
            st.plotly_chart(fig, use_container_width=True)

with tab3:
    c1, c2 = st.columns(2)
    with c1:
        top = master.nlargest(15, '出荷実績')
        fig = go.Figure()
        fig.add_trace(go.Bar(name='予測', x=top['商品名'].str[:10], y=top['出荷予測']))
        fig.add_trace(go.Bar(name='実績', x=top['商品名'].str[:10], y=top['出荷実績']))
        fig.update_layout(barmode='group', height=350, title="出荷TOP15")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        top = master.nlargest(15, '製造実績')
        fig = go.Figure()
        fig.add_trace(go.Bar(name='予定', x=top['商品名'].str[:10], y=top['製造予定']))
        fig.add_trace(go.Bar(name='実績', x=top['商品名'].str[:10], y=top['製造実績']))
        fig.update_layout(barmode='group', height=350, title="製造TOP15")
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    search = st.text_input("🔍 検索")
    display = master[['商品コード', '商品名', '出荷予測', '出荷実績', '出荷ズレ率', '製造予定', '製造実績', '製造ズレ率', '製造指示']].copy()
    if search:
        display = display[display['商品名'].str.contains(search, na=False) | display['商品コード'].str.contains(search, na=False)]
    display['出荷ズレ率'] = display['出荷ズレ率'].round(1)
    display['製造ズレ率'] = display['製造ズレ率'].round(1)
    st.dataframe(display, use_container_width=True, height=500)
    st.download_button("📥 CSV", display.to_csv(index=False).encode('utf-8-sig'), "products.csv")
