import streamlit as st
import sqlite3
import pandas as pd
import os
import time
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta

# --- 言語設定を日本語にする ---
st.set_page_config(layout="wide", page_title="開発管理統合システム")

st.markdown("""
    <style>
    /* 1. 入力欄やテキストエリアが「無効」の時の文字色を強制的に青にする */
    input:disabled, textarea:disabled, [data-baseweb="select"] [aria-disabled="true"] {
        -webkit-text-fill-color: #0000ff !important; 
        color: #0000ff !important;
        opacity: 1 !important; 
    }

    /* 2. スライダーなどの数値表示部分も青くする */
    .stSlider [data-disabled="true"] {
        color: #0000ff !important;
    }

    /* 3. ラベル（項目名）を黒く太くして、背景とのコントラストを上げる */
    .stWidgetLabel p {
        color: #000000 !important;
        font-weight: bold !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- 1. 環境設定 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(current_dir, "../database.db")

# --- 2. 門番 & セッションの再構築 ---
if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
    st.switch_page("login.py")
    st.stop()

# スタッフ情報をデータベースから確実に取得する
if "user_name" not in st.session_state or st.session_state.user_name == st.session_state.get('user_id'):
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        # TB_IDテーブルの役職カラム名「post_id」を使用して取得
        cur.execute("""
            SELECT T2.staff_name, T1.team_id, T1.post_id, T3.post_name
            FROM TB_ID T1 
            JOIN TB_staff T2 ON T1.staff_id = T2.staff_id 
            LEFT JOIN TB_post T3 ON T1.post_id = T3.post_id
            WHERE T1.user_id = ?
        """, (st.session_state.get('user_id'),))
        res = cur.fetchone()
        if res:
            st.session_state.user_name = res[0] 
            st.session_state.team_id = res[1]
            st.session_state.role_id = res[2] 
            st.session_state.post_name = res[3]  # ここで「役職名」をセッションに保存
        if res:
            # 取得したスタッフ名をセット
            st.session_state.user_name = res[0] 
            st.session_state.team_id = res[1]
            st.session_state.role_id = res[2] 
        conn.close()
    except Exception as e:
        st.error(f"スタッフ情報の取得に失敗しました: {e}")

# セッション情報の復旧
if "user_name" not in st.session_state:
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT T2.staff_name, T1.team_id 
            FROM TB_ID T1 
            JOIN TB_staff T2 ON T1.staff_id = T2.staff_id 
            WHERE T1.user_id = ?
        """, (st.session_state.get('user_id'),))
        res = cur.fetchone()
        if res:
            st.session_state.user_name = res[0]
            st.session_state.team_id = res[1]
        conn.close()
    except:
        pass

# --- 3. 関数：データ処理 ---
def get_db_connection():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def save_matter(data, is_new=True):
    conn = get_db_connection()
    cur = conn.cursor()
    now_str = datetime.now().strftime('%Y/%m/%d %H:%M')
    try:
        if is_new:
            cur.execute("SELECT matter_id FROM TB_matter WHERE fiscal_year = 2026 AND team_id = ? ORDER BY matter_id DESC LIMIT 1", (st.session_state.team_id,))
            last_record = cur.fetchone()
            new_num = int(last_record['matter_id'].split('-')[-1]) + 1 if last_record else 1
            new_id = f"2026-D{st.session_state.team_id}-{new_num:03}"
            cur.execute("""
                INSERT INTO TB_matter (matter_id, fiscal_year, matter_title, team_id, user_id, purpose, summary, detail, category_id, est_man_hours, est_amount, status_id, progress_rate, start_date, end_date, monthly_report, remarks, item_id, budget_amount, fixed_amount, last_updated, is_hidden)
                VALUES (?, 2026, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, 1, ?, ?, ?, 0)
            """, (new_id, data['title'], st.session_state.team_id, st.session_state.user_id, data['purpose'], data['summary'], data['detail'], data['cat_id'], data['man_hours'], data['amount'], data['status'], data['s_date'], data['e_date'], data['report'], data['remarks'], data['budget'], data['fixed'], now_str))
        else:
            cur.execute("""
                UPDATE TB_matter SET matter_title=?, purpose=?, summary=?, detail=?, category_id=?, est_man_hours=?, est_amount=?, status_id=?, start_date=?, end_date=?, progress_rate=?, monthly_report=?, remarks=?, budget_amount=?, fixed_amount=?, last_updated=? WHERE matter_id=?
            """, (data['title'], data['purpose'], data['summary'], data['detail'], data['cat_id'], data['man_hours'], data['amount'], data['status'], data['s_date'], data['e_date'], data['progress'], data['report'], data['remarks'], data['budget'], data['fixed'], now_str, data['id']))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"保存エラー: {e}")
        return False
    finally:
        conn.close()

