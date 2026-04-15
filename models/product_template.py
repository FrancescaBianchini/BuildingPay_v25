# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class ProductTemplate(models.Model):
    """
    Estensione del prodotto per BuildingPay.
    Aggiunge il flag 'Condominio PagoPa'.
    """
    _inherit = 'product.template'

    is_condominio_pagopa = fields.Boolean(
        string='Condominio PagoPa',
        default=False,
        help='Se attivo, questo prodotto viene utilizzato come prodotto di '
             'default per la generazione delle fatture PagoPa dei condomini.',
    )
