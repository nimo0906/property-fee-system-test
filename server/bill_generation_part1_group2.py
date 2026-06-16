from server.bill_generation_shared import *

class BillGenerationMixinPart1Group2(BaseHandler):
    def _parse_bill_generation_filters(self, d):
        return {
            'building': qs(d, 'building').strip(),
            'category': qs(d, 'category').strip(),
            'room_from': qs(d, 'room_from').strip(),
            'room_to': qs(d, 'room_to').strip(),
            'unit': qs(d, 'unit').strip(),
            'mode_scope': qs(d, 'mode_scope').strip(),
        }

    def _parse_fee_type_ids(self, d):
        raw_ft = d.get('fee_type_ids', [])
        if isinstance(raw_ft, list):
            all_ids = []
            for item in raw_ft:
                all_ids.extend(x.strip() for x in item.split(',') if x.strip())
            return [int(x) for x in all_ids]
        return [int(x) for x in raw_ft.split(',') if x]

    def _build_bill_generation_plan(self, db, period, due_date, ft_ids, filters=None, period_start='', period_end='', month_count=1):
        filters = filters or {}
        period_start = period_start or period_to_date(period)
        period_end = period_end or due_date
        rooms = [r for r in self._query_bill_generation_rooms(db, filters) if _room_active_in_date_range(r, period_start, period_end)]
        fts_map = {f['id']: f for f in db.execute("SELECT * FROM fee_types WHERE is_active=1").fetchall()}
        owners_map = {o['id']: o['name'] for o in db.execute("SELECT id,name FROM owners").fetchall()}
        owners_map[None] = '未知'
        existing = {row[0] for row in db.execute(
            "SELECT DISTINCT room_id || ':' || fee_type_id || ':' || billing_period FROM bills"
        ).fetchall()}
        items = []
        skipped = 0
        for rm in rooms:
            rcat = rm['category'] or '居民'
            for fid in ft_ids:
                ft = fts_map.get(fid)
                if not ft or not fee_applies_to_room(ft['name'] or '', rm):
                    continue
                bill_months = month_count
                bill_period = period
                service_end = period_end
                key = f"{rm['id']}:{fid}:{bill_period}"
                if key in existing:
                    skipped += 1
                    continue
                calc = calculate_bill_amount(db, rm, ft, bill_period, bill_months, None, period_start, service_end)
                amt = calc['amount']
                formula = calc['formula']
                if amt <= 0:
                    continue
                items.append({
                    'room_id': rm['id'], 'fee_type_id': fid, 'amount': amt, 'formula': formula, 'billing_period': bill_period, 'months': bill_months,
                    'building': rm['building'], 'room_number': rm['room_number'],
                    'category': rcat, 'fee_name': ft['name'], 'calc_method': ft['calc_method'],
                    'service_start': period_start, 'service_end': service_end, 'due_date': due_date,
                })
        inactive = len(self._query_bill_generation_rooms(db, filters)) - len(rooms)
        return {'items': items, 'skipped': skipped, 'inactive': inactive, 'existing_keys': existing, 'owners_map': owners_map, 'rooms': rooms}

    def _query_bill_generation_rooms(self, db, filters):
        sql = "SELECT * FROM rooms"
        cond = []
        vals = []
        if filters.get('building'):
            cond.append("building=?")
            vals.append(filters['building'])
        if filters.get('category'):
            cond.append("category=?")
            vals.append(filters['category'])
        if filters.get('unit'):
            cond.append("unit=?")
            vals.append(filters['unit'])
        if filters.get('mode_scope') == 'commercial':
            cond.append("unit='商场'")
            cond.append("category IN ('商户','商业')")
        if filters.get('room_from'):
            cond.append("room_number>=?")
            vals.append(filters['room_from'])
        if filters.get('room_to'):
            cond.append("room_number<=?")
            vals.append(filters['room_to'])
        if cond:
            sql += " WHERE " + " AND ".join(cond)
        sql += " ORDER BY building,unit,room_number"
        return db.execute(sql, vals).fetchall()
