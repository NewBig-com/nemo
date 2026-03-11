import streamlit as st
import pandas as pd
import sqlite3
import os
import ast
import plotly.express as px

# Set page config
st.set_page_config(page_title="Nemo App - 상가 매물 검색", layout="wide")

st.title("🏙️ 네모 앱(Nemo App) 상가 매물 검색 대시보드")
st.markdown("수집된 데이터를 바탕으로 조건에 맞는 상가 매물을 검색하고 현황을 파악합니다.")

# Define relative path to DB for deployment compatibility
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "nemo_stores.db")

@st.cache_data
def load_data():
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    
    conn = sqlite3.connect(DB_PATH)
    # Select key columns
    query = """
    SELECT 
        id,
        title as '매물명',
        priceTypeName as '거래유형',
        deposit as '보증금_만원',
        monthlyRent as '월세_만원',
        premium as '권리금_만원',
        maintenanceFee as '관리비_만원',
        size as '면적_m2',
        floor as '층수',
        businessMiddleCodeName as '업종별',
        nearSubwayStation as '지하철역',
        smallPhotoUrls
    FROM stores
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Preprocessing
    df['면적_평'] = (df['면적_m2'] * 0.3025).round(1)
    
    # Handle NaNs and convert to integer for money
    df['권리금_만원'] = df['권리금_만원'].fillna(0).astype(int)
    df['보증금_만원'] = df['보증금_만원'].fillna(0).astype(int)
    df['월세_만원'] = df['월세_만원'].fillna(0).astype(int)
    df['관리비_만원'] = df['관리비_만원'].fillna(0).astype(int)
    
    # Handle NaNs for text
    df['업종별'] = df['업종별'].fillna('미분류')
    df['지하철역'] = df['지하철역'].fillna('기재안됨')
    df['층수_분류'] = df['층수'].apply(lambda x: '지하' if pd.notnull(x) and int(x) < 0 else '지상')
    
    # Parse image urls
    def parse_urls(url_str):
        try:
            urls = ast.literal_eval(url_str)
            if isinstance(urls, list) and len(urls) > 0:
                return urls[0]
            return None
        except:
            return None
            
    df['썸네일'] = df['smallPhotoUrls'].apply(parse_urls)
    
    return df

df = load_data()

if df.empty:
    st.error(f"데이터베이스 파일을 찾을 수 없거나 데이터가 없습니다. (경로: {DB_PATH})")
    st.stop()


# Helper function for currency formatting
def format_currency(price_manwon):
    if price_manwon == 0:
        return "0원"
    if price_manwon >= 10000:
        uk = price_manwon // 10000
        man = price_manwon % 10000
        if man == 0:
            return f"{uk}억 원"
        return f"{uk}억 {man:,}만 원"
    return f"{price_manwon:,}만 원"

# ----- Sidebar Filters -----
st.sidebar.header("🔍 검색 필터")
st.sidebar.markdown("**주의: 필터 금액의 기준 단위는 '만원'입니다.**")

with st.sidebar.expander("📝 텍스트 및 기본 검색", expanded=True):
    keyword = st.text_input("매물명 통합 검색", placeholder="예: 코너, 역세권, 1층 등")

with st.sidebar.expander("💸 가격 조건 (만원)", expanded=True):
    # 1. 보증금 (가격)
    max_deposit = int(df['보증금_만원'].max())
    deposit_range = st.slider("보증금", min_value=0, max_value=max_deposit, value=(0, max_deposit), step=100)

    # 2. 월세 (임대료)
    max_rent = int(df['월세_만원'].max())
    rent_range = st.slider("월 임대료", min_value=0, max_value=max_rent, value=(0, max_rent), step=10)

    # 3. 권리금
    max_premium = int(df['권리금_만원'].max())
    if max_premium == 0:
        st.info("권리금 정보가 있는 매물이 없습니다.")
        premium_range = (0, 0)
        exclude_no_premium = False
    else:
        premium_range = st.slider("권리금", min_value=0, max_value=max_premium, value=(0, max_premium), step=50)
        exclude_no_premium = st.checkbox("권리금 미기재(0원) 매물 제외")

with st.sidebar.expander("🏢 상가 스펙 (면적, 업종 등)", expanded=True):
    # 4. 면적
    max_size = float(df['면적_평'].max())
    size_range = st.slider("전용 면적 (평)", min_value=0.0, max_value=max_size, value=(0.0, max_size), step=5.0)

    # 5. 다중 선택 (업종, 역세권, 층수 등)
    business_options = sorted(df['업종별'].unique())
    selected_business = st.multiselect("업종 선택", business_options, default=business_options)
    
    station_options = sorted(df['지하철역'].unique())
    selected_station = st.multiselect("인근 지하철역", station_options, default=station_options)
    
    floor_options = ['지상', '지하']
    selected_floor = st.multiselect("층수 분류", floor_options, default=floor_options)

# ----- Filter Data -----
filtered_df = df[
    (df['보증금_만원'] >= deposit_range[0]) & (df['보증금_만원'] <= deposit_range[1]) &
    (df['월세_만원'] >= rent_range[0]) & (df['월세_만원'] <= rent_range[1]) &
    (df['권리금_만원'] >= premium_range[0]) & (df['권리금_만원'] <= premium_range[1]) &
    (df['면적_평'] >= size_range[0]) & (df['면적_평'] <= size_range[1])
]

if exclude_no_premium:
    filtered_df = filtered_df[filtered_df['권리금_만원'] > 0]
    
if keyword:
    filtered_df = filtered_df[filtered_df['매물명'].str.contains(keyword, na=False)]

if selected_business:
    filtered_df = filtered_df[filtered_df['업종별'].isin(selected_business)]
    
if selected_station:
    filtered_df = filtered_df[filtered_df['지하철역'].isin(selected_station)]
    
if selected_floor:
    filtered_df = filtered_df[filtered_df['층수_분류'].isin(selected_floor)]

# Formatted DataFrame for Display
display_df = filtered_df.copy()
display_df['보증금'] = display_df['보증금_만원'].apply(format_currency)
display_df['월 임대료'] = display_df['월세_만원'].apply(format_currency)
display_df['권리금'] = display_df['권리금_만원'].apply(format_currency)
display_df['전용면적(평)'] = display_df['면적_평']

# ----- Main Content Layout -----
st.subheader(f"📊 검색 결과: 총 {len(filtered_df)}건")

if len(filtered_df) == 0:
    st.warning("선택하신 조건에 맞는 매물이 없습니다. 필터 조건을 완화해 보세요.")
    st.stop()
    
def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8-sig')

csv = convert_df_to_csv(display_df[['매물명', '거래유형', '보증금', '월 임대료', '권리금', '전용면적(평)', '층수', '업종별', '지하철역']])
st.download_button(
    label="📥 현재 검색 결과 CSV 다운로드",
    data=csv,
    file_name='nemo_filtered_stores.csv',
    mime='text/csv',
)


# Tabs (3 main areas)
tab1, tab2, tab3 = st.tabs([
    "🏙️ 매물 갤러리 및 상세", 
    "📋 매물 테이블 리스트", 
    "📈 가격 및 요인 분석"
])

with tab1:
    st.markdown("### 📸 사진 갤러리 뷰")
    
    # Gallery settings
    cols_per_row = 4
    
    # We display a selectbox to allow selecting a property from the filtered results for deep dive
    selected_property_title = st.selectbox(
        "🔎 매물 상세 분석을 보려면 아래 목록에서 매물을 선택하세요:", 
        options=["상세 리포트를 볼 매물을 선택하세요..."] + filtered_df['매물명'].tolist()
    )
    
    if selected_property_title != "상세 리포트를 볼 매물을 선택하세요...":
        # Property Detail View
        prop_data = filtered_df[filtered_df['매물명'] == selected_property_title].iloc[0]
        
        st.markdown(f"## 🏢 {prop_data['매물명']}")
        
        detail_col1, detail_col2 = st.columns([1, 2])
        with detail_col1:
            if prop_data['썸네일']:
                # Trying to get large photo by replacing /s.jpg with /l.jpg if possible
                large_pic = prop_data['썸네일'].replace('/s.jpg', '/l.jpg')
                st.image(large_pic, use_container_width=True)
            else:
                st.image("https://via.placeholder.com/400x300?text=No+Image", use_container_width=True)
                
        with detail_col2:
            st.markdown("### 주요 스펙")
            sp_col1, sp_col2 = st.columns(2)
            sp_col1.metric("보증금", format_currency(prop_data['보증금_만원']))
            sp_col2.metric("월 임대료", format_currency(prop_data['월세_만원']))
            sp_col1.metric("권리금", format_currency(prop_data['권리금_만원']))
            sp_col2.metric("전용면적", f"{prop_data['면적_평']} 평")
            
            st.write(f"**업종**: {prop_data['업종별']} | **지하철역**: {prop_data['지하철역']} | **층수**: {prop_data['층수']}층")
            
            st.markdown("---")
            st.markdown("### 📊 주변/업종 대비 가치 평가 (Benchmarking)")
            
            # calculate benchmarks
            same_station = df[df['지하철역'] == prop_data['지하철역']]
            same_business = df[df['업종별'] == prop_data['업종별']]
            
            avg_rent_station = same_station['월세_만원'].mean()
            avg_rent_biz = same_business['월세_만원'].mean()
            
            diff_station = ((prop_data['월세_만원'] - avg_rent_station) / avg_rent_station * 100) if avg_rent_station else 0
            diff_biz = ((prop_data['월세_만원'] - avg_rent_biz) / avg_rent_biz * 100) if avg_rent_biz else 0
            
            b_col1, b_col2 = st.columns(2)
            # Inverse color for rent: negative difference (cheaper) is good (green inverse)
            b_col1.metric(f"동일 지역({prop_data['지하철역']}) 평균 대비", 
                          f"{prop_data['월세_만원']}만", 
                          f"{diff_station:.1f}%", 
                          delta_color="inverse")
                          
            b_col2.metric(f"동일 업종({prop_data['업종별']}) 평균 대비", 
                          f"{prop_data['월세_만원']}만", 
                          f"{diff_biz:.1f}%", 
                          delta_color="inverse")
                          
            st.caption("※ % 수치가 마이너스(-)일수록 지역 평균 대비 월세가 저렴함을 의미합니다.")
            
    st.markdown("---")
    
    # Grid gallery
    rows = [filtered_df.iloc[i:i+cols_per_row] for i in range(0, len(filtered_df), cols_per_row)]
    for row in rows:
        cols = st.columns(cols_per_row)
        for i, (_, current_row) in enumerate(row.iterrows()):
            with cols[i]:
                if current_row['썸네일']:
                    st.image(current_row['썸네일'], use_container_width=True)
                else:
                    st.image("https://via.placeholder.com/150x150?text=No+Image", use_container_width=True)
                st.write(f"**{current_row['매물명'][:15]}...**")
                st.caption(f"{format_currency(current_row['보증금_만원'])} / {format_currency(current_row['월세_만원'])}")
    

with tab2:
    st.markdown("### 📋 현재 조건에 부합하는 매물 리스트")
    # KPIs
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("평균 보증금", format_currency(int(filtered_df['보증금_만원'].mean())))
    kpi2.metric("평균 월 임대료", format_currency(int(filtered_df['월세_만원'].mean())))
    kpi3.metric("평균 관리비", format_currency(int(filtered_df['관리비_만원'].mean())))
    kpi4.metric("평균 면적", f"{round(filtered_df['면적_평'].mean(), 1)} 평")

    st.dataframe(
        display_df[['매물명', '거래유형', '보증금', '월 임대료', '관리비_만원', '권리금', '전용면적(평)', '층수', '업종별', '지하철역']],
        use_container_width=True,
        hide_index=True
    )

with tab3:
    st.markdown("### 📈 다양한 요인 분석 및 상관관계")
    
    # 1. 층별 임대료 트렌드 (Box Plot)
    st.markdown("#### 지상 vs 지하 층별 월세(임대료) 분포")
    if len(filtered_df) > 1:
        fig_box = px.box(filtered_df, x="층수_분류", y="월세_만원", color="층수_분류",
                         title="지상/지하 층별 월 임대료 분포도",
                         labels={"층수_분류": "층 위치 기준", "월세_만원": "월 임대료 (만원)"})
        st.plotly_chart(fig_box, use_container_width=True)
    
    # 2. 업종별 평균 가격 막대 (Bar)
    st.markdown("#### 주요 업종별 평균 월 임대료 비교")
    if len(filtered_df) > 0:
        biz_avg = filtered_df.groupby('업종별')['월세_만원'].mean().reset_index()
        biz_avg = biz_avg.sort_values(by='월세_만원', ascending=False)
        fig_bar = px.bar(biz_avg, x="업종별", y="월세_만원", color="업종별",
                         title="업종별 평균 월 임대료 현황",
                         labels={"업종별": "상가 업종 구분", "월세_만원": "평균 월 임대료 (만원)"})
        st.plotly_chart(fig_bar, use_container_width=True)

    # 3. 보증금 대비 월세 산점도 (기존 유지, 한글 레이블 고도화)
    st.markdown("#### 보증금 비용 대비 월 임대료 관계도")
    if len(filtered_df) > 0:
        fig_scatter = px.scatter(
            filtered_df, 
            x="보증금_만원", 
            y="월세_만원", 
            size="면적_평", 
            color="업종별",
            hover_name="매물명",
            title="보증금 및 월세 분포 (원 크기: 전용면적 편차 반영)",
            labels={
                "보증금_만원": "보증금 (만원)",
                "월세_만원": "월 임대료 (만원)",
                "업종별": "상가 상권 업종 분류",
                "면적_평": "사용 전용면적 (평)"
            }
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
