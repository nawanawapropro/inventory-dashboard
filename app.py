import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime, timedelta

st.set_page_config(
    page_title="製造指示ダッシュボード",
    page_icon="🏭",
    layout="wide"
)

# ========================================
# フォルダ設定
# ========================================
BASE_DIR = Path(r"Z:\Users\fujinawa\Documents\進行中プロジェクト\味のちぬや\inventory_dashboard")
DATA_DIR = BASE_DIR / "data"

FOLDERS = {
    '出荷実績': DATA_DIR / "01_出荷実績",
    '特売情報': DATA_DIR / "02_特売情報",
    '販売実績': DATA_DIR / "03_販売実績",
    '製造予定': DATA_DIR / "04_製造予定",
    '製造実績': DATA_DIR / "05_製造実績",
}


def get_single_file(folder_path, extensions=['.xlsx', '.csv']):
    """フォルダ内の唯一のファイルを取得"""
    if not folder_path.exists():
        return None, f"フォルダが存在しません"
    files = []
    for ext in extensions:
        files.extend(list(folder_path.glob(f"*{ext}")))
    if len(files) == 0:
        return None, f"ファイルなし"
    elif len(files) > 1:
        return None, f"複数ファイル"
    return files[0], None


def create_folders_if_not_exist():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name, path in FOLDERS.items():
        path.mkdir(parents=True, exist_ok=True)


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
        # 8桁数字 (20251120)
        if value.isdigit() and len(value) == 8:
            try:
                return pd.to_datetime(value, format='%Y%m%d')
            except:
                pass
        # その他の形式
        try:
            return pd.to_datetime(value)
        except:
            return pd.NaT
    
    # datetime型
    if isinstance(value, (datetime, pd.Timestamp)):
        return pd.Timestamp(value)
    
    return pd.NaT


def load_raw_data():
    """生データを読み込み"""
    raw_data = {}
    file_info = {}
    errors = []
    
    # 1. 出荷実績（必須）
    file_path, err = get_single_file(FOLDERS['出荷実績'], ['.xlsx'])
    if err:
        errors.append(f"① 出荷実績: {err}")
        return None, None, errors
    
    df = pd.read_excel(file_path)
    df['商品コード'] = df['商品コード'].astype(str)
    
    # 日付変換（整数形式対応）
    if '納品日' in df.columns:
        df['日付'] = df['納品日'].apply(parse_date)
    
    raw_data['出荷実績'] = df
    
    dates = df['日付'].dropna() if '日付' in df.columns else pd.Series()
    file_info['出荷実績'] = {
        'file_name': file_path.name,
        'rows': len(df),
        'min_date': dates.min() if len(dates) > 0 else None,
        'max_date': dates.max() if len(dates) > 0 else None,
        'date_column': '納品日',
    }
    
    # 2. 特売情報（任意）
    file_path, err = get_single_file(FOLDERS['特売情報'], ['.csv'])
    if file_path:
        df = pd.read_csv(file_path, encoding='cp932')
        # 1行目はフィールド定義なのでスキップ
        df = df.iloc[1:]
        df['商品コード'] = df['商品コード'].astype(str)
        df['特売数量'] = pd.to_numeric(df['特売数量'], errors='coerce').fillna(0)
        
        # 日付変換
        if 'デポ出庫日' in df.columns:
            df['日付'] = df['デポ出庫日'].apply(parse_date)
        
        raw_data['特売情報'] = df
        
        dates = df['日付'].dropna() if '日付' in df.columns else pd.Series()
        file_info['特売情報'] = {
            'file_name': file_path.name,
            'rows': len(df),
            'min_date': dates.min() if len(dates) > 0 else None,
            'max_date': dates.max() if len(dates) > 0 else None,
            'date_column': 'デポ出庫日',
        }
    else:
        file_info['特売情報'] = {'file_name': None, 'rows': 0, 'min_date': None, 'max_date': None, 'date_column': None}
    
    # 3. 販売実績（任意）
    file_path, err = get_single_file(FOLDERS['販売実績'], ['.xlsx'])
    if file_path:
        try:
            df = pd.read_excel(file_path, sheet_name='販売経過(25.11月)', header=2)
        except:
            # シート名が違う場合は最初のシートを読む
            df = pd.read_excel(file_path, header=2)
        
        df['商品コード'] = df['商品コード'].astype(str)
        month_cols = ['25.10月', '25.9月', '25.8月']
        for col in month_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # 過去3ヶ月の平均を計算
        available_cols = [c for c in month_cols if c in df.columns]
        if available_cols:
            df['過去3ヶ月平均'] = df[available_cols].mean(axis=1)
        else:
            df['過去3ヶ月平均'] = 0
        df['日次予測'] = df['過去3ヶ月平均'] / 30
        
        raw_data['販売実績'] = df
        
        file_info['販売実績'] = {
            'file_name': file_path.name,
            'rows': len(df),
            'min_date': None,
            'max_date': None,
            'date_column': '月次データ（8〜10月平均）',
        }
    else:
        file_info['販売実績'] = {'file_name': None, 'rows': 0, 'min_date': None, 'max_date': None, 'date_column': None}
    
    # 4. 製造予定（必須）
    file_path, err = get_single_file(FOLDERS['製造予定'], ['.xlsx'])
    if err:
        errors.append(f"④ 製造予定: {err}")
        return None, None, errors
    
    df = pd.read_excel(file_path)
    df['商品コード'] = df['商品コード'].astype(str)
    
    # 日付変換（整数形式対応）
    if '入庫予定日' in df.columns:
        df['日付'] = df['入庫予定日'].apply(parse_date)
    
    raw_data['製造予定'] = df
    
    dates = df['日付'].dropna() if '日付' in df.columns else pd.Series()
    file_info['製造予定'] = {
        'file_name': file_path.name,
        'rows': len(df),
        'min_date': dates.min() if len(dates) > 0 else None,
        'max_date': dates.max() if len(dates) > 0 else None,
        'date_column': '入庫予定日',
    }
    
    # 5. 製造実績（必須）
    file_path, err = get_single_file(FOLDERS['製造実績'], ['.xlsx'])
    if err:
        errors.append(f"⑤ 製造実績: {err}")
        return None, None, errors
    
    df = pd.read_excel(file_path)
    df['商品コード'] = df['商品コード'].astype(str)
    
    # 日付変換（整数形式対応）
    if '伝票日付' in df.columns:
        df['日付'] = df['伝票日付'].apply(parse_date)
    
    raw_data['製造実績'] = df
    
    dates = df['日付'].dropna() if '日付' in df.columns else pd.Series()
    file_info['製造実績'] = {
        'file_name': file_path.name,
        'rows': len(df),
        'min_date': dates.min() if len(dates) > 0 else None,
        'max_date': dates.max() if len(dates) > 0 else None,
        'date_column': '伝票日付',
    }
    
    return raw_data, file_info, []


