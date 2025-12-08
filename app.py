"""
製造指示ダッシュボード - クラウド対応版
ローカル（Zドライブ）とクラウド（ファイルアップロード）両方で動作
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime

st.set_page_config(
    page_title="製造指示ダッシュボード",
    page_icon="🏭",
    layout="wide"
)

# ========================================
# 環境判定
# ========================================
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


def parse_date(value):
    """様々な日付形式をパース（整数8桁対応）"""
    if pd.isna(value):
        return pd.NaT
    
    # 整数形式 (20251120)
    if isinstance(value, (int, float)):
        try:
            return pd.to_datetime(str(int(value)), format='%Y%m%d')
        except:
            return pd.NaT
    
    # 文字列形式
    if isinstance(value, str):
        if value.isdigit() and len(value) == 8:
            try:
                return pd.to_datetime(value, format='%Y%m%d')
            except:
                pass
        try:
            return pd.to_datetime(value)
        except:
            return pd.NaT
    
    if isinstance(value, (datetime, pd.Timestamp)):
        return pd.Timestamp(value)
    
    return pd.NaT


def load_data_from_folder():
    """フォルダからデータ読み込み（ローカル用）"""
    raw_data = {}
    file_info = {}
    errors = []
    
    # 出荷実績
    fp, err = get_single_file(FOLDERS['出荷実績'], ['.xlsx'])
    if err:
        errors.append(f"出荷実績: {err}")
        return None, None, errors
    df = pd.read_excel(fp)
    df['商品コード'] = df['商品コード'].astype(str)
    if '納品日' in df.columns:
        df['日付'] = df['納品日'].apply(parse_date)
    raw_data['出荷実績'] = df
    dates = df['日付'].dropna() if '日付' in df.columns else pd.Series()
    file_info['出荷実績'] = {'file_name': fp.name, 'rows': len(df),
                           'min_date': dates.min() if len(dates) else None,
                           'max_date': dates.max() if len(dates) else None}
    
    # 特売情報
    fp, err = get_single_file(FOLDERS['特売情報'], ['.csv'])
    if fp:
        df = pd.read_csv(fp, encoding='cp932').iloc[1:]
        df['商品コード'] = df['商品コード'].astype(str)
        df['特売数量'] = pd.to_numeric(df['特売数量'], errors='coerce').fillna(0)
        if 'デポ出庫日' in df.columns:
            df['日付'] = df['デポ出庫日'].apply(parse_date)
        raw_data['特売情報'] = df
        dates = df['日付'].dropna() if '日付' in df.columns else pd.Series()
        file_info['特売情報'] = {'file_name': fp.name, 'rows': len(df),
                               'min_date': dates.min() if len(dates) else None,
                               'max_date': dates.max() if len(dates) else None}
    else:
        file_info['特売情報'] = {'file_name': None}
    
    # 販売実績
    fp, err = get_single_file(FOLDERS['販売実績'], ['.xlsx'])
    if fp:
        try:
            df = pd.read_excel(fp, sheet_name='販売経過(25.11月)', header=2)
        except:
            df = pd.read_excel(fp, header=2)
        df['商品コード'] = df['商品コード'].astype(str)
        for col in ['25.10月', '25.9月', '25.8月']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        available = [c for c in ['25.10月', '25.9月', '25.8月'] if c in df.columns]
        df['過去3ヶ月平均'] = df[available].mean(axis=1) if available else 0
        df['日次予測'] = df['過去3ヶ月平均'] / 30
        raw_data['販売実績'] = df
        file_info['販売実績'] = {'file_name': fp.name, 'rows': len(df)}
    else:
        file_info['販売実績'] = {'file_name': None}
    
    # 製造予定
    fp, err = get_single_file(FOLDERS['製造予定'], ['.xlsx'])
    if err:
        errors.append(f"製造予定: {err}")
        return None, None, errors
    df = pd.read_excel(fp)
    df['商品コード'] = df['商品コード'].astype(str)
    if '入庫予定日' in df.columns:
        df['日付'] = df['入庫予定日'].apply(parse_date)
    raw_data['製造予定'] = df
    dates = df['日付'].dropna() if '日付' in df.columns else pd.Series()
    file_info['製造予定'] = {'file_name': fp.name, 'rows': len(df),
                           'min_date': dates.min() if len(dates) else None,
                           'max_date': dates.max() if len(dates) else None}
    
    # 製造実績
    fp, err = get_single_file(FOLDERS['製造実績'], ['.xlsx'])
    if err:
        errors.append(f"製造実績: {err}")
        return None, None, errors
    df = pd.read_excel(fp)
    df['商品コード'] = df['商品コード'].astype(str)
    if '伝票日付' in df.columns:
        df['日付'] = df['伝票日付'].apply(parse_date)
    raw_data['製造実績'] = df
    dates = df['日付'].dropna() if '日付' in df.columns else pd.Series()
    file_info['製造実績'] = {'file_name': fp.name, 'rows': len(df),
                           'min_date': dates.min() if len(dates) else None,
                           'max_date': dates.max() if len(dates) else None}
    
    return raw_data, file_info, []


def load_data_from_upload(uploaded_files):
    """アップロードからデータ読み込み（クラウド用）"""
    raw_data = {}
    file_info = {}
    errors = []
    
    # 出荷実績
    if uploaded_files.get('出荷実績'):
        df = pd.read_excel(uploaded_files['出荷実績'])
        df['商品コード'] = df['商品コード'].astype(str)
        if '納品日' in df.columns:
            df['日付'] = df['納品日'].apply(parse_date)
        raw_data['出荷実績'] = df
        dates = df['日付'].dropna() if '日付' in df.columns else pd.Series()
        file_info['出荷実績'] = {'file_name': uploaded_files['出荷実績'].name, 'rows': len(df),
                               'min_date': dates.min() if len(dates) else None,
                               'max_date': dates.max() if len(dates) else None}
    else:
        errors.append("出荷実績ファイルが必要です")
    
    # 特売情報
    if uploaded_files.get('特売情報'):
        df = pd.read_csv(uploaded_files['特売情報'], encoding='cp932').iloc[1:]
        df['商品コード'] = df['商品コード'].astype(str)
        df['特売数量'] = pd.to_numeric(df['特売数量'], errors='coerce').fillna(0)
        if 'デポ出庫日' in df.columns:
            df['日付'] = df['デポ出庫日'].apply(parse_date)
        raw_data['特売情報'] = df
        dates = df['日付'].dropna() if '日付' in df.columns else pd.Series()
        file_info['特売情報'] = {'file_name': uploaded_files['特売情報'].name, 'rows': len(df),
                               'min_date': dates.min() if len(dates) else None,
                               'max_date': dates.max() if len(dates) else None}
    else:
        file_info['特売情報'] = {'file_name': None}
    
    # 販売実績
    if uploaded_files.get('販売実績'):
        try:
            df = pd.read_excel(uploaded_files['販売実績'], sheet_name='販売経過(25.11月)', header=2)
        except:
            df = pd.read_excel(uploaded_files['販売実績'], header=2)
        df['商品コード'] = df['商品コード'].astype(str)
        for col in ['25.10月', '25.9月', '25.8月']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        available = [c for c in ['25.10月', '25.9月', '25.8月'] if c in df.columns]
        df['過去3ヶ月平均'] = df[available].mean(axis=1) if available else 0
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
            df['日付'] = df['入庫予定日'].apply(parse_date)
        raw_data['製造予定'] = df
        dates = df['日付'].dropna() if '日付' in df.columns else pd.Series()
        file_info['製造予定'] = {'file_name': uploaded_files['製造予定'].name, 'rows': len(df),
                               'min_date': dates.min() if len(dates) else None,
                               'max_date': dates.max() if len(dates) else None}
    else:
        errors.append("製造予定ファイルが必要です")
    
    # 製造実績
    if uploaded_files.get('製造実績'):
        df = pd.read_excel(uploaded_files['製造実績'])
        df['商品コード'] = df['商品コード'].astype(str)
        if '伝票日付' in df.columns:
            df['日付'] = df['伝票日付'].apply(parse_date)
        raw_data['製造実績'] = df
        dates = df['日付'].dropna() if '日付' in df.columns else pd.Series()
        file_info['製造実績'] = {'file_name': uploaded_files['製造実績'].name, 'rows': len(df),
                               'min_date': dates.min() if len(dates) else None,
                               'max_date': dates.max() if len(dates) else None}
    else:
        errors.append("製造実績ファイルが必要です")
    
    if errors:
        return None, None, errors
    return raw_data, file_info, []


def process_data(raw_data, file_info, date_filters):
    """データ処理"""
    all_products = {}
    
    def apply_filter(df, data_name):
        if df is None or len(df) == 0:
            return pd.DataFrame()
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
    
    ship_summary = pd.DataFrame({'商品コード': [], '出荷実績': []})
    if len(df_ship) > 0:
        ship_summary = df_ship.groupby('商品コード').agg({'売上数荷': 'sum'}).reset_index()
        ship_summary.columns = ['商品コード', '出荷実績']
    
    daily_ship = pd.DataFrame()
    if len(df_ship) > 0 and '日付' in df_ship.columns:
        daily_ship = df_ship.groupby('日付').agg({'売上数荷': 'sum'}).reset_index()
        daily_ship.columns = ['日付', '出荷実績']
    
    # 特売情報
    special_summary = pd.DataFrame({'商品コード': [], '特売予測': []})
    daily_special = pd.DataFrame()
    daily_normal_rate = 0
    
    if '特売情報' in raw_data and raw_data['特売情報'] is not None:
        df_special = apply_filter(raw_data['特売情報'], '特売情報')
        if len(df_special) > 0:
            special_summary = df_special.groupby('商品コード').agg({'特売数量': 'sum'}).reset_index()
            special_summary.columns = ['商品コード', '特売予測']
            if '日付' in df_special.columns:
                daily_special = df_special.groupby('日付').agg({'特売数量': 'sum'}).reset_index()
                daily_special.columns = ['日付', '特売予測']
    
    # 販売実績
    sales_summary = pd.DataFrame({'商品コード': [], '通常出荷予測': []})
    if '販売実績' in raw_data and raw_data['販売実績'] is not None:
        df_sales = raw_data['販売実績']
        if len(df_sales) > 0 and '日次予測' in df_sales.columns:
            sales_summary = df_sales[['商品コード', '日次予測']].copy()
            sales_summary.columns = ['商品コード', '通常出荷予測']
            daily_normal_rate = df_sales['日次予測'].sum()
    
    # 製造予定
    df_prod_plan = apply_filter(raw_data['製造予定'], '製造予定')
    prod_plan_summary = pd.DataFrame({'商品コード': [], '製造予定': []})
    if len(df_prod_plan) > 0:
        prod_plan_summary = df_prod_plan.groupby('商品コード').agg({'入庫予定数': 'sum'}).reset_index()
        prod_plan_summary.columns = ['商品コード', '製造予定']
    
    daily_prod_plan = pd.DataFrame()
    if len(df_prod_plan) > 0 and '日付' in df_prod_plan.columns:
        daily_prod_plan = df_prod_plan.groupby('日付').agg({'入庫予定数': 'sum'}).reset_index()
        daily_prod_plan.columns = ['日付', '製造予定']
    
    # 製造実績
    df_prod_actual = apply_filter(raw_data['製造実績'], '製造実績')
    prod_actual_summary = pd.DataFrame({'商品コード': [], '製造実績': []})
    if len(df_prod_actual) > 0:
        prod_actual_summary = df_prod_actual.groupby('商品コード').agg({'荷合数量': 'sum'}).reset_index()
        prod_actual_summary.columns = ['商品コード', '製造実績']
    
    daily_prod_actual = pd.DataFrame()
    if len(df_prod_actual) > 0 and '日付' in df_prod_actual.columns:
        daily_prod_actual = df_prod_actual.groupby('日付').agg({'荷合数量': 'sum'}).reset_index()
        daily_prod_actual.columns = ['日付', '製造実績']
    
    # マスタ統合
    if len(all_products) == 0:
        for _, row in raw_data['製造予定'].iterrows():
            code = str(row['商品コード'])
            if code not in all_products:
                all_products[code] = {'商品名': row.get('品名', ''), '規格': row.get('規格', '')}
    
    master = pd.DataFrame([{'商品コード': c, '商品名': i['商品名'], '規格': i['規格']} for c, i in all_products.items()])
    
    if len(master) == 0:
        return pd.DataFrame(), pd.DataFrame(), {}
    
    master = master.merge(ship_summary, on='商品コード', how='left')
    master = master.merge(special_summary, on='商品コード', how='left')
    master = master.merge(sales_summary, on='商品コード', how='left')
    master = master.merge(prod_plan_summary, on='商品コード', how='left')
    master = master.merge(prod_actual_summary, on='商品コード', how='left')
    
    for col in ['出荷実績', '特売予測', '通常出荷予測', '製造予定', '製造実績']:
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
        for df in [daily_ship, daily_special, daily_prod_plan, daily_prod_actual]:
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
                          '指示': '⬆️ 製造増加', '出荷予測': f"{r['出荷予測']:.0f}", '出荷実績': f"{r['出荷実績']:.0f}",
                          '製造予定': f"{r['製造予定']:.0f}", '製造実績': f"{r['製造実績']:.0f}"})
        elif r['出荷ズレ率'] < -th_ship:
            alerts.append({'優先度': '🟡 中', '商品コード': r['商品コード'], '商品名': r['商品名'],
                          '指示': '⬇️ 製造減少', '出荷予測': f"{r['出荷予測']:.0f}", '出荷実績': f"{r['出荷実績']:.0f}",
                          '製造予定': f"{r['製造予定']:.0f}", '製造実績': f"{r['製造実績']:.0f}"})
        if r['製造ズレ率'] < -th_prod and r['製造予定'] > 0:
            alerts.append({'優先度': '🔴 高', '商品コード': r['商品コード'], '商品名': r['商品名'],
                          '指示': '⚠️ 製造遅れ', '出荷予測': f"{r['出荷予測']:.0f}", '出荷実績': f"{r['出荷実績']:.0f}",
                          '製造予定': f"{r['製造予定']:.0f}", '製造実績': f"{r['製造実績']:.0f}"})
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
    st.success("📁 ローカルモード: Zドライブからデータを自動読み込み")
else:
    st.info("☁️ クラウドモード: ファイルをアップロードしてください")

st.markdown("---")

# データ読み込み
raw_data, file_info, errors = None, None, []

if IS_LOCAL:
    raw_data, file_info, errors = load_data_from_folder()
else:
    st.sidebar.header("📁 ファイルアップロード")
    st.sidebar.markdown("**必須ファイル（3つ）**")
    uploaded = {}
    uploaded['出荷実績'] = st.sidebar.file_uploader("① 出荷実績 (.xlsx)", type=['xlsx'], key='u1')
    uploaded['製造予定'] = st.sidebar.file_uploader("② 製造予定 (.xlsx)", type=['xlsx'], key='u4')
    uploaded['製造実績'] = st.sidebar.file_uploader("③ 製造実績 (.xlsx)", type=['xlsx'], key='u5')
    
    st.sidebar.markdown("**任意ファイル**")
    uploaded['特売情報'] = st.sidebar.file_uploader("④ 特売情報 (.csv)", type=['csv'], key='u2')
    uploaded['販売実績'] = st.sidebar.file_uploader("⑤ 販売実績 (.xlsx)", type=['xlsx'], key='u3')
    
    if uploaded['出荷実績'] and uploaded['製造予定'] and uploaded['製造実績']:
        raw_data, file_info, errors = load_data_from_upload(uploaded)
    else:
        st.warning("👈 サイドバーから必須ファイル3つをアップロードしてください")
        st.markdown("""
        ### 📋 必要なファイル
        
        | # | ファイル | 形式 | 必須 |
        |---|---------|------|------|
        | 1 | 出荷実績（出荷売上日記帳） | .xlsx | ✅ |
        | 2 | 製造予定（製造入庫予定一覧表） | .xlsx | ✅ |
        | 3 | 製造実績 | .xlsx | ✅ |
        | 4 | 特売情報 | .csv | 任意 |
        | 5 | 販売実績（本社販売実績） | .xlsx | 任意 |
        """)
        st.stop()

if errors:
    for e in errors:
        st.error(e)
    st.stop()

if raw_data is None:
    st.stop()

# サイドバー: 期間設定
st.sidebar.markdown("---")
st.sidebar.header("📅 期間設定")
date_filters = {}
for name in ['出荷実績', '特売情報', '製造予定', '製造実績']:
    info = file_info.get(name, {})
    min_d, max_d = info.get('min_date'), info.get('max_date')
    if min_d is not None and max_d is not None and pd.notna(min_d) and pd.notna(max_d):
        with st.sidebar.expander(f"{name}"):
            st.caption(f"{min_d.strftime('%m/%d')}〜{max_d.strftime('%m/%d')}")
            c1, c2 = st.columns(2)
            with c1:
                s = st.date_input("開始", value=min_d.date(), min_value=min_d.date(), max_value=max_d.date(), key=f"{name}_s")
            with c2:
                e = st.date_input("終了", value=max_d.date(), min_value=min_d.date(), max_value=max_d.date(), key=f"{name}_e")
            date_filters[name] = {'start': s, 'end': e}

st.sidebar.markdown("---")
st.sidebar.header("⚙️ アラート設定")
th_ship = st.sidebar.slider("出荷ズレ警告%", 10, 100, 30)
th_prod = st.sidebar.slider("製造ズレ警告%", 10, 100, 20)

# データ処理
master, daily_master, totals = process_data(raw_data, file_info, date_filters)
alerts_df = generate_alerts(master, th_ship, th_prod)

# サマリー
cols = st.columns(5)
cols[0].metric("商品数", f"{len(master):,}")
cols[1].metric("🔴 要対応", f"{len(alerts_df[alerts_df['優先度']=='🔴 高']) if len(alerts_df) else 0}件")
cols[2].metric("出荷実績", f"{totals.get('出荷実績', 0):,.0f}")
cols[3].metric("製造予定", f"{totals.get('製造予定', 0):,.0f}")
cols[4].metric("製造実績", f"{totals.get('製造実績', 0):,.0f}")

st.markdown("---")

# タブ
tab1, tab2, tab3, tab4 = st.tabs(["🚨 アラート", "📈 日別推移", "📊 分析", "📋 全商品"])

with tab1:
    st.markdown("### 🚨 製造指示アラート")
    if len(alerts_df) > 0:
        col1, col2 = st.columns(2)
        with col1:
            pf = st.multiselect("優先度", ['🔴 高', '🟡 中'], default=['🔴 高', '🟡 中'])
        with col2:
            inf = st.multiselect("指示", ['⬆️ 製造増加', '⬇️ 製造減少', '⚠️ 製造遅れ'], default=['⬆️ 製造増加', '⬇️ 製造減少', '⚠️ 製造遅れ'])
        filtered = alerts_df[alerts_df['優先度'].isin(pf) & alerts_df['指示'].isin(inf)]
        
        def hl(row):
            c = '#ff6b6b' if row['優先度'] == '🔴 高' else '#ffd93d'
            return [f'background-color:{c};color:#000;font-weight:bold'] * len(row)
        st.dataframe(filtered.style.apply(hl, axis=1), use_container_width=True, height=400)
        st.download_button("📥 CSV", filtered.to_csv(index=False).encode('utf-8-sig'), "alerts.csv")
    else:
        st.success("✅ アラートなし")

with tab2:
    st.markdown("### 📈 日別推移")
    if len(daily_master) > 0:
        view = st.radio("表示", ["日別", "累計"], horizontal=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 📦 出荷")
            fig = go.Figure()
            if view == "日別":
                fig.add_trace(go.Scatter(x=daily_master['日付'], y=daily_master['出荷予測'], name='予測', line=dict(color='lightblue')))
                fig.add_trace(go.Scatter(x=daily_master['日付'], y=daily_master['出荷実績'], name='実績', line=dict(color='#1f77b4')))
            else:
                fig.add_trace(go.Scatter(x=daily_master['日付'], y=daily_master['出荷予測_累計'], name='予測累計', fill='tozeroy', line=dict(color='lightblue')))
                fig.add_trace(go.Scatter(x=daily_master['日付'], y=daily_master['出荷実績_累計'], name='実績累計', line=dict(color='#1f77b4')))
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.markdown("#### 🏭 製造")
            fig = go.Figure()
            if view == "日別":
                fig.add_trace(go.Scatter(x=daily_master['日付'], y=daily_master['製造予定'], name='予定', line=dict(color='lightgreen')))
                fig.add_trace(go.Scatter(x=daily_master['日付'], y=daily_master['製造実績'], name='実績', line=dict(color='#2ca02c')))
            else:
                fig.add_trace(go.Scatter(x=daily_master['日付'], y=daily_master['製造予定_累計'], name='予定累計', fill='tozeroy', line=dict(color='lightgreen')))
                fig.add_trace(go.Scatter(x=daily_master['日付'], y=daily_master['製造実績_累計'], name='実績累計', line=dict(color='#2ca02c')))
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
        
        # ズレグラフ
        c1, c2 = st.columns(2)
        with c1:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=daily_master['日付'], y=daily_master['出荷ズレ'],
                                marker_color=np.where(daily_master['出荷ズレ'] >= 0, '#1f77b4', '#ff6b6b')))
            fig.add_hline(y=0, line_dash="dash")
            fig.update_layout(height=200, title="出荷ズレ")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=daily_master['日付'], y=daily_master['製造ズレ'],
                                marker_color=np.where(daily_master['製造ズレ'] >= 0, '#2ca02c', '#ff6b6b')))
            fig.add_hline(y=0, line_dash="dash")
            fig.update_layout(height=200, title="製造ズレ")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("日別データがありません")

with tab3:
    st.markdown("### 📊 出荷・製造分析")
    c1, c2 = st.columns(2)
    with c1:
        if len(master) > 0:
            top = master.nlargest(15, '出荷実績')
            fig = go.Figure()
            fig.add_trace(go.Bar(name='予測', x=top['商品名'].str[:10], y=top['出荷予測'], marker_color='lightblue'))
            fig.add_trace(go.Bar(name='実績', x=top['商品名'].str[:10], y=top['出荷実績'], marker_color='#1f77b4'))
            fig.update_layout(barmode='group', height=350, title="出荷TOP15", xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        if len(master) > 0:
            top = master.nlargest(15, '製造実績')
            fig = go.Figure()
            fig.add_trace(go.Bar(name='予定', x=top['商品名'].str[:10], y=top['製造予定'], marker_color='lightgreen'))
            fig.add_trace(go.Bar(name='実績', x=top['商品名'].str[:10], y=top['製造実績'], marker_color='#2ca02c'))
            fig.update_layout(barmode='group', height=350, title="製造TOP15", xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.markdown("### 📋 全商品データ")
    search = st.text_input("🔍 検索")
    cols_to_show = ['商品コード', '商品名', '出荷予測', '出荷実績', '出荷ズレ率', '製造予定', '製造実績', '製造ズレ率', '製造指示']
    display = master[[c for c in cols_to_show if c in master.columns]].copy()
    if search:
        display = display[display['商品名'].str.contains(search, na=False) | display['商品コード'].str.contains(search, na=False)]
    if '出荷ズレ率' in display.columns:
        display['出荷ズレ率'] = display['出荷ズレ率'].round(1)
    if '製造ズレ率' in display.columns:
        display['製造ズレ率'] = display['製造ズレ率'].round(1)
    st.dataframe(display, use_container_width=True, height=500)
    st.download_button("📥 CSV", display.to_csv(index=False).encode('utf-8-sig'), "products.csv")
