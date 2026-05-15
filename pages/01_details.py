import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from supabase import create_client

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

# --- 1. 環境設定 (Supabaseへの接続) ---
def get_db_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

# --- 2. 門番 & セッションの再構築 ---
if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
    st.switch_page("login.py")
    st.stop()

# スタッフ情報をSupabaseから確実に取得する
if "user_name" not in st.session_state or st.session_state.user_name == st.session_state.get('user_id'):
    try:
        supabase = get_db_connection()
        # TB_IDから情報取得
        res_id = supabase.table("TB_ID").select("staff_id, post_id, team_id").eq("user_id", st.session_state.get('user_id')).execute()
        if res_id.data:
            user_info = res_id.data[0]
            staff_id = user_info['staff_id']
            post_id = user_info['post_id']
            
            # TB_staffから名前取得
            res_staff = supabase.table("TB_staff").select("staff_name").eq("staff_id", staff_id).execute()
            staff_name = res_staff.data[0]['staff_name'] if res_staff.data else "未設定"
            
            # TB_postから役職名取得
            res_post = supabase.table("TB_post").select("post_name").eq("post_id", post_id).execute()
            post_name = res_post.data[0]['post_name'] if res_post.data else ""
            
            st.session_state.user_name = staff_name 
            st.session_state.team_id = user_info['team_id']
            st.session_state.role_id = post_id 
            st.session_state.post_name = post_name
    except Exception as e:
        st.error(f"スタッフ情報の取得に失敗しました: {e}")

# --- 3. 関数：データ処理 (Supabase版) ---
def save_matter(data, is_new=True):
    supabase = get_db_connection()
    now_str = datetime.now().strftime('%Y/%m/%d %H:%M')
    try:
        if is_new:
            # 最新のmatter_idを取得して連番作成
            res_last = supabase.table("TB_matter").select("matter_id").eq("fiscal_year", 2026).eq("team_id", st.session_state.team_id).order("matter_id", desc=True).limit(1).execute()
            last_record = res_last.data[0] if res_last.data else None
            new_num = int(last_record['matter_id'].split('-')[-1]) + 1 if last_record else 1
            new_id = f"2026-D{st.session_state.team_id}-{new_num:03}"
            
            insert_data = {
                "matter_id": new_id, "fiscal_year": 2026, "matter_title": data['title'],
                "team_id": st.session_state.team_id, "user_id": st.session_state.user_id,
                "purpose": data['purpose'], "summary": data['summary'], "detail": data['detail'],
                "category_id": data['cat_id'], "est_man_hours": data['man_hours'],
                "est_amount": data['amount'], "status_id": data['status'], "progress_rate": 0,
                "start_date": data['s_date'], "end_date": data['e_date'], "monthly_report": data['report'],
                "remarks": data['remarks'], "item_id": 1, "budget_amount": data['budget'],
                "fixed_amount": data['fixed'], "last_updated": now_str, "is_hidden": 0
            }
            supabase.table("TB_matter").insert(insert_data).execute()
        else:
            update_data = {
                "matter_title": data['title'], "purpose": data['purpose'], "summary": data['summary'],
                "detail": data['detail'], "category_id": data['cat_id'], "est_man_hours": data['man_hours'],
                "est_amount": data['amount'], "status_id": data['status'], "start_date": data['s_date'],
                "end_date": data['e_date'], "progress_rate": data['progress'], "monthly_report": data['report'],
                "remarks": data['remarks'], "budget_amount": data['budget'], "fixed_amount": data['fixed'],
                "last_updated": now_str
            }
            supabase.table("TB_matter").update(update_data).eq("matter_id", data['id']).execute()
        return True
    except Exception as e:
        st.error(f"保存エラー: {e}")
        return False

def get_budget_remaining(team_id):
    supabase = get_db_connection()
    # 予算総額の取得
    res_b = supabase.table("TB_budget").select("total_budget").eq("team_id", team_id).eq("fiscal_year", 2026).execute()
    total = res_b.data[0]['total_budget'] if res_b.data else 0
    # 申請額の合計を取得 (is_hidden=0)
    res_m = supabase.table("TB_matter").select("est_amount").eq("team_id", team_id).eq("fiscal_year", 2026).eq("is_hidden", 0).execute()
    used = sum([item['est_amount'] or 0 for item in res_m.data]) if res_m.data else 0
    return total - used

