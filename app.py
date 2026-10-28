import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime

# --- 1. Google 試算表連線設定 ---
@st.cache_resource
def init_gsheets():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    client = gspread.authorize(credentials)
    sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1MZkh8sYBg8o7dW9WOQcshm0DkTk_r-wv9BwPY95r_NM/edit")
    return sheet

sheet_client = init_gsheets()

st.set_page_config(page_title="May 的日常飲食紀錄", page_icon="🍱", layout="centered")
st.title("🍱 May 的專屬健康紀錄 App")

# --- 2. 從 Google 試算表動態載入早餐與點心品項設定 ---
@st.cache_data(ttl=10) # 每 10 秒自動重新讀取一次，讓試算表的修改即時生效
def load_custom_options():
    default_breakfast = {
        "番茄吉士蛋堡": 288,
        "培根雞蛋堡": 411,
        "火腿歐姆蛋堡": 310,
        "金咖哩豬排堡": 332,
        "新咕咕雞堡": 377,
        "黃金塔塔鱈魚堡": 362,
        "摩斯豬排堡": 336,
        "摩斯炸蝦堡": 353,
        "方塊薯餅": 227
    }
    default_snacks = {
        "水煮蛋": 80,
        "起司 莫札瑞拉": 63,
        "巧克力 明治 95%": 30,
        "豌豆 蒜香": 45,
        "豌豆 芥末": 45,
        "花生 黑糖海鹽": 133,
        "花生 嗆蔥辛辣": 124,
        "花生 芋頭花生嗆蔥辛辣": 117,
        "惜惜康普茶": 24
    }
    try:
        ws = sheet_client.worksheet("品項設定")
        rows = ws.get_all_values()
        if len(rows) > 1:
            b_dict = {}
            s_dict = {}
            for row in rows[1:]:
                if len(row) >= 3:
                    cat, name, cal = row[0].strip(), row[1].strip(), int(row[2])
                    if cat == "早餐":
                        b_dict[name] = cal
                    elif cat == "點心":
                        s_dict[name] = cal
            if b_dict:
                default_breakfast = b_dict
            if s_dict:
                default_snacks = s_dict
    except Exception:
        pass # 若尚未建立「品項設定」分頁，則自動使用預設清單
    return default_breakfast, default_snacks

mos_options, snack_options = load_custom_options()
mos_options["自訂早餐品項"] = 0
snack_options["自訂點心品項"] = 0

# --- 3. 日期選擇與雲端同步載入 ---
today_date = datetime.date.today()

selected_date = st.date_input("📅 選擇記錄日期", value=today_date)
selected_date_str = selected_date.strftime("%Y/%m/%d")

# 重新載入對應選定日期的暫存與數據
if "current_date_loaded" not in st.session_state or st.session_state.current_date_loaded != selected_date_str:
    st.session_state.total_calories = 0
    st.session_state.exercise_cal = 0
    st.session_state.food_log = []
    st.session_state.exercise_log = []
    
    try:
        food_ws = sheet_client.worksheet("飲食紀錄")
        food_rows = food_ws.get_all_values()
        if len(food_rows) > 1:
            for row in food_rows[1:]:
                if len(row) >= 5 and row[0] == selected_date_str:
                    meal_t, f_name, cal = row[2], row[3], int(row[4])
                    st.session_state.total_calories += cal
                    st.session_state.food_log.append({"時間": row[1], "分類": meal_t, "內容與備註": f_name, "熱量 (大卡)": cal})
        
        ex_ws = sheet_client.worksheet("運動紀錄")
        ex_rows = ex_ws.get_all_values()
        if len(ex_rows) > 1:
            for row in ex_rows[1:]:
                if len(row) >= 4 and row[0] == selected_date_str:
                    ex_desc, ex_cal = row[2], int(row[3])
                    st.session_state.exercise_cal += ex_cal
                    st.session_state.exercise_log.append({"時間": row[1], "活動內容": ex_desc, "消耗熱量 (大卡)": ex_cal})
    except Exception as e:
        pass
    
    st.session_state.current_date_loaded = selected_date_str

