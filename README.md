# 🌊 Seafood Management AI ERP
## Thuc hanh DevOps Lab 2 - Git & Jenkins
![Odoo](https://img.shields.io/badge/Odoo-19.0-purple?style=flat-square&logo=odoo)
![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)
![AI](https://img.shields.io/badge/AI-Google%20Gemini-orange?style=flat-square&logo=google)

Module **Seafood Management AI** là hệ thống Quản trị Doanh nghiệp (ERP) thông minh được phát triển trên nền tảng Odoo, chuyên biệt cho ngành cung ứng Thủy Hải Sản. Hệ thống tích hợp trực tiếp với API trí tuệ nhân tạo tạo sinh (GenAI) của Google Gemini để tự động hóa và tối ưu hóa các quy trình cốt lõi.

## ✨ Tính năng nổi bật

### 1. 🤖 Đầu Bếp AI & Trợ lý Chốt Sale (Website)
- Chatbot thông minh tự động đọc dữ liệu tồn kho theo thời gian thực để tư vấn món ăn và báo giá cho khách hàng.
- Tự động thay đổi mô hình AI (Auto-fallback) nếu máy chủ Google quá tải, đảm bảo web luôn hoạt động 24/7.

### 2. 📊 Khách Hàng Thông Minh (CRM AI)
- Phân tích lịch sử mua hàng của khách (Số lượng, giá trị, tần suất).
- AI tự động gán nhãn phân loại (VIP, Tiềm năng, Rời bỏ) và đề xuất chiến lược tiếp thị (Marketing) cá nhân hóa cho từng khách hàng.

### 3. 📉 Dự Báo Nhu Cầu & Nhập Hàng (Supply Chain AI)
- AI phân tích tốc độ bán ra (Sales Velocity) trong 30 ngày qua và lượng tồn kho hiện tại.
- Tự động ra quyết định chiến lược: Đề xuất nhập thêm khẩn cấp, giữ nguyên tồn kho, hoặc xả kho.

### 4. ⚠️ Quản lý Lô Hàng & Cảnh báo Hạn (Inventory AI)
- Lệnh ngầm (Cron Job) tự động quét toàn bộ kho lúc nửa đêm.
- Nếu phát hiện hải sản sắp hết hạn bảo quản, AI tự động đánh giá mức độ suy giảm chất lượng và **tự động tính toán mức % giảm giá (Discount)** phù hợp để xả hàng ngay lập tức.

## 📂 Cấu trúc thư mục (Professional Odoo Structure)
```text
seafood_management/
├── controllers/          # Xử lý API và logic Frontend (Chatbot, Web)
├── data/                 # Dữ liệu mẫu và Cấu hình Cron Job tự động hóa
├── models/               # Kế thừa Database (Bổ sung trường dữ liệu AI)
├── security/             # Phân quyền bảo mật truy cập
├── static/               # Assets (Hình ảnh, CSS, JS)
├── views/                # Giao diện Backend và Frontend Odoo (XML)
├── __init__.py           
├── __manifest__.py       # Khai báo cấu hình Module Odoo
└── README.md             # Tài liệu dự án
```

## 🚀 Hướng dẫn cài đặt
1. Clone repository này vào thư mục `addons` của hệ thống Odoo.
2. Mở file `odoo.conf` và thêm cấu hình System Parameter `gemini_api_key`.
3. Bật chế độ Developer Mode trên Odoo.
4. Cập nhật danh sách ứng dụng và cài đặt `Seafood Management`.

---
*Phát triển bởi Nhang Dinh - Đồ án Tốt nghiệp / Thực tập 2026*