def process_data_with_individual_filters(raw_data, file_info, date_filters):
    """各ファイルごとの期間フィルタを適用してデータ処理"""
    
    all_products = {}
    daily_raw = {}  # 商品×日付の生データ保持
    
    def apply_filter(df, data_name):
        if df is None or len(df) == 0:
            return pd.DataFrame()
        if '日付' not in df.columns:
            return df.copy()
        
        filters = date_filters.get(data_name, {})
        start = filters.get('start')
        end = filters.get('end')
        
        if start and end:
            mask = (df['日付'] >= pd.Timestamp(start)) & (df['日付'] <= pd.Timestamp(end))
            return df[mask].copy()
        return df.copy()
    
    # 1. 出荷実績
    df_ship = apply_filter(raw_data['出荷実績'], '出荷実績')
    
    for _, row in df_ship.iterrows():
        code = str(row['商品コード'])
        if code not in all_products:
            all_products[code] = {'商品名': row.get('商品名１', ''), '規格': row.get('商品名２', '')}
    
    ship_summary = pd.DataFrame({'商品コード': [], '出荷実績': []})
    if len(df_ship) > 0:
        ship_summary = df_ship.groupby('商品コード').agg({'売上数荷': 'sum'}).reset_index()
        ship_summary.columns = ['商品コード', '出荷実績']
    
    # 日別（全体）
    daily_ship = pd.DataFrame()
    if len(df_ship) > 0 and '日付' in df_ship.columns:
        daily_ship = df_ship.groupby('日付').agg({'売上数荷': 'sum'}).reset_index()
        daily_ship.columns = ['日付', '出荷実績']
    
    # 商品×日付（商品詳細用）
    if len(df_ship) > 0 and '日付' in df_ship.columns:
        daily_raw['出荷実績'] = df_ship.groupby(['商品コード', '日付']).agg({'売上数荷': 'sum'}).reset_index()
        daily_raw['出荷実績'].columns = ['商品コード', '日付', '出荷実績']
    
    # 2. 特売情報
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
                
                # 商品×日付
                daily_raw['特売予測'] = df_special.groupby(['商品コード', '日付']).agg({'特売数量': 'sum'}).reset_index()
                daily_raw['特売予測'].columns = ['商品コード', '日付', '特売予測']
    
    # 3. 販売実績
    sales_summary = pd.DataFrame({'商品コード': [], '通常出荷予測': []})
    
    if '販売実績' in raw_data and raw_data['販売実績'] is not None:
        df_sales = raw_data['販売実績']
        if len(df_sales) > 0 and '日次予測' in df_sales.columns:
            sales_summary = df_sales[['商品コード', '日次予測']].copy()
            sales_summary.columns = ['商品コード', '通常出荷予測']
            daily_normal_rate = df_sales['日次予測'].sum()
    
    # 4. 製造予定
    df_prod_plan = apply_filter(raw_data['製造予定'], '製造予定')
    
    prod_plan_summary = pd.DataFrame({'商品コード': [], '製造予定': []})
    if len(df_prod_plan) > 0:
        prod_plan_summary = df_prod_plan.groupby('商品コード').agg({'入庫予定数': 'sum'}).reset_index()
        prod_plan_summary.columns = ['商品コード', '製造予定']
    
    daily_prod_plan = pd.DataFrame()
    if len(df_prod_plan) > 0 and '日付' in df_prod_plan.columns:
        daily_prod_plan = df_prod_plan.groupby('日付').agg({'入庫予定数': 'sum'}).reset_index()
        daily_prod_plan.columns = ['日付', '製造予定']
        
        # 商品×日付
        daily_raw['製造予定'] = df_prod_plan.groupby(['商品コード', '日付']).agg({'入庫予定数': 'sum'}).reset_index()
        daily_raw['製造予定'].columns = ['商品コード', '日付', '製造予定']
    
    # 5. 製造実績
    df_prod_actual = apply_filter(raw_data['製造実績'], '製造実績')
    
    prod_actual_summary = pd.DataFrame({'商品コード': [], '製造予定数_実績ファイル': [], '製造実績': []})
    if len(df_prod_actual) > 0:
        prod_actual_summary = df_prod_actual.groupby('商品コード').agg({
            'ケース数': 'sum',
            '荷合数量': 'sum'
        }).reset_index()
        prod_actual_summary.columns = ['商品コード', '製造予定数_実績ファイル', '製造実績']
    
    daily_prod_actual = pd.DataFrame()
    if len(df_prod_actual) > 0 and '日付' in df_prod_actual.columns:
        daily_prod_actual = df_prod_actual.groupby('日付').agg({'荷合数量': 'sum'}).reset_index()
        daily_prod_actual.columns = ['日付', '製造実績']
        
        # 商品×日付
        daily_raw['製造実績'] = df_prod_actual.groupby(['商品コード', '日付']).agg({'荷合数量': 'sum'}).reset_index()
        daily_raw['製造実績'].columns = ['商品コード', '日付', '製造実績']
    
    # マスタ統合
    if len(all_products) == 0:
        # 出荷実績が空の場合、製造予定から商品を取得
        for _, row in raw_data['製造予定'].iterrows():
            code = str(row['商品コード'])
            if code not in all_products:
                all_products[code] = {'商品名': row.get('品名', ''), '規格': row.get('規格', '')}
    
    master = pd.DataFrame([
        {'商品コード': code, '商品名': info['商品名'], '規格': info['規格']}
        for code, info in all_products.items()
    ])
    
    if len(master) == 0:
        st.error("商品データが見つかりません")
        return pd.DataFrame(), pd.DataFrame(), {}, {}
    
    master = master.merge(ship_summary, on='商品コード', how='left')
    master = master.merge(special_summary, on='商品コード', how='left')
    master = master.merge(sales_summary, on='商品コード', how='left')
    master = master.merge(prod_plan_summary, on='商品コード', how='left')
    master = master.merge(prod_actual_summary, on='商品コード', how='left')
    
    for col in ['出荷実績', '特売予測', '通常出荷予測', '製造予定', '製造予定数_実績ファイル', '製造実績']:
        if col in master.columns:
            master[col] = master[col].fillna(0)
    
    master['出荷予測'] = master['特売予測'] + master['通常出荷予測']
    master['出荷ズレ'] = master['出荷実績'] - master['出荷予測']
    master['出荷ズレ率'] = np.where(master['出荷予測'] != 0, master['出荷ズレ'] / master['出荷予測'] * 100, 0)
    master['製造ズレ'] = master['製造実績'] - master['製造予定']
    master['製造ズレ率'] = np.where(master['製造予定'] != 0, master['製造ズレ'] / master['製造予定'] * 100, 0)
    
    def get_instruction(row):
        instructions = []
        if row['出荷ズレ率'] > 30:
            instructions.append("⬆️ 出荷増→製造増")
        elif row['出荷ズレ率'] < -30:
            instructions.append("⬇️ 出荷減→製造減")
        if row['製造ズレ率'] < -20:
            instructions.append("⚠️ 製造遅れ")
        elif row['製造ズレ率'] > 20:
            instructions.append("✅ 製造順調")
        return ' / '.join(instructions) if instructions else "➡️ 様子見"
    
    master['製造指示'] = master.apply(get_instruction, axis=1)
    
    # 日別データ統合
    all_dates = set()
    for df in [daily_ship, daily_special, daily_prod_plan, daily_prod_actual]:
        if len(df) > 0 and '日付' in df.columns:
            all_dates.update(df['日付'].dropna().tolist())
    
    daily_master = pd.DataFrame()
    if all_dates:
        date_range = pd.date_range(start=min(all_dates), end=max(all_dates), freq='D')
        daily_master = pd.DataFrame({'日付': date_range})
        
        if len(daily_ship) > 0:
            daily_master = daily_master.merge(daily_ship, on='日付', how='left')
        if len(daily_special) > 0:
            daily_master = daily_master.merge(daily_special, on='日付', how='left')
        if len(daily_prod_plan) > 0:
            daily_master = daily_master.merge(daily_prod_plan, on='日付', how='left')
        if len(daily_prod_actual) > 0:
            daily_master = daily_master.merge(daily_prod_actual, on='日付', how='left')
        
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
    
    # フィルタ後の集計値
    filtered_totals = {
        '出荷実績': master['出荷実績'].sum(),
        '特売予測': master['特売予測'].sum(),
        '製造予定': master['製造予定'].sum(),
        '製造実績': master['製造実績'].sum(),
    }
    
    return master.sort_values('商品コード').reset_index(drop=True), daily_master, filtered_totals, daily_raw


