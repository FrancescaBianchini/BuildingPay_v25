# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class ProductPricelist(models.Model):
    """
    Estensione del listino prezzi per BuildingPay.
    Aggiunge il flag 'Listino condominio' e i campi relativi
    alle percentuali di retrocessione.
    """
    _inherit = 'product.pricelist'

    # -------------------------------------------------------
    # Flag listino condominio
    # -------------------------------------------------------
    is_listino_condominio = fields.Boolean(
        string='Listino Condominio',
        default=False,
        help='Se attivo, questo listino è dedicato ai condomini e '
             'mostra i campi di retrocessione.',
    )

    # -------------------------------------------------------
    # Campi visibili solo se is_listino_condominio = True
    # -------------------------------------------------------
    amministratore_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='buildingpay_v25_pricelist_admin_rel',
        column1='pricelist_id',
        column2='partner_id',
        string='Amministratori associati',
        domain=[('is_amministratore', '=', True)],
        help='Amministratori a cui è associato questo listino condominio.',
    )
    perc_retrocessione_amministratore = fields.Float(
        string='% Retrocessione Amministratore',
        digits=(5, 2),
        default=0.0,
        help='Percentuale di retrocessione riconosciuta all\'amministratore '
             'sul totale imponibile della fattura del condominio.',
    )
    perc_retrocessione_referrer = fields.Float(
        string='% Retrocessione Referrer',
        digits=(5, 2),
        default=0.0,
        help='Percentuale di retrocessione riconosciuta al referrer '
             'dell\'amministratore sul totale imponibile della fattura.',
    )

    # -------------------------------------------------------
    # Metodi di utilità
    # -------------------------------------------------------
    def get_condominio_pagopa_price(self):
        """
        Restituisce il prezzo del prodotto 'Condominio PagoPa'
        da questo listino.
        """
        self.ensure_one()
        product = self.env['product.template'].search([
            ('is_condominio_pagopa', '=', True),
        ], limit=1)
        if not product:
            return 0.0
        product_product = product.product_variant_id
        if not product_product:
            return 0.0
        # Usa la logica del listino per ottenere il prezzo
        price = self.get_product_price(
            product=product_product,
            quantity=1.0,
            partner=False,
        )
        return price
