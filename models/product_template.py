from odoo import models, fields, api
import requests
import json
from datetime import datetime, timedelta
from odoo.exceptions import UserError
from markupsafe import Markup

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    ai_restock_suggestion = fields.Char(string='AI Đề xuất Nhập hàng', readonly=True, help="Số lượng đề xuất nhập hàng từ Giám đốc Chuỗi cung ứng AI")
    ai_forecast_date = fields.Datetime(string='Lần dự báo cuối', readonly=True)

    def action_forecast_demand_ai(self):
        self.ensure_one()
        api_key_param = self.env['ir.config_parameter'].sudo().get_param('gemini_api_key')
        api_key = api_key_param.strip() if api_key_param else False
        
        if not api_key:
            raise UserError("🚨 CHƯA CẤU HÌNH API KEY!\nVui lòng cấu hình 'gemini_api_key' trong System Parameters.")
            
        # 1. Thu thập dữ liệu bán hàng 30 ngày qua
        thirty_days_ago = fields.Datetime.now() - timedelta(days=30)
        domain = [
            ('product_id.product_tmpl_id', '=', self.id),
            ('order_id.state', 'in', ['sale', 'done']),
            ('order_id.date_order', '>=', thirty_days_ago)
        ]
        
        # Nếu model là product.product thì sẽ dùng cách khác, nhưng ở đây là template nên join sang sale.order.line
        order_lines = self.env['sale.order.line'].search(domain)
        
        total_sold = sum(order_lines.mapped('product_uom_qty'))
        current_stock = self.qty_available
        
        prompt = f"""Bạn là Giám đốc Chuỗi Cung Ứng AI của Nhang Dinh Seafood.
Phân tích mặt hàng sau để lên kế hoạch nhập hàng cho 7 ngày tới:
- Tên sản phẩm: {self.name}
- Tồn kho hiện tại: {current_stock} kg
- Tổng bán ra (30 ngày qua): {total_sold} kg
- Tốc độ bán trung bình: {total_sold/30:.1f} kg/ngày

Nhiệm vụ:
1. Đưa ra một câu đề xuất ngắn gọn (dưới 15 chữ) làm Tiêu đề. Ví dụ: 'Nhập gấp 50kg', 'Giữ nguyên tồn kho', 'Xả hàng, không nhập'.
2. Đưa ra lập luận giải thích ngắn gọn (dưới 80 chữ) bằng tiếng Việt. Sử dụng HTML (<b>, <ul>, <li>) để trang trí, không dùng markdown.

Trả về định dạng JSON nguyên thủy:
{{
  "short_suggestion": "tiêu đề",
  "reasoning": "lập luận html"
}}"""

        target_model = "models/gemini-1.5-flash-latest"
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
                break # Success!
            except Exception as e:
                last_error = str(e)
                continue
                
        if not result:
            raise UserError(f"Tất cả các model AI đều đang bị quá tải hoặc lỗi kết nối. Chi tiết lỗi cuối: {last_error}")
            
        try:
            ai_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
            
            if ai_text.startswith('```json'): ai_text = ai_text[7:]
            if ai_text.startswith('```'): ai_text = ai_text[3:]
            if ai_text.endswith('```'): ai_text = ai_text[:-3]
            ai_text = ai_text.strip()
            
            parsed_res = json.loads(ai_text)
            
            self.ai_restock_suggestion = parsed_res.get('short_suggestion', 'Chưa có đề xuất')
            self.ai_forecast_date = fields.Datetime.now()
            
            msg = Markup(f"""
                <div style='background-color: #f0f9ff; border-left: 4px solid #0284c7; padding: 10px; margin: 10px 0;'>
                    <h4 style='color: #0369a1; margin-top: 0;'><i class="fa fa-line-chart"></i> AI DỰ BÁO NHU CẦU: {self.ai_restock_suggestion}</h4>
                    {parsed_res.get('reasoning', '')}
                </div>
            """)
            self.message_post(body=msg, subtype_xmlid='mail.mt_note')
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Dự báo thành công!',
                    'message': f'AI Đề xuất: {self.ai_restock_suggestion}',
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            raise UserError(f"Lỗi phân tích kết quả từ AI: {str(e)}\n\nRAW: {ai_text if 'ai_text' in locals() else ''}")
