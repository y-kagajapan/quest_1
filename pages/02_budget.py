import streamlit as st
import pandas as pd
import os
from supabase import create_client # ★sqlite3を削除し、Supabaseを追加

# --- 1. 環境設定 ---
def get_db_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

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

st.header("💰 予算状況一覧")

user_role = st.session_state.get('role_id')
user_team = st.session_state.get('team_id')

try:
    supabase = get_db_connection()
    
    # --- Supabaseからデータを取得し、Pandasで集計する ---
    # 1. 必要なテーブルをすべて取得
    res_team = supabase.table("TB_team").select("*").execute()
    df_team = pd.DataFrame(res_team.data)
    
    res_budget = supabase.table("TB_budget").select("*").eq("fiscal_year", 2026).execute()
    df_budget = pd.DataFrame(res_budget.data)
    
    res_matter = supabase.table("TB_matter").select("*").eq("fiscal_year", 2026).eq("is_hidden", 0).execute()
    df_matter = pd.DataFrame(res_matter.data)

    # 2. 権限による絞り込み（本部管理者(4)以外は自部署のみ）
    if user_role != 4:
        df_team = df_team[df_team["team_id"] == user_team]

    # 3. 部署ごとに予算と案件額を集計
    data_list = []
    for _, row in df_team.iterrows():
        t_id = row["team_id"]
        t_name = row["team_name"]

        # 総予算の取得
        total_b = 0
        if not df_budget.empty:
            b_match = df_budget[df_budget["team_id"] == t_id]
            if not b_match.empty:
                # Noneの場合は0にする
                total_b = b_match.iloc[0]["total_budget"] or 0

        # 案件金額の集計（加賀さんのロジックを完全再現）
        appr_sum = 0
        appl_sum = 0
        if not df_matter.empty:
            m_match = df_matter[df_matter["team_id"] == t_id]
            # ステータス5,6は fixed_amount を合算
            appr_sum = m_match[m_match["status_id"].isin([5, 6])]["fixed_amount"].fillna(0).sum()
            # ステータス3,4は est_amount を合算
            appl_sum = m_match[m_match["status_id"].isin([3, 4])]["est_amount"].fillna(0).sum()

        data_list.append({
            "部署名": t_name,
            "総予算": total_b,
            "承認済_確定": appr_sum,
            "申請中_仮押さえ": appl_sum
        })

    df_raw = pd.DataFrame(data_list)

    # 4. 計算を行う（変数名を「予算残高」に統一）
    df = df_raw.copy()
    if not df.empty:
        df["予算残高"] = df["総予算"] - df["承認済_確定"]
        df["消費率_数値"] = (df["承認済_確定"] / df["総予算"].replace(0, 1)) * 100
    else:
        df = pd.DataFrame(columns=["部署名", "総予算", "承認済_確定", "申請中_仮押さえ", "予算残高", "消費率_数値"])

except Exception as e:
    st.error(f"データベース接続エラー: {e}")
    st.stop()

# --- 5. フィルター & 表示 ---
c1, c2, c3 = st.columns([2, 2, 2])
with c1:
    dept_options = ["すべて"] + df["部署名"].tolist() if user_role == 4 else df["部署名"].tolist()
    if not dept_options: # 空の対策
        dept_options = ["すべて"]
    selected_dept = st.selectbox("部署名選択", dept_options)
with c2:
    st.selectbox("項目名選択", ["すべて"], disabled=True)
with c3:
    st.write("")
    st.write("")
    alert_only = st.checkbox("80%以上のみ表示")

st.divider()

if not df.empty:
    # 整形表示用DF
    df_disp = df.copy()
    df_disp["消費率"] = df_disp["消費率_数値"].apply(lambda x: f"{int(x)}%") 
    df_disp["総予算_表示"] = df_disp["総予算"].apply(lambda x: f"{int(x):,}")
    df_disp["承認済_表示"] = df_disp["承認済_確定"].apply(lambda x: f"{int(x):,}")
    df_disp["申請中_表示"] = df_disp["申請中_仮押さえ"].apply(lambda x: f"{int(x):,}")
    df_disp["予算残高_表示"] = df_disp["予算残高"].apply(lambda x: f"△ {abs(int(x)):,}" if x < 0 else f"{int(x):,}")

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
else:
    st.info("データがありません。")
    final_df = pd.DataFrame()

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
        supabase = get_db_connection()
        
        # 1. 選択された部署の team_id を取得
        res_t = supabase.table("TB_team").select("team_id").eq("team_name", selected_dept).execute()
        
        if res_t.data:
            s_team_id = res_t.data[0]["team_id"]
            
            # 2. その team_id に紐づく案件を取得（除外案件 is_hidden=1 も含めて取得するロジックを継承）
            res_m = supabase.table("TB_matter").select("matter_id, matter_title, status_id, is_hidden, est_amount, fixed_amount").eq("team_id", s_team_id).eq("fiscal_year", 2026).execute()
            df_details = pd.DataFrame(res_m.data)

            if not df_details.empty:
                # 状況（ステータス）を日本語に変換
                df_details['ステータス'] = df_details['status_id'].map(status_name_map)

                # グレーアウト用の色付け関数
                def apply_detail_style(row):
                    if row.get('is_hidden') == 1:
                        return ['color: #a0a0a0; background-color: #f9f9f9; font-style: italic;'] * len(row)
                    return [''] * len(row)

                styled_details = df_details.style.apply(apply_detail_style, axis=1)

                st.dataframe(
                    styled_details, 
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
            else:
                st.write("この部署にはまだ案件がありません。")
        else:
            st.write("部署情報が見つかりません。")

    except Exception as e:
        st.error(f"内訳取得エラー: {e}")

# CSV出力
if not final_df.empty:
    csv = final_df.drop(columns=['hidden_num']).to_csv(index=False).encode('utf_8_sig')
    st.download_button("📥 CSV出力", data=csv, file_name='budget_report.csv', mime='text/csv')