# --- 4. サイドバー (変更なし) ---
st.markdown("<style>[data-testid='stSidebarNav'] {display: none;}</style>", unsafe_allow_html=True)
with st.sidebar:
    st.title("開発管理統合システム")
    u_name = st.session_state.get('user_name', '未取得')
    p_name = st.session_state.get('post_name', '')
    st.write(f"👤 {u_name} {p_name}")
    st.divider()

    if st.session_state.get('edit_mode'):
        if st.button("🏠 一覧に戻る", key="sb_back_unique", use_container_width=True):
            st.session_state.edit_mode = None
            st.rerun()
    else:
        if st.button("🔄 案件詳細・登録", key="sb_refresh_unique", use_container_width=True): 
            st.rerun()

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
        1: "⏳ 一時保存", 2: "↩️ 差し戻し", 3: "👤 課長承認待ち",
        4: "🏢 本部確認待ち", 5: "✅ 承認済", 6: "🏁 完了", 7: "❌ 却下"
    }
    
    # --- データ取得 (SupabaseとPandasの連携) ---
    supabase = get_db_connection()
    role_id = st.session_state.get('role_id')
    
    # 基本のデータ取得
    query = supabase.table("TB_matter").select("*")
    if role_id == 1:
        query = query.eq("team_id", st.session_state.team_id)
    elif role_id == 2:
        query = query.eq("user_id", st.session_state.user_id)
    
    res_matter = query.execute()
    df = pd.DataFrame(res_matter.data)

    # データがある場合のみ、名前を結合(JOINの代わり)
    if not df.empty:
        # 部署名と名前を一括でくっつける魔法（Pandas）
        df_team = pd.DataFrame(supabase.table("TB_team").select("*").execute().data)
        df_id = pd.DataFrame(supabase.table("TB_ID").select("user_id, staff_id").execute().data)
        df_staff = pd.DataFrame(supabase.table("TB_staff").select("staff_id, staff_name").execute().data)
        
        if not df_team.empty:
            df = df.merge(df_team, on='team_id', how='left')
        if not df_id.empty and not df_staff.empty:
            df_user_staff = df_id.merge(df_staff, on='staff_id', how='left')
            df = df.merge(df_user_staff, on='user_id', how='left')
        
        df['status_name'] = df['status_id'].map(status_name_map)
        df.loc[df['is_hidden'] == 1, 'status_name'] = "🗑️ 削除"
    else:
        # 空っぽの時の枠組み
        df = pd.DataFrame(columns=[
            'matter_id', 'fiscal_year', 'matter_title', 'team_name', 'staff_name', 
            'purpose', 'summary', 'last_updated', 'status_id', 'team_id', 'end_date', 
            'progress_rate', 'is_hidden', 'est_amount'
        ])

    # --- 1. 検索・絞り込み (変更なし) ---
    with st.expander("🔍 検索・絞り込み"):
        c_s1, c_s2 = st.columns(2)
        sk = c_s1.text_input("キーワード検索")
        status_map = {1:"新規", 2:"差し戻し", 3:"部署承認中", 4:"本部回議中", 5:"最終承認済"}
        ss = c_s2.multiselect("ステータス", options=list(status_map.keys()), format_func=lambda x: status_map[x])

    df_display = df.copy()
    if not df_display.empty:
        if sk:
            df_display = df_display[df_display['matter_title'].str.contains(sk, case=False, na=False) | df_display['matter_id'].astype(str).str.contains(sk, case=False, na=False)]
        if ss:
            df_display = df_display[df_display['status_id'].isin(ss)]

    # --- 2. 期限超過・実績更新のアラート (変更なし) ---
    today_dt = datetime.now()
    today_str_slash = today_dt.strftime('%Y/%m/%d')
    today_str_hyphen = today_dt.strftime('%Y-%m-%d')

    if not df.empty and st.session_state.get('last_alert_date') != today_str_hyphen:
        overdue_df = df[
            (df['end_date'] < today_str_slash) & 
            (df['progress_rate'] < 100) & 
            (df['is_hidden'] == 0) 
        ]
        if not overdue_df.empty:
            st.error(f"⚠️ **期限超過のアラート**: 完了予定日を過ぎた未完了案件が {len(overdue_df)} 件あります。進捗状況を確認してください。")
            if st.button("❌ 了解"):
                st.session_state.last_alert_date = today_str_hyphen
                st.rerun()

    # --- 3. 一覧表示（ハイライトと日本語化を統合） (変更なし) ---
    def highlight_todo(row):
        if row.get('is_hidden') == 1:
            return ['color: #a0a0a0; background-color: #f0f0f0; font-style: italic;'] * len(row)
        if row['progress_rate'] == 100:
            return ['background-color: #c6f6d5; color: #22543d; font-weight: bold; text-decoration: line-through; border: 1px solid #38a169;'] * len(row)

        role = st.session_state.get('role_id')
        status = row['status_id']
        today_str = datetime.now().strftime('%Y/%m/%d')
        limit_time = (datetime.now() - timedelta(days=2)).strftime('%Y/%m/%d %H:%M:%S')
        
        is_overdue = str(row['end_date']) < today_str       
        is_outdated = str(row['last_updated']) < limit_time 
        
        if (is_overdue or is_outdated) and (3 <= status <= 5):
            return ['background-color: #ffffcc; font-weight: bold; border: 1px solid #ffcc00'] * len(row)
        
        if str(row['end_date']) < today_str and row['progress_rate'] < 100:
            return ['background-color: #ffffcc; font-weight: bold; border: 1px solid #ffcc00'] * len(row)

        style_blue = ['background-color: #e6f3ff; border: 1px solid #b3d9ff'] * len(row)

        if role == 1: 
            if status in [2, 3]: 
                return style_blue
        elif role == 4 and status == 4:  
            return style_blue
        elif role == 2 and status == 2:  
            return style_blue
            
        return [''] * len(row)

    if not df_display.empty:
        styled_df = df_display.style.apply(highlight_todo, axis=1)
    else:
        styled_df = df_display

    st.dataframe(
        styled_df, 
        use_container_width=True, 
        hide_index=True, 
        selection_mode="single-row", 
        on_select="rerun",
        key="matter_table",
        column_config={
            "matter_id": "案件番号", "fiscal_year": None, "matter_title": "案件名",
            "team_name": "部署名", "staff_name": "担当者", "status_name": "ステータス",
            "purpose": None, "summary": None, "last_updated": "最終更新",
            "est_amount": st.column_config.NumberColumn("概算予算", format="¥%,.0f"),
            "progress_rate": st.column_config.NumberColumn("進捗", format="%d%%"),
            "end_date": "期限日", "status_id": None, "team_id": None, "is_hidden": None,
            "user_id": None, "category_id": None, "est_man_hours": None, "start_date": None,
            "monthly_report": None, "remarks": None, "item_id": None, "budget_amount": None, "fixed_amount": None
        }
    )

    if st.session_state.matter_table.selection.rows:
        selected_row_index = st.session_state.matter_table.selection.rows[0]
        st.session_state.selected_id = df_display.iloc[selected_row_index]['matter_id']
        st.session_state.edit_mode = 'edit'
        st.rerun()

    if st.session_state.get('role_id') == 2:
        if st.button("➕ 新規登録"):
            st.session_state.edit_mode = 'new'
            st.rerun()