# --- 4. 核心功能：快速記錄餐點 ---
st.subheader(f"🍽️ 新增餐點紀錄 ({selected_date_str})")

meal_type = st.selectbox("選擇餐別", ["早餐", "午餐", "晚餐", "點心"])

food_name = ""
calories = 0

if meal_type == "早餐":
    selected_mos = st.selectbox("選擇常吃的早餐品項 (可至試算表「品項設定」增修)", list(mos_options.keys()))
    
    if selected_mos == "自訂早餐品項":
        food_name = st.text_input("輸入自訂早餐名稱", placeholder="例如：水煮蛋+無糖豆漿")
        calories = st.number_input("輸入熱量 (大卡)", min_value=0, max_value=2000, value=200, step=10)
    else:
        food_name = selected_mos
        default_cal = mos_options[selected_mos]
        calories = st.number_input(f"確認或微調熱量 (大卡，預設 {default_cal} 大卡)", min_value=0, max_value=2000, value=default_cal, step=10)

elif meal_type == "點心":
    selected_snack = st.selectbox("選擇常吃的點心品項 (可至試算表「品項設定」增修)", list(snack_options.keys()))
    
    if selected_snack == "自訂點心品項":
        food_name = st.text_input("輸入自訂點心名稱", placeholder="例如：其他零食")
        calories = st.number_input("輸入熱量 (大卡)", min_value=0, max_value=2000, value=50, step=10)
    else:
        food_name = selected_snack
        default_cal = snack_options[selected_snack]
        calories = st.number_input(f"確認或微調熱量 (大卡，預設 {default_cal} 大卡)", min_value=0, max_value=2000, value=default_cal, step=10)

else:
    placeholder_text = "例如：四神湯半碗" if meal_type == "午餐" else "例如：糙米飯半碗+燙青菜"
    food_name = st.text_input(f"輸入{meal_type}名稱", placeholder=placeholder_text)
    default_cals = 400
    calories = st.number_input("輸入熱量 (大卡)", min_value=0, max_value=2000, value=default_cals, step=10)

if st.button("✨ 確認送出並寫入雲端試算表"):
    if food_name.strip():
        try:
            now_time = datetime.datetime.now().strftime("%H:%M")
            
            worksheet = sheet_client.worksheet("飲食紀錄")
            worksheet.append_row([selected_date_str, now_time, meal_type, food_name, calories])
            
            if selected_date_str == today_date.strftime("%Y/%m/%d"):
                st.session_state.total_calories += calories
                st.session_state.food_log.append({
                    "時間": now_time, "分類": meal_type, "內容與備註": food_name, "熱量 (大卡)": calories
                })
            st.success(f"成功記錄至 {selected_date_str}！「{food_name}」({calories} 大卡) 已存入雲端！")
        except Exception as e:
            st.error(f"寫入試算表時發生錯誤: {e}")
    else:
        st.warning("請輸入餐點名稱喔！")

st.divider()

# --- 5. 核心功能：運動紀錄 ---
st.subheader(f"🏃‍♀️ 新增運動與活動 ({selected_date_str})")
exercise_note = st.text_input("輸入活動描述", placeholder="例如：從捷運雙連站走到捷運中山站")
exercise_cal = st.number_input("估算消耗熱量 (大卡)", min_value=0, max_value=1000, value=100, step=10)

if st.button("💪 送出運動並寫入試算表"):
    if exercise_note:
        try:
            now_time = datetime.datetime.now().strftime("%H:%M")
            
            worksheet = sheet_client.worksheet("運動紀錄")
            worksheet.append_row([selected_date_str, now_time, exercise_note, exercise_cal])
            
            if selected_date_str == today_date.strftime("%Y/%m/%d"):
                st.session_state.exercise_cal += exercise_cal
                st.session_state.exercise_log.append({
                    "時間": now_time, "活動內容": exercise_note, "消耗熱量 (大卡)": exercise_cal
                })
            st.success(f"運動記錄成功存入 {selected_date_str}！")
        except Exception as e:
            st.error(f"發生錯誤: {e}")
    else:
        st.warning("請輸入活動描述喔！")

