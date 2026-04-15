# -*- coding: utf-8 -*-
import base64
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class BuildingPayConfig(models.Model):
    """
    Configurazione singleton del modulo BuildingPay.
    Gestisce tutte le impostazioni centralizzate del modulo.
    """
    _name = 'buildingpay_v25.config'
    _description = 'Configurazione BuildingPay'
    _rec_name = 'website_id'

    # -------------------------------------------------------
    # Selezione sito web
    # -------------------------------------------------------
    website_id = fields.Many2one(
        comodel_name='website',
        string='Sito Web BuildingPay',
        required=True,
        help='Selezionare il sito web su cui attivare le funzionalità BuildingPay.',
    )

    # -------------------------------------------------------
    # Configurazione attività automatica
    # -------------------------------------------------------
    create_activity_on_contract = fields.Boolean(
        string='Creare attività automatica quando si carica il contratto '
               'Accordo condomini aggregati',
        default=False,
    )
    activity_responsible_id = fields.Many2one(
        comodel_name='res.users',
        string='Responsabile attività',
        help='Utente a cui viene assegnata l\'attività automatica.',
    )
    activity_days = fields.Integer(
        string='Giorni scadenza attività',
        default=5,
        help='Numero di giorni dalla data di caricamento per la scadenza attività.',
    )

    # -------------------------------------------------------
    # Template contratto 1: Accordo Retrocessioni Amministratore ED
    # Placeholder nel template:
    #   [NOME AMMINISTRATORE]  → partner.name
    #   [CODICE FISCALE]       → partner.fiscalcode
    #   [IBAN]                 → primo res.partner.bank.acc_number
    #   [NOME BANCA]           → bank_id.name su res.partner.bank
    #   [DATA]                 → data odierna DD/MM/YYYY
    # -------------------------------------------------------
    accordo_retrocessioni_template = fields.Binary(
        string='Template Accordo Retrocessioni Amministratore ED',
        attachment=True,
        help='File .docx/.pdf da utilizzare come template per l\'Accordo Retrocessioni.',
    )
    accordo_retrocessioni_template_filename = fields.Char(
        string='Nome file template retrocessioni',
        default='Accordo Retrocessioni Amministratore ED.docx',
    )

    # -------------------------------------------------------
    # Template contratto 2: Accordo Condomini Aggregati ED
    # Placeholder nel template:
    #   [NOME AMMINISTRATORE]  → partner.name
    #   [________]             → partner.fiscalcode
    #   [ALLEGATO_A]           → tabella condomini attivi (nome | indirizzo | IBAN)
    # -------------------------------------------------------
    contratto_template = fields.Binary(
        string='Template Accordo Condomini Aggregati ED',
        attachment=True,
        help='File .docx da utilizzare come template per l\'Accordo Condomini Aggregati ED.',
    )
    contratto_template_filename = fields.Char(
        string='Nome file template condomini aggregati',
        default='Accordo Condomini Aggregati ED.docx',
    )

    # -------------------------------------------------------
    # Destinatari email report Excel
    # -------------------------------------------------------
    condomini_attivati_email = fields.Char(
        string='Destinatari condomini attivati',
        help='Indirizzi email (separati da virgola) a cui inviare il report '
             'giornaliero dei condomini attivi.',
    )
    condomini_dismessi_email = fields.Char(
        string='Destinatari condomini dismessi',
        help='Indirizzi email (separati da virgola) a cui inviare la notifica '
             'quando un condominio viene dismesso.',
    )

    # -------------------------------------------------------
    # Constraints
    # -------------------------------------------------------
    @api.constrains('create_activity_on_contract', 'activity_responsible_id', 'activity_days')
    def _check_activity_fields(self):
        for rec in self:
            if rec.create_activity_on_contract:
                if not rec.activity_responsible_id:
                    raise ValidationError(_(
                        'Il campo "Responsabile attività" è obbligatorio quando '
                        '"Creare attività automatica" è attivo.'
                    ))
                if not rec.activity_days or rec.activity_days <= 0:
                    raise ValidationError(_(
                        'Il campo "Giorni scadenza attività" deve essere maggiore di zero.'
                    ))

    @api.constrains('website_id')
    def _check_unique_website(self):
        """Ogni sito web può avere una sola configurazione BuildingPay."""
        for rec in self:
            existing = self.search([
                ('website_id', '=', rec.website_id.id),
                ('id', '!=', rec.id),
            ])
            if existing:
                raise ValidationError(_(
                    'Esiste già una configurazione BuildingPay per il sito web "%s".'
                ) % rec.website_id.name)

    # -------------------------------------------------------
    # Metodi di utilità
    # -------------------------------------------------------
    @api.model
    def get_config_for_website(self, website_id=None):
        """
        Restituisce la configurazione BuildingPay per il sito web corrente.
        Se website_id non è specificato, usa il sito web corrente dalla request.
        """
        if not website_id:
            website = self.env['website'].get_current_website()
            website_id = website.id
        return self.search([('website_id', '=', website_id)], limit=1)

    def get_retrocessioni_template_attachment(self):
        """Restituisce l'attachment del template Accordo Retrocessioni."""
        self.ensure_one()
        if not self.accordo_retrocessioni_template:
            return None
        return self.env['ir.attachment'].search([
            ('res_model', '=', self._name),
            ('res_field', '=', 'accordo_retrocessioni_template'),
            ('res_id', '=', self.id),
        ], limit=1)

    def get_contratto_template_attachment(self):
        """Restituisce l'attachment del template Accordo Condomini Aggregati ED."""
        self.ensure_one()
        if not self.contratto_template:
            return None
        return self.env['ir.attachment'].search([
            ('res_model', '=', self._name),
            ('res_field', '=', 'contratto_template'),
            ('res_id', '=', self.id),
        ], limit=1)