def get_product_daily_data(product_code, daily_raw, sales_df=None):
    """商品別の日別データを取得"""
    all_dates = set()
    
    for key, df in daily_raw.items():
        if len(df) > 0:
            prod_df = df[df['商品コード'] == product_code]
            if len(prod_df) > 0:
                all_dates.update(prod_df['日付'].dropna().tolist())
    
    if not all_dates:
        return pd.DataFrame()
    
    date_range = pd.date_range(start=min(all_dates), end=max(all_dates), freq='D')
    result = pd.DataFrame({'日付': date_range})
    
    # 出荷実績
    if '出荷実績' in daily_raw:
        prod_ship = daily_raw['出荷実績'][daily_raw['出荷実績']['商品コード'] == product_code]
        if len(prod_ship) > 0:
            result = result.merge(prod_ship[['日付', '出荷実績']], on='日付', how='left')
    
    # 特売予測
    if '特売予測' in daily_raw:
        prod_special = daily_raw['特売予測'][daily_raw['特売予測']['商品コード'] == product_code]
        if len(prod_special) > 0:
            result = result.merge(prod_special[['日付', '特売予測']], on='日付', how='left')
    
    # 製造予定
    if '製造予定' in daily_raw:
        prod_plan = daily_raw['製造予定'][daily_raw['製造予定']['商品コード'] == product_code]
        if len(prod_plan) > 0:
            result = result.merge(prod_plan[['日付', '製造予定']], on='日付', how='left')
    
    # 製造実績
    if '製造実績' in daily_raw:
        prod_actual = daily_raw['製造実績'][daily_raw['製造実績']['商品コード'] == product_code]
        if len(prod_actual) > 0:
            result = result.merge(prod_actual[['日付', '製造実績']], on='日付', how='left')
    
    # 通常出荷予測（販売実績から）
    daily_normal = 0
    if sales_df is not None and len(sales_df) > 0:
        prod_sales = sales_df[sales_df['商品コード'] == product_code]
        if len(prod_sales) > 0 and '日次予測' in prod_sales.columns:
            daily_normal = prod_sales['日次予測'].values[0]
    
    for col in ['出荷実績', '特売予測', '製造予定', '製造実績']:
        if col not in result.columns:
            result[col] = 0
        result[col] = result[col].fillna(0)
    
    result['通常出荷予測'] = daily_normal
    result['出荷予測'] = result['特売予測'] + result['通常出荷予測']
    result['出荷ズレ'] = result['出荷実績'] - result['出荷予測']
    result['製造ズレ'] = result['製造実績'] - result['製造予定']
    
    # 累計
    result['出荷実績_累計'] = result['出荷実績'].cumsum()
    result['出荷予測_累計'] = result['出荷予測'].cumsum()
    result['製造予定_累計'] = result['製造予定'].cumsum()
    result['製造実績_累計'] = result['製造実績'].cumsum()
    
    return result


