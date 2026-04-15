# -*- coding: utf-8 -*-
from odoo import fields, models


class BuildingPayImportError(models.Model):
    """
    Riga di errore associata a una importazione BuildingPay.
    Traccia numero riga, codice errore e descrizione leggibile.
    """
    _name = 'buildingpay_v25.import.error'
    _description = 'Errore Importazione BuildingPay'
    _order = 'row_number asc'

    import_id = fields.Many2one(
        comodel_name='buildingpay_v25.import',
        string='Importazione',
        required=True,
        ondelete='cascade',
        index=True,
    )
    row_number = fields.Integer(
        string='Numero riga',
        default=0,
    )
    error_code = fields.Char(
        string='Codice errore',
        size=10,
    )
    error_description = fields.Text(
        string='Descrizione errore',
    )
