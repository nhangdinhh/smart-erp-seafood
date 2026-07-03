from odoo import models, fields, api
from datetime import datetime, timedelta

class SeafoodLot(models.Model):
    _inherit = 'stock.lot'

    storage_temperature = fields.Float(string='Nhiệt độ bảo quản (°C)', default=-18.0)
    origin_area = fields.Char(string='Vùng nuôi/Tàu cá đánh bắt')
    quality_grade = fields.Selection([
        ('A', 'Loại A (Xuất khẩu)'),
        ('B', 'Loại B (Nội địa cao cấp)'),
        ('C', 'Loại C (Chế biến phụ phẩm)'),
    ], string='Phân loại chất lượng')
    
    # AI Feature fields
    ai_discount_recommendation = fields.Float(string='Gợi ý giảm giá AI (%)', compute='_compute_ai_discount', store=True)
    ai_warning_message = fields.Char(string='Cảnh báo AI', compute='_compute_ai_discount', store=True)

    @api.depends('expiration_date')
    def _compute_ai_discount(self):
        for lot in self:
            if not lot.expiration_date:
                lot.ai_discount_recommendation = 0.0
                lot.ai_warning_message = 'Không có HSD'
                continue
                
            # Đơn giản hóa thuật toán AI cho mục đích học tập
            # Nếu còn dưới 7 ngày: Gợi ý giảm 30%
            # Nếu còn dưới 3 ngày: Gợi ý giảm 50%
            days_left = (lot.expiration_date - datetime.now()).days
            
            if days_left <= 0:
                lot.ai_discount_recommendation = 100.0
                lot.ai_warning_message = 'HÀNG HẾT HẠN - CHỜ HỦY'
            elif days_left <= 3:
                lot.ai_discount_recommendation = 50.0
                lot.ai_warning_message = 'NGUY HIỂM: Gợi ý xả hàng gấp!'
            elif days_left <= 7:
                lot.ai_discount_recommendation = 30.0
                lot.ai_warning_message = 'CẢNH BÁO: Hàng cận Date'
            else:
                lot.ai_discount_recommendation = 0.0
                lot.ai_warning_message = 'An toàn'

    @api.model
    def _cron_check_expiration_ai(self):
        """
        Hàm được gọi tự động bởi Cron Job mỗi ngày.
        Nó quét các lô hàng cận Date và gửi cảnh báo vào Chatter.
        """
        # Tìm các lô hàng có gợi ý giảm giá > 0
        lots_to_warn = self.search([
            ('ai_discount_recommendation', '>', 0.0)
        ])
        
        from markupsafe import Markup
        
        for lot in lots_to_warn:
            # Nếu ngày hết hạn lớn hơn ngày hiện tại (chưa hết hạn hẳn)
            if lot.expiration_date and lot.expiration_date > datetime.now():
                msg = Markup(f"""
                    <div style='color: red; font-weight: bold; font-size: 14px;'>
                        <i class="fa fa-exclamation-triangle"></i> HỆ THỐNG AI CẢNH BÁO TỰ ĐỘNG
                    </div>
                    <ul>
                        <li><b>Tình trạng:</b> {lot.ai_warning_message}</li>
                        <li><b>Đề xuất xử lý:</b> Lên chiến dịch giảm giá {lot.ai_discount_recommendation}% ngay lập tức.</li>
                    </ul>
                """)
                # Gửi log vào lịch sử của lô hàng
                lot.message_post(body=msg, subtype_xmlid='mail.mt_note')

    def action_analyze_ai(self):
        """
        Nút bấm thủ công gọi trực tiếp API của Google Gemini để phân tích Lô hàng
        """
        self.ensure_one()
        from markupsafe import Markup
        import requests
        import json
        from odoo.exceptions import UserError
        
        # 1. Lấy API Key từ Cấu hình hệ thống (Bảo mật chuyên nghiệp)
        api_key_param = self.env['ir.config_parameter'].sudo().get_param('gemini_api_key')
        api_key = api_key_param.strip() if api_key_param else False
        
        if not api_key:
            raise UserError("🚨 CHƯA CẤU HÌNH API KEY!\n\nHệ thống cần khóa API của Google Gemini để hoạt động.\n\nVui lòng làm theo hướng dẫn sau:\n1. Vào Thiết lập (Settings) -> Kỹ thuật (Technical) -> Tham số hệ thống (System Parameters).\n2. Tạo một tham số mới với:\n   - Khóa (Key): gemini_api_key\n   - Giá trị (Value): [Dán API Key bạn lấy từ Google AI Studio vào đây]")
            
        # 2. Xây dựng Prompt (Câu lệnh) gửi cho AI
        days_left = (self.expiration_date - datetime.now()).days if self.expiration_date else 'Không rõ'
        prompt = f"""
        Bạn là một chuyên gia phân tích chuỗi cung ứng thủy sản cấp cao.
        Hãy phân tích Lô hàng sau và đưa ra chiến lược kinh doanh cực kỳ ngắn gọn (dưới 150 chữ):
        - Tên sản phẩm: {self.product_id.name}
        - Vùng xuất xứ: {self.origin_area or 'Chưa rõ'}
        - Nhiệt độ bảo quản hiện tại: {self.storage_temperature}°C
        - Số ngày còn lại trước khi hết hạn: {days_left} ngày.
        
        Yêu cầu trả về báo cáo theo định dạng HTML (chỉ dùng các thẻ <b>, <i>, <ul>, <li>, <p>). KHÔNG dùng markdown. 
        Nội dung bắt buộc gồm 3 phần: Đánh giá chất lượng, Phân tích thị trường, và Đề xuất chiến lược (Bao gồm mức % giảm giá cụ thể).
        """
        
        target_model = "models/gemini-1.5-flash-latest" # Mặc định
        flash_models = [target_model]
        try:
            list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            list_res = requests.get(list_url, timeout=10)
            if list_res.status_code == 200:
                models_data = list_res.json().get('models', [])
                valid_models = [m['name'] for m in models_data if 'generateContent' in m.get('supportedGenerationMethods', [])]
                found_flash = [m for m in valid_models if 'flash' in m and 'gemini' in m]
                if found_flash:
                    flash_models = found_flash
        except Exception:
            pass
            
        last_error = None
        result = None
        for model_name in flash_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={api_key}"
            headers = {'Content-Type': 'application/json'}
            data = {"contents": [{"parts": [{"text": prompt}]}]}
            
            try:
                response = requests.post(url, headers=headers, data=json.dumps(data), timeout=15)
                response.raise_for_status()
                result = response.json()
                break
            except Exception as e:
                last_error = str(e)
                continue
                
        if not result:
            raise UserError(f"Tất cả các model AI đều bị quá tải hoặc lỗi kết nối. Lỗi cuối: {last_error}")
            
        try:
            ai_text = result['candidates'][0]['content']['parts'][0]['text']
            ai_text = ai_text.replace('```html', '').replace('```', '')
        except Exception as e:
            raise UserError(f"Lỗi phân tích kết quả từ AI: {str(e)}")
        except Exception as e:
            raise UserError(f"Lỗi mất kết nối với Google AI: {str(e)}")
            
        # 4. Lưu báo cáo vào hệ thống (Chatter)
        msg = Markup(f"""
            <div style='background-color: #f0fdf4; border-left: 4px solid #16a34a; padding: 10px; margin: 10px 0;'>
                <h4 style='color: #166534; margin-top: 0;'><i class="fa fa-line-chart"></i> BÁO CÁO PHÂN TÍCH THỰC TẾ TỪ GOOGLE GEMINI AI</h4>
                {ai_text}
            </div>
        """)
        
        self.message_post(body=msg, subtype_xmlid='mail.mt_note')
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Gemini AI Phân tích thành công!',
                'message': 'Đã nhận kết nối trực tiếp từ Google. Xem báo cáo chi tiết ở phần Lịch sử bên dưới.',
                'type': 'success',
                'sticky': False,
            }
        }

