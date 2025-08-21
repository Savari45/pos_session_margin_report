# -*- coding: utf-8 -*-
from odoo import api, models, fields
import logging

_logger = logging.getLogger(__name__)


class ReportSaleDetails(models.AbstractModel):
    _inherit = 'report.point_of_sale.report_saledetails'

    @api.model
    def get_sale_details(self, date_start=False, date_stop=False, config_ids=False, session_ids=False, **kwargs):
        _logger.info("[POS Session Margin] get_sale_details called with session_ids=%s, config_ids=%s, date_start=%s, date_stop=%s", session_ids, config_ids, date_start, date_stop)
        data = super().get_sale_details(date_start=date_start, date_stop=date_stop, config_ids=config_ids, session_ids=session_ids, **kwargs)

        # Compute session total margin and margin percentage
        orders_domain = self._get_domain(date_start, date_stop, config_ids, session_ids, **kwargs)
        orders = self.env['pos.order'].search(orders_domain)
        _logger.info("[POS Session Margin] Considered %s orders for margin computation", len(orders))

        # Try to compute margins in real-time for eligible lines (e.g., non FIFO/AVCO or when possible)
        try:
            orders._compute_total_cost_in_real_time()
        except Exception as e:
            _logger.info("[POS Session Margin] _compute_total_cost_in_real_time failed: %s", e)

        total_margin = 0.0
        amount_untaxed = 0.0
        # Ensure margins are computed (session closing already computes FIFO/AVCO lines; for open sessions
        # some margins might still be pending, so we only sum what is available per line)
        for order in orders:
            for line in order.lines:
                # Prefer accurate cost if available; otherwise approximate with current standard price converted to order currency
                if line.is_total_cost_computed:
                    line_cost = line.total_cost
                else:
                    product = line.product_id
                    product_cost = product.standard_price
                    line_cost = line.qty * product.cost_currency_id._convert(
                        from_amount=product_cost,
                        to_currency=line.currency_id,
                        company=line.company_id or self.env.company,
                        date=order.date_order or fields.Date.today(),
                        round=False,
                    )
                total_margin += (line.price_subtotal - line_cost)
                amount_untaxed += line.price_subtotal

        margin_percent = (total_margin / amount_untaxed) if amount_untaxed else 0.0
        _logger.info("[POS Session Margin] total_margin=%s, amount_untaxed=%s, margin_percent=%s", total_margin, amount_untaxed, margin_percent)
        
        # Inject computed values into the report data and return
        data.update({
            'session_total_margin': total_margin,
            'session_margin_percent': margin_percent,
        })

        return data

    @api.model
    def _get_report_values(self, docids, data=None):
        _logger.info("[POS Session Margin] _get_report_values called: docids=%s", docids)
        return super()._get_report_values(docids, data=data)