def get_budget_remaining(team_id):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # 2026年度固定、所属ID（team_id）に紐づく残高を計算するSQL
    query = """
        SELECT 
            b.total_budget - IFNULL(SUM(m.est_amount), 0) AS remaining
        FROM TB_budget b
        LEFT JOIN TB_matter m ON b.team_id = m.team_id AND b.fiscal_year = m.fiscal_year
        AND m.is_hidden = 0  -- 除外案件は計算に入れない
        WHERE b.team_id = ? AND b.fiscal_year = 2026;
    """
    cur.execute(query, (team_id,))
    res = cur.fetchone()
    conn.close()
    return res[0] if res else 0

# --- 4. サイドバー ---
st.markdown("<style>[data-testid='stSidebarNav'] {display: none;}</style>", unsafe_allow_html=True)
with st.sidebar:
    st.title("開発管理統合システム")
    
    # 佐藤、大内などの「スタッフ名」を優先して表示
    u_name = st.session_state.get('user_name', '未取得')
    p_name = st.session_state.get('post_name', '')
    
    # 二つをくっつけて表示
    st.write(f"👤 {u_name} {p_name}")
    st.divider()

    if st.session_state.get('edit_mode'):
        if st.button("🏠 一覧に戻る", key="sb_back_unique", use_container_width=True):
            st.session_state.edit_mode = None
            st.rerun()
    else:
        if st.button("🔄 案件詳細・登録", key="sb_refresh_unique", use_container_width=True): 
            st.rerun()

    # 権限チェック：post_id(role_id) が 1(課長) または 4(本部) の場合のみ表示
    current_role = st.session_state.get('role_id')
    if current_role in [1, 4]:
        if st.button("📊 予算管理", key="sb_budget_unique", use_container_width=True): 
            st.switch_page("pages/02_budget.py")
    
    st.divider()
    if st.button("🚪 ログアウト", key="sb_logout_unique", use_container_width=True):
        st.session_state.clear()
        st.switch_page("login.py")