def generate_alerts(master, threshold_ship, threshold_prod):
    alerts = []
    for _, row in master.iterrows():
        if row['出荷ズレ率'] > threshold_ship:
            alerts.append({
                '優先度': '🔴 高', '商品コード': row['商品コード'], '商品名': row['商品名'],
                '指示': '⬆️ 製造増加', '理由': f"出荷+{row['出荷ズレ率']:.0f}%",
                '出荷予測': f"{row['出荷予測']:.0f}", '出荷実績': f"{row['出荷実績']:.0f}",
                '製造予定': f"{row['製造予定']:.0f}", '製造実績': f"{row['製造実績']:.0f}",
            })
        elif row['出荷ズレ率'] < -threshold_ship:
            alerts.append({
                '優先度': '🟡 中', '商品コード': row['商品コード'], '商品名': row['商品名'],
                '指示': '⬇️ 製造減少検討', '理由': f"出荷{row['出荷ズレ率']:.0f}%",
                '出荷予測': f"{row['出荷予測']:.0f}", '出荷実績': f"{row['出荷実績']:.0f}",
                '製造予定': f"{row['製造予定']:.0f}", '製造実績': f"{row['製造実績']:.0f}",
            })
        if row['製造ズレ率'] < -threshold_prod and row['製造予定'] > 0:
            alerts.append({
                '優先度': '🔴 高', '商品コード': row['商品コード'], '商品名': row['商品名'],
                '指示': '⚠️ 製造遅れ対応', '理由': f"製造{row['製造ズレ率']:.0f}%",
                '出荷予測': f"{row['出荷予測']:.0f}", '出荷実績': f"{row['出荷実績']:.0f}",
                '製造予定': f"{row['製造予定']:.0f}", '製造実績': f"{row['製造実績']:.0f}",
            })
    
    df = pd.DataFrame(alerts)
    if len(df) > 0:
        df['sort_key'] = df['優先度'].map({'🔴 高': 0, '🟡 中': 1})
        df = df.sort_values('sort_key').drop('sort_key', axis=1)
    return df


