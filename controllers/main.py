from odoo import http
from odoo.http import request

class SeafoodAIWebsite(http.Controller):
    
    @http.route('/seafood/ai-market', type='http', auth='public')
    def ai_market(self, **kwargs):
        # Lấy tất cả các lô hàng thủy sản
        lots = request.env['stock.lot'].sudo().search([])
        
        # Render giao diện trang chủ cực xịn
        return request.render('seafood_management.seafood_ai_shop', {
            'lots': lots
        })
        
    @http.route('/seafood/generate_stock', type='http', auth='public')
    def generate_stock(self, **kwargs):
        lots = request.env['stock.lot'].sudo().search([])
        wh = request.env['stock.warehouse'].sudo().search([], limit=1)
        if not wh:
            return "No warehouse found"
        loc_id = wh.lot_stock_id.id
        
        import random
        count = 0
        for lot in lots:
            # Fix error: Cannot create quant for consumable/service
            # We must ensure the product is a "storable" product
            
            # Skip consumable/service products safely to avoid breaking DB transaction
            if getattr(lot.product_id, 'detailed_type', None) != 'product' and getattr(lot.product_id, 'type', None) != 'product':
                try:
                    with request.env.cr.savepoint():
                        request.env.cr.execute("UPDATE product_template SET type='product' WHERE id=%s", (lot.product_id.product_tmpl_id.id,))
                except Exception:
                    pass
                try:
                    with request.env.cr.savepoint():
                        request.env.cr.execute("UPDATE product_template SET detailed_type='product' WHERE id=%s", (lot.product_id.product_tmpl_id.id,))
                except Exception:
                    pass
                try:
                    with request.env.cr.savepoint():
                        request.env.cr.execute("UPDATE product_template SET is_storable=true WHERE id=%s", (lot.product_id.product_tmpl_id.id,))
                except Exception:
                    pass
                    
            qty = random.randint(30, 200)
            try:
                quant = request.env['stock.quant'].sudo().search([
                    ('product_id', '=', lot.product_id.id),
                    ('lot_id', '=', lot.id),
                    ('location_id', '=', loc_id)
                ], limit=1)
                
                if not quant:
                    quant = request.env['stock.quant'].sudo().create({
                        'product_id': lot.product_id.id,
                        'lot_id': lot.id,
                        'location_id': loc_id,
                    })
                quant.inventory_quantity = qty
                quant.action_apply_inventory()
                count += 1
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Could not add stock for lot %s: %s", lot.id, str(e))
                continue
            
        return f"Successfully added random stock (30-200 kg) to {count} lots!"
        
    @http.route('/seafood/checkout', type='json', auth='public')
    def ai_checkout(self, items, customer_info=None, **kwargs):
        # Tạo đơn hàng (Sale Order)
        partner = request.env.ref('base.public_partner')
        
        payment_note = ""
        if customer_info and customer_info.get('phone'):
            phone = customer_info['phone']
            name = customer_info.get('name', 'Khách hàng Seafood')
            address = customer_info.get('address', '')
            payment_method = customer_info.get('payment_method', 'cod')
            
            if payment_method == 'cod': payment_note = "Thanh toán: Tiền mặt khi nhận hàng (COD)"
            elif payment_method == 'bank': payment_note = "Thanh toán: Chuyển khoản Ngân hàng"
            elif payment_method == 'momo': payment_note = "Thanh toán: Ví MoMo / ZaloPay"
            
            partner_sudo = request.env['res.partner'].sudo()
            partner = partner_sudo.search([('phone', '=', phone)], limit=1)
            if partner:
                # Cập nhật thông tin giao hàng mới nhất
                partner.write({'name': name, 'street': address})
            else:
                partner = partner_sudo.create({
                    'name': name,
                    'phone': phone,
                    'street': address,
                })
        
        order_vals = {
            'partner_id': partner.id,
            'note': payment_note,
            'order_line': [],
        }
        
        for item in items:
            lot_id = int(item['lotId'])
            qty = int(item['qty'])
            lot = request.env['stock.lot'].sudo().browse(lot_id)
            
            # Tính giá
            price_unit = lot.product_id.list_price
            discount = lot.ai_discount_recommendation
            
            order_vals['order_line'].append((0, 0, {
                'product_id': lot.product_id.id,
                'product_uom_qty': qty,
                'price_unit': price_unit,
                'discount': discount,
                'name': f"{lot.product_id.name} (Lô: {lot.name})"
            }))
            
        order = request.env['sale.order'].sudo().create(order_vals)
        # Tự động xác nhận đơn hàng
        order.action_confirm()
        
        # Tự động xuất kho để trừ số lượng thực tế ngay lập tức cho từng Lô hàng
        try:
            for item in items:
                lot_id = int(item['lotId'])
                deduct_qty = int(item['qty'])
                
                quants = request.env['stock.quant'].sudo().search([
                    ('lot_id', '=', lot_id),
                    ('location_id.usage', '=', 'internal')
                ])
                
                for q in quants:
                    if deduct_qty <= 0:
                        break
                    available = q.quantity
                    if available > 0:
                        take = min(available, deduct_qty)
                        q.inventory_quantity = available - take
                        q.action_apply_inventory()
                        deduct_qty -= take
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Lỗi trừ tồn kho: %s", str(e))
        
        return {'status': 'success', 'order_id': order.name}

    @http.route('/seafood/my_orders', type='json', auth='public')
    def my_orders(self, phone, **kwargs):
        if not phone:
            return {'orders': []}
            
        partner = request.env['res.partner'].sudo().search([('phone', '=', phone)], limit=1)
        if not partner:
            return {'orders': []}
            
        orders = request.env['sale.order'].sudo().search([('partner_id', '=', partner.id)], order='date_order desc')
        
        res = []
        for o in orders:
            res.append({
                'id': o.name,
                'date': o.date_order.strftime('%d/%m/%Y %H:%M') if o.date_order else '',
                'total': o.amount_total,
                'items': sum(line.product_uom_qty for line in o.order_line),
                'state': o.state
            })
            
        return {'orders': res}

    @http.route('/seafood/init_images', type='http', auth='public')
    def init_images(self, **kwargs):
        import urllib.request
        import base64
        
        img_map = {
            'Cá Hố': 'https://images.unsplash.com/photo-1529144415895-6aaf8beae89f?q=80&w=500',
            'Cá Nục': 'https://images.unsplash.com/photo-1580481072645-022f9a6d4cb4?q=80&w=500',
            'Mực Ống': 'https://images.unsplash.com/photo-1551221884-2a62ff70d9bd?q=80&w=500',
            'Cua Biển': 'https://images.unsplash.com/photo-1520171286195-09559c402127?q=80&w=500',
            'Cá Ngừ': 'https://images.unsplash.com/photo-1615141982883-c7ad0e69fd62?q=80&w=500',
            'Bạch Tuộc': 'https://images.unsplash.com/photo-1551221884-2a62ff70d9bd?q=80&w=500',
            'Hàu Sữa': 'https://images.unsplash.com/photo-1565680018434-b513d5e5fd47?q=80&w=500',
            'Sò Huyết': 'https://images.unsplash.com/photo-1565680018434-b513d5e5fd47?q=80&w=500',
            'Cá Thu': 'https://images.unsplash.com/photo-1580481072645-022f9a6d4cb4?q=80&w=500',
            'Tôm Càng Xanh': 'https://images.unsplash.com/photo-1604909052743-94f877f240b9?q=80&w=500',
            'Tôm Hùm': 'https://images.unsplash.com/photo-1579899321151-5095e7b28f3f?q=80&w=500',
            'Mực Lá': 'https://images.unsplash.com/photo-1551221884-2a62ff70d9bd?q=80&w=500',
            'Ghẹ Xanh': 'https://images.unsplash.com/photo-1520171286195-09559c402127?q=80&w=500',
            'Ốc Hương': 'https://images.unsplash.com/photo-1565680018434-b513d5e5fd47?q=80&w=500',
            'Ngao 2 Cùi': 'https://images.unsplash.com/photo-1565680018434-b513d5e5fd47?q=80&w=500',
            'Cua Hoàng Đế': 'https://images.unsplash.com/photo-1496841733618-b27b3d4fba71?q=80&w=500',
            'Bào Ngư': 'https://images.unsplash.com/photo-1565680018434-b513d5e5fd47?q=80&w=500',
            'Tôm Tít': 'https://images.unsplash.com/photo-1600007283728-22ce9a51550d?q=80&w=500',
            'Cá Mú': 'https://images.unsplash.com/photo-1529144415895-6aaf8beae89f?q=80&w=500',
            'Mực Sữa': 'https://images.unsplash.com/photo-1551221884-2a62ff70d9bd?q=80&w=500',
        }
        
        products = request.env['product.template'].sudo().search([])
        updated = []
        for p in products:
            if p.name in img_map:
                try:
                    req = urllib.request.Request(img_map[p.name], headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req) as response:
                        img_data = response.read()
                        b64 = base64.b64encode(img_data)
                        p.write({'image_1920': b64})
                        updated.append(p.name)
                except Exception as e:
                    pass
        return "Images updated for: " + ", ".join(updated)

    @http.route('/seafood/chat', type='json', auth='public')
    def ai_chat(self, message, **kwargs):
        import requests
        import json
        
        api_key_param = request.env['ir.config_parameter'].sudo().get_param('gemini_api_key')
        api_key = api_key_param.strip() if api_key_param else False
        
        if not api_key:
            return {'status': 'error', 'message': 'Chưa cấu hình API Key của Google Gemini trong hệ thống!'}
            
        lots = request.env['stock.lot'].sudo().search([])
        product_context = ""
        for lot in lots[:15]:
            price = lot.product_id.list_price * (1 - lot.ai_discount_recommendation/100)
            product_context += f"- {lot.product_id.name} (Lô: {lot.name}): {price:,.0f} đ/kg\n"
            
        prompt = f"""
Bạn là chuyên gia ẩm thực hải sản và là nhân viên chốt sale của Nhang Dinh Seafood.
Kho hàng hôm nay có:
{product_context}

Khách hỏi: "{message}"

Trả lời tự nhiên, thân thiện, tư vấn trực tiếp vào câu hỏi và gợi ý sản phẩm phù hợp.
Trả lời cực kỳ ngắn gọn dưới 80 chữ, dùng text bình thường, KHÔNG dùng markdown.
"""
        target_model = "models/gemini-1.5-flash-latest"
        flash_models = [target_model]
        try:
            list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            list_res = requests.get(list_url, timeout=5)
            if list_res.status_code == 200:
                valid_models = [m['name'] for m in list_res.json().get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
                found_flash = [m for m in valid_models if 'flash' in m and 'gemini' in m]
                if found_flash: flash_models = found_flash
        except Exception:
            pass
            
        last_error = None
        result = None
        for model_name in flash_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={api_key}"
            headers = {'Content-Type': 'application/json'}
            data = {"contents": [{"parts": [{"text": prompt}]}]}
            
            try:
                response = requests.post(url, headers=headers, data=json.dumps(data), timeout=10)
                response.raise_for_status()
                result = response.json()
                break
            except Exception as e:
                last_error = str(e)
                continue
                
        if not result:
            return {'status': 'error', 'message': 'Hệ thống AI đang quá tải, vui lòng thử lại sau!'}
            
        try:
            ai_text = result['candidates'][0]['content']['parts'][0]['text']
            return {'status': 'success', 'message': ai_text}
        except Exception as e:
            return {'status': 'error', 'message': 'Lỗi xử lý phản hồi từ AI!'}

    @http.route('/seafood/ai-recipe', type='json', auth='public')
    def ai_recipe(self, product_name, **kwargs):
        import requests
        import json
        
        api_key_param = request.env['ir.config_parameter'].sudo().get_param('gemini_api_key')
        api_key = api_key_param.strip() if api_key_param else False
        
        if not api_key:
            return {'status': 'error', 'message': 'Chưa cấu hình API Key của Google Gemini trong hệ thống!'}
            
        prompt = f"""
Bạn là một siêu đầu bếp nhà hàng 5 sao. Hãy gợi ý 1 công thức nấu ăn cực ngon và chi tiết cho món: {product_name}.
Yêu cầu định dạng:
**Tên món:** (Tên món ăn sáng tạo)
**Nguyên liệu chuẩn bị:**
- ...
**Các bước thực hiện:**
- ...
**Mẹo nhỏ của đầu bếp:**
- ...
"""
        target_model = "models/gemini-1.5-flash-latest"
        flash_models = [target_model]
        try:
            list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            list_res = requests.get(list_url, timeout=5)
            if list_res.status_code == 200:
                valid_models = [m['name'] for m in list_res.json().get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
                found_flash = [m for m in valid_models if 'flash' in m and 'gemini' in m]
                if found_flash: flash_models = found_flash
        except Exception:
            pass
            
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
            except Exception:
                continue
                
        if not result:
            return {'status': 'error', 'message': 'Hệ thống Đầu Bếp AI đang quá tải, vui lòng thử lại sau!'}
            
        try:
            ai_text = result['candidates'][0]['content']['parts'][0]['text']
            return {'status': 'success', 'message': ai_text}
        except Exception as e:
            return {'status': 'error', 'message': 'Lỗi xử lý phản hồi từ AI!'}

    @http.route('/seafood/register', type='json', auth='public')
    def seafood_register(self, name, phone, email, address, password, **kwargs):
        Partner = request.env['res.partner'].sudo()
        if Partner.search([('phone', '=', phone)]):
            return {'status': 'error', 'message': 'Số điện thoại này đã được đăng ký!'}
            
        Partner.create({
            'name': name,
            'phone': phone,
            'email': email,
            'street': address,
            'comment': password,
        })
        return {'status': 'success', 'user_info': {'name': name, 'phone': phone, 'email': email, 'address': address}}

    @http.route('/seafood/login', type='json', auth='public')
    def seafood_login(self, email_or_phone, password, **kwargs):
        Partner = request.env['res.partner'].sudo()
        partner = Partner.search([('phone', '=', email_or_phone)], limit=1)
        if not partner:
            partner = Partner.search([('email', '=', email_or_phone)], limit=1)
            
        if not partner or partner.comment != password:
            return {'status': 'error', 'message': 'Sai thông tin đăng nhập hoặc mật khẩu!'}
            
        return {'status': 'success', 'user_info': {
            'name': partner.name,
            'phone': partner.phone,
            'email': partner.email,
            'address': partner.street or ''
        }}

    @http.route('/seafood/recommend', type='json', auth='public')
    def ai_recommend(self, lot_id, **kwargs):
        lots = request.env['stock.lot'].sudo().search([])
        try:
            target_lot = request.env['stock.lot'].sudo().browse(int(lot_id))
            target_cat = target_lot.product_id.categ_id.id
            
            similar_lots = []
            other_lots = []
            for l in lots:
                if l.id == target_lot.id: continue
                if l.product_id.categ_id.id == target_cat:
                    similar_lots.append(l)
                else:
                    other_lots.append(l)
                    
            import random
            random.shuffle(similar_lots)
            random.shuffle(other_lots)
            
            recommended = similar_lots[:3] + other_lots[:2]
            if len(recommended) < 5:
                recommended = (similar_lots + other_lots)[:5]
                
            res = [str(l.id) for l in recommended]
            return {'status': 'success', 'recommendations': res}
        except Exception:
            import random
            res = [str(l.id) for l in random.sample(list(lots), min(5, len(lots)))]
            return {'status': 'success', 'recommendations': res}