# --- 5. メインロジック ---
if not st.session_state.get('edit_mode'):
    st.header("📋 案件一覧")

    status_name_map = {
        1: "⏳ 一時保存",
        2: "↩️ 差し戻し",
        3: "👤 課長承認待ち",
        4: "🏢 本部確認待ち",
        5: "✅ 承認済",
        6: "🏁 完了",
        7: "❌ 却下"
    }
    
    # データ取得
    # --- 5. メインロジック（データ取得部分） ---
    conn = get_db_connection()
    
    # SQLクエリ：マスターテーブルを結合（JOIN）して名前を取得するように強化
    # --- 5. メインロジック（データ取得部分） ---
    conn = get_db_connection()
    
    # SQLクエリ：カラム名は英語のまま取得する
    base_query = """
        SELECT 
            M.matter_id, M.fiscal_year, M.matter_title, T.team_name, S.staff_name,
            M.purpose, M.summary, M.last_updated, M.status_id, M.team_id,
            M.end_date, M.progress_rate,
            M.is_hidden
        FROM TB_matter M
        LEFT JOIN TB_team T ON M.team_id = T.team_id
        LEFT JOIN TB_ID I ON M.user_id = I.user_id
        LEFT JOIN TB_staff S ON I.staff_id = S.staff_id
    """

    # --- 権限に応じたデータ取得（修正版） ---
    role_id = st.session_state.get('role_id')

    if role_id == 4:
        # 【本部】 全部署の全案件を取得
        df = pd.read_sql(base_query, conn)
    elif role_id == 1:
        # 【課長】 自部署（team_id）の全員分を取得
        query = base_query + " WHERE M.team_id = ?"
        df = pd.read_sql(query, conn, params=(st.session_state.team_id,))
    else:
        # 【担当者】 自分の分（user_id）だけ取得
        query = base_query + " WHERE M.user_id = ?" 
        df = pd.read_sql(query, conn, params=(st.session_state.user_id,))

    # ステータス名を日本語に変換
    df['status_name'] = df['status_id'].map(status_name_map)

    df.loc[df['is_hidden'] == 1, 'status_name'] = "🗑️ 削除"
    
    conn.close()

    # --- 1. 検索・絞り込み ---
    with st.expander("🔍 検索・絞り込み"):
        c_s1, c_s2 = st.columns(2)
        sk = c_s1.text_input("キーワード検索")
        status_map = {1:"新規", 2:"差し戻し", 3:"部署承認中", 4:"本部回議中", 5:"最終承認済"}
        ss = c_s2.multiselect("ステータス", options=list(status_map.keys()), format_func=lambda x: status_map[x])

    # フィルタリング
    df_display = df.copy()
    if sk:
        df_display = df_display[df_display['matter_title'].str.contains(sk, case=False, na=False) | df_display['matter_id'].astype(str).str.contains(sk, case=False, na=False)]
    if ss:
        df_display = df_display[df_display['status_id'].isin(ss)]

    # --- 2. 期限超過・実績更新のアラート ---
    today_dt = datetime.now()
    today_str_slash = today_dt.strftime('%Y/%m/%d')
    today_str_hyphen = today_dt.strftime('%Y-%m-%d')

    if st.session_state.get('last_alert_date') != today_str_hyphen:
        # 💡 overdue_df の判定条件に「is_hidden == 0」を追加します
        overdue_df = df[
            (df['end_date'] < today_str_slash) & 
            (df['progress_rate'] < 100) & 
            (df['is_hidden'] == 0)  # ✅ これで除外済み案件を無視します
        ]
        
        if not overdue_df.empty:
            st.error(f"⚠️ **期限超過のアラート**: 完了予定日を過ぎた未完了案件が {len(overdue_df)} 件あります。進捗状況を確認してください。")
            if st.button("❌ 了解"):
                st.session_state.last_alert_date = today_str_hyphen
                st.rerun()

    # --- 3. 一覧表示（ハイライトと日本語化を統合） ---
    def highlight_todo(row):
        # 1. 除外案件はグレー（最優先）
        if row.get('is_hidden') == 1:
            return ['color: #a0a0a0; background-color: #f0f0f0; font-style: italic;'] * len(row)

        # 2. 100%完了案件：エメラルドグリーンで「達成」を強調
        if row['progress_rate'] == 100:
            return ['background-color: #c6f6d5; color: #22543d; font-weight: bold; text-decoration: line-through; border: 1px solid #38a169;'] * len(row)

        role = st.session_state.get('role_id')
        status = row['status_id']
        today_str = datetime.now().strftime('%Y/%m/%d')
    
        # 最終更新のチェック（48時間以上前を境界とする）
        # 1. 境界線となる日時の算出（2日以上前）
        limit_time = (datetime.now() - timedelta(days=2)).strftime('%Y/%m/%d %H:%M:%S')
        
        # 2. 各種フラグの判定
        is_overdue = str(row['end_date']) < today_str       # 期限切れか
        is_outdated = str(row['last_updated']) < limit_time # 放置されているか
        
        # 3. 【警告】の実行判定
        # 💡 条件1：期限切れ または 放置
        # 💡 条件2：ステータスが 3(課長承認待ち) 〜 5(承認済) であること（一時保存や差し戻し、完了を除外）
        if (is_overdue or is_outdated) and (3 <= status <= 5):
            return ['background-color: #ffffcc; font-weight: bold; border: 1px solid #ffcc00'] * len(row)
        
        # 3. 【警告】期限超過は全役職共通で「黄色」
        if str(row['end_date']) < today_str and row['progress_rate'] < 100:
            return ['background-color: #ffffcc; font-weight: bold; border: 1px solid #ffcc00'] * len(row)

        # 3. 役職ごとの「自分のボール（仕事）」だけを「青色」にする
        style_blue = ['background-color: #e6f3ff; border: 1px solid #b3d9ff'] * len(row)

        if role == 1: # 課長の場合 承認待ち(3)に加えて、差し戻し(2)の時も青く光らせる
            if status in [2, 3]: 
                return style_blue
        elif role == 4 and status == 4:  # 本部：本部確認待ちのみ
            return style_blue
        elif role == 2 and status == 2:  # 担当者：差し戻し(2)のみ！
            return style_blue
            
        # 4. 上記以外は色なし
        return [''] * len(row)

    # スタイル適用（df_displayに対して行う）
    styled_df = df_display.style.apply(highlight_todo, axis=1)
    
    # 唯一の表示部分：ここで項目名を日本語に変え、不要なIDを隠します
    # 1. 直接 st.dataframe を呼び出す (event = は不要)
    st.dataframe(
        styled_df, 
        use_container_width=True, 
        hide_index=True, 
        selection_mode="single-row", 
        on_select="rerun",
        key="matter_table", # ★重要：これで選択状態を管理します
        column_config={
            "matter_id": "案件番号",
            "fiscal_year": None,
            "matter_title": "案件名",
            "team_name": "部署名",
            "staff_name": "担当者",
            "status_name": "ステータス",
            "purpose": None,
            "summary": None,
            "last_updated": "最終更新",
            "est_amount": st.column_config.NumberColumn("概算予算", format="¥%,.0f"),
            "progress_rate": st.column_config.NumberColumn("進捗", format="%d%%"),
            "end_date": "期限日",
            "status_id": None,
            "team_id": None,
            "is_hidden": None
        }
    )

    # 2. 選択された時の処理（テーブルの外側に書く）
    if st.session_state.matter_table.selection.rows:
        selected_row_index = st.session_state.matter_table.selection.rows[0]
        st.session_state.selected_id = df_display.iloc[selected_row_index]['matter_id']
        st.session_state.edit_mode = 'edit'
        st.rerun()

    # 担当者の時だけ「新規登録」ボタンを出す
    if st.session_state.get('role_id') == 2:
        if st.button("➕ 新規登録"):
            st.session_state.edit_mode = 'new'
            st.rerun()

    if st.session_state.matter_table.selection.rows:
        selected_row_index = st.session_state.matter_table.selection.rows[0]
        st.session_state.selected_id = df_display.iloc[selected_row_index]['matter_id']
        st.session_state.edit_mode = 'edit'
        st.rerun()

