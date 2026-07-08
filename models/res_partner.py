from odoo import models, fields, api
import requests
import json
from odoo.exceptions import UserError
from markupsafe import Markup

class ResPartner(models.Model):
    _inherit = 'res.partner'

    ai_segmentation_tag = fields.Char(string='Phân loại khách hàng (AI)', readonly=True, help="Nhãn (Tag) được gán tự động bởi AI.")

    def action_analyze_customer_ai(self):
        self.ensure_one()
        api_key_param = self.env['ir.config_parameter'].sudo().get_param('gemini_api_key')
        api_key = api_key_param.strip() if api_key_param else False
        
        if not api_key:
            raise UserError("🚨 CHƯA CẤU HÌNH API KEY!\nVui lòng cấu hình 'gemini_api_key' trong System Parameters.")
            
        # Gather customer data
        orders = self.env['sale.order'].search([
            ('partner_id', '=', self.id),
            ('state', 'in', ['sale', 'done'])
        ])
        
        total_spent = sum(orders.mapped('amount_total'))
        order_count = len(orders)
        
        product_names = []
        for order in orders:
            for line in order.order_line:
                if line.product_id:
                    product_names.append(line.product_id.name)
        
        product_summary = "Chưa mua gì"
        if product_names:
            from collections import Counter
            counts = Counter(product_names)
            top_products = [f"{name} ({qty} lần)" for name, qty in counts.most_common(5)]
            product_summary = ", ".join(top_products)

        prompt = f"""Bạn là Giám đốc Marketing AI của Nhang Dinh Seafood.
Phân tích lịch sử mua sắm của khách hàng này:
- Tên khách hàng: {self.name}
- Tổng số đơn đã chốt: {order_count}
- Tổng số tiền đã chi: {total_spent:,.0f} VND
- Sở thích (Sản phẩm hay mua): {product_summary}

Nhiệm vụ:
1. Đặt 1 thẻ (Tag) cực ngắn (tối đa 4 từ) đại diện cho khách này (ví dụ: 'Đại Gia', 'Fan Cá Hồi', 'Khách Vãng Lai').
2. Đề xuất chiến lược chăm sóc và Up-sell (Bán kèm) dưới 100 chữ bằng tiếng Việt. Bọc chiến lược trong các thẻ HTML cơ bản (<b>, <ul>, <li>) cho đẹp mắt.

Trả về duy nhất định dạng JSON nguyên thủy sau (không dùng markdown block):
{{
  "tag": "tên thẻ",
  "strategy": "chiến lược html"
}}"""

        target_model = "models/gemini-1.5-flash-latest" # Fallback
        try:
            list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            list_res = requests.get(list_url, timeout=10)
            if list_res.status_code == 200:
                models_data = list_res.json().get('models', [])
                valid_models = [m['name'] for m in models_data if 'generateContent' in m.get('supportedGenerationMethods', [])]
                flash_models = [m for m in valid_models if 'flash' in m and 'gemini' in m]
                if flash_models:
                    target_model = flash_models[0]
                elif valid_models:
                    target_model = valid_models[0]
        except Exception:
            pass
            
        url = f"https://generativelanguage.googleapis.com/v1beta/{target_model}:generateContent?key={api_key}"
        headers = {'Content-Type': 'application/json'}
        data = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        
        try:
            response = requests.post(url, headers=headers, data=json.dumps(data), timeout=15)
            response.raise_for_status()
            result = response.json()
            
            ai_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
            
            # Clean up markdown if any
            if ai_text.startswith('```json'): ai_text = ai_text[7:]
            if ai_text.startswith('```'): ai_text = ai_text[3:]
            if ai_text.endswith('```'): ai_text = ai_text[:-3]
            ai_text = ai_text.strip()
            
            parsed_res = json.loads(ai_text)
            
            # Save Tag
            self.ai_segmentation_tag = parsed_res.get('tag', 'Không rõ')
            
            # Post chatter message
            msg = Markup(f"""
                <div style='background-color: #fdf4ff; border-left: 4px solid #c026d3; padding: 10px; margin: 10px 0;'>
                    <h4 style='color: #86198f; margin-top: 0;'><i class="fa fa-magic"></i> AI PHÂN TÍCH KHÁCH HÀNG: {self.ai_segmentation_tag}</h4>
                    {parsed_res.get('strategy', '')}
                </div>
            """)
            self.message_post(body=msg, subtype_xmlid='mail.mt_note')
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'AI Đã Phân Tích Xong!',
                    'message': f'Khách hàng được gắn nhãn: {self.ai_segmentation_tag}',
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            raise UserError(f"Lỗi kết nối hoặc xử lý AI: {str(e)}\n\nRAW: {ai_text if 'ai_text' in locals() else ''}")