st.divider()

# --- 6. 檢視明細清單與刪除功能 ---
st.subheader(f"📝 {selected_date_str} 明細清單")
tab1, tab2 = st.tabs(["🍱 飲食紀錄", "🏃‍♀️ 運動紀錄"])

with tab1:
    if st.session_state.food_log:
        df_food = pd.DataFrame(st.session_state.food_log)
        st.dataframe(df_food, use_container_width=True, hide_index=True)
        
        if st.button("🗑️ 刪除最後一筆飲食紀錄"):
            try:
                food_ws = sheet_client.worksheet("飲食紀錄")
                all_rows = food_ws.get_all_values()
                
                target_row_idx = -1
                for idx in range(len(all_rows) - 1, 0, -1):
                    if all_rows[idx][0] == selected_date_str:
                        target_row_idx = idx + 1
                        break
                
                if target_row_idx != -1:
                    food_ws.delete_rows(target_row_idx)
                    removed_item = st.session_state.food_log.pop()
                    if selected_date_str == today_date.strftime("%Y/%m/%d"):
                        st.session_state.total_calories -= removed_item["熱量 (大卡)"]
                    
                    st.success("已成功刪除最後一筆飲食紀錄！")
                    st.rerun()
                else:
                    st.warning("雲端試算表中找不到該日期的紀錄可刪除。")
            except Exception as e:
                st.error(f"刪除失敗: {e}")
    else:
        st.info("該日期尚無飲食紀錄")
        
with tab2:
    if st.session_state.exercise_log:
        df_exercise = pd.DataFrame(st.session_state.exercise_log)
        st.dataframe(df_exercise, use_container_width=True, hide_index=True)
        
        if st.button("🗑️ 刪除最後一筆運動紀錄"):
            try:
                ex_ws = sheet_client.worksheet("運動紀錄")
                all_rows = ex_ws.get_all_values()
                
                target_row_idx = -1
                for idx in range(len(all_rows) - 1, 0, -1):
                    if all_rows[idx][0] == selected_date_str:
                        target_row_idx = idx + 1
                        break
                
                if target_row_idx != -1:
                    ex_ws.delete_rows(target_row_idx)
                    removed_item = st.session_state.exercise_log.pop()
                    if selected_date_str == today_date.strftime("%Y/%m/%d"):
                        st.session_state.exercise_cal -= removed_item["消耗熱量 (大卡)"]
                    
                    st.success("已成功刪除最後一筆運動紀錄！")
                    st.rerun()
                else:
                    st.warning("雲端試算表中找不到該日期的紀錄可刪除。")
            except Exception as e:
                st.error(f"刪除失敗: {e}")
    else:
        st.info("該日期尚無運動紀錄")

# --- 7. 側邊欄：儀表板 (專注熱量) ---
with st.sidebar:
    st.header(f"📊 狀態總覽")
    st.caption(f"目前檢視日期：{selected_date_str}")
    
    net_calories = st.session_state.total_calories - st.session_state.exercise_cal
    
    st.metric(label="淨熱量 (大卡)", 
              value=net_calories, 
              delta=f"目標 1300", 
              delta_color="inverse") 
              
    progress_val = min(max(net_calories / 1300, 0.0), 1.0)
    st.progress(progress_val)
    st.caption(f"已攝取：{st.session_state.total_calories} 大卡 | 運動消耗：{st.session_state.exercise_cal} 大卡")
    
    st.divider()
    
    if st.button("⚠️ 重置今日暫存紀錄", use_container_width=True):
         st.session_state.total_calories = 0
         st.session_state.exercise_cal = 0
         st.session_state.food_log = []
         st.session_state.exercise_log = []
         st.rerun()