# ========================================
# アプリ本体
# ========================================

st.title("🏭 製造指示ダッシュボード")
st.markdown("**目的**: 出荷と製造のズレを分析し、製造数量の指示を的確に出す")
st.markdown("---")

create_folders_if_not_exist()

# データ読み込み
raw_data, file_info, errors = load_raw_data()

if errors:
    st.error("### ❌ データ読み込みエラー")
    for err in errors:
        st.error(err)
    st.stop()

# ========================================
# サイドバー: 各ファイルの期間設定
# ========================================
st.sidebar.header("📅 各ファイルの期間設定")

date_filters = {}

for data_name in ['出荷実績', '特売情報', '製造予定', '製造実績']:
    info = file_info.get(data_name, {})
    
    if info.get('file_name') is None:
        continue
    
    with st.sidebar.expander(f"📁 {data_name}", expanded=True):
        st.caption(f"**ファイル:** {info['file_name']}")
        st.caption(f"**行数:** {info['rows']:,}行")
        
        min_d = info.get('min_date')
        max_d = info.get('max_date')
        
        if min_d is not None and max_d is not None and pd.notna(min_d) and pd.notna(max_d):
            st.caption(f"**データ範囲:** {min_d.strftime('%Y/%m/%d')} 〜 {max_d.strftime('%Y/%m/%d')}")
            
            col1, col2 = st.columns(2)
            with col1:
                start = st.date_input(
                    "開始",
                    value=min_d.date(),
                    min_value=min_d.date(),
                    max_value=max_d.date(),
                    key=f"{data_name}_start"
                )
            with col2:
                end = st.date_input(
                    "終了",
                    value=max_d.date(),
                    min_value=min_d.date(),
                    max_value=max_d.date(),
                    key=f"{data_name}_end"
                )
            
            date_filters[data_name] = {'start': start, 'end': end}
            
            days = (end - start).days + 1
            st.info(f"📆 使用期間: **{days}日間**")
        else:
            st.warning("日付データなし")

st.sidebar.markdown("---")
st.sidebar.header("⚙️ アラート設定")
threshold_ship = st.sidebar.slider("出荷ズレ警告（%）", 10, 100, 30)
threshold_prod = st.sidebar.slider("製造ズレ警告（%）", 10, 100, 20)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 データ再読込", type="primary"):
    st.rerun()

# ========================================
# データ処理
# ========================================
master, daily_master, filtered_totals, daily_raw = process_data_with_individual_filters(raw_data, file_info, date_filters)
alerts_df = generate_alerts(master, threshold_ship, threshold_prod)

# ========================================
# ヘッダー: ファイル別期間サマリー
# ========================================
st.markdown("### 📅 使用データ期間")

cols = st.columns(4)
data_items = [
    ('出荷実績', '📦'),
    ('特売情報', '🏷️'),
    ('製造予定', '📋'),
    ('製造実績', '🏭'),
]

for i, (name, icon) in enumerate(data_items):
    with cols[i]:
        info = file_info.get(name, {})
        filters = date_filters.get(name, {})
        
        if info.get('file_name'):
            start = filters.get('start')
            end = filters.get('end')
            
            if start and end:
                days = (end - start).days + 1
                st.metric(
                    f"{icon} {name}",
                    f"{start.strftime('%m/%d')}〜{end.strftime('%m/%d')}",
                    f"{days}日間"
                )
            else:
                st.metric(f"{icon} {name}", "日付なし", "⚠️")
        else:
            st.metric(f"{icon} {name}", "ファイルなし", "➖")

st.markdown("---")

# サマリー
st.markdown("### 📊 サマリー（選択期間）")

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("商品数", f"{len(master):,}")
with col2:
    high_alerts = len(alerts_df[alerts_df['優先度'] == '🔴 高']) if len(alerts_df) > 0 else 0
    st.metric("🔴 要対応", f"{high_alerts}件")
with col3:
    st.metric("出荷実績計", f"{filtered_totals['出荷実績']:,.0f}")
with col4:
    st.metric("製造予定計", f"{filtered_totals['製造予定']:,.0f}")
with col5:
    st.metric("製造実績計", f"{filtered_totals['製造実績']:,.0f}")

st.markdown("---")

# ========================================
# タブ
# ========================================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🚨 製造指示アラート",
    "📈 日別推移",
    "🔍 商品詳細",
    "📊 出荷分析",
    "🏭 製造分析",
    "📋 全商品データ"
])

