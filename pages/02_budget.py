import streamlit as st
import sqlite3
import pandas as pd
import os

# --- 1. 環境設定 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(current_dir, "../database.db")

if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
    st.switch_page("login.py")
    st.stop()

# 2. ページ設定
st.set_page_config(layout="wide", page_title="予算管理システム")

# --- 1. 標準ナビゲーションの徹底排除 ---
st.markdown(
    """
    <style>
        /* 標準のナビゲーションを非表示 */
        [data-testid="stSidebarNav"] {display: none;}
        
        /* 余白を詳細画面に合わせて1remに削減 */
        section[data-testid="stSidebar"] > div {
            padding-top: 1rem !important;
        }

        /* タイトルのフォントサイズを微調整し、1行に収める */
        [data-testid="stSidebar"] h1 {
            font-size: 1.5rem !important; 
            white-space: nowrap;          /* 改行を禁止 */
            overflow: hidden;             /* はみ出し防止 */
            text-overflow: ellipsis;      /* 長すぎる場合は「...」 */
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# 3. サイドバー
with st.sidebar:
    st.title("開発管理統合システム")
    p_name = st.session_state.get('post_name', '')
    st.write(f"👤 {st.session_state.user_name} {p_name}")
    st.divider()

    # 1. 案件詳細・登録（全員共通）
    if st.button("🆕 案件詳細・登録", use_container_width=True):
        st.switch_page("pages/01_details.py")

    # 2. 予算管理（一般社員 role_id=2 以外にのみ表示）
    if st.session_state.get('role_id') != 2:
        if st.button("📊 予算管理", use_container_width=True):
            st.switch_page("pages/02_budget.py")
            
    st.divider()
    if st.button("🚪 ログアウト", use_container_width=True):
        st.session_state.clear()
        st.switch_page("login.py")

# --- 4. メインコンテンツロジック ---

def get_db_connection():
    return sqlite3.connect(db_path, check_same_thread=False)

st.header("💰 予算状況一覧")

# デバッグ用：開発一部の承認済案件のナマデータを見る
# conn = get_db_connection()
# check = pd.read_sql("SELECT matter_id, status_id, fixed_amount FROM TB_matter WHERE team_id = 1", conn)
# st.write("デバッグ用データチェック:", check)
# conn.close()

user_role = st.session_state.get('role_id')
user_team = st.session_state.get('team_id')

try:
    conn = get_db_connection()
    
    # 権限による絞り込み（本部管理者(4)以外は自部署のみ）
    where_clause = "WHERE B.fiscal_year = 2026"
    params = []
    if user_role != 4:
        where_clause += " AND T.team_id = ?"
        params.append(user_team)

    # 最新ステータス定義に基づいた集計
    # 💡 部署ごとに「確定額」と「申請中」を先に計算するクエリ
    # 💡 サブクエリを使って「重複」を物理的に発生させないクエリ
    query = f"""
    SELECT 
        T.team_name AS 部署名,
        IFNULL(B.total_budget, 0) AS 総予算,
        IFNULL(M.approved_sum, 0) AS 承認済_確定,
        IFNULL(M.applying_sum, 0) AS 申請中_仮押さえ
    FROM TB_team T
    LEFT JOIN TB_budget B ON T.team_id = B.team_id AND B.fiscal_year = 2026
    LEFT JOIN (
        SELECT 
            team_id,
            -- ✅ ステータス5(承認済)と6(完了)を「確定」として合算
            SUM(CASE WHEN status_id IN (5, 6) THEN fixed_amount ELSE 0 END) AS approved_sum,
            -- ✅ ステータス3(課長承認待ち)と4(本部確認待ち)のみを「申請中」とする
            SUM(CASE WHEN status_id IN (3, 4) THEN est_amount ELSE 0 END) AS applying_sum
        FROM TB_matter
        -- ✅ ここで is_hidden = 0 を徹底（削除案件は計算から完全に除外）
        WHERE is_hidden = 0 AND fiscal_year = 2026
        GROUP BY team_id
    ) M ON T.team_id = M.team_id
    {where_clause}
    """
    
    # 1. データを読み込む
    df_raw = pd.read_sql(query, conn, params=params)
    conn.close()

    # 2. 計算を行う（変数名を「予算残高」に統一）
    df = df_raw.copy()
    df["予算残高"] = df["総予算"] - df["承認済_確定"]
    df["消費率_数値"] = (df["承認済_確定"] / df["総予算"].replace(0, 1)) * 100

except Exception as e:
    st.error(f"データベース接続エラー: {e}")
    st.stop()

# --- 5. フィルター & 表示 ---
c1, c2, c3 = st.columns([2, 2, 2])
with c1:
    dept_options = ["すべて"] + df["部署名"].tolist() if user_role == 4 else df["部署名"].tolist()
    selected_dept = st.selectbox("部署名選択", dept_options)
with c2:
    st.selectbox("項目名選択", ["すべて"], disabled=True)
with c3:
    st.write("")
    st.write("")
    alert_only = st.checkbox("80%以上のみ表示")

st.divider()

# 整形表示用DF
df_disp = df.copy()
df_disp["消費率"] = df_disp["消費率_数値"].apply(lambda x: f"{int(x)}%") 
df_disp["総予算_表示"] = df_disp["総予算"].apply(lambda x: f"{x:,}")
df_disp["承認済_表示"] = df_disp["承認済_確定"].apply(lambda x: f"{x:,}")
df_disp["申請中_表示"] = df_disp["申請中_仮押さえ"].apply(lambda x: f"{x:,}")
df_disp["予算残高_表示"] = df_disp["予算残高"].apply(lambda x: f"△ {abs(x):,}" if x < 0 else f"{x:,}")

final_df = df_disp[["部署名", "総予算_表示", "承認済_表示", "申請中_表示", "予算残高_表示", "消費率", "消費率_数値"]]
final_df.columns = ["部署名", "総予算", "承認済（確定）", "申請中（仮押さえ）", "予算残高", "消費率", "hidden_num"]

if selected_dept != "すべて":
    final_df = final_df[final_df["部署名"] == selected_dept]
if alert_only:
    final_df = final_df[final_df["hidden_num"] >= 80]

def apply_row_style(row):
    styles = [''] * len(row)
    color = None
    if row['hidden_num'] >= 100: color = 'red'
    elif row['hidden_num'] >= 80: color = 'orange'
    if color:
        styles[0] = f'color: {color}; font-weight: bold;'
        styles[5] = f'color: {color}; font-weight: bold;'
    return styles

st.dataframe(
    final_df.style.apply(apply_row_style, axis=1), 
    use_container_width=True, 
    hide_index=True, 
    column_order=("部署名", "総予算", "承認済（確定）", "申請中（仮押さえ）", "予算残高", "消費率")
)

# --- 6. ここからが「内訳」の追加コード ---
st.divider() # 区切り線
st.subheader(f"🔍 {selected_dept} の予算内訳（案件別）")

if selected_dept == "すべて":
    st.info("左上の「部署名選択」で部署を選ぶと、ここに案件ごとの内訳が表示されます。")
else:
    # 案件一覧と同じ日本語名を定義
    status_name_map = {
        1: "⏳ 一時保存", 2: "↩️ 差し戻し", 3: "👤 課長承認待ち", 
        4: "🏢 本部確認待ち", 5: "✅ 承認済", 6: "🏁 完了", 7: "❌ 却下"
    }

    try:
        conn = get_db_connection()
        # 💡 is_hidden も忘れずに取得（現在のコードで入っていますね）
        detail_query = """
            SELECT matter_id, matter_title, status_id, is_hidden, est_amount, fixed_amount
            FROM TB_matter 
            WHERE team_id = (SELECT team_id FROM TB_team WHERE team_name = ?)
              AND fiscal_year = 2026
        """
        df_details = pd.read_sql(detail_query, conn, params=(selected_dept,))
        conn.close()

        # 1. 状況（ステータス）を日本語に変換
        df_details['ステータス'] = df_details['status_id'].map(status_name_map)

        # 💡 2. グレーアウト用の色付け関数をここで定義
        def apply_detail_style(row):
            if row.get('is_hidden') == 1:
                # 文字を薄いグレーにする
                return ['color: #a0a0a0; background-color: #f9f9f9; font-style: italic;'] * len(row)
            return [''] * len(row)

        # 💡 3. スタイルを適用したデータ（styled_details）を作る
        styled_details = df_details.style.apply(apply_detail_style, axis=1)

        # 💡 4. st.dataframe に styled_details を渡す
        st.dataframe(
            styled_details, # ここを df_details から変更！
            use_container_width=True,
            hide_index=True,
            column_order=("matter_id", "matter_title", "ステータス", "est_amount", "fixed_amount"),
            column_config={
                "matter_id": "案件番号",
                "matter_title": "案件名",
                "ステータス": "状況",
                "est_amount": st.column_config.NumberColumn("概算予算", format="¥%,.0f"),
                "fixed_amount": st.column_config.NumberColumn("実績額（確定）", format="¥%,.0f"),
            }
        )
    except Exception as e:
        st.error(f"内訳取得エラー: {e}")

# CSV出力
csv = final_df.drop(columns=['hidden_num']).to_csv(index=False).encode('utf_8_sig')
st.download_button("📥 CSV出力", data=csv, file_name='budget_report.csv', mime='text/csv')