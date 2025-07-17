import streamlit as st
from PIL import Image
import base64
from io import BytesIO
import json
import os
import random
import string
import copy
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import pandas as pd

st.set_page_config(page_title="Trắc nghiệm ảnh", layout="wide")

hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .block-container {
        padding-top: 0rem;
        padding-bottom: 0rem;
        padding-left: 1vw;
        padding-right: 1vw;
        max-width: 100vw;
    }
    .stApp {padding-top: 0rem;}
    </style>
    """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

def generate_exam_id(k=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=k))

def save_exam(data, exam_id):
    with open(f"exam_{exam_id}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

def load_exam(exam_id):
    try:
        with open(f"exam_{exam_id}.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return None

def save_result(new_result, exam_id):
    fname = f"results_{exam_id}.json"
    results = []
    if os.path.exists(fname):
        with open(fname, "r", encoding="utf-8") as f:
            try: results = json.load(f)
            except: pass
    results.append(new_result)
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False)

def load_results(exam_id):
    fname = f"results_{exam_id}.json"
    if not os.path.exists(fname): return []
    with open(fname, "r", encoding="utf-8") as f:
        try: return json.load(f)
        except: return []

def display_image_base64(b64str, caption="", img_ratio=0.5):
    img = Image.open(BytesIO(base64.b64decode(b64str)))
    max_display = int(1600 * img_ratio)
    buf = BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    html = f"""
    <div style="display: flex; justify-content: center;">
        <img src="data:image/png;base64,{b64}" width="{max_display}">
    </div>
    <div style="text-align: center; color: grey; font-size: 90%;">{caption}</div>
    """
    st.markdown(html, unsafe_allow_html=True)

def randomize_by_group(questions):
    group_mcq = [q for q in questions if q.get("type") == "mcq"]
    group_tf = [q for q in questions if q.get("type") == "true_false"]
    group_sa = [q for q in questions if q.get("type") == "short_answer"]
    idx_mcq = list(range(len(group_mcq)))
    idx_tf = list(range(len(group_tf)))
    idx_sa = list(range(len(group_sa)))
    random.shuffle(idx_mcq)
    random.shuffle(idx_tf)
    random.shuffle(idx_sa)
    shuffled_mcq = [copy.deepcopy(group_mcq[i]) for i in idx_mcq]
    shuffled_tf = [copy.deepcopy(group_tf[i]) for i in idx_tf]
    shuffled_sa = [copy.deepcopy(group_sa[i]) for i in idx_sa]
    shuffled = shuffled_mcq + shuffled_tf + shuffled_sa
    indices = idx_mcq + [i+len(group_mcq) for i in idx_tf] + [i+len(group_mcq)+len(group_tf) for i in idx_sa]
    return shuffled, indices

query_params = st.query_params
query_exam_id = query_params.get("exam_id", [None])[0]

if "role" not in st.session_state:
    st.title("🎓 Hệ thống trắc nghiệm ảnh - Đa giáo viên/đa đề")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Tôi là Giáo viên"):
            st.session_state["role"] = "teacher"
    with col2:
        if st.button("Tôi là Học sinh"):
            st.session_state["role"] = "student"
    st.stop()

if st.session_state["role"] == "teacher":
    st.title("👩‍🏫 Tạo đề kiểm tra trắc nghiệm từ ảnh (tự động ghép STT với ảnh)")

    img_percent = st.slider("Tỷ lệ ảnh so với khung (%)", min_value=20, max_value=100, value=50, step=5)
    img_ratio = img_percent / 100.0

    teacher_name = st.text_input("Nhập họ tên giáo viên", key="teacher_name_img")
    if teacher_name.strip() == "":
        st.info("Vui lòng nhập họ tên để tiếp tục.")
        st.stop()

    excel_file = st.file_uploader("Bước 1: Tải lên file Excel đáp án (theo mẫu: STT | Đáp án)", type=["xlsx", "xls"], key="excel_ans")
    uploaded_files = st.file_uploader(
        "Bước 2: Tải lên các file ảnh (Cau_xx: câu hỏi, Da_xx: lời giải - có thể bỏ qua nếu không có)", 
        type=["png", "jpg", "jpeg"], 
        accept_multiple_files=True
    )

    exam_time = st.number_input("Thời gian làm bài (phút)", min_value=1, max_value=120, value=15)
    allow_review = st.checkbox("Cho phép học sinh xem đáp án sau khi nộp bài", value=True)

    questions = []

    if excel_file and uploaded_files:
        df = pd.read_excel(excel_file)
        df.columns = [c.strip() for c in df.columns]
        col_stt = df.columns[0]   # Cột số thứ tự
        col_ans = df.columns[1]   # Đáp án

        file_map = {f.name: f for f in uploaded_files}
        da_file_map = {}
        for f in uploaded_files:
            if f.name.startswith("Da_"):
                da_file_map[f.name] = f

        for idx, row in df.iterrows():
            stt_raw = str(row[col_stt]).strip()
            try:
                stt = f"{int(float(stt_raw)):02d}"
            except:
                st.warning(f"Sai định dạng STT ở dòng {idx+2}: {stt_raw}")
                continue

            img_name = f"Cau_{stt}.jpg"
            if img_name not in file_map:
                for ext in ["png", "jpeg"]:
                    if f"Cau_{stt}.{ext}" in file_map:
                        img_name = f"Cau_{stt}.{ext}"
                        break

            answer = str(row[col_ans]).strip().upper()

            da_img_name = None
            for ext in ["jpg", "jpeg", "png"]:
                test_name = f"Da_{stt}.{ext}"
                if test_name in da_file_map:
                    da_img_name = test_name
                    break

            img_file = file_map.get(img_name)
            da_img_file = da_file_map.get(da_img_name) if da_img_name else None
            if not img_file:
                st.warning(f"Không tìm thấy file ảnh câu hỏi cho STT {stt} (dòng {idx+2})")
                continue
            img_data = img_file.read()
            img_file.seek(0)
            da_img = base64.b64encode(da_img_file.read()).decode() if da_img_file else None
            if da_img_file: da_img_file.seek(0)

            # Tự động phân loại câu hỏi
            if len(answer) == 1 and answer in ["A", "B", "C", "D"]:
                q_type = "mcq"
            elif len(answer) == 4 and all(c in ["Đ", "S"] for c in answer):
                q_type = "true_false"
                answer4 = list(answer)
            else:
                q_type = "short_answer"

            q = {
                "img_name": img_name,
                "img_data": base64.b64encode(img_data).decode(),
                "type": q_type,
                "da_img_data": da_img
            }
            if q_type == "mcq":
                q["answer"] = answer
            elif q_type == "true_false":
                q["answers"] = answer4
            else:
                q["answer"] = answer

            questions.append(q)

        if questions:
            st.success(f"Đã nhận {len(questions)} câu hỏi từ Excel và ảnh.")
            for i, q in enumerate(questions):
                st.write(f"**Câu {i+1}: Loại:** {'Trắc nghiệm' if q['type']=='mcq' else ('Đúng/Sai' if q['type']=='true_false' else 'Trả lời ngắn')}")
                display_image_base64(q["img_data"], caption=q["img_name"], img_ratio=img_ratio)
                st.write(f"Đáp án: {q['answer'] if q['type']!='true_false' else ''.join(q['answers'])}")
                if q.get("da_img_data"):
                    display_image_base64(q["da_img_data"], caption=f"Lời giải {i+1}", img_ratio=img_ratio)
                st.markdown("---")

    if questions and st.button("Lưu bộ đề này"):
        exam_id = generate_exam_id()
        exam_data = {
            "exam_id": exam_id,
            "type": "image_exam",
            "teacher": teacher_name,
            "questions": questions,
            "exam_time": exam_time,
            "allow_review": allow_review,
            "img_ratio": img_ratio
        }
        save_exam(exam_data, exam_id)
        st.success(f"Đã lưu đề thành công! Mã đề: **{exam_id}**")
        link_rel = f"?exam_id={exam_id}"
        st.markdown(f"- Gửi link này cho học sinh: [Làm bài ngay]({link_rel})")
        st.code(link_rel)
        st.info("Giáo viên lưu lại mã đề, học sinh vào đúng link/mã đề này để làm bài.")

    st.markdown("---")
    st.subheader("📋 Xem/tổng hợp kết quả của một đề")
    check_exam_id = st.text_input("Nhập MÃ ĐỀ muốn xem kết quả:", key="examid_gv")
    if check_exam_id.strip():
        check_exam_id = check_exam_id.strip().upper()
        exdata = load_exam(check_exam_id)
        if st.button("🔄 Làm mới danh sách", key="refresh_results"):
            st.session_state[f"refresh_{check_exam_id}"] = st.session_state.get(f"refresh_{check_exam_id}", 0) + 1
        refresh_times = st.session_state.get(f"refresh_{check_exam_id}", 0)
        results = load_results(check_exam_id)
        if not exdata:
            st.error("Không tìm thấy đề này!")
        else:
            if not results:
                st.info("Chưa có học sinh nào nộp bài cho đề này.")
            else:
                st.write(f"**Tổng số học sinh đã nộp: {len(results)}**")
                student_scores = []
                for idx, r in enumerate(results):
                    diem = r['score']
                    st.write(f"{idx+1}. {r['name']} - {r['school']} - Lớp {r['class_']} - Điểm: {diem}")
                    student_scores.append((r['name'], diem))
                if student_scores:
                    student_scores = sorted(student_scores, key=lambda x: -x[1])
                    names = [x[0] for x in student_scores]
                    diems = [x[1] for x in student_scores]

                    bar_colors = ["#EFFFF4"] * len(diems)  # màu xanh lá tươi cho cả cột
                    bar_edgecolors = ["#17D46A"] * len(diems)  # viền cùng màu

                    fig, ax = plt.subplots(figsize=(max(6, 0.8*len(names)), 5))
                    bars = ax.bar(names, diems, color=bar_colors, edgecolor=bar_edgecolors, linewidth=2)


                    ax.set_ylabel("Điểm", fontsize=12)
                    ax.set_xlabel("Học sinh", fontsize=12)
                    ax.set_title("Biểu đồ điểm học sinh", fontsize=14)
                    for bar, diem in zip(bars, diems):
                        ax.annotate(f"{diem}", xy=(bar.get_x() + bar.get_width() / 2, diem),
                                    xytext=(0, 4), textcoords="offset points", ha='center', va='bottom', fontsize=12, color="#1d1d1d", fontweight="bold")
                    plt.xticks(rotation=45, ha='right', fontsize=11)
                    plt.tight_layout()
                    st.pyplot(fig)
                if st.button("Xóa tất cả kết quả của đề này", key="xoakq"+check_exam_id):
                    os.remove(f"results_{check_exam_id}.json")
                    st.rerun()

elif st.session_state["role"] == "student":
    st.title("🧑‍🎓 Làm bài trắc nghiệm ảnh (vào đề riêng biệt)")
    exam_id = query_exam_id
    if not exam_id:
        exam_id = st.text_input("Nhập MÃ ĐỀ được giáo viên gửi:", key="examid_hs")
    if not exam_id or not exam_id.strip():
        st.info("Vui lòng nhập đúng mã đề hoặc vào đúng link.")
        st.stop()
    exam_id = exam_id.strip().upper()

    exam_data = load_exam(exam_id)
    if not exam_data:
        st.warning("Mã đề không tồn tại. Hỏi lại giáo viên hoặc nhập đúng!")
        st.stop()
    img_ratio = exam_data.get("img_ratio", 0.5)
    exam_time = exam_data.get("exam_time", 15)
    allow_review = exam_data.get("allow_review", True)

    name = st.text_input("Họ tên học sinh", key="stu_name_img")
    school = st.text_input("Trường", key="stu_school_img")
    class_ = st.text_input("Lớp", key="stu_class_img")
    if name.strip() == "" or school.strip() == "" or class_.strip() == "":
        st.info("Điền đầy đủ thông tin để bắt đầu.")
        st.stop()

    def student_exists(name, school, class_, exam_id):
        results = load_results(exam_id)
        for r in results:
            if (
                r["name"].strip().lower() == name.strip().lower() and
                r["school"].strip().lower() == school.strip().lower() and
                r["class_"].strip().lower() == class_.strip().lower()
            ):
                return True
        return False

    if student_exists(name, school, class_, exam_id):
        st.warning("Bạn đã nộp bài cho đề này. Không thể làm lại!")
        st.stop()

    # Countdown và giới hạn thời gian
    # Nút "Bắt đầu làm bài"
    if f"time_end_{exam_id}" not in st.session_state:
        if st.button("🚀 Bắt đầu làm bài"):
            st.session_state[f"time_end_{exam_id}"] = (datetime.now() + timedelta(minutes=exam_time)).strftime('%Y-%m-%d %H:%M:%S')
            st.rerun()
        else:
            st.info("Ấn 'Bắt đầu làm bài' để tính thời gian và vào bài kiểm tra.")
            st.stop()


    now = datetime.now()
    time_end = datetime.strptime(st.session_state[f"time_end_{exam_id}"], '%Y-%m-%d %H:%M:%S')
    seconds_left = int((time_end - now).total_seconds())
    if seconds_left <= 0:
        st.error("⏰ Đã hết thời gian làm bài! Bạn chỉ có thể nộp bài, mọi lựa chọn đã bị khóa.")
        allow_do = False
    else:
        mins, secs = divmod(seconds_left, 60)
        st.success(f"⏳ Thời gian còn lại: {mins:02d}:{secs:02d}")
        allow_do = True

    # RANDOM ĐỀ THEO NHÓM
    if f"stu_img_rand_idx_{exam_id}" not in st.session_state:
        shuffled_questions, indices = randomize_by_group(exam_data["questions"])
        st.session_state[f"stu_img_rand_idx_{exam_id}"] = indices
        st.session_state[f"stu_img_rand_questions_{exam_id}"] = shuffled_questions
    questions = st.session_state[f"stu_img_rand_questions_{exam_id}"]

    # Đáp án
    if f"stu_img_answers_{exam_id}" not in st.session_state or len(st.session_state[f"stu_img_answers_{exam_id}"]) != len(questions):
        st.session_state[f"stu_img_answers_{exam_id}"] = [None] * len(questions)

    opts = ["A", "B", "C", "D"]
    for i, q in enumerate(questions):
        if q.get("type") == "mcq":
            st.markdown(f"### Câu {i+1} (Trắc nghiệm)")
            display_image_base64(q["img_data"], caption=f"Câu hỏi {i+1}", img_ratio=img_ratio)
            cols = st.columns(4)
            for idx, opt in enumerate(opts):
                btn_style = (
                    "background-color:#FFD700;color:black;font-weight:bold;border-radius:10px;font-size:20px;padding:18px 0px;"
                    if st.session_state[f"stu_img_answers_{exam_id}"][i] == opt
                    else "background-color:white;color:#FFD700;border:2px solid #FFD700;border-radius:10px;font-size:20px;padding:18px 0px;"
                )
                if allow_do:
                    if cols[idx].button(opt, key=f"ans_{i}_{opt}_{exam_id}", use_container_width=True):
                        st.session_state[f"stu_img_answers_{exam_id}"][i] = opt
                if st.session_state[f"stu_img_answers_{exam_id}"][i] == opt:
                    cols[idx].markdown(
                        f"<div style='{btn_style};text-align:center;margin-top:-40px;position:relative;z-index:1;'>{opt}</div>",
                        unsafe_allow_html=True
                    )
            if st.session_state[f"stu_img_answers_{exam_id}"][i]:
                st.success(f"Đã chọn đáp án: {st.session_state[f'stu_img_answers_{exam_id}'][i]}")
            else:
                st.info("Hãy chọn đáp án.")
        elif q.get("type") == "true_false":
            st.markdown(f"### Câu {i+1} (Đúng/Sai từng ý)")
            display_image_base64(q["img_data"], caption=f"Câu hỏi Đúng/Sai {i+1}", img_ratio=img_ratio)
            cols = st.columns(2)
            tf_labels = ["Ý a", "Ý b", "Ý c", "Ý d"]
            if isinstance(st.session_state[f"stu_img_answers_{exam_id}"][i], list) and len(st.session_state[f"stu_img_answers_{exam_id}"][i]) == 4:
                user_tf = st.session_state[f"stu_img_answers_{exam_id}"][i]
            else:
                user_tf = [None]*4
            for j in range(4):
                key_true = f"tf_{i}_{j}_Đ_{exam_id}"
                key_false = f"tf_{i}_{j}_S_{exam_id}"
                with cols[0]:
                    val_true = st.checkbox(tf_labels[j] + " - Đúng", key=key_true, value=(user_tf[j]=="Đ"), disabled=not allow_do)
                with cols[1]:
                    val_false = st.checkbox(tf_labels[j] + " - Sai", key=key_false, value=(user_tf[j]=="S"), disabled=not allow_do)
                if val_true and val_false:
                    if st.session_state[key_true]: st.session_state[key_false] = False
                    if st.session_state[key_false]: st.session_state[key_true] = False
                    val_false = not val_true
                user_tf[j] = "Đ" if val_true else ("S" if val_false else None)
            st.session_state[f"stu_img_answers_{exam_id}"][i] = user_tf
            st.info("Tick mỗi ý 1 đáp án Đúng/Sai.")
        elif q.get("type") == "short_answer":
            st.markdown(f"### Câu {i+1} (Trả lời ngắn)")
            display_image_base64(q["img_data"], caption=f"Câu trả lời ngắn {i+1}", img_ratio=img_ratio)
            ans = st.text_input("Nhập đáp án của bạn:", key=f"sa_{i}_{exam_id}", disabled=not allow_do)
            st.session_state[f"stu_img_answers_{exam_id}"][i] = ans

    # Chỉ hiện nút Nộp nếu còn thời gian hoặc hết thời gian <= 30 giây
    if st.button("Nộp bài", disabled=(seconds_left <= -30)):
        answers = st.session_state[f"stu_img_answers_{exam_id}"]
        total_score = 0.0
        for i, q in enumerate(questions):
            if q.get("type") == "mcq":
                if answers[i] == q["answer"]:
                    total_score += 0.25
            elif q.get("type") == "true_false":
                if isinstance(answers[i], list) and len(answers[i]) == 4 and all(x in ["Đ","S"] for x in answers[i]):
                    correct_cnt = sum([answers[i][k] == q["answers"][k] for k in range(4)])
                    if correct_cnt == 1:
                        total_score += 0.1
                    elif correct_cnt == 2:
                        total_score += 0.25
                    elif correct_cnt == 3:
                        total_score += 0.5
                    elif correct_cnt == 4:
                        total_score += 1.0
            elif q.get("type") == "short_answer":
                ans = str(answers[i]).replace(" ", "")
                key = str(q["answer"]).replace(" ", "")
                if ans and ans.lower() == key.lower():
                    total_score += 0.5
        total_score = round(total_score, 2)
        save_result({
            "name": name,
            "school": school,
            "class_": class_,
            "answers": answers,
            "score": total_score,
            "rand_indices": st.session_state[f"stu_img_rand_idx_{exam_id}"],
        }, exam_id)

        if allow_review:
            st.success(f"Đã nộp bài! Tổng điểm: {total_score}")
            st.write("---")
            st.markdown(f"""
            <div style='
                background-color:#e6ffed;
                border-radius:10px;
                padding:18px;
                margin-bottom:10px;
                font-size:22px;
                border:2px solid #19c37d;
                text-align:center;'>
                <b>Điểm của bạn: <span style="color:#0d9455;font-size:30px;">{total_score}</span></b>
            </div>
            """, unsafe_allow_html=True)
            st.write("### Đáp án đúng và lời giải:")
            for i, (a, q) in enumerate(zip(answers, questions)):
                if q.get("type") == "mcq":
                    st.markdown(f"#### Câu {i+1} (Trắc nghiệm)")
                    col1, col2 = st.columns([1,1])
                    with col1:
                        display_image_base64(q["img_data"], caption=f"Đề bài {i+1}", img_ratio=img_ratio)
                        if a == q["answer"]:
                            st.success(f"Bạn chọn {a} ✅ Đúng")
                        elif a:
                            st.error(f"Bạn chọn {a} ❌ Sai (Đáp án đúng: {q['answer']})")
                        else:
                            st.warning("Bạn chưa trả lời câu này")
                    with col2:
                        if q.get("da_img_data"):
                            display_image_base64(q["da_img_data"], caption=f"Lời giải {i+1}", img_ratio=img_ratio)
                        else:
                            st.info("Không có ảnh lời giải")
                elif q.get("type") == "true_false":
                    st.markdown(f"#### Câu {i+1} (Đúng/Sai từng ý)")
                    col1, col2 = st.columns([1,1])
                    with col1:
                        display_image_base64(q["img_data"], caption=f"Đề bài Đúng/Sai {i+1}", img_ratio=img_ratio)
                        if isinstance(a, list):
                            for j in range(4):
                                label = f"Ý {j+1}: Bạn chọn {a[j]}" if a[j] else f"Ý {j+1}: Bạn chưa trả lời"
                                if a[j] and a[j] == q["answers"][j]:
                                    st.success(label + " ✅ Đúng")
                                elif a[j] and a[j] != q["answers"][j]:
                                    st.error(label + f" ❌ Sai (Đáp án: {q['answers'][j]})")
                                else:
                                    st.warning(label)
                        else:
                            st.warning("Bạn chưa trả lời câu này")
                    with col2:
                        if q.get("da_img_data"):
                            display_image_base64(q["da_img_data"], caption=f"Lời giải Đ/S {i+1}", img_ratio=img_ratio)
                        else:
                            st.info("Không có ảnh lời giải")
                elif q.get("type") == "short_answer":
                    st.markdown(f"#### Câu {i+1} (Trả lời ngắn)")
                    col1, col2 = st.columns([1,1])
                    with col1:
                        display_image_base64(q["img_data"], caption=f"Câu trả lời ngắn {i+1}", img_ratio=img_ratio)
                        ans_disp = a if a else "(Bạn chưa trả lời)"
                        if a and str(a).replace(" ","").lower() == str(q["answer"]).replace(" ","").lower():
                            st.success(f"Bạn trả lời: {ans_disp} ✅ Đúng")
                        elif a:
                            st.error(f"Bạn trả lời: {ans_disp} ❌ Sai (Đáp án đúng: {q['answer']})")
                        else:
                            st.warning("Bạn chưa trả lời câu này")
                    with col2:
                        if q.get("da_img_data"):
                            display_image_base64(q["da_img_data"], caption=f"Lời giải TLN {i+1}", img_ratio=img_ratio)
                        else:
                            st.info("Không có ảnh lời giải")
        else:
            st.success("Bạn đã hoàn thành bài thi. Hãy chờ giáo viên công bố kết quả.")
            st.stop()