# タブ1: アラート
with tab1:
    st.markdown("### 🚨 製造指示アラート")
    
    st.info("""
    **📖 見方** — 🔴高: 今すぐ対応 / 🟡中: 検討が必要
    """)
    
    if len(alerts_df) > 0:
        col1, col2 = st.columns(2)
        with col1:
            priority_filter = st.multiselect("優先度", ['🔴 高', '🟡 中'], default=['🔴 高', '🟡 中'])
        with col2:
            instruction_filter = st.multiselect("指示", ['⬆️ 製造増加', '⬇️ 製造減少検討', '⚠️ 製造遅れ対応'], 
                                                default=['⬆️ 製造増加', '⬇️ 製造減少検討', '⚠️ 製造遅れ対応'])
        
        filtered = alerts_df[alerts_df['優先度'].isin(priority_filter) & alerts_df['指示'].isin(instruction_filter)]
        
        st.markdown(f"**{len(filtered)}件**")
        
        def highlight(row):
            if row['優先度'] == '🔴 高':
                return ['background-color: #ff6b6b; color: #000; font-weight: bold'] * len(row)
            return ['background-color: #ffd93d; color: #000; font-weight: bold'] * len(row)
        
        st.dataframe(filtered.style.apply(highlight, axis=1), use_container_width=True, height=500)
        
        csv = filtered.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 CSV", data=csv, file_name="alerts.csv", mime="text/csv")
    else:
        st.success("✅ アラートなし")

# タブ2: 日別推移
with tab2:
    st.markdown("### 📈 日別推移（全体）")
    
    if len(daily_master) > 0:
        st.info("💡 日別/累計を切り替えて、予測と実績のズレを確認できます")
        
        view_mode = st.radio("表示", ["日別", "累計"], horizontal=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📦 出荷")
            if view_mode == "日別":
                fig1 = go.Figure()
                fig1.add_trace(go.Scatter(x=daily_master['日付'], y=daily_master['出荷予測'], name='予測', line=dict(color='lightblue')))
                fig1.add_trace(go.Scatter(x=daily_master['日付'], y=daily_master['出荷実績'], name='実績', line=dict(color='#1f77b4')))
            else:
                fig1 = go.Figure()
                fig1.add_trace(go.Scatter(x=daily_master['日付'], y=daily_master['出荷予測_累計'], name='予測累計', fill='tozeroy', line=dict(color='lightblue')))
                fig1.add_trace(go.Scatter(x=daily_master['日付'], y=daily_master['出荷実績_累計'], name='実績累計', line=dict(color='#1f77b4')))
            fig1.update_layout(height=350)
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            st.markdown("#### 🏭 製造")
            if view_mode == "日別":
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=daily_master['日付'], y=daily_master['製造予定'], name='予定', line=dict(color='lightgreen')))
                fig2.add_trace(go.Scatter(x=daily_master['日付'], y=daily_master['製造実績'], name='実績', line=dict(color='#2ca02c')))
            else:
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=daily_master['日付'], y=daily_master['製造予定_累計'], name='予定累計', fill='tozeroy', line=dict(color='lightgreen')))
                fig2.add_trace(go.Scatter(x=daily_master['日付'], y=daily_master['製造実績_累計'], name='実績累計', line=dict(color='#2ca02c')))
            fig2.update_layout(height=350)
            st.plotly_chart(fig2, use_container_width=True)
        
        # ズレ
        st.markdown("---")
        st.markdown("#### 📉 日別ズレ")
        
        col1, col2 = st.columns(2)
        with col1:
            fig3 = go.Figure()
            fig3.add_trace(go.Bar(x=daily_master['日付'], y=daily_master['出荷ズレ'],
                                  marker_color=np.where(daily_master['出荷ズレ'] >= 0, '#1f77b4', '#ff6b6b')))
            fig3.add_hline(y=0, line_dash="dash")
            fig3.update_layout(height=250, title="出荷ズレ（実績−予測）")
            st.plotly_chart(fig3, use_container_width=True)
        
        with col2:
            fig4 = go.Figure()
            fig4.add_trace(go.Bar(x=daily_master['日付'], y=daily_master['製造ズレ'],
                                  marker_color=np.where(daily_master['製造ズレ'] >= 0, '#2ca02c', '#ff6b6b')))
            fig4.add_hline(y=0, line_dash="dash")
            fig4.update_layout(height=250, title="製造ズレ（実績−予定）")
            st.plotly_chart(fig4, use_container_width=True)
        
        # データテーブル
        st.markdown("---")
        st.markdown("#### 📋 日別データ")
        display = daily_master[['日付', '出荷予測', '出荷実績', '出荷ズレ', '製造予定', '製造実績', '製造ズレ']].copy()
        display['日付'] = display['日付'].dt.strftime('%Y/%m/%d')
        for c in ['出荷予測', '出荷実績', '出荷ズレ', '製造予定', '製造実績', '製造ズレ']:
            display[c] = display[c].round(0).astype(int)
        st.dataframe(display, use_container_width=True, height=250)
        
        csv = display.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 日別CSV", data=csv, file_name="daily.csv", mime="text/csv")
    else:
        st.warning("日別データがありません")

# タブ3: 商品詳細
with tab3:
    st.markdown("### 🔍 商品詳細")
    
    # 商品検索・選択
    col1, col2 = st.columns([1, 2])
    with col1:
        search_term = st.text_input("🔎 商品検索", placeholder="商品名またはコード")
    
    # フィルタリング
    if search_term:
        filtered_products = master[
            master['商品名'].str.contains(search_term, na=False) | 
            master['商品コード'].str.contains(search_term, na=False)
        ]
    else:
        filtered_products = master
    
    if len(filtered_products) == 0:
        st.warning("該当する商品がありません")
    else:
        # 商品選択
        product_options = [f"{row['商品コード']} - {row['商品名']}" for _, row in filtered_products.iterrows()]
        
        with col2:
            selected_product = st.selectbox("商品を選択", product_options)
        
        if selected_product:
            selected_code = selected_product.split(" - ")[0]
            product_row = master[master['商品コード'] == selected_code].iloc[0]
            
            # 商品サマリー
            st.markdown("---")
            st.markdown(f"#### 📦 {product_row['商品名']}")
            st.caption(f"商品コード: {product_row['商品コード']} / 規格: {product_row['規格']}")
            
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("出荷予測", f"{product_row['出荷予測']:.0f}")
            with col2:
                st.metric("出荷実績", f"{product_row['出荷実績']:.0f}")
            with col3:
                color = "normal" if abs(product_row['出荷ズレ率']) < 30 else "inverse"
                st.metric("出荷ズレ率", f"{product_row['出荷ズレ率']:.1f}%", delta_color=color)
            with col4:
                st.metric("製造予定", f"{product_row['製造予定']:.0f}")
            with col5:
                st.metric("製造実績", f"{product_row['製造実績']:.0f}")
            
            # 製造指示
            instruction = product_row['製造指示']
            if "⬆️" in instruction or "⚠️" in instruction:
                st.error(f"**製造指示:** {instruction}")
            elif "⬇️" in instruction:
                st.warning(f"**製造指示:** {instruction}")
            else:
                st.success(f"**製造指示:** {instruction}")
            
            # 日別推移グラフ
            st.markdown("---")
            st.markdown("#### 📈 日別推移")
            
            sales_df = raw_data.get('販売実績')
            product_daily = get_product_daily_data(selected_code, daily_raw, sales_df)
            
            if len(product_daily) > 0:
                view_mode_product = st.radio("表示モード", ["日別", "累計"], horizontal=True, key="product_view")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("##### 📦 出荷")
                    fig = go.Figure()
                    if view_mode_product == "日別":
                        fig.add_trace(go.Scatter(x=product_daily['日付'], y=product_daily['出荷予測'], name='予測', line=dict(color='lightblue')))
                        fig.add_trace(go.Scatter(x=product_daily['日付'], y=product_daily['出荷実績'], name='実績', line=dict(color='#1f77b4')))
                    else:
                        fig.add_trace(go.Scatter(x=product_daily['日付'], y=product_daily['出荷予測_累計'], name='予測累計', fill='tozeroy', line=dict(color='lightblue')))
                        fig.add_trace(go.Scatter(x=product_daily['日付'], y=product_daily['出荷実績_累計'], name='実績累計', line=dict(color='#1f77b4')))
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    st.markdown("##### 🏭 製造")
                    fig = go.Figure()
                    if view_mode_product == "日別":
                        fig.add_trace(go.Scatter(x=product_daily['日付'], y=product_daily['製造予定'], name='予定', line=dict(color='lightgreen')))
                        fig.add_trace(go.Scatter(x=product_daily['日付'], y=product_daily['製造実績'], name='実績', line=dict(color='#2ca02c')))
                    else:
                        fig.add_trace(go.Scatter(x=product_daily['日付'], y=product_daily['製造予定_累計'], name='予定累計', fill='tozeroy', line=dict(color='lightgreen')))
                        fig.add_trace(go.Scatter(x=product_daily['日付'], y=product_daily['製造実績_累計'], name='実績累計', line=dict(color='#2ca02c')))
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, use_container_width=True)
                
                # ズレグラフ
                col1, col2 = st.columns(2)
                with col1:
                    fig = go.Figure()
                    fig.add_trace(go.Bar(x=product_daily['日付'], y=product_daily['出荷ズレ'],
                                        marker_color=np.where(product_daily['出荷ズレ'] >= 0, '#1f77b4', '#ff6b6b')))
                    fig.add_hline(y=0, line_dash="dash")
                    fig.update_layout(height=200, title="出荷ズレ")
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    fig = go.Figure()
                    fig.add_trace(go.Bar(x=product_daily['日付'], y=product_daily['製造ズレ'],
                                        marker_color=np.where(product_daily['製造ズレ'] >= 0, '#2ca02c', '#ff6b6b')))
                    fig.add_hline(y=0, line_dash="dash")
                    fig.update_layout(height=200, title="製造ズレ")
                    st.plotly_chart(fig, use_container_width=True)
                
                # データテーブル
                st.markdown("---")
                st.markdown("#### 📋 日別データ")
                display = product_daily[['日付', '出荷予測', '出荷実績', '出荷ズレ', '製造予定', '製造実績', '製造ズレ']].copy()
                display['日付'] = display['日付'].dt.strftime('%Y/%m/%d')
                for c in ['出荷予測', '出荷実績', '出荷ズレ', '製造予定', '製造実績', '製造ズレ']:
                    display[c] = display[c].round(0).astype(int)
                st.dataframe(display, use_container_width=True, height=200)
                
                csv = display.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 商品日別CSV", data=csv, file_name=f"product_{selected_code}.csv", mime="text/csv")
            else:
                st.info("この商品の日別データはありません")

# タブ4: 出荷分析
with tab4:
    st.markdown("### 📊 出荷分析")
    
    if len(master) > 0:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 📦 出荷実績 TOP20")
            top = master.nlargest(20, '出荷実績')
            fig = go.Figure()
            fig.add_trace(go.Bar(name='予測', x=top['商品名'].str[:12], y=top['出荷予測'], marker_color='lightblue'))
            fig.add_trace(go.Bar(name='実績', x=top['商品名'].str[:12], y=top['出荷実績'], marker_color='#1f77b4'))
            fig.update_layout(barmode='group', height=400, xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("#### 📉 出荷ズレ率分布")
            fig = px.histogram(master[master['出荷ズレ率'].between(-200, 200)], x='出荷ズレ率', nbins=50)
            fig.add_vline(x=threshold_ship, line_dash="dash", line_color="red", annotation_text=f"+{threshold_ship}%")
            fig.add_vline(x=-threshold_ship, line_dash="dash", line_color="red", annotation_text=f"-{threshold_ship}%")
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        # 出荷ズレTOP
        st.markdown("---")
        st.markdown("#### ⚠️ 出荷ズレが大きい商品")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**📈 予測より多い（製造増加検討）**")
            over = master[master['出荷ズレ率'] > 0].nlargest(10, '出荷ズレ率')[['商品コード', '商品名', '出荷予測', '出荷実績', '出荷ズレ率']]
            over['出荷ズレ率'] = over['出荷ズレ率'].round(1)
            st.dataframe(over, use_container_width=True, height=300)
        
        with col2:
            st.markdown("**📉 予測より少ない（製造減少検討）**")
            under = master[master['出荷ズレ率'] < 0].nsmallest(10, '出荷ズレ率')[['商品コード', '商品名', '出荷予測', '出荷実績', '出荷ズレ率']]
            under['出荷ズレ率'] = under['出荷ズレ率'].round(1)
            st.dataframe(under, use_container_width=True, height=300)

# タブ5: 製造分析
with tab5:
    st.markdown("### 🏭 製造分析")
    
    if len(master) > 0:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🏭 製造実績 TOP20")
            top = master.nlargest(20, '製造実績')
            fig = go.Figure()
            fig.add_trace(go.Bar(name='予定', x=top['商品名'].str[:12], y=top['製造予定'], marker_color='lightgreen'))
            fig.add_trace(go.Bar(name='実績', x=top['商品名'].str[:12], y=top['製造実績'], marker_color='#2ca02c'))
            fig.update_layout(barmode='group', height=400, xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("#### 📉 製造ズレ率分布")
            prod_f = master[(master['製造予定'] > 0) & master['製造ズレ率'].between(-200, 200)]
            fig = px.histogram(prod_f, x='製造ズレ率', nbins=50, color_discrete_sequence=['forestgreen'])
            fig.add_vline(x=-threshold_prod, line_dash="dash", line_color="red", annotation_text=f"-{threshold_prod}%（遅れ）")
            fig.add_vline(x=threshold_prod, line_dash="dash", line_color="orange", annotation_text=f"+{threshold_prod}%")
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        # 製造ズレTOP
        st.markdown("---")
        st.markdown("#### ⚠️ 製造ズレが大きい商品")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**⚠️ 製造遅れ（予定より少ない）**")
            behind = master[(master['製造予定'] > 0) & (master['製造ズレ率'] < 0)].nsmallest(10, '製造ズレ率')[['商品コード', '商品名', '製造予定', '製造実績', '製造ズレ率']]
            behind['製造ズレ率'] = behind['製造ズレ率'].round(1)
            st.dataframe(behind, use_container_width=True, height=300)
        
        with col2:
            st.markdown("**✅ 製造順調（予定より多い）**")
            ahead = master[(master['製造予定'] > 0) & (master['製造ズレ率'] > 0)].nlargest(10, '製造ズレ率')[['商品コード', '商品名', '製造予定', '製造実績', '製造ズレ率']]
            ahead['製造ズレ率'] = ahead['製造ズレ率'].round(1)
            st.dataframe(ahead, use_container_width=True, height=300)

# タブ6: 全商品
with tab6:
    st.markdown("### 📋 全商品データ")
    
    search = st.text_input("🔍 検索（商品名・コード）")
    
    cols = ['商品コード', '商品名', '出荷予測', '出荷実績', '出荷ズレ率', '製造予定', '製造実績', '製造ズレ率', '製造指示']
    display = master[cols].copy()
    
    if search:
        display = display[display['商品名'].str.contains(search, na=False) | display['商品コード'].str.contains(search, na=False)]
    
    display['出荷ズレ率'] = display['出荷ズレ率'].round(1)
    display['製造ズレ率'] = display['製造ズレ率'].round(1)
    
    st.markdown(f"**{len(display)}件**")
    st.dataframe(display, use_container_width=True, height=500)
    
    csv = display.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 全商品CSV", data=csv, file_name="all_products.csv", mime="text/csv")