# --- 6. 詳細入力画面 ---
else:
    is_new = st.session_state.edit_mode == 'new'
    
    # 1. rowの初期値
    row = {
        "matter_title":"", "purpose":"", "summary":"", "detail":"", "category_id":1, 
        "est_man_hours":0, "est_amount":0, "status_id":1, "progress_rate":0, 
        "start_date":date.today().strftime("%Y/%m/%d"), 
        "end_date":(date.today() + relativedelta(months=3)).strftime("%Y/%m/%d"), 
        "monthly_report":"", "remarks":"", 
        "budget_amount":0, "fixed_amount":0, "user_id": st.session_state.user_id, "team_id": st.session_state.team_id
    }
    
    # 2. 既存データの読み込み（ここで一旦 budget_amount が 0 になります）
    if not is_new:
        conn = get_db_connection()
        res = conn.execute("SELECT * FROM TB_matter WHERE matter_id=?", (st.session_state.selected_id,)).fetchone()
        if res:
            row.update(dict(res))
        conn.close()

    # 3. ★総合の予算を取得して、確定予算に【上書き】する★
    target_team_id = row.get('team_id')
    if target_team_id:
        conn = get_db_connection()
        res_budget = conn.execute(
            "SELECT total_budget FROM TB_budget WHERE team_id = ? AND fiscal_year = 2026", 
            (target_team_id,)
        ).fetchone()
        
        if res_budget:
            row['budget_amount'] = res_budget['total_budget']
        conn.close()

    # 変数の確定
    user_role = st.session_state.get('role_id')
    status = row['status_id']
    # --- 編集ロックの判定ロジック ---
    user_role = st.session_state.get('role_id')
    status = row['status_id']
    
    # 基本はロック状態(True)から開始
    is_core_disabled = True     # 案件名や予算など（申請内容）
    is_progress_disabled = True # 進捗・報告・備考（実績報告）
    
    # 1. 担当者(2)の場合
    if user_role == 2: # 担当者の場合
        if is_new or status in [1, 2]: # 新規 or 差し戻し
            is_core_disabled = False
            is_progress_disabled = False
        elif status == 5: # 最終承認済
            is_core_disabled = True     # 申請内容はロック
            is_progress_disabled = False # 進捗報告は入力OK！

    # --- 画面表示 ---
    display_id = "新規" if is_new else st.session_state.get('selected_id', '不明')
    st.subheader(f"📝 案件詳細: {display_id}")
    
    
    st.divider()

    with st.form("edit_form"):
        
        # --- A. 承認後はロックしたい「コア項目」 (is_core_disabled) ---
        col_top1, col_top2 = st.columns([1, 1]) 
        m_title = col_top1.text_input("案件名", value=row['matter_title'], disabled=is_core_disabled, max_chars=50)
        m_purpose = col_top2.text_input("目的", value=row['purpose'], disabled=is_core_disabled, max_chars=100)
        m_summary = st.text_input("概要", value=row['summary'], disabled=is_core_disabled, max_chars=100)
        m_detail = st.text_area("詳細", value=row['detail'], disabled=is_core_disabled, max_chars=1000, height=150)
        
        g1, g2, g3 = st.columns(3)
        m_cat = g1.selectbox("カテゴリ", [1,2,3,4], format_func=lambda x: ["新規","保守","改修","スポット"][x-1], index=row['category_id']-1, disabled=is_core_disabled)
        m_hours = g2.number_input("工数", value=row['est_man_hours'], disabled=is_core_disabled)
        # --- 予算のリアルタイム・チェック機能 ---
        m_amount = g3.number_input("概算予算", min_value=0, value=int(row['est_amount']), disabled=is_core_disabled, step=1000)
        # 【追加】入力された金額をカンマ付きで表示するプレビュー
        if m_amount > 0:
            g3.caption(f"💰 金額確認: ¥{m_amount:,.0f}")

        # 💡 ここで残高チェックを行い、警告を表示する
        remaining = get_budget_remaining(st.session_state.team_id)
        
        # 新規作成時は「そのまま比較」、更新時は「自分の今の予算を一度戻してから比較」
        current_val = row['est_amount'] if not is_new else 0
        if (m_amount - current_val) > remaining:
             st.warning(f"⚠️ 予算残高不足です！ （現在の部署残高: ¥{remaining:,.0f}）")
        elif remaining < 100000: # 残りが10万を切ったら注意喚起
             st.info(f"💡 予算の残りが少なくなっています （残り: ¥{remaining:,.0f}）")
        
        # --- B. 承認後もいじれる「実績報告系」 (is_progress_disabled) ---
        v1, v2, v3 = st.columns(3)
        m_budget = v1.number_input("確定予算", value=int(row['budget_amount']), disabled=True) # これは常にロック
        if m_budget > 0:
            v1.caption(f"💰 予算総額: ¥{m_budget:,.0f}")
        m_fixed = v2.number_input("実績金額", value=int(row['fixed_amount']), disabled=is_progress_disabled)
        if m_fixed > 0:
            v2.caption(f"📉 執行済: ¥{m_fixed:,.0f}") # [cite: 44, 47]
        m_progress = v3.slider("進捗(%)", 0, 100, int(row['progress_rate']), disabled=is_progress_disabled)
                # --- 開始日と期限日の入力欄 ---
        d_col1, d_col2 = st.columns(2)
        # 文字列(YYYY/MM/DD)をdateオブジェクトに変換して表示
        try:
            start_val = datetime.strptime(row['start_date'], '%Y/%m/%d').date()
            end_val = datetime.strptime(row['end_date'], '%Y/%m/%d').date()
        except:
            start_val = date.today()
            end_val = date.today() + relativedelta(months=3)
        m_s_date = d_col1.date_input("開始日", value=start_val, disabled=is_core_disabled, format="YYYY/MM/DD")
        m_e_date = d_col2.date_input("期限日", value=end_val, disabled=is_core_disabled, format="YYYY/MM/DD")

        m_report = st.text_area("報告", value=row['monthly_report'], disabled=is_progress_disabled, max_chars=1000, height=150)
        m_remarks = st.text_area("備考", value=row['remarks'], disabled=is_progress_disabled, max_chars=500, height=100)

        # --- フォーム内のボタン配置 ---
        bt_col1, bt_col2, bt_col3 = st.columns([1.0, 1.0, 4])
        save, apply, remand, back, hide = False, False, False, False, False

        # 1. 除外済みの案件（アーカイブ）の場合
        if not is_new and row.get('is_hidden') == 1:
            back = bt_col1.form_submit_button("🔙 戻る", key="btn_back_hidden")

        # 2. 通常の案件（除外されていない）の場合
        elif is_new or row.get('is_hidden') == 0:
            if user_role == 2: # 担当者の場合 [cite: 98]
                if is_new or status in [1, 2]: # 新規・保存・差し戻し [cite: 99, 102]
                    save = bt_col1.form_submit_button("💾 上書き保存")
                    apply = bt_col2.form_submit_button("📤 申請する", type="primary")
                elif status == 5: # 承認済（進捗・実績更新フェーズ） [cite: 100, 101]
                    save = bt_col1.form_submit_button("💾 実績を更新")
                elif status == 6: # 完了
                    back = bt_col1.form_submit_button("🔙 戻る", key="btn_back_finish")
                else:
                    back = bt_col1.form_submit_button("🔙 戻る", key="btn_back_staff")

            elif user_role == 1 and status == 3: # 課長：承認待ち [cite: 104]
                remand = bt_col1.form_submit_button("❌ 差し戻す")
                apply = bt_col2.form_submit_button("✅ 本部へ回議", type="primary")

            elif user_role == 4 and status == 4: # 本部：確認待ち [cite: 106]
                remand = bt_col1.form_submit_button("❌ 本部差し戻し")
                apply = bt_col2.form_submit_button("🉐 最終承認", type="primary")
            
            else: # 自分のボールではない時（承認待ちを眺めている時など）
                back = bt_col1.form_submit_button("🔙 戻る", key="btn_back_general")

            # --- 除外ボタンの表示判定（ここは変えない） ---
            show_hide_button = False
            if user_role == 1 and status == 3:
                show_hide_button = True
            elif user_role == 4 and (status == 4 or status == 5):
                show_hide_button = True

            if not is_new and show_hide_button:
                hide = bt_col3.form_submit_button("🗑️ 案件を除外する", key="btn_hide_perfect")

    # --- 7. ロジック：フォームの外側 ---
    if back:
        st.session_state.edit_mode = None
        st.rerun()

    if save or apply or remand:
        d = {
            "id": st.session_state.get('selected_id'),
            "title": m_title, "purpose": m_purpose, "summary": m_summary, "detail": m_detail,
            "cat_id": m_cat, "man_hours": m_hours, "amount": m_amount,
            "s_date": m_s_date.strftime('%Y/%m/%d'), "e_date": m_e_date.strftime('%Y/%m/%d'),
            "status": status, "progress": m_progress,
            "report": m_report, "remarks": m_remarks, "budget": m_budget, "fixed": m_fixed
        }

        if apply:
            d['status'] = 3 if user_role == 2 else (4 if user_role == 1 else 5)
        elif remand:
            d['status'] = 2
            now_md = datetime.now().strftime('%m/%d')
            log_msg = f"【{now_md} 差戻：{st.session_state.user_name}】 先ほどの打ち合わせ通り、指摘箇所の修正をお願いします。\n"
            d['remarks'] = log_msg + m_remarks

        if d['progress'] == 100:
            if not m_report.strip():
                st.error("❌ 完了（100%）にする場合は、報告欄に実績内容を記入してください。")
                st.stop() 
            d['status'] = 6

        if save_matter(d, is_new):
            st.session_state.edit_mode = None
            st.rerun()

    # --- 1. ボタンが押されたら「除外モード」をONにする ---
    if hide:
        st.session_state.confirm_hide_mode = True

    # --- 2. 除外モードがONの間だけ、警告とチェックボックスを出し続ける ---
    if st.session_state.get('confirm_hide_mode'):
        st.warning("⚠️ 本当にこの案件を除外しますか？ 予算計算からは外れ、復帰はできません。")
        confirm = st.checkbox("上記の内容を理解し、実行します")
        
        if confirm:
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("UPDATE TB_matter SET is_hidden = 1 WHERE matter_id = ?", (st.session_state.get('selected_id'),))
                conn.commit()
                conn.close()
                
                st.success("✅ 案件を除外しました。")
                # 処理が終わったら記憶を消す
                st.session_state.confirm_hide_mode = False
                time.sleep(1.5)
                st.session_state.edit_mode = None
                st.rerun()
            except Exception as e:
                st.error(f"除外に失敗しました: {e}")