# --- 6. 詳細入力画面 ---
else:
    is_new = st.session_state.edit_mode == 'new'
    
    row = {
        "matter_title":"", "purpose":"", "summary":"", "detail":"", "category_id":1, 
        "est_man_hours":0, "est_amount":0, "status_id":1, "progress_rate":0, 
        "start_date":date.today().strftime("%Y/%m/%d"), 
        "end_date":(date.today() + relativedelta(months=3)).strftime("%Y/%m/%d"), 
        "monthly_report":"", "remarks":"", 
        "budget_amount":0, "fixed_amount":0, "user_id": st.session_state.user_id, "team_id": st.session_state.team_id,
        "is_hidden": 0
    }
    
    # 既存データの読み込み (Supabase版)
    if not is_new:
        supabase = get_db_connection()
        res = supabase.table("TB_matter").select("*").eq("matter_id", st.session_state.selected_id).execute()
        if res.data:
            row.update(res.data[0])

    target_team_id = row.get('team_id')
    if target_team_id:
        supabase = get_db_connection()
        res_budget = supabase.table("TB_budget").select("total_budget").eq("team_id", target_team_id).eq("fiscal_year", 2026).execute()
        if res_budget.data:
            row['budget_amount'] = res_budget.data[0]['total_budget']

    user_role = st.session_state.get('role_id')
    status = row['status_id']
    
    is_core_disabled = True     
    is_progress_disabled = True 
    
    if user_role == 2: 
        if is_new or status in [1, 2]: 
            is_core_disabled = False
            is_progress_disabled = False
        elif status == 5: 
            is_core_disabled = True     
            is_progress_disabled = False 

    # --- 画面表示 (変更なし) ---
    display_id = "新規" if is_new else st.session_state.get('selected_id', '不明')
    st.subheader(f"📝 案件詳細: {display_id}")
    st.divider()

    with st.form("edit_form"):
        col_top1, col_top2 = st.columns([1, 1]) 
        m_title = col_top1.text_input("案件名", value=row['matter_title'], disabled=is_core_disabled, max_chars=50)
        m_purpose = col_top2.text_input("目的", value=row['purpose'], disabled=is_core_disabled, max_chars=100)
        m_summary = st.text_input("概要", value=row['summary'], disabled=is_core_disabled, max_chars=100)
        m_detail = st.text_area("詳細", value=row['detail'], disabled=is_core_disabled, max_chars=1000, height=150)
        
        g1, g2, g3 = st.columns(3)
        m_cat = g1.selectbox("カテゴリ", [1,2,3,4], format_func=lambda x: ["新規","保守","改修","スポット"][x-1], index=row['category_id']-1, disabled=is_core_disabled)
        m_hours = g2.number_input("工数", value=row['est_man_hours'], disabled=is_core_disabled)
        m_amount = g3.number_input("概算予算", min_value=0, value=int(row['est_amount']), disabled=is_core_disabled, step=1000)
        
        if m_amount > 0:
            g3.caption(f"💰 金額確認: ¥{m_amount:,.0f}")

        remaining = get_budget_remaining(st.session_state.team_id)
        current_val = row['est_amount'] if not is_new else 0
        if (m_amount - current_val) > remaining:
             st.warning(f"⚠️ 予算残高不足です！ （現在の部署残高: ¥{remaining:,.0f}）")
        elif remaining < 100000: 
             st.info(f"💡 予算の残りが少なくなっています （残り: ¥{remaining:,.0f}）")
        
        v1, v2, v3 = st.columns(3)
        m_budget = v1.number_input("確定予算", value=int(row['budget_amount']), disabled=True) 
        if m_budget > 0:
            v1.caption(f"💰 予算総額: ¥{m_budget:,.0f}")
        m_fixed = v2.number_input("実績金額", value=int(row['fixed_amount']), disabled=is_progress_disabled)
        if m_fixed > 0:
            v2.caption(f"📉 執行済: ¥{m_fixed:,.0f}") 
        m_progress = v3.slider("進捗(%)", 0, 100, int(row['progress_rate']), disabled=is_progress_disabled)
        
        d_col1, d_col2 = st.columns(2)
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

        bt_col1, bt_col2, bt_col3 = st.columns([1.0, 1.0, 4])
        save, apply, remand, back, hide = False, False, False, False, False

        if not is_new and row.get('is_hidden') == 1:
            back = bt_col1.form_submit_button("🔙 戻る", key="btn_back_hidden")
        elif is_new or row.get('is_hidden') == 0:
            if user_role == 2: 
                if is_new or status in [1, 2]: 
                    save = bt_col1.form_submit_button("💾 上書き保存")
                    apply = bt_col2.form_submit_button("📤 申請する", type="primary")
                elif status == 5: 
                    save = bt_col1.form_submit_button("💾 実績を更新")
                elif status == 6: 
                    back = bt_col1.form_submit_button("🔙 戻る", key="btn_back_finish")
                else:
                    back = bt_col1.form_submit_button("🔙 戻る", key="btn_back_staff")

            elif user_role == 1 and status == 3: 
                remand = bt_col1.form_submit_button("❌ 差し戻す")
                apply = bt_col2.form_submit_button("✅ 本部へ回議", type="primary")

            elif user_role == 4 and status == 4: 
                remand = bt_col1.form_submit_button("❌ 本部差し戻し")
                apply = bt_col2.form_submit_button("🉐 最終承認", type="primary")
            else: 
                back = bt_col1.form_submit_button("🔙 戻る", key="btn_back_general")

            show_hide_button = False
            if user_role == 1 and status == 3:
                show_hide_button = True
            elif user_role == 4 and (status == 4 or status == 5):
                show_hide_button = True

            if not is_new and show_hide_button:
                hide = bt_col3.form_submit_button("🗑️ 案件を除外する", key="btn_hide_perfect")

    # --- 7. ロジック：フォームの外側 (Supabase版) ---
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

    if hide:
        st.session_state.confirm_hide_mode = True

    if st.session_state.get('confirm_hide_mode'):
        st.warning("⚠️ 本当にこの案件を除外しますか？ 予算計算からは外れ、復帰はできません。")
        confirm = st.checkbox("上記の内容を理解し、実行します")
        
        if confirm:
            try:
                supabase = get_db_connection()
                supabase.table("TB_matter").update({"is_hidden": 1}).eq("matter_id", st.session_state.get('selected_id')).execute()
                st.success("✅ 案件を除外しました。")
                st.session_state.confirm_hide_mode = False
                time.sleep(1.5)
                st.session_state.edit_mode = None
                st.rerun()
            except Exception as e:
                st.error(f"除外に失敗しました: {